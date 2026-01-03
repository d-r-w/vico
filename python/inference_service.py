from __future__ import annotations

import base64
import io
import subprocess
import threading
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from PIL import Image, ImageOps
from pydantic import BaseModel, model_validator

load_dotenv()

import logging
import os

import memory_storage_service
from streaming_inference_service import (
    cache_manager,
    describe_image,
    stream_chat_with_memories,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("inference_service")

app = FastAPI()

_STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}


@app.get("/api/chat/")
async def chat(
    query: str = Query(..., description="Chat query"),
    is_agent: bool = Query(False, description="Use the agentic model for the response")
):
    return StreamingResponse(
        stream_chat_with_memories(query, is_agent=is_agent),
        media_type="text/event-stream",
        headers=_STREAM_HEADERS,
    )


@app.get("/api/recent_memories/")
def get_recent_memories(limit: int = Query(5, description="Number of memories to fetch")):
    memories = memory_storage_service.get_recent_memories(limit)
    return {"memories": memories}


@app.get("/api/search_memories/")
def search_memories(search: List[str] = Query(..., description="Search query")):
    memories = memory_storage_service.search_memories(search)
    return {"memories": memories}


@app.get("/api/memories_by_tag/")
def get_memories_by_tag(tag_id: int = Query(..., description="Tag ID")):
    memories = memory_storage_service.get_memories_by_tag_id(tag_id)
    return {"memories": memories}


class SaveMemoryRequest(BaseModel):
    memory_text: Optional[str] = None
    memory_image_base64: Optional[str] = None
    tags: Optional[List[int]] = None

    @model_validator(mode="after")
    def require_one(cls, values) -> "SaveMemoryRequest":
        if not (values.memory_text or values.memory_image_base64):
            raise ValueError("Either memory_text or memory_image_base64 must be provided")
        return values


def _process_image_memory(base64_string: str, memory_text: Optional[str] = None, tags: Optional[List[int]] = None):
    decoded_bytes = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(decoded_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image_description = describe_image(image, memory_text)
    final_memory = f"{memory_text}\n\nImage: {image_description}" if memory_text else f"Image: {image_description}"
    memory_storage_service.save_memory(final_memory, decoded_bytes, tag_ids=tags)
    cache_manager.invalidate_memory_caches()


@app.post("/api/save_memory/")
async def save_memory(request: SaveMemoryRequest):
    if request.memory_image_base64:
        request.memory_image_base64 = request.memory_image_base64.split(",", 1)[1]
        threading.Thread(
            target=_process_image_memory, args=(request.memory_image_base64, request.memory_text, request.tags)
        ).start()
        return {"success": True}
    if request.memory_text:
        memory_storage_service.save_memory(request.memory_text, tag_ids=request.tags)
        cache_manager.invalidate_memory_caches()
        return {"success": True}


class DeleteMemoryRequest(BaseModel):
    memory_id: int


@app.delete("/api/delete_memory/")
async def delete_memory(request: DeleteMemoryRequest):
    memory_storage_service.delete_memory(request.memory_id)
    cache_manager.invalidate_memory_caches()
    return {"success": True}


@app.patch("/api/edit_memory/")
async def edit_memory(request: Request):
    data = await request.json()
    memory_id = data.get("id")
    new_memory_text = data.get("memory")
    tags = data.get("tags")

    if not memory_id or not new_memory_text:
        return {"success": False, "error": "Both id and memory are required"}, 400

    memory_storage_service.edit_memory(memory_id, new_memory_text, tag_ids=tags)
    cache_manager.invalidate_memory_caches()
    return {"success": True}


class TagRequest(BaseModel):
    label: str


@app.post("/api/tags/")
async def add_tag(request: TagRequest):
    tag_id = memory_storage_service.add_tag(request.label)
    return {"success": True, "id": tag_id}

class DeleteTagRequest(BaseModel):
    tag_id: int


@app.delete("/api/tags/")
async def delete_tag(request: DeleteTagRequest):
    memory_storage_service.delete_tag(request.tag_id)
    return {"success": True}


@app.get("/api/tags/")
async def get_tags():
    tags = memory_storage_service.get_all_tags() or []
    return {"tags": [{"id": t[0], "label": t[1]} for t in tags]}


class TTSRequest(BaseModel):
    text: str

@app.post("/api/tts/")
async def tts(request: TTSRequest):
    if not request.text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        logger.info(f"Generating TTS for text: {request.text[:100]}...")

        tts_script_path = os.getenv("TTS_SCRIPT_PATH")
        tts_quantize = os.getenv("TTS_QUANTIZE")

        command = ["uv", "run", tts_script_path, "-", "-", "--quantize", tts_quantize]

        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False
        )

        audio_data, error = process.communicate(input=request.text.encode("utf-8"))

        if process.returncode != 0:
            logger.error(f"TTS command failed with return code {process.returncode}: {error.decode()}")
            raise HTTPException(status_code=500, detail=f"TTS generation failed: {error.decode()}")

        logger.info(f"TTS generation completed successfully, audio size: {len(audio_data)} bytes")

        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=tts_output.wav"},
        )

    except subprocess.TimeoutExpired:
        logger.error("TTS generation timed out")
        raise HTTPException(status_code=504, detail="TTS generation timed out")
    except Exception as e:
        logger.error(f"TTS generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3020, timeout_keep_alive=600)
