from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse
from mlx_vlm import load as vlm_load, apply_chat_template as vlm_apply_chat_template, generate as vlm_generate
from mlx_lm import load as lm_load, stream_generate as lm_generate_streaming
from mlx_lm.models.cache import load_prompt_cache, make_prompt_cache, save_prompt_cache
from PIL import Image, ImageOps
import io
import base64
from datetime import datetime
import memory_storage_service
import threading
import os
from pathlib import Path
import logging
from pydantic import BaseModel, model_validator
from typing import Optional, Dict, Any, Tuple, Set
import prompt_templates
from tools.tool_definitions import get_tool_definitions
from tools.tool_executor import get_tool_call_results
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("inference_service")

class ModelInfo:
    def __init__(self, model, processor, config):
        self.model = model
        self.processor = processor
        self.config = config
        
    def __repr__(self):
        return f"ModelInfo(model={self.model}, processor={self.processor}, config={self.config})"

class ModelLoader:
    def load_model(self, model_name: str) -> Any:
        raise NotImplementedError("Subclasses must implement load_model")

class VLMModelLoader(ModelLoader):
    def load_model(self, model_name: str) -> ModelInfo:
        logger.info(f"Loading VLM model: {model_name}...")
        model, processor = vlm_load(model_name)
        config = model.config
        logger.info(f"VLM Model {model_name} loaded successfully.")
        return ModelInfo(model, processor, config)

class LMModelLoader(ModelLoader):
    def load_model(self, model_name: str) -> Tuple[Any, Any]:
        logger.info(f"Loading LM model: {model_name}...")
        model, tokenizer = lm_load(model_name)
        logger.info(f"LM Model {model_name} loaded successfully.")
        return (model, tokenizer)

class ModelRegistry:
    def __init__(self):
        self._vlm_loader = VLMModelLoader()
        self._lm_loader = LMModelLoader()
        self._loaded_models: Dict[str, Any] = {}
    
    def get_vlm_model(self, model_name: str) -> ModelInfo:
        if model_name not in self._loaded_models:
            self._loaded_models[model_name] = self._vlm_loader.load_model(model_name)
        return self._loaded_models[model_name]
    
    def get_lm_model(self, model_name: str) -> Tuple[Any, Any]:
        if model_name not in self._loaded_models:
            self._loaded_models[model_name] = self._lm_loader.load_model(model_name)
        return self._loaded_models[model_name]

