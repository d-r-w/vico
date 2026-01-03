from __future__ import annotations

import gc
import io
import json
import logging
import os
import queue
import re
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, Union, cast

from dotenv import load_dotenv
from mlx_lm.generate import stream_generate as lm_generate_streaming
from mlx_lm.models.cache import load_prompt_cache, make_prompt_cache, save_prompt_cache
from mlx_lm.sample_utils import make_logits_processors, make_sampler
from mlx_lm.utils import load as lm_load
from mlx_vlm import apply_chat_template as vlm_apply_chat_template
from mlx_vlm import generate as vlm_generate
from mlx_vlm import GenerationResult as VLMGenerationResult
from mlx_vlm import load as vlm_load

import memory_storage_service
import prompt_templates
from tools.tool_definitions import get_tool_definitions
from tools.tool_executor import get_tool_call_results, parse_tool_call, ToolCallParseError

load_dotenv()

logger = logging.getLogger("streaming_inference")

class ModelInfo:
    """Container for VLM model components."""

    def __init__(self, model: Any, processor: Any, config: Any) -> None:
        self.model = model
        self.processor = processor
        self.config = config

    def __repr__(self) -> str:
        return f"ModelInfo(model={self.model}, processor={self.processor}, config={self.config})"


class ModelLoader:
    """Base class for model loaders."""

    def load_model(self, model_name: str) -> Any:
        raise NotImplementedError


class VLMModelLoader(ModelLoader):
    """Loader for vision-language models."""

    def load_model(self, model_name: str) -> ModelInfo:
        logger.info(f"Loading VLM model: {model_name}...")
        model, processor = vlm_load(model_name)
        config = model.config
        logger.info(f"VLM Model {model_name} loaded successfully.")
        return ModelInfo(model, processor, config)


class LMModelLoader(ModelLoader):
    """Loader for language models."""

    def load_model(self, model_name: str) -> Tuple[Any, Any]:
        logger.info(f"Loading LM model: {model_name}...")
        model, tokenizer = lm_load(model_name)
        logger.info(f"LM Model {model_name} loaded successfully.")
        return (model, tokenizer)


class ModelRegistry:
    """Registry for loaded models with lazy loading and caching."""

    def __init__(self) -> None:
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
        if model_name not in self._loaded_models:
            return
        del self._loaded_models[model_name]
        gc.collect()
        try:
            import mlx.core as mx

            if hasattr(mx, "clear_cache"):
                mx.clear_cache()
        except Exception:
            pass
        logger.info(f"Unloaded model: {model_name}")

