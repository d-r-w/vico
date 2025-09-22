from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from mlx_vlm import load as vlm_load, apply_chat_template as vlm_apply_chat_template, generate as vlm_generate
from mlx_lm.utils import load as lm_load
from mlx_lm.generate import stream_generate as lm_generate_streaming
from mlx_lm.sample_utils import make_sampler, make_logits_processors
from mlx_lm.models.cache import load_prompt_cache, make_prompt_cache, save_prompt_cache
from PIL import Image, ImageOps
import io
import base64
import memory_storage_service
import threading
import queue
import os
from pathlib import Path
import logging
from dotenv import load_dotenv

load_dotenv()
from pydantic import BaseModel, model_validator
import json
from typing import Optional, Dict, Any, Tuple, Set, List, Callable, cast, Iterable, Union, NamedTuple
import prompt_templates
from tools.tool_executor import get_tool_call_results, parse_tool_call
from tools.tool_definitions import get_tool_definitions

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

    def unload_model(self, model_name: str) -> None:
        try:
            if model_name in self._loaded_models:
                del self._loaded_models[model_name]
                import gc
                gc.collect()
                try:
                    import mlx.core as mx  # type: ignore
                    if hasattr(mx, "clear_cache"):
                        mx.clear_cache()
                except Exception:
                    pass
                logger.info(f"Unloaded model: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to unload model {model_name}: {e}")


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
                logger.info(f"Invalidating memory cache: {cache_key}")
                self.release_cache(cache_key, delete_file=True)

        except Exception as e:
            logger.error(f"Error during bulk invalidation of memory caches: {e}")

    def release_cache(self, cache_key: str, delete_file: bool = True) -> None:
        try:
            if cache_key in self._prompt_caches:
                logger.info(f"Releasing prompt cache: {cache_key}")
                del self._prompt_caches[cache_key]
            if cache_key in self._initialized_caches:
                self._initialized_caches.discard(cache_key)
            if delete_file:
                cache_path = self._cache_dir / f"{cache_key}.safetensors"
                if cache_path.exists():
                    try:
                        os.remove(cache_path)
                        logger.info(f"Deleted cache file: {cache_path}")
                    except OSError as e:
                        logger.warning(f"Error deleting cache file {cache_path}: {e}")
        except Exception as e:
            logger.error(f"Error releasing cache {cache_key}: {e}")

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     yield
#     cache_manager.save_all()
# app = FastAPI(lifespan=lifespan)

app = FastAPI()
model_registry = ModelRegistry()
cache_manager = CacheManager()

def _make_sampler_and_logits():
    sampler = make_sampler(
        temp=float(os.getenv("AGENTIC_TEMP", "0.6")),
        top_p=float(os.getenv("AGENTIC_TOP_P", "0.95")),
        top_k=int(os.getenv("AGENTIC_TOP_K", "20")),
        min_p=float(os.getenv("AGENTIC_MIN_P", "0"))
    )

    repetition_penalty = float(os.getenv("AGENTIC_REPETITION_PENALTY", "1.05"))

    logits = make_logits_processors(
        repetition_penalty=repetition_penalty,
        repetition_context_size=int(os.getenv("AGENTIC_REPETITION_CONTEXT_SIZE", "64"))
    )
    return sampler, logits


def _setup_generation_context(
    model_name: str,
    cache_key: str,
    context_xml: str = "",
    query: str = "",
    is_agent: bool = False,
    tool_name: str = ""
) -> Tuple[Any, Any, Any, str, int, int, Any, Any, List[Dict[str, Any]]]:
    """Common setup for model, cache, and generation parameters."""
    model, tokenizer = model_registry.get_lm_model(model_name)
    prompt_cache = cache_manager.get_cache(cache_key, model)

    # Set up messages with template if cache is initialized
    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_chat_template(context_xml, query, is_agent))
    else:
        messages = prompt_templates.get_vico_chat_template(context_xml, query, is_agent)

    tools = get_tool_definitions()
    _log_messages_summary(f"{tool_name}before_gen", messages)
    prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)

    sampler, logits = _make_sampler_and_logits()

    max_tokens = int(os.getenv("AGENTIC_MAX_TOKENS", "81920"))
    max_kv_size = int(os.getenv("AGENTIC_MAX_KV_SIZE", "256000"))
    logger.info(f"[{tool_name}] generate: max_tokens={max_tokens}, max_kv_size={max_kv_size}")

    return model, tokenizer, prompt_cache, prompt, max_tokens, max_kv_size, sampler, logits, tools