class CacheManager:
    def __init__(self, cache_dir: str = "../data/prompt_caches"):
        self._prompt_caches: Dict[str, Any] = {}
        self._initialized_caches: Set[str] = set()
        self._cache_dir = Path(cache_dir)
        os.makedirs(self._cache_dir, exist_ok=True)
    
    def get_cache(self, cache_key: str, model: Any) -> Any:
        if cache_key in self._prompt_caches:
            logger.info(f"Using existing in-memory prompt cache for {cache_key}")
            return self._prompt_caches[cache_key]

        cache_path = self._cache_dir / f"{cache_key}.safetensors"
        if cache_path.exists():
            logger.info(f"Loading prompt cache from disk: {cache_path}")
            try:
                self._prompt_caches[cache_key] = load_prompt_cache(str(cache_path))
                self._initialized_caches.add(cache_key)
                return self._prompt_caches[cache_key]
            except Exception as e:
                logger.error(f"Error loading prompt cache from disk: {e}")
        
        logger.info(f"Creating new prompt cache for {cache_key}")
        prompt_cache = make_prompt_cache(model)
        self._prompt_caches[cache_key] = prompt_cache
        return prompt_cache
    
    def mark_initialized(self, cache_key: str) -> None:
        if cache_key in self._prompt_caches:
            self._initialized_caches.add(cache_key)
            logger.info(f"Marked cache {cache_key} as fully initialized")
    
    def is_initialized(self, cache_key: str) -> bool:
        return cache_key in self._initialized_caches
    
    def save_cache(self, cache_key: str) -> bool:
        if cache_key in self._prompt_caches:
            cache_path = self._cache_dir / f"{cache_key}.safetensors"
            try:
                logger.info(f"Saving prompt cache to disk: {cache_path}")
                save_prompt_cache(str(cache_path), self._prompt_caches[cache_key])
                self._initialized_caches.add(cache_key)
                return True
            except Exception as e:
                logger.error(f"Error saving prompt cache {cache_key}: {e}")
                return False
        return False
    
    def save_all(self) -> None:
        for cache_key in list(self._prompt_caches.keys()):
            self.save_cache(cache_key)
    
    def invalidate_memory_caches(self) -> None:
        try:
            memory_cache_keys = [k for k in list(self._prompt_caches.keys()) if '_memory_cache' in k]
            
            for cache_key in memory_cache_keys:
                logger.info(f"Invalidating in-memory cache: {cache_key}")
                if cache_key in self._prompt_caches:
                    del self._prompt_caches[cache_key]
                
                if cache_key in self._initialized_caches:
                    self._initialized_caches.remove(cache_key)
                    logger.info(f"Removed {cache_key} from initialized caches")
                
                cache_path = self._cache_dir / f"{cache_key}.safetensors"
                if cache_path.exists():
                    logger.info(f"Removing outdated cache file: {cache_path}")
                    try:
                        os.remove(cache_path)
                    except OSError as e:
                        logger.warning(f"Error deleting cache file {cache_path}: {e}")
        except Exception as e:
            logger.error(f"Error invalidating caches: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    cache_manager.save_all()

app = FastAPI(lifespan=lifespan)
model_registry = ModelRegistry()
cache_manager = CacheManager()

def get_current_date():
    return datetime.today().strftime('%Y-%m-%d')

def describe_image(image, memory_text = None):
    model_info = model_registry.get_vlm_model("mlx-community/Qwen2.5-VL-72B-Instruct-4bit")
    
    messages = prompt_templates.get_image_description_template(memory_text)
    
    prompt = vlm_apply_chat_template(model_info.processor, model_info.config, messages)
    return vlm_generate(model_info.model, model_info.processor, prompt, image, verbose=True, max_tokens=10000, temperature=0.7)

def infer_with_context(context, query, is_deep = False):
    # mlx-community/QwQ-32B-8bit
    model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-bf16" if not is_deep else "mlx-community/QwQ-32B-8bit" # Testing
    # model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-bf16" if not is_deep else "mlx-community/TinyR1-32B-Preview-8bit" # Works well
    # model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-bf16" if not is_deep else "mlx-community/DeepSeek-R1-Distill-Qwen-14B"
    model, tokenizer = model_registry.get_lm_model(model_name)
    
    cache_key = f"{model_name.split('/')[-1]}_memory_cache"
    prompt_cache = cache_manager.get_cache(cache_key, model)
    
    messages = []
            
    if cache_manager.is_initialized(cache_key):
        logger.info(f"Using cached prompt, appending new query")
        messages.append(prompt_templates.get_memory_user_query_message(query, is_deep))
        
    else:
        logger.info(f"Building full prompt with context for {cache_key}")
        messages = prompt_templates.get_memory_chat_template(context, query, is_deep)
        
    tools = get_tool_definitions()
    prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False) # TODO Doesn't this mean that the tools are being added twice? (once when cached, once again always)
    
    response = lm_generate_streaming(model, tokenizer, prompt, max_tokens=100000, prompt_cache=prompt_cache)
    response_text = ""
    
    for response_part in response:
        response_text += response_part.text
        yield response_part.text
        
    if "<tool_call>" in response_text:
        logger.info("Tool call detected")
        tool_call_results = get_tool_call_results(response_text, logger, memory_storage_service, cache_manager)
        logger.info(f"Tool call results: {tool_call_results}") # TODO Use results for inference

    cache_manager.save_cache(cache_key) # TODO Does this need to happen for every call? Why?
    cache_manager.mark_initialized(cache_key)