class CacheManager:
    """Manages prompt caches for efficient context reuse."""

    def __init__(self, cache_dir: str = "../data/prompt_caches") -> None:
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
        if cache_key not in self._prompt_caches:
            return False
        cache_path = self._cache_dir / f"{cache_key}.safetensors"
        try:
            logger.info(f"Saving prompt cache to disk: {cache_path}")
            save_prompt_cache(str(cache_path), self._prompt_caches[cache_key])
            self._initialized_caches.add(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error saving prompt cache {cache_key}: {e}")
            return False

    def save_all(self) -> None:
        for cache_key in list(self._prompt_caches.keys()):
            self.save_cache(cache_key)

    def invalidate_memory_caches(self) -> None:
        memory_cache_keys = [k for k in list(self._prompt_caches.keys()) if "_memory_cache" in k]
        for cache_key in memory_cache_keys:
            logger.info(f"Invalidating memory cache: {cache_key}")
            self.release_cache(cache_key, delete_file=True)

    def release_cache(self, cache_key: str, delete_file: bool = True) -> None:
        if cache_key in self._prompt_caches:
            logger.info(f"Releasing prompt cache: {cache_key}")
            del self._prompt_caches[cache_key]
        self._initialized_caches.discard(cache_key)
        if delete_file:
            cache_path = self._cache_dir / f"{cache_key}.safetensors"
            if cache_path.exists():
                try:
                    os.remove(cache_path)
                    logger.info(f"Deleted cache file: {cache_path}")
                except OSError as e:
                    logger.warning(f"Error deleting cache file {cache_path}: {e}")


model_registry = ModelRegistry()
cache_manager = CacheManager()

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

class ToolCallTagScan(NamedTuple):
    has_open: bool
    has_close: bool

def make_sse(event_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Format an SSE event string."""
    try:
        body: Dict[str, Any] = {"type": event_type}
        if payload:
            body.update(payload)
        return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
    except Exception as e:
        return f"data: {json.dumps({'type': 'error', 'message': f'encoding failure: {e}'})}\n\n"

def strip_think_blocks(text: str) -> str:
    """Remove content within <think>...</think> tags."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

def clean_tool_output_for_event(output: str) -> str:
    """Clean tool output for SSE events - strip think blocks and normalize whitespace."""
    cleaned = strip_think_blocks(output)
    # Collapse multiple newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_think_content(text: str) -> str:
    """Extract content from within <think>...</think> tags."""
    matches = re.findall(r"<think>([\s\S]*?)</think>", text)
    return "".join(matches)


def scan_tool_call_tags(text: str) -> ToolCallTagScan:
    """Scan text for <tool_call> and </tool_call> tags."""
    open_tag = "<tool_call>"
    close_tag = "</tool_call>"
    open_len = len(open_tag)

    has_open = False
    index = 0
    limit = len(text)

    while index < limit:
        if not has_open and text.startswith(open_tag, index):
            has_open = True
            index += open_len
            continue
        if text.startswith(close_tag, index):
            return ToolCallTagScan(has_open, True)
        index += 1

    return ToolCallTagScan(has_open, False)


def is_qwen3_thinking_model(model_name: str) -> bool:
    """Check if model requires special think tag handling."""
    return "Qwen3-Next-80B-A3B-Thinking" in model_name


def inject_think_tag_if_missing(response_text: str, model_name: str) -> str:
    """Inject <think> tag at beginning for models that omit it."""
    if (
        is_qwen3_thinking_model(model_name)
        and len(response_text) > len("<think>")
        and "<think>" not in response_text
    ):
        return "<think>" + response_text
    return response_text


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

def log_messages_summary(context_name: str, messages: List[Dict[str, Any]], max_items: int = 6) -> None:
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


def log_returned_message(context_name: str, tool_name: str, content: str, max_chars: int = 1500) -> None:
    length = len(content) if isinstance(content, str) else 0
    preview = content if length <= max_chars else content[:max_chars] + "\n...[truncated]"
    logger.info(f"[{context_name}] tool '{tool_name}' returned message len={length}")
    logger.info(f"[{context_name}] tool '{tool_name}' message preview:\n{preview}")

def make_sampler_and_logits() -> Tuple[Any, Any]:
    """Create sampler and logits processors from environment config."""
    sampler = make_sampler(
        temp=float(os.getenv("AGENTIC_TEMP", "0.6")),
        top_p=float(os.getenv("AGENTIC_TOP_P", "0.95")),
        top_k=int(os.getenv("AGENTIC_TOP_K", "20")),
        min_p=float(os.getenv("AGENTIC_MIN_P", "0")),
    )
    logits = make_logits_processors(
        repetition_penalty=float(os.getenv("AGENTIC_REPETITION_PENALTY", "1.05")),
        repetition_context_size=int(os.getenv("AGENTIC_REPETITION_CONTEXT_SIZE", "64")),
    )
    return sampler, logits

def setup_generation_context(
    model_name: str,
    cache_key: str,
    context_xml: str = "",
    query: str = "",
    is_agent: bool = False,
    tool_name: str = "",
) -> Tuple[Any, Any, Any, str, int, int, Any, Any, List[Dict[str, Any]]]:
    """Common setup for model, cache, and generation parameters."""
    model, tokenizer = model_registry.get_lm_model(model_name)
    prompt_cache = cache_manager.get_cache(cache_key, model)

    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_chat_template(context_xml, query, is_agent))
    else:
        messages = prompt_templates.get_vico_chat_template(context_xml, query, is_agent)

    tools = get_tool_definitions()
    log_messages_summary(f"{tool_name}before_gen", messages)
    prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)

    sampler, logits = make_sampler_and_logits()

    max_tokens = int(os.getenv("AGENTIC_MAX_TOKENS", "81920"))
    max_kv_size = int(os.getenv("AGENTIC_MAX_KV_SIZE", "256000"))
    logger.info(f"[{tool_name}] generate: max_tokens={max_tokens}, max_kv_size={max_kv_size}")

    return model, tokenizer, prompt_cache, prompt, max_tokens, max_kv_size, sampler, logits, tools