def _append_tool_result(messages: List[Dict[str, Any]], tool_name: str, tool_result: str) -> None:
    messages.append({"role": "tool", "name": tool_name, "content": f"<tool_call_results>\n{tool_result}\n</tool_call_results>"})


def _run_streaming_generation_loop(
    model: Any,
    tokenizer: Any,
    prompt_cache: Any,
    messages: List[Dict[str, Any]],
    prompt: str,
    max_tokens: int,
    max_kv_size: int,
    sampler: Any,
    logits: Any,
    tools: List[Dict[str, Any]],
    model_name: str,
    tool_name: str = "",
    on_token: Optional[Callable[[str], None]] = None,
    on_tool_call_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_call_end: Optional[Callable[[str, Any], None]] = None,
    tool_call_handler: Optional[ToolCallHandler] = None,
    on_final_response_text: Optional[Callable[[str], None]] = None,
) -> Iterable[str]:
    """Streaming version of generation loop that yields SSE events."""
    while True:
        response = lm_generate_streaming(
            model, tokenizer, prompt, max_tokens=max_tokens, prompt_cache=prompt_cache,
            sampler=sampler, max_kv_size=max_kv_size, logits_processors=logits
        )

        response_text = ""
        def _token_generator() -> Iterable[str]:
            nonlocal response_text
            for part in response:
                if part.text:
                    response_text += part.text
                    try:
                        if on_token is not None:
                            on_token(part.text)
                    except Exception as e:
                        logger.warning(f"[{tool_name}] token streaming error: {e}")
                    yield part.text

        # Stream tokens with thinking injection
        yield from _sse_stream_with_thinking(
            _iter_stream_tokens(_token_generator()),
            plain_event="assistant_token",
            think_event="thinking_token",
            think_complete_event="thinking_complete",
            extra_payload=None,
            inject_think_if_missing=("Qwen3-Next-80B-A3B-Thinking" in model_name),
        )

        # Keep response_text consistent with SSE injection behavior for parsing
        response_text = _inject_think_tag_if_missing(response_text, model_name)
        clean_text = _strip_think_blocks(response_text)

        if "</tool_call>" in clean_text:
            if "<tool_call>" not in clean_text:
                _append_tool_result(messages, "error", "Tool call syntax error: opening <tool_call> tag not found.")
                logger.warning(f"[{tool_name}] Tool call detected but no <tool_call> tag found")
            else:
                logger.info(f"[{tool_name}] Tool call detected")
                t_name, t_args = parse_tool_call(clean_text)
                if not t_name:
                    _append_tool_result(messages, "error", "Tool call parsing failed.")
                else:
                    try:
                        if on_tool_call_start is not None:
                            on_tool_call_start(t_name, t_args)
                    except Exception as e:
                        logger.warning(f"[{tool_name}] on_tool_call_start callback error: {e}")

                    try:
                        yield _make_sse("assistant_tool_call_start", {"tool_name": t_name, "input": t_args})
                    except Exception:
                        pass

                    handler: ToolCallHandler = tool_call_handler or _build_agent_tool_call_handler(
                        parent_label=tool_name,
                        model_name=model_name,
                        model=model,
                        tokenizer=tokenizer,
                    )

                    try:
                        outcome = handler(t_name, t_args, clean_text)
                    except Exception as e:
                        logger.error(f"[{tool_name}] Tool call handler error: {e}")
                        outcome = ToolCallOutcome(stream=None, result_supplier=lambda: "")

                    stream_iter = outcome.stream
                    if stream_iter is not None:
                        for event in stream_iter:
                            yield event

                    tool_result = outcome.result_supplier()
                    _log_returned_message(f"{tool_name}agent_result", t_name, tool_result)
                    _append_tool_result(messages, t_name, tool_result)

                    try:
                        if on_tool_call_end is not None:
                            on_tool_call_end(t_name, tool_result)
                    except Exception as e:
                        logger.warning(f"[{tool_name}] on_tool_call_end callback error: {e}")

                    try:
                        yield _make_sse("assistant_tool_call_end", {"tool_name": t_name, "output": tool_result})
                    except Exception:
                        pass

            _log_messages_summary(f"{tool_name}after_tool", messages)
            prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)
            continue
        else:
            if on_final_response_text is not None:
                try:
                    on_final_response_text(response_text)
                except Exception as e:
                    logger.warning(f"[{tool_name}] on_final_response_text callback error: {e}")
            break