def _process_image_memory(base64_string, memory_text = None):
    decoded_bytes = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(decoded_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image_description = describe_image(image, memory_text)
    final_memory = (
        f"{memory_text}\n\nImage: {image_description}" if memory_text 
        else f"Image: {image_description}"
    )
    
    memory_storage_service.save_memory(final_memory, decoded_bytes)
    cache_manager.invalidate_memory_caches()

@app.get("/api/recent_memories/")
def get_recent_memories(limit: int = Query(5, description="Number of memories to fetch")):
    memories = memory_storage_service.get_recent_memories(limit)
    
    return {"memories": memories}

@app.get("/api/search_memories/")
def search_memories(search: str = Query(..., description="Search query")):
    memories = memory_storage_service.search_memories(search)
    
    return {"memories": memories}

def _get_memories_xml():
    memories = memory_storage_service.get_all_memories()
    indent_sequence = "\n\t"
    newline_char = "\n"
    
    return "\n\n\n".join([f"<memory id='{memory_row[0]}' createdAt='{memory_row[1].strftime('%Y-%m-%d %H:%M')}'>\n\t{memory_row[2].replace(newline_char, indent_sequence)}\n</memory>" for memory_row in memories])

def stream_response(query: str, is_deep: bool = False):
    memories_xml = _get_memories_xml()
    
    def token_generator():
        for token in infer_with_context(memories_xml, query, is_deep=is_deep):
            yield token
            
    return StreamingResponse(token_generator(), media_type="text/plain")

@app.get("/api/chat_with_memories/")
def chat_with_memories(query: str = Query(..., description="Chat query")):
    return stream_response(query)

@app.get("/api/probe_memories/")
async def probe_memories(query: str = Query(..., description="Probe query")):
    return stream_response(query, is_deep=True)

class SaveMemoryRequest(BaseModel):
    memory_text: Optional[str] = None
    memory_image_base64: Optional[str] = None
    
    @model_validator(mode="after")
    def require_one(cls, model: SaveMemoryRequest) -> SaveMemoryRequest:
        if not (model.memory_text or model.memory_image_base64):
            raise ValueError("Either memory_text or memory_image_base64 must be provided")
        return model

@app.post("/api/save_memory/")
async def save_memory(request: SaveMemoryRequest):
    if request.memory_image_base64:
        request.memory_image_base64 = request.memory_image_base64.split(',', 1)[1] # Remove `data:png,` etc
        threading.Thread(target=_process_image_memory, args=(request.memory_image_base64, request.memory_text)).start()
        return {"success": True}

    if request.memory_text:
        memory_storage_service.save_memory(request.memory_text)
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
    memory_id = data.get('id')
    new_memory_text = data.get('memory')
    
    if not memory_id or not new_memory_text:
        return {"success": False, "error": "Both id and memory are required"}, 400
        
    memory_storage_service.edit_memory(memory_id, new_memory_text)
    cache_manager.invalidate_memory_caches()
    return {"success": True}

def summarize_text(text_data):
    model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-bf16"
    model, tokenizer = model_registry.get_lm_model(model_name)
    
    cache_key = f"{model_name.split('/')[-1]}_summarize_cache"
    prompt_cache = cache_manager.get_cache(cache_key, model)
    
    # Create a prompt for summarization
    messages = [
        {"role": "system", "content": "You are a helpful assistant that summarizes text content concisely while preserving the key information."},
        {"role": "user", "content": f"Please summarize the following text from a web search:\n\n{text_data}. Please cite your sources using the supplied page numbers."}
    ]
    
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    
    response = lm_generate_streaming(model, tokenizer, prompt, max_tokens=10000, prompt_cache=prompt_cache)
    
    response_text = ""
    for response_part in response:
        response_text += response_part.text
        yield response_part.text
    
    cache_manager.save_cache(cache_key)
    cache_manager.mark_initialized(cache_key)

@app.post("/api/summarize_text/")
async def api_summarize_text(request: Request):
    data = await request.json()
    text_data = data.get('text_data')
    
    if not text_data:
        return {"success": False, "error": "text_data is required"}, 400
    
    def token_generator():
        for token in summarize_text(text_data):
            yield token
    
    return StreamingResponse(token_generator(), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3020)