def append_tool_result(messages: List[Dict[str, Any]], tool_name: str, tool_result: str) -> None:
    """Append a tool result message."""
    messages.append({
        "role": "tool",
        "name": tool_name,
        "content": f"<tool_call_results>\n{tool_result}\n</tool_call_results>",
    })

def iter_stream_tokens(chunks: Iterable[str]) -> Iterable[StreamItem]:
    for chunk in chunks:
        if chunk:
            yield StreamToken(chunk)


def sse_stream_with_thinking(
    stream: Iterable[StreamItem],
    *,
    plain_event: str,
    think_event: str,
    think_complete_event: str,
    extra_payload: Optional[Dict[str, Any]] = None,
    inject_think_if_missing: bool = False,
) -> Iterable[str]:
    """Yield SSE strings from a stream of token chunks and inline events.

    - Emits StreamEvent items immediately via make_sse
    - Emits plain_event for normal tokens with payload {"token": ...}
    - Emits think_event and think_complete_event for thinking tokens
    """
    think_open = THINK_OPEN_TAG
    think_close = THINK_CLOSE_TAG

    buffer = ""
    pending = ""
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
            yield make_sse(item.event_type, item.payload)
            continue
        raw_chunk = item.text
        if not raw_chunk:
            continue
        pending += raw_chunk

        if not emission_started:
            opening_index = pending.find(think_open)
            if opening_index != -1:
                pre_think = pending[:opening_index]
                if pre_think:
                    yield make_sse(plain_event, make_payload(pre_think))
                pending = pending[opening_index + len(think_open) :]
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

        buffer += pending
        pending = ""

        while True:
            if in_think_block:
                closing_index = buffer.find(think_close)
                if closing_index != -1:
                    think_content = buffer[:closing_index]
                    if think_content:
                        yield make_sse(think_event, make_payload(think_content))
                    yield make_sse(think_complete_event, make_payload())
                    buffer = buffer[closing_index + len(think_close) :]
                    in_think_block = False
                    continue

                safe_len = _safe_length(buffer, think_close)
                if safe_len:
                    think_delta = buffer[:safe_len]
                    if think_delta:
                        yield make_sse(think_event, make_payload(think_delta))
                    buffer = buffer[safe_len:]
                break
            else:
                opening_index = buffer.find(think_open)
                if opening_index != -1:
                    pre_think = buffer[:opening_index]
                    if pre_think:
                        yield make_sse(plain_event, make_payload(pre_think))
                    buffer = buffer[opening_index + len(think_open) :]
                    in_think_block = True
                    continue

                safe_len = _safe_length(buffer, think_open)
                if safe_len:
                    assistant_delta = buffer[:safe_len]
                    if assistant_delta:
                        yield make_sse(plain_event, make_payload(assistant_delta))
                    buffer = buffer[safe_len:]
                break

    # Flush remaining buffer
    if emission_started:
        if buffer:
            if in_think_block:
                yield make_sse(think_event, make_payload(buffer))
                yield make_sse(think_complete_event, make_payload())
            else:
                yield make_sse(plain_event, make_payload(buffer))
    elif pending:
        yield make_sse(plain_event, make_payload(pending))

def build_agent_tool_call_handler(
    *,
    parent_label: str,
    model_name: str,
    model: Any,
    tokenizer: Any,
) -> ToolCallHandler:
    """Build a handler that spawns subagents for tool execution."""

    def handler(tool_call_name: str, tool_args: Dict[str, Any], _clean_text: str) -> ToolCallOutcome:
        executor = SubAgentExecutor(
            parent_label=parent_label,
            tool_call_name=tool_call_name,
            tool_args=tool_args,
            model_name=model_name,
            model=model,
            tokenizer=tokenizer,
        )
        stream = executor.stream_sse(inject_think_if_missing=is_qwen3_thinking_model(model_name))
        return ToolCallOutcome(stream=stream, result_supplier=executor.result)

    return handler