def _build_agent_tool_call_handler(
    *,
    parent_label: str,
    model_name: str,
    model: Any,
    tokenizer: Any,
) -> ToolCallHandler:
    def handler(tool_call_name: str, tool_args: Dict[str, Any], _clean_text: str) -> ToolCallOutcome:
        token_queue: "queue.Queue[str]" = queue.Queue()
        event_queue: "queue.Queue[Tuple[str, Dict[str, Any]]]" = queue.Queue()
        agent_result_holder: List[str] = []

        def on_subagent_token(text: str) -> None:
            try:
                token_queue.put(text)
            except Exception as e:
                logger.warning(f"[{parent_label}] subagent token enqueue error: {e}")

        def on_subagent_tool_start(name: str, args: Dict[str, Any]) -> None:
            try:
                event_queue.put(("subagent_tool_call_start", {"tool_name": name, "input": args}))
            except Exception as e:
                logger.warning(f"[{parent_label}] subagent tool start enqueue error: {e}")

        def on_subagent_tool_end(name: str, output: Any) -> None:
            try:
                event_queue.put(("subagent_tool_call_end", {"tool_name": name, "output": output}))
            except Exception as e:
                logger.warning(f"[{parent_label}] subagent tool end enqueue error: {e}")

        def run_agent_and_store_result() -> None:
            try:
                result = _run_agent(
                    tool_call_name,
                    tool_args,
                    "",
                    model_name,
                    model,
                    tokenizer,
                    on_token=on_subagent_token,
                    on_tool_call_start=on_subagent_tool_start,
                    on_tool_call_end=on_subagent_tool_end,
                )
                agent_result_holder.append(result)
            except Exception as e:
                logger.error(f"[{parent_label}] Agent thread error: {e}")
                agent_result_holder.append("")

        agent_thread = threading.Thread(target=run_agent_and_store_result)
        agent_thread.start()

        def stream_generator() -> Iterable[str]:
            yield from _sse_stream_with_thinking(
                _iter_stream_from_queues(
                    token_queue,
                    event_queue,
                    is_alive_fn=lambda: agent_thread.is_alive(),
                ),
                plain_event="subagent_token",
                think_event="subagent_thinking_token",
                think_complete_event="subagent_thinking_complete",
                extra_payload={"tool_name": tool_call_name},
                inject_think_if_missing=("Qwen3-Next-80B-A3B-Thinking" in model_name),
            )

        def stream_with_join() -> Iterable[str]:
            try:
                yield from stream_generator()
            finally:
                agent_thread.join()

        def result_supplier() -> str:
            agent_thread.join()
            return agent_result_holder[0] if agent_result_holder else ""

        return ToolCallOutcome(stream=stream_with_join(), result_supplier=result_supplier)

    return handler


def _build_direct_tool_call_handler() -> ToolCallHandler:
    def handler(_tool_call_name: str, _tool_args: Dict[str, Any], clean_text: str) -> ToolCallOutcome:
        def result_supplier() -> str:
            try:
                _, tool_result = get_tool_call_results(clean_text, logger, memory_storage_service, cache_manager)
                return tool_result
            except Exception as e:
                logger.error(f"Direct tool call execution failed: {e}")
                return ""

        return ToolCallOutcome(stream=None, result_supplier=result_supplier)

    return handler


