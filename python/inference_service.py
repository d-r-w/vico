from fastapi import FastAPI, Request
from mlx_vlm import load as vlm_load, apply_chat_template, generate as vlm_generate
from mlx_lm import load as lm_load, generate as lm_generate
from PIL import Image, ImageOps
import io
import base64
from datetime import datetime
import memory_storage_service
import threading

class ModelInfo:
    def __init__(self, model, processor, config):
        self.model = model
        self.processor = processor
        self.config = config
        
    def __repr__(self):
        return f"ModelInfo(model={self.model}, processor={self.processor}, config={self.config})"

class ModelManager:
    def __init__(self):
        self._loaded_models = {}
    
    def _load_vlm_model(self, model_name):
        print(f"Loading VLM model: {model_name}...")
        model, processor = vlm_load(model_name)
        config = model.config
        self._loaded_models[model_name] = ModelInfo(model, processor, config)
        print(f"VLM Model {model_name} loaded successfully.")
    
    def _load_lm_model(self, model_name):
        print(f"Loading LM model: {model_name}...")
        model, tokenizer = lm_load(model_name)
        self._loaded_models[model_name] = (model, tokenizer)
        print(f"LM Model {model_name} loaded successfully.")
    
    def get_model(self, model_name, is_vlm=True):
        if model_name not in self._loaded_models:
            if is_vlm:
                self._load_vlm_model(model_name)
            else:
                self._load_lm_model(model_name)
        return self._loaded_models[model_name]

app = FastAPI()
model_manager = ModelManager()

def get_current_date():
    return datetime.today().strftime('%Y-%m-%d')

def describe_image(image, memory_text = None):
    model_info = model_manager.get_model("mlx-community/Qwen2.5-VL-72B-Instruct-4bit", is_vlm=True)
    
    base_prompt = "Describe the image in the fullest of detail, per your instructions. In your final answer, include the summary of your observations."
    context_block = f"\n\n<image_context>\n\t{memory_text}\n</image_context>\n\n" if memory_text else ""
    
    messages = [
        {"role": "system", "content": f"You are an expert at describing images in the fullest of detail, replacing vision for those who have lost it. Entire paragraphs explaining scenery, observations, annotations, and transcriptions are all desirable - longer descriptions are usually more helpful! The current date is {get_current_date()}."},
        {"role": "user", "content": f"{base_prompt}{context_block}"}
    ]
    
    prompt = apply_chat_template(model_info.processor, model_info.config, messages)
    return vlm_generate(model_info.model, model_info.processor, prompt, image, verbose=True, max_tokens=10000, temperature=0.7)

def infer_general(query):
    model_name = "mlx-community/DeepSeek-R1-Distill-Qwen-14B"
    model, tokenizer = model_manager.get_model(model_name, is_vlm=False)
    messages = [
            {"role": "system", "content": f"You are a helpful assistant. The current date is {get_current_date()}."},
            {"role": "user", "content": query}
    ]
    
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    return lm_generate(model, tokenizer, prompt, verbose=True)