def build_direct_tool_call_handler() -> ToolCallHandler:
    """Build a handler that executes tools directly without subagents."""

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

def run_streaming_generation_loop(
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
    """Streaming generation loop that yields SSE events."""
    while True:
        response = lm_generate_streaming(
            model,
            tokenizer,
            prompt,
            max_tokens=max_tokens,
            prompt_cache=prompt_cache,
            sampler=sampler,
            max_kv_size=max_kv_size,
            logits_processors=logits,
        )

        response_buffer = io.StringIO()

        def _token_generator() -> Iterable[str]:
            for part in response:
                if part.text:
                    chunk_text = part.text
                    response_buffer.write(chunk_text)
                    if on_token is not None:
                        try:
                            on_token(chunk_text)
                        except Exception as e:
                            logger.warning(f"[{tool_name}] token streaming error: {e}")
                    yield chunk_text

        yield from sse_stream_with_thinking(
            iter_stream_tokens(_token_generator()),
            plain_event="assistant_token",
            think_event="thinking_token",
            think_complete_event="thinking_complete",
            extra_payload=None,
            inject_think_if_missing=is_qwen3_thinking_model(model_name),
        )

        response_text = response_buffer.getvalue()
        response_text = inject_think_tag_if_missing(response_text, model_name)
        clean_text = strip_think_blocks(response_text)
        tag_scan = scan_tool_call_tags(clean_text)

        if tag_scan.has_close:
            if not tag_scan.has_open:
                append_tool_result(messages, "error", "Tool call syntax error: opening <tool_call> tag not found.")
                logger.warning(f"[{tool_name}] Tool call detected but no <tool_call> tag found")
            else:
                logger.info(f"[{tool_name}] Tool call detected")
                try:
                    tool_call = parse_tool_call(clean_text)
                except ToolCallParseError as exc:
                    logger.warning(f"[{tool_name}] Tool call parsing failed: {exc.message}")
                    append_tool_result(messages, "error", f"Tool call parsing failed: {exc.message}")
                else:
                    t_name, t_args = tool_call
                    if on_tool_call_start is not None:
                        try:
                            on_tool_call_start(t_name, t_args)
                        except Exception as e:
                            logger.warning(f"[{tool_name}] on_tool_call_start callback error: {e}")

                    try:
                        yield make_sse("assistant_tool_call_start", {"tool_name": t_name, "input": t_args})
                    except Exception:
                        pass

                    handler: ToolCallHandler = tool_call_handler or build_agent_tool_call_handler(
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

                    if outcome.stream is not None:
                        yield from outcome.stream

                    tool_result = outcome.result_supplier()
                    log_returned_message(f"{tool_name}agent_result", t_name, tool_result)
                    append_tool_result(messages, t_name, tool_result)

                    if on_tool_call_end is not None:
                        try:
                            on_tool_call_end(t_name, tool_result)
                        except Exception as e:
                            logger.warning(f"[{tool_name}] on_tool_call_end callback error: {e}")

                    try:
                        yield make_sse("assistant_tool_call_end", {
                            "tool_name": t_name,
                            "output": clean_tool_output_for_event(tool_result),
                        })
                    except Exception:
                        pass

            log_messages_summary(f"{tool_name}after_tool", messages)
            prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)
            continue
        else:
            if on_final_response_text is not None:
                try:
                    on_final_response_text(response_text)
                except Exception as e:
                    logger.warning(f"[{tool_name}] on_final_response_text callback error: {e}")
            break


def collect_blocking_response(
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
    """Run generation loop to completion and return final response text."""
    final_text_parts: List[str] = []

    def capture_final_text(text: str) -> None:
        final_text_parts.append(text)

    handler = build_direct_tool_call_handler()

    for _ in run_streaming_generation_loop(
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
        on_token=on_token,
        on_tool_call_start=on_tool_call_start,
        on_tool_call_end=on_tool_call_end,
        tool_call_handler=handler,
        on_final_response_text=capture_final_text,
    ):
        pass

    return "".join(final_text_parts).strip()


def run_agent(
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
    """Execute a subagent task with the given tool and arguments."""
    model, tokenizer = parent_model, parent_tokenizer
    logger.info(f"[Agent:{tool_name}] Reusing assistant model: {parent_model_name}")

    cache_key = f"{parent_model_name.split('/')[-1]}_agent_cache__{tool_name}"
    prompt_cache = cache_manager.get_cache(cache_key, model)

    system_instructions = (
        "You are a specialized sub-agent. Your goal is to execute the requested tool-task end-to-end "
        "using available tools, iterating as needed. When finished, output a concise final result intended "
        "to be consumed by the parent assistant. Do not include internal notes."
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_instructions},
        {
            "role": "user",
            "content": (
                f"Parent query: {user_query}\n\n"
                f"Tool to execute: {tool_name}\n"
                f"Arguments: {arguments}\n\n"
                "Plan your steps and use tools with <tool_call> when needed."
            ),
        },
    ]

    tools = get_tool_definitions()
    log_messages_summary(f"Agent:{tool_name}:before_gen", messages)
    prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)

    sampler, logits = make_sampler_and_logits()

    max_tokens = int(os.getenv("AGENTIC_MAX_TOKENS", "81920"))
    max_kv_size = int(os.getenv("AGENTIC_MAX_KV_SIZE", "256000"))
    logger.info(f"[Agent:{tool_name}] generate: max_tokens={max_tokens}, max_kv_size={max_kv_size}")

    result = collect_blocking_response(
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
        model_name=parent_model_name,
        tool_name=f"Agent:{tool_name}:",
        on_token=on_token,
        on_tool_call_start=on_tool_call_start,
        on_tool_call_end=on_tool_call_end,
    )

    cache_manager.release_cache(cache_key, delete_file=True)
    return result


class SubAgentExecutor:
    """Executes a subagent in a background thread with token streaming."""

    def __init__(
        self,
        *,
        parent_label: str,
        tool_call_name: str,
        tool_args: Dict[str, Any],
        model_name: str,
        model: Any,
        tokenizer: Any,
    ) -> None:
        self._parent_label = parent_label
        self._tool_call_name = tool_call_name
        self._tool_args = tool_args
        self._model_name = model_name
        self._model = model
        self._tokenizer = tokenizer
        self._queue: queue.Queue[Optional[StreamItem]] = queue.Queue()
        self._result_future: Future[str] = Future()
        self._thread = threading.Thread(target=self._run, name=f"SubAgent-{tool_call_name}")
        self._thread.start()

    def _emit_item(self, item: Optional[StreamItem]) -> None:
        try:
            self._queue.put(item)
        except Exception as exc:
            logger.warning(f"[{self._parent_label}] subagent queue enqueue error: {exc}")

    def _run(self) -> None:
        def on_token(text: str) -> None:
            if text:
                self._emit_item(StreamToken(text))

        def on_tool_start(name: str, args: Dict[str, Any]) -> None:
            self._emit_item(
                StreamEvent(
                    "subagent_tool_call_start",
                    {"tool_name": name, "input": args, "parent_tool_name": self._tool_call_name},
                )
            )

        def on_tool_end(name: str, output: Any) -> None:
            cleaned_output = clean_tool_output_for_event(output) if isinstance(output, str) else output
            self._emit_item(
                StreamEvent(
                    "subagent_tool_call_end",
                    {"tool_name": name, "output": cleaned_output, "parent_tool_name": self._tool_call_name},
                )
            )

        try:
            result = run_agent(
                self._tool_call_name,
                self._tool_args,
                "",
                self._model_name,
                self._model,
                self._tokenizer,
                on_token=on_token,
                on_tool_call_start=on_tool_start,
                on_tool_call_end=on_tool_end,
            )
            if not self._result_future.done():
                self._result_future.set_result(result)
        except Exception as exc:
            logger.error(f"[{self._parent_label}] Agent thread error: {exc}")
            if not self._result_future.done():
                self._result_future.set_result("")
        finally:
            self._emit_item(None)

    def _stream_items(self) -> Iterable[StreamItem]:
        while True:
            try:
                item = self._queue.get()
            except Exception as exc:
                logger.warning(f"[{self._parent_label}] subagent queue retrieval error: {exc}")
                continue
            if item is None:
                break
            yield item

    def stream_sse(self, *, inject_think_if_missing: bool) -> Iterable[str]:
        """Stream SSE events from the subagent execution."""

        def generator() -> Iterable[str]:
            try:
                yield from sse_stream_with_thinking(
                    self._stream_items(),
                    plain_event="subagent_token",
                    think_event="subagent_thinking_token",
                    think_complete_event="subagent_thinking_complete",
                    extra_payload={"tool_name": self._tool_call_name},
                    inject_think_if_missing=inject_think_if_missing,
                )
            finally:
                self._thread.join()

        return generator()

    def result(self) -> str:
        """Get the final result (blocks until complete)."""
        self._thread.join()
        try:
            return self._result_future.result()
        except Exception:
            return ""

def get_memories_xml() -> str:
    """Build XML representation of all stored memories."""
    memories = memory_storage_service.get_all_memories() or []
    indent_sequence = "\n\t"
    newline_char = "\n"
    return "\n\n\n".join(
        [
            f"<memory id='{row[0]}' createdAt='{row[1].strftime('%Y-%m-%d %H:%M')}' tags='{','.join(row[3]) if row[3] else ''}'>\n\t{row[2].replace(newline_char, indent_sequence)}\n</memory>"
            for row in memories
        ]
    )

def describe_image(image: Any, memory_text: Optional[str] = None) -> str:
    """Generate a description of an image using a VLM."""
    model_info = model_registry.get_vlm_model(os.getenv("IMAGE_MODEL_NAME", "mlx-community/gemma-3-27b-it-8bit"))
    messages = prompt_templates.get_image_description_template(memory_text)
    prompt = cast(
        str,
        vlm_apply_chat_template(
            model_info.processor,
            model_info.config,
            messages,
            num_images=1,
        ),
    )
    generation = vlm_generate(
        model_info.model,
        model_info.processor,
        prompt,
        [image],
        verbose=True,
        max_tokens=int(os.getenv("IMAGE_MAX_TOKENS", "100000")),
        temperature=float(os.getenv("IMAGE_TEMP", "0.7")),
    )
    if isinstance(generation, VLMGenerationResult):
        return generation.text
    return generation


def stream_chat(query: str, context_xml: str, *, is_agent: bool = True) -> Iterable[str]:
    """
    Stream a chat response with agentic tool-calling support.

    Args:
        query: The user's query
        context_xml: XML context (typically memories)
        is_agent: Whether to use agentic model and tool-calling

    Yields:
        SSE event strings
    """
    default_model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-8bit"
    chat_model_name = os.getenv("CHAT_MODEL_NAME", default_model_name)
    agentic_model_name = os.getenv("AGENTIC_MODEL_NAME", default_model_name)

    model_name = agentic_model_name if is_agent else chat_model_name
    cache_key = f"{model_name.split('/')[-1]}_memory_cache"

    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_chat_template(context_xml, query, is_agent))
    else:
        messages = prompt_templates.get_vico_chat_template(context_xml, query, is_agent)

    model, tokenizer, prompt_cache, prompt, max_tokens, max_kv_size, sampler, logits, tools = setup_generation_context(
        model_name, cache_key, context_xml, query, is_agent, "Assistant:"
    )

    yield from run_streaming_generation_loop(
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
    )

    cache_manager.mark_initialized(cache_key)


def stream_chat_with_memories(query: str, *, is_agent: bool = True) -> Iterable[str]:
    """
    Stream a chat response with memory context automatically loaded.

    Args:
        query: The user's query
        is_agent: Whether to use agentic model and tool-calling

    Yields:
        SSE event strings
    """
    memories_xml = get_memories_xml()
    yield from stream_chat(query, memories_xml, is_agent=is_agent)
    yield make_sse("end")