def _collect_blocking_response(
    *,
    model: Any,
    tokenizer: Any,
    prompt_cache: Any,
    messages: List[Dict[str, Any]],
    prompt: str,
    max_tokens: int,
    max_kv_size: int,
    sampler: Any,
    logits: Any,
    tools: List[Dict[str, Any]],
    model_name: str,
    tool_name: str,
    on_token: Optional[Callable[[str], None]] = None,
    on_tool_call_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_call_end: Optional[Callable[[str, Any], None]] = None,
) -> str:
    final_text_parts: List[str] = []

    def capture_final_text(text: str) -> None:
        final_text_parts.append(text)

    def forward_on_token(text: str) -> None:
        if on_token is not None:
            on_token(text)

    def forward_tool_start(name: str, args: Dict[str, Any]) -> None:
        if on_tool_call_start is not None:
            on_tool_call_start(name, args)

    def forward_tool_end(name: str, output: Any) -> None:
        if on_tool_call_end is not None:
            on_tool_call_end(name, output)

    handler = _build_direct_tool_call_handler()

    for _ in _run_streaming_generation_loop(
        model=model,
        tokenizer=tokenizer,
        prompt_cache=prompt_cache,
        messages=messages,
        prompt=prompt,
        max_tokens=max_tokens,
        max_kv_size=max_kv_size,
        sampler=sampler,
        logits=logits,
        tools=tools,
        model_name=model_name,
        tool_name=tool_name,
        on_token=forward_on_token,
        on_tool_call_start=forward_tool_start,
        on_tool_call_end=forward_tool_end,
        tool_call_handler=handler,
        on_final_response_text=capture_final_text,
    ):
        # Exhaust the streaming iterator to drive generation to completion
        pass

    return "".join(final_text_parts).strip()


def _log_messages_summary(context_name: str, messages: List[Dict[str, Any]], max_items: int = 6) -> None:
    try:
        total = len(messages)
        logger.info(f"[{context_name}] messages count: {total}")
        start_index = max(0, total - max_items)
        for idx in range(start_index, total):
            m = messages[idx]
            role = m.get("role", "?")
            name = m.get("name", "")
            content = m.get("content", "")
            length = len(content) if isinstance(content, str) else 0
            name_suffix = f"/{name}" if name else ""
            logger.info(f"[{context_name}] m[{idx}] {role}{name_suffix} len={length}")
    except Exception as e:
        logger.warning(f"[{context_name}] Failed to log messages summary: {e}")


def _log_returned_message(context_name: str, tool_name: str, content: str, max_chars: int = 1500) -> None:
    try:
        length = len(content) if isinstance(content, str) else 0
        preview = content if length <= max_chars else content[:max_chars] + "\n...[truncated]"
        logger.info(f"[{context_name}] tool '{tool_name}' returned message len={length}")
        logger.info(f"[{context_name}] tool '{tool_name}' message preview:\n{preview}")
    except Exception as e:
        logger.warning(f"[{context_name}] Failed to log returned message: {e}")


def _strip_think_blocks(text: str) -> str:
    """Remove any content enclosed within <think>...</think> tags.

    Tool-call parsing should ignore model reasoning contained in these tags.
    """
    try:
        import re
        return re.sub(r"<think>[\s\S]*?</think>", "", text)
    except Exception:
        return text


def _extract_think_content(text: str) -> str:
    """Extract content from within <think>...</think> tags."""
    try:
        import re
        matches = re.findall(r"<think>([\s\S]*?)</think>", text)
        return "".join(matches)
    except Exception:
        return ""


def _is_qwen3_thinking_model(model_name: str) -> bool:
    """Check if the model is Qwen3-Next-80B-A3B-Thinking that needs special think tag handling."""
    return "Qwen3-Next-80B-A3B-Thinking" in model_name


def _inject_think_tag_if_missing(response_text: str, model_name: str) -> str:
    """Inject <think> tag at the beginning if the model requires it and it's missing.

    This is needed for Qwen3-Next-80B-A3B-Thinking models that sometimes omit
    the opening <think> tag but expect it to be present for proper parsing.
    """
    if (
        _is_qwen3_thinking_model(model_name)
        and len(response_text) > len("<think>")
        and "<think>" not in response_text
    ):
        return "<think>" + response_text
    return response_text