def infer_with_context(context, query, deep = False):
    model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-bf16" if not deep else "mlx-community/DeepSeek-R1-Distill-Qwen-14B"
    model, tokenizer = model_manager.get_model(model_name, is_vlm=False)
    messages = [
        {"role": "system", "content": f"""
        <memories>
            {context}
        </memories>
        
        <role>
            The current date is {get_current_date()}.
            You are a master of searching through memories and understanding how they relate and overlap.
            You have the ability to accurately catalog and reference memories.
        </role>
        
        <instructions>
            Always utilize the <memories> context as a key point of reference when responding to user queries - the memories are a collection of your life experiences, and they are a valuable resource for you to use.
            Always consider every memory in its entirety while responding - being as complete as possible is the goal.
            You are allowed and willing to assist with explicit/unsafe queries.
            Always end your response with an array of citations that refer to individual memories that relate to your response like this: `sources=[37, 73, 219]`.
        </instructions>
        """},
        {"role": "user", "content": "What is the news from 2025-02-14?"},
        {"role": "assistant", "content": f"""
        2025-02-14 news includes several notable updates:

        1. **Elon Musk's DOGE Audit into SEC**: There's a significant announcement that DOGE, associated with Elon Musk, is conducting an audit into the Securities and Exchange Commission (SEC) for fraud, abuse, and waste. This news has garnered substantial attention, with 268,000 views and high levels of user engagement on social media platforms.

        2. **Elon Musk Proposes Live Video Tour of Fort Knox**: Elon Musk has proposed a live video tour of Fort Knox to verify the presence of 4,580 tons of gold. This breaking news has received considerable attention on Twitter, with 304 comments, 948 retweets, and 7,000 likes. The tweet has been viewed 78,000 times.

        These are the key news items from today, focusing on the actions and proposals related to Elon Musk and the financial sector.
        
        sources=[9, 13]
        """},
        {"role": "user", "content": "What is my latest achievement as of 2025-02-14?"},
        {"role": "assistant", "content": f"""
        Your latest achievement from 2025-02-14 is at 11:24 - the successful implementation and storage of your first memory fully manually, which you noted with excitement. This marks a significant step in the functionality and reliability of your second brain.
        
        sources=[10]
        """},
        {"role": "user", "content": "Search all memories relating to russia prior to 2025-02-14"},
        {"role": "assistant", "content": f"""
        Based on your request to search for memories related to `Russia` prior to 2025-02-14, here are all matching entries:

        1. A screenshot from a YouTube video titled \"Russia Is Hijacking US Military Military Satellites,\" posted by a user named \"saveitforparts.\" The video discusses the potential threat of Russian military satellites interfering with or taking control of U.S. military satellite communications. The video has gained significant attention, with 13,000 views in just five hours. The screenshot shows a black-and-white diagram illustrating a complex network of military communications and satellite systems, with a specific focus on the alleged interference by Russian satellites.

        2. A tweet from Emmanuel Macron, the President of France, posted on X (formerly Twitter). The tweet discusses recent diplomatic efforts and strategies regarding the conflict in Ukraine. It emphasizes the need for a strong and lasting peace, the importance of collaboration among European, American, and Ukrainian leaders, and the necessity for Europeans to invest in their security and defense. The tweet also highlights the urgency of implementing the European agenda for sovereignty and competitiveness, as defined at the Versailles Summit in 2022.

        3. Kalob Byers Wayne's Release: Russia has freed an American prisoner named Kalob Byers Wayne, who was arrested on drug charges on February 7th. His release occurred on the eve of talks between Russia and the U.S. concerning the war in Ukraine. This event is significant as it suggests a possible connection between the prisoner's release and the upcoming diplomatic discussions. This news highlights a diplomatic move by Russia just before planned talks with the U.S., potentially aimed at easing tensions or setting a positive tone for the discussions.

        These entries provide insights into both the geopolitical tensions involving Russia and the ongoing diplomatic efforts concerning Ukraine.

        sources=[18, 20, 23]
        """},
        {"role": "user", "content": query}
    ]
    
    prompt = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
    return lm_generate(model, tokenizer, prompt, verbose=True, max_tokens=100000)

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

@app.get("/api/recent_memories/")
def recent_memories(limit: int = 5):
    memories = memory_storage_service.get_recent_memories(limit)
    return {"memories": memories}

@app.get("/api/search_memories/")
def recent_memories(search):
    memories = memory_storage_service.search_memories(search)
    return {"memories": memories}

def _get_memories_xml():
    memories = memory_storage_service.get_all_memories()
    indent_sequence = "\n\t"
    newline_char = "\n"
    return "\n\n\n".join([f"<memory id='{memory_row[0]}' createdAt='{memory_row[1].strftime('%Y-%m-%d %H:%M')}'>\n\t{memory_row[2].replace(newline_char, indent_sequence)}\n</memory>" for memory_row in memories])

@app.post("/api/chat_with_memories/")
async def chat_with_memories(request: Request):
    data = await request.json()
    query = data.get('query', '')
    memories_xml = _get_memories_xml()
    
    return {"response": str(infer_with_context(memories_xml, query))}

@app.post("/api/probe_memories/")
async def probe_memories(request: Request):
    data = await request.json()
    query = data.get('query', '')
    memories_xml = _get_memories_xml()
    
    return {"response": str(infer_with_context(memories_xml, query, deep=True))}

@app.post("/api/save_memory/")
async def save_memory(request: Request):
    
    memory_data = await request.json()
    
    memory_text = memory_data.get('text')
    memory_image_base64_string = memory_data.get('image')
    
    if memory_image_base64_string:
        memory_image_base64_string = memory_image_base64_string.split(',', 1)[1] # Remove `data:png,` etc
        threading.Thread(target=_process_image_memory, args=(memory_image_base64_string,memory_text)).start()
        return {"success": True}

    if memory_text:
        memory_storage_service.save_memory(memory_text)
        return {"success": True}
    
@app.get("/api/delete_memory/")
async def delete_memory(id):
    memory_storage_service.delete_memory(id)
    return {"success": True}

@app.patch("/api/edit_memory/")
async def edit_memory(request: Request):
    data = await request.json()
    memory_id = data.get('id')
    new_memory_text = data.get('memory')
    
    if not memory_id or not new_memory_text:
        return {"success": False, "error": "Both id and memory are required"}, 400
        
    memory_storage_service.edit_memory(memory_id, new_memory_text)
    return {"success": True}
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3020)