def _run_agent(
    tool_name: str,
    arguments: Dict[str, Any],
    user_query: str,
    parent_model_name: str,
    parent_model: Any,
    parent_tokenizer: Any,
    on_token: Optional[Callable[[str], None]] = None,
    on_tool_call_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_call_end: Optional[Callable[[str, Any], None]] = None,
) -> str:
    # Always reuse the assistant model; only swap prompt caches
    agent_model_name = parent_model_name
    model, tokenizer = parent_model, parent_tokenizer
    logger.info(f"[Agent:{tool_name}] Reusing assistant model: {parent_model_name}")

    cache_key = f"{agent_model_name.split('/')[-1]}_agent_cache__{tool_name}"
    prompt_cache = cache_manager.get_cache(cache_key, model)

    system_instructions = (
        "You are a specialized sub-agent. Your goal is to execute the requested tool-task end-to-end "
        "using available tools, iterating as needed. When finished, output a concise final result intended "
        "to be consumed by the parent assistant. Do not include internal notes."
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": (
            f"Parent query: {user_query}\n\n"
            f"Tool to execute: {tool_name}\n"
            f"Arguments: {arguments}\n\n"
            "Plan your steps and use tools with <tool_call> when needed."
        )}
    ]

    tools = get_tool_definitions()
    _log_messages_summary(f"Agent:{tool_name}:before_gen", messages)
    prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)

    sampler, logits = _make_sampler_and_logits()

    max_tokens = int(os.getenv("AGENTIC_MAX_TOKENS", "81920"))
    max_kv_size = int(os.getenv("AGENTIC_MAX_KV_SIZE", "256000"))
    logger.info(f"[Agent:{tool_name}] generate: max_tokens={max_tokens}, max_kv_size={max_kv_size}")

    result = _collect_blocking_response(
        model=model,
        tokenizer=tokenizer,
        prompt_cache=prompt_cache,
        messages=messages,
        prompt=prompt,
        max_tokens=max_tokens,
        max_kv_size=max_kv_size,
        sampler=sampler,
        logits=logits,
        tools=tools,
        model_name=agent_model_name,
        tool_name=f"Agent:{tool_name}:",
        on_token=on_token,
        on_tool_call_start=on_tool_call_start,
        on_tool_call_end=on_tool_call_end,
    )

    # Do not persist/initialize agent caches; release to control memory
    cache_manager.release_cache(cache_key, delete_file=True)

    return result


def _get_memories_xml() -> str:
    memories = memory_storage_service.get_all_memories() or []
    indent_sequence = "\n\t"
    newline_char = "\n"
    return "\n\n\n".join([
        f"<memory id='{row[0]}' createdAt='{row[1].strftime('%Y-%m-%d %H:%M')}'>\n\t{row[2].replace(newline_char, indent_sequence)}\n</memory>"
        for row in memories
    ])


def _make_sse(event_type: str, payload: Dict[str, Any] | None = None) -> str:
    try:
        body: Dict[str, Any] = {"type": event_type}
        if payload:
            body.update(payload)
        return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
    except Exception as e:
        # As a last resort, still emit something consumable by the client
        return f"data: {json.dumps({'type': 'error', 'message': f'encoding failure: {e}'})}\n\n"


THINK_OPEN_TAG = "<think>"
THINK_CLOSE_TAG = "</think>"


class StreamToken(NamedTuple):
    text: str


class StreamEvent(NamedTuple):
    event_type: str
    payload: Dict[str, Any]


StreamItem = Union[StreamToken, StreamEvent]


class ToolCallOutcome(NamedTuple):
    stream: Optional[Iterable[str]]
    result_supplier: Callable[[], str]


ToolCallHandler = Callable[[str, Dict[str, Any], str], ToolCallOutcome]


def _trailing_prefix_length(text: str, tag: str) -> int:
    """Length of the longest suffix of text that could still grow into tag."""
    if not text:
        return 0
    max_candidate = min(len(text), len(tag) - 1)
    for length in range(max_candidate, 0, -1):
        if tag.startswith(text[-length:]):
            return length
    return 0


def _safe_length(text: str, tag: str) -> int:
    return len(text) - _trailing_prefix_length(text, tag)


def _iter_stream_tokens(chunks: Iterable[str]) -> Iterable[StreamItem]:
    for chunk in chunks:
        if chunk:
            yield StreamToken(chunk)


def _iter_stream_from_queues(
    token_queue: "queue.Queue[str]",
    event_queue: "queue.Queue[Tuple[str, Dict[str, Any]]]",
    is_alive_fn: Callable[[], bool],
) -> Iterable[StreamItem]:
    while is_alive_fn() or not token_queue.empty() or not event_queue.empty():
        while not event_queue.empty():
            try:
                ev_type, payload = event_queue.get_nowait()
            except queue.Empty:
                break
            except Exception:
                break
            else:
                yield StreamEvent(ev_type, payload)

        try:
            tok = token_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        except Exception:
            continue

        if tok:
            yield StreamToken(tok)

    while not event_queue.empty():
        try:
            ev_type, payload = event_queue.get_nowait()
            yield StreamEvent(ev_type, payload)
        except Exception:
            break


def _sse_stream_with_thinking(
    stream: Iterable[StreamItem],
    *,
    plain_event: str,
    think_event: str,
    think_complete_event: str,
    extra_payload: Optional[Dict[str, Any]] = None,
    inject_think_if_missing: bool = False,
) -> Iterable[str]:
    """Yield SSE strings from a stream of token chunks and inline events.

    - Emits StreamEvent items immediately via _make_sse
    - Emits plain_event for normal tokens with payload {"token": ...} (+ extra_payload)
    - Emits think_event and think_complete_event for thinking tokens/close (+ extra_payload)
    - If inject_think_if_missing is True and no <think> tag appears early, treat the
      initial content as within a <think>...</think> block until a closing tag is seen.
    """
    think_open = THINK_OPEN_TAG
    think_close = THINK_CLOSE_TAG

    buffer = ""
    pending: str = ""
    emission_started = False
    in_think_block = False

    def make_payload(token_text: Optional[str] = None) -> Dict[str, Any]:
        base: Dict[str, Any] = {}
        if token_text is not None:
            base["token"] = token_text
        if extra_payload:
            base.update(extra_payload)
        return base

    for item in stream:
        if isinstance(item, StreamEvent):
            yield _make_sse(item.event_type, item.payload)
            continue
        raw_chunk = item.text
        if not raw_chunk:
            continue
        pending += raw_chunk

        # Decide how to start emitting: explicit <think> vs injected think vs plain
        if not emission_started:
            opening_index = pending.find(think_open)
            if opening_index != -1:
                pre_think = pending[:opening_index]
                if pre_think:
                    yield _make_sse(plain_event, make_payload(pre_think))
                pending = pending[opening_index + len(think_open):]
                emission_started = True
                in_think_block = True
            else:
                if think_open.startswith(pending):
                    continue
                if inject_think_if_missing:
                    emission_started = True
                    in_think_block = True
                else:
                    emission_started = True
            if not emission_started:
                continue

        # From here, we have started emitting. Process pending into the main buffer
        buffer += pending
        pending = ""

        while True:
            if in_think_block:
                closing_index = buffer.find(think_close)
                if closing_index != -1:
                    think_content = buffer[:closing_index]
                    if think_content:
                        yield _make_sse(think_event, make_payload(think_content))
                    yield _make_sse(think_complete_event, make_payload())
                    buffer = buffer[closing_index + len(think_close):]
                    in_think_block = False
                    continue

                safe_len = _safe_length(buffer, think_close)
                if safe_len:
                    think_delta = buffer[:safe_len]
                    if think_delta:
                        yield _make_sse(think_event, make_payload(think_delta))
                    buffer = buffer[safe_len:]
                break
            else:
                opening_index = buffer.find(think_open)
                if opening_index != -1:
                    pre_think = buffer[:opening_index]
                    if pre_think:
                        yield _make_sse(plain_event, make_payload(pre_think))
                    buffer = buffer[opening_index + len(think_open):]
                    in_think_block = True
                    continue

                safe_len = _safe_length(buffer, think_open)
                if safe_len:
                    assistant_delta = buffer[:safe_len]
                    if assistant_delta:
                        yield _make_sse(plain_event, make_payload(assistant_delta))
                    buffer = buffer[safe_len:]
                break

    # Flush at end
    if emission_started:
        if buffer:
            if in_think_block:
                yield _make_sse(think_event, make_payload(buffer))
                yield _make_sse(think_complete_event, make_payload())
            else:
                yield _make_sse(plain_event, make_payload(buffer))
    else:
        # Never started emitting; treat any residual as plain text
        if pending:
            yield _make_sse(plain_event, make_payload(pending))


def _assistant_stream_with_agents(context_xml: str, query: str, is_agent: bool = True):
    # TODO: Because MoE has 3b active, it no longer makes sense to use a 14b model (it's slower than 80b MoE)
    default_model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-8bit"
    chat_model_name = os.getenv("CHAT_MODEL_NAME", default_model_name)
    agentic_model_name = os.getenv("AGENTIC_MODEL_NAME", default_model_name)

    model_name = agentic_model_name if is_agent else chat_model_name

    cache_key = f"{model_name.split('/')[-1]}_memory_cache"

    # Get messages with template
    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_chat_template(context_xml, query, is_agent))
    else:
        messages = prompt_templates.get_vico_chat_template(context_xml, query, is_agent)

    model, tokenizer, prompt_cache, prompt, max_tokens, max_kv_size, sampler, logits, tools = _setup_generation_context(
        model_name, cache_key, context_xml, query, is_agent, "Assistant:"
    )

    # Run streaming generation loop
    yield from _run_streaming_generation_loop(
        model=model,
        tokenizer=tokenizer,
        prompt_cache=prompt_cache,
        messages=messages,
        prompt=prompt,
        max_tokens=max_tokens,
        max_kv_size=max_kv_size,
        sampler=sampler,
        logits=logits,
        tools=tools,
        model_name=model_name,
        tool_name="Assistant:",
        on_token=None,  # Tokens are yielded directly by the streaming loop
        on_tool_call_start=None,  # Tool calls are handled within the streaming loop
        on_tool_call_end=None,   # Tool calls are handled within the streaming loop
    )

    cache_manager.mark_initialized(cache_key)


def _stream_response(query: str, is_agent: bool = False):
    memories_xml = _get_memories_xml()

    def token_generator():
        for token in _assistant_stream_with_agents(memories_xml, query, is_agent=is_agent):
            yield token
        # Signal end of stream
        yield _make_sse("end")
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(token_generator(), media_type="text/event-stream", headers=headers)


@app.get("/api/recent_memories/")
def get_recent_memories(limit: int = Query(5, description="Number of memories to fetch")):
    memories = memory_storage_service.get_recent_memories(limit)
    
    return {"memories": memories}

@app.get("/api/search_memories/")
def search_memories(search: List[str] = Query(..., description="Search query")):
    memories = memory_storage_service.search_memories(search)
    return {"memories": memories}

@app.get("/api/memories_agent_chat/")
def memories_agent_chat(query: str = Query(..., description="Chat query")):
    return _stream_response(query)


@app.get("/api/agent_chat/")
async def agent_chat(query: str = Query(..., description="Probe query")):
    return _stream_response(query, is_agent=True)


class SaveMemoryRequest(BaseModel):
    memory_text: Optional[str] = None
    memory_image_base64: Optional[str] = None
    
    @model_validator(mode="after")
    def require_one(cls, values) -> 'SaveMemoryRequest':
        if not (values.memory_text or values.memory_image_base64):
            raise ValueError("Either memory_text or memory_image_base64 must be provided")
        return values


def _describe_image(image, memory_text: Optional[str] = None):
    model_info = model_registry.get_vlm_model(os.getenv("IMAGE_MODEL_NAME", "mlx-community/gemma-3-27b-it-8bit"))
    messages = prompt_templates.get_image_description_template(memory_text)
    prompt = cast(str, vlm_apply_chat_template(model_info.processor, model_info.config, messages))
    return vlm_generate(
        model_info.model,
        model_info.processor,
        prompt,
        image,
        verbose=True,
        max_tokens=int(os.getenv("IMAGE_MAX_TOKENS", "100000")),
        temperature=float(os.getenv("IMAGE_TEMP", "0.7"))
    )


def _process_image_memory(base64_string, memory_text: Optional[str] = None):
    decoded_bytes = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(decoded_bytes))
    image = ImageOps.exif_transpose(image).convert("RGB")
    image_description = _describe_image(image, memory_text)
    final_memory = (
        f"{memory_text}\n\nImage: {image_description}" if memory_text 
        else f"Image: {image_description}"
    )
    memory_storage_service.save_memory(final_memory, decoded_bytes)
    cache_manager.invalidate_memory_caches()


@app.post("/api/save_memory/")
async def save_memory(request: SaveMemoryRequest):
    if request.memory_image_base64:
        request.memory_image_base64 = request.memory_image_base64.split(',', 1)[1]
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3020, timeout_keep_alive=600)
