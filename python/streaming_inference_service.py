from __future__ import annotations

from collections import deque
from datetime import datetime
import gc
import io
import json
import logging
import os
import queue
import re
import threading
from uuid import uuid4
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, NamedTuple, Optional, Set, Tuple, Union, cast

from dotenv import load_dotenv
from mlx_lm.generate import stream_generate as lm_generate_streaming
from mlx_lm.models.cache import make_prompt_cache
from mlx_lm.sample_utils import make_logits_processors, make_sampler
from mlx_lm.utils import load as lm_load
from mlx_vlm import apply_chat_template as vlm_apply_chat_template
from mlx_vlm import generate as vlm_generate
from mlx_vlm import GenerationResult as VLMGenerationResult
from mlx_vlm import load as vlm_load

import memory_storage_service
import prompt_templates
from agent_profiles import (
    AgentProfile,
    build_agent_profile_tool_definitions,
    build_tool_usage_prompt,
    filter_tool_definitions,
    get_agent_cache_suffix,
    get_agent_profile,
    get_specialized_agent_profiles,
)
from tools.tool_executor import execute_tool_call, parse_tool_calls, ToolCallParseError

load_dotenv()

logger = logging.getLogger("streaming_inference")

_MODEL_GENERATION_LOCKS: Dict[str, threading.Lock] = {}
_MODEL_GENERATION_LOCKS_GUARD = threading.Lock()


def get_model_generation_lock(model_name: str) -> threading.Lock:
    """Ensure only one generation runs per loaded model at a time (thread-safety)."""
    with _MODEL_GENERATION_LOCKS_GUARD:
        lock = _MODEL_GENERATION_LOCKS.get(model_name)
        if lock is None:
            lock = threading.Lock()
            _MODEL_GENERATION_LOCKS[model_name] = lock
        return lock


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
        load_result = lm_load(model_name)
        if len(load_result) == 2:
            model, tokenizer = load_result
        else:
            model, tokenizer, _ = load_result
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
        self._lock = threading.Lock()
        self._debug_context_by_cache_key: Dict[str, Deque[Dict[str, Any]]] = {}
        os.makedirs(self._cache_dir, exist_ok=True)

    def get_cache(self, cache_key: str, model: Any) -> Any:
        with self._lock:
            if cache_key in self._prompt_caches:
                logger.info(f"Using existing in-memory prompt cache for {cache_key}")
                return self._prompt_caches[cache_key]

        logger.info(f"Creating new prompt cache for {cache_key}")
        prompt_cache = make_prompt_cache(model)
        with self._lock:
            self._prompt_caches[cache_key] = prompt_cache
        return prompt_cache

    def mark_initialized(self, cache_key: str) -> None:
        with self._lock:
            if cache_key in self._prompt_caches:
                self._initialized_caches.add(cache_key)
                logger.info(f"Marked cache {cache_key} as fully initialized")

    def is_initialized(self, cache_key: str) -> bool:
        with self._lock:
            return cache_key in self._initialized_caches

    def record_cache_context(
        self,
        cache_key: str,
        *,
        phase: str,
        messages: List[Dict[str, Any]],
        prompt: str,
        assistant_response: str | None = None,
    ) -> None:
        """Record the explicit prompt/messages used for this cache_key (bounded; for debugging only)."""
        if not self._debug_enabled():
            return
        max_items = int(os.getenv("LOG_CONTEXT_PER_CACHE_MAX_ITEMS", "100"))
        max_chars = int(os.getenv("LOG_CONTEXT_PER_CACHE_MAX_CHARS_STORE", "200000"))

        def clip(text: str) -> str:
            if len(text) <= max_chars:
                return text
            head = text[: max_chars // 2]
            tail = text[-max_chars // 2 :]
            return f"{head}\n...[truncated {len(text) - max_chars} chars]...\n{tail}"

        try:
            messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
        except Exception as exc:
            messages_json = f"<<messages_json_encoding_failed: {exc}>>"

        record: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "phase": phase,
            "messages_json": clip(messages_json),
            "prompt": clip(prompt),
            "prompt_chars": len(prompt),
            "messages_count": len(messages),
        }
        if assistant_response is not None:
            record["assistant_response"] = clip(assistant_response)
            record["assistant_response_chars"] = len(assistant_response)

        with self._lock:
            buf = self._debug_context_by_cache_key.get(cache_key)
            if buf is None:
                buf = deque(maxlen=max_items)
                self._debug_context_by_cache_key[cache_key] = buf
            buf.append(record)

    def dump_cache_context(self, cache_key: str) -> None:
        """Dump recorded context for cache_key (entire in-process history)."""
        if not self._debug_enabled():
            return

        with self._lock:
            records = list(self._debug_context_by_cache_key.get(cache_key, []))

        logger.info("[cache=%s] CONTEXT_DUMP_BEGIN records=%d", cache_key, len(records))
        for idx, r in enumerate(records):
            ts = r.get("ts", "")
            phase = r.get("phase", "")
            prompt_chars = r.get("prompt_chars", 0)
            messages_count = r.get("messages_count", 0)
            logger.info(
                "[cache=%s] record[%d] ts=%s phase=%s messages=%s prompt_chars=%s",
                cache_key,
                idx,
                ts,
                phase,
                messages_count,
                prompt_chars,
            )
            messages_json = r.get("messages_json", "")
            if messages_json:
                logger.info("[cache=%s] record[%d] messages:\n%s", cache_key, idx, messages_json)
        logger.info("[cache=%s] CONTEXT_DUMP_END", cache_key)

    def release_cache(self, cache_key: str) -> None:
        with self._lock:
            if cache_key in self._prompt_caches:
                logger.info(f"Releasing prompt cache: {cache_key}")
                del self._prompt_caches[cache_key]
            self._initialized_caches.discard(cache_key)
            self._debug_context_by_cache_key.pop(cache_key, None)

    def _debug_enabled(self) -> bool:
        return os.getenv("LOG_CONTEXT_PER_CACHE", "0") == "1"


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
    has_function_call: bool

_SSE_EVENT_SOURCE_BY_TYPE: Dict[str, str] = {
    "assistant_token": "assistant",
    "thinking_token": "assistant_thinking",
    "thinking_complete": "assistant_thinking",
    "subagent_token": "subagent",
    "subagent_thinking_token": "subagent_thinking",
    "subagent_thinking_complete": "subagent_thinking",
}

def _event_source_for_type(event_type: str) -> str:
    """Map SSE event types to a UI-friendly source label."""
    if event_type.startswith("assistant_tool_call_"):
        return "assistant_tool"
    if event_type.startswith("subagent_tool_call_"):
        return "subagent_tool"
    return _SSE_EVENT_SOURCE_BY_TYPE.get(event_type, "system")

def make_sse(event_type: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """Format an SSE event string."""
    try:
        body: Dict[str, Any] = {"type": event_type}
        if payload:
            body.update(payload)
        if "source" not in body:
            body["source"] = _event_source_for_type(event_type)
        return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
    except Exception as e:
        fallback = {"type": "error", "source": "system", "message": f"encoding failure: {e}"}
        return f"data: {json.dumps(fallback, ensure_ascii=False)}\n\n"

def make_assistant_tool_call_start_event(call_id: str, tool_name: str, tool_input: Dict[str, Any]) -> str:
    return make_sse("assistant_tool_call_start", {"call_id": call_id, "tool_name": tool_name, "input": tool_input})

def make_assistant_tool_call_end_event(call_id: str, tool_name: str, tool_output: Any) -> str:
    return make_sse("assistant_tool_call_end", {"call_id": call_id, "tool_name": tool_name, "output": tool_output})

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
    """Scan text for <tool_call> tags and function-style calls."""
    open_tag = "<tool_call>"
    close_tag = "</tool_call>"
    open_len = len(open_tag)
    has_function_call = "<function=" in text.lower()

    has_open = False
    index = 0
    limit = len(text)

    while index < limit:
        if not has_open and text.startswith(open_tag, index):
            has_open = True
            index += open_len
            continue
        if text.startswith(close_tag, index):
            return ToolCallTagScan(has_open, True, has_function_call)
        index += 1

    return ToolCallTagScan(has_open, False, has_function_call)


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

def log_full_messages_summary(context_name: str, messages: List[Dict[str, Any]]) -> None:
    """Log a one-line summary for every message (role/name/content length)."""
    log_messages_summary(context_name, messages, max_items=len(messages))


def log_system_prompt(context_name: str, messages: List[Dict[str, Any]], max_chars: int = 4000) -> None:
    """Log the system prompt content (truncated) for debugging agent initialization."""
    for idx, m in enumerate(messages):
        if m.get("role") != "system":
            continue
        content = m.get("content", "")
        if not isinstance(content, str):
            logger.info(f"[{context_name}] system prompt m[{idx}] (non-string content)")
            return
        text = content.strip()
        length = len(text)
        preview = text if length <= max_chars else text[:max_chars] + "\n...[truncated]"
        logger.info(f"[{context_name}] system prompt m[{idx}] len={length}")
        logger.info(f"[{context_name}] system prompt preview:\n{preview}")
        return
    logger.info(f"[{context_name}] system prompt not found")


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
    tool_name: str = "",
    *,
    tool_usage_prompt: str,
    allowed_tool_definitions: List[Dict[str, Any]] | None = None,
    extra_instructions: Optional[str] = None,
) -> Tuple[Any, Any, Any, str, int, int, Any, Any, List[Dict[str, Any]]]:
    """Common setup for model, cache, and generation parameters."""
    model, tokenizer = model_registry.get_lm_model(model_name)
    prompt_cache = cache_manager.get_cache(cache_key, model)

    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_agent_template(query, tool_usage_prompt, False, extra_instructions=extra_instructions))
    else:
        messages = prompt_templates.get_vico_agent_template(query, tool_usage_prompt, extra_instructions=extra_instructions)

    tools = allowed_tool_definitions if allowed_tool_definitions is not None else []
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
        "content": f"<tool_call_results>\n{strip_think_blocks(tool_result)}\n</tool_call_results>",
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
    tokenizer: Any
) -> ToolCallHandler:
    """Build a handler that spawns subagents for tool execution."""

    def handler(tool_call_name: str, tool_args: Dict[str, Any], _clean_text: str) -> ToolCallOutcome:
        try:
            logger.info(
                "[%s] spawning subagent '%s' with args=%s",
                parent_label,
                tool_call_name,
                json.dumps(tool_args, ensure_ascii=False) if isinstance(tool_args, dict) else str(tool_args)
            )
        except Exception:
            logger.info("[%s] spawning subagent '%s'", parent_label, tool_call_name)
        subagent_profile = get_agent_profile(tool_call_name)
        executor = SubAgentExecutor(
            parent_label=parent_label,
            tool_call_name=tool_call_name,
            tool_args=tool_args,
            model_name=model_name,
            model=model,
            tokenizer=tokenizer,
            agent_profile=subagent_profile
        )
        stream = executor.stream_sse(inject_think_if_missing=is_qwen3_thinking_model(model_name))
        return ToolCallOutcome(stream=stream, result_supplier=executor.result)

    return handler


def build_direct_tool_call_handler(*, agent_profile: AgentProfile) -> ToolCallHandler:
    """Build a handler that executes tools directly without subagents."""

    def handler(tool_call_name: str, tool_args: Dict[str, Any], _clean_text: str) -> ToolCallOutcome:
        def result_supplier() -> str:
            try:
                return execute_tool_call(
                    tool_call_name,
                    tool_args,
                    allowed_tool_names=agent_profile.allowed_tool_names,
                    memory_storage_service=memory_storage_service,
                    cache_manager=cache_manager,
                )
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
    cache_key: str | None,
    max_tokens: int,
    max_kv_size: int,
    sampler: Any,
    logits: Any,
    tools: List[Dict[str, Any]],
    model_name: str,
    agent_profile: AgentProfile,
    tool_name: str = "",
    on_token: Optional[Callable[[str], None]] = None,
    on_tool_call_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_call_end: Optional[Callable[[str, Any], None]] = None,
    tool_call_handler: Optional[ToolCallHandler] = None,
    on_final_response_text: Optional[Callable[[str], None]] = None,
) -> Iterable[str]:
    """Streaming generation loop that yields SSE events."""
    while True:
        generation_lock = get_model_generation_lock(model_name)
        response_buffer = io.StringIO()
        with generation_lock:
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

        if tag_scan.has_close or tag_scan.has_function_call:
            if tag_scan.has_close and not tag_scan.has_open and not tag_scan.has_function_call:
                append_tool_result(messages, "error", "Tool call syntax error: opening <tool_call> tag not found.")
                logger.warning(f"[{tool_name}] Tool call detected but no <tool_call> tag found")
            else:
                logger.info(f"[{tool_name}] Tool call detected")
                try:
                    tool_calls = parse_tool_calls(clean_text)
                except ToolCallParseError as exc:
                    logger.warning(f"[{tool_name}] Tool call parsing failed: {exc.message}")
                    append_tool_result(messages, "error", f"Tool call parsing failed: {exc.message}")
                else:
                    handler: ToolCallHandler = tool_call_handler or build_agent_tool_call_handler(
                        parent_label=tool_name,
                        model_name=model_name,
                        model=model,
                        tokenizer=tokenizer
                    )

                    for t_name, t_args in tool_calls:
                        call_id = str(uuid4())
                        if t_name not in agent_profile.allowed_tool_names:
                            tool_result = (
                                f"Error: Tool `{t_name}` is not permitted for this agent. "
                                f"Allowed tools: {', '.join(sorted(agent_profile.allowed_tool_names)) if agent_profile.allowed_tool_names else '(none)'}"
                            )
                            append_tool_result(messages, t_name, tool_result)
                            yield make_assistant_tool_call_start_event(call_id, t_name, t_args)
                            yield make_assistant_tool_call_end_event(call_id, t_name, clean_tool_output_for_event(tool_result))
                            continue

                        if on_tool_call_start is not None:
                            try:
                                on_tool_call_start(t_name, t_args)
                            except Exception as e:
                                logger.warning(f"[{tool_name}] on_tool_call_start callback error: {e}")

                        yield make_assistant_tool_call_start_event(call_id, t_name, t_args)

                        try:
                            outcome = handler(t_name, t_args, clean_text)
                        except Exception as e:
                            logger.error(f"[{tool_name}] Tool call handler error: {e}")
                            outcome = ToolCallOutcome(stream=None, result_supplier=lambda: "")

                        if outcome.stream is not None:
                            yield from outcome.stream

                        tool_result = outcome.result_supplier()
                        append_tool_result(messages, t_name, tool_result)

                        if on_tool_call_end is not None:
                            try:
                                on_tool_call_end(t_name, tool_result)
                            except Exception as e:
                                logger.warning(f"[{tool_name}] on_tool_call_end callback error: {e}")

                        yield make_assistant_tool_call_end_event(call_id, t_name, clean_tool_output_for_event(tool_result))

            prompt = tokenizer.apply_chat_template(messages, tools, add_generation_prompt=True, tokenize=False)
            continue
        else:
            if on_final_response_text is not None:
                try:
                    on_final_response_text(clean_text)
                except Exception as e:
                    logger.warning(f"[{tool_name}] on_final_response_text callback error: {e}")
            final_messages = [*messages, {"role": "assistant", "content": clean_text}]
            log_full_messages_summary(f"{tool_name}final", final_messages)
            if cache_key is not None and tool_name == "Assistant:":
                cache_manager.record_cache_context(
                    cache_key,
                    phase="final",
                    messages=final_messages,
                    prompt=prompt,
                    assistant_response=clean_text,
                )
                cache_manager.dump_cache_context(cache_key)
            break


def collect_blocking_response(
    *,
    model: Any,
    tokenizer: Any,
    prompt_cache: Any,
    messages: List[Dict[str, Any]],
    prompt: str,
    cache_key: str | None,
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
    agent_profile: AgentProfile,
) -> str:
    """Run generation loop to completion and return final response text."""
    final_text_parts: List[str] = []

    def capture_final_text(text: str) -> None:
        final_text_parts.append(text)

    handler = build_direct_tool_call_handler(agent_profile=agent_profile)

    for _ in run_streaming_generation_loop(
        model=model,
        tokenizer=tokenizer,
        prompt_cache=prompt_cache,
        messages=messages,
        prompt=prompt,
        cache_key=cache_key,
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
        agent_profile=agent_profile,
    ):
        pass

    return strip_think_blocks("".join(final_text_parts)).strip()


def run_agent(
    tool_name: str,
    arguments: Dict[str, Any],
    parent_model_name: str,
    parent_model: Any,
    parent_tokenizer: Any,
    agent_profile: AgentProfile,
    on_token: Optional[Callable[[str], None]] = None,
    on_tool_call_start: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    on_tool_call_end: Optional[Callable[[str, Any], None]] = None,
) -> str:
    """Execute a subagent task with the given tool and arguments."""
    model, tokenizer = parent_model, parent_tokenizer
    logger.info(f"[Agent:{tool_name}] Reusing assistant model: {parent_model_name}")
    try:
        logger.info(
            "[Agent:%s] init profile=%s allowed_tools=%s detailed_task=%s",
            tool_name,
            agent_profile.agent_id,
            ",".join(sorted(agent_profile.allowed_tool_names)),
            arguments.get("detailed_task", "")
        )
    except Exception:
        logger.info("[Agent:%s] init profile=%s", tool_name, agent_profile.agent_id)

    cache_key = f"{parent_model_name.split('/')[-1]}_agent_cache__{tool_name}__{get_agent_cache_suffix(agent_profile)}"
    prompt_cache = cache_manager.get_cache(cache_key, model)

    allowed_tool_definitions = filter_tool_definitions(agent_profile.allowed_tool_names)
    tool_usage_prompt = build_tool_usage_prompt(allowed_tool_definitions=allowed_tool_definitions, is_subagent=True)
    
    instructions_list = [
        prompt_templates.get_date_system_instructions(),
        "",
        "You are a specialized sub-agent. Your goal is to execute the requested tool-task end-to-end using available tools, iterating as needed.",
        "When finished, output a concise final result intended to be consumed by the parent assistant. Do not include internal notes.",
        "",
    ]
    if agent_profile.system_instructions:
        instructions_list.extend([
            "SPECIAL INSTRUCTIONS:",
            agent_profile.system_instructions,
            "",
        ])
    instructions_list.append(tool_usage_prompt)
    system_instructions = "\n".join(instructions_list).strip()

    logger.info(f"[Agent:{tool_name}] system_instructions:\n{system_instructions}")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_instructions},
        {
            "role": "user",
            "content": (
                f"Agent profile: {agent_profile.agent_id}\n"
                f"Task: {arguments.get('detailed_task', '')}\n\n"
                "Plan your steps and use tools with <tool_call> when needed."
            ),
        },
    ]

    tools = allowed_tool_definitions
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
        cache_key=cache_key,
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
        agent_profile=agent_profile,
    )

    cache_manager.release_cache(cache_key)
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
        agent_profile: AgentProfile
    ) -> None:
        self._parent_label = parent_label
        self._tool_call_name = tool_call_name
        self._tool_args = tool_args
        self._model_name = model_name
        self._model = model
        self._tokenizer = tokenizer
        self._agent_profile = agent_profile
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
        pending_tool_call_ids: Dict[str, Deque[str]] = {}

        def on_token(text: str) -> None:
            if text:
                self._emit_item(StreamToken(text))

        def on_tool_start(name: str, args: Dict[str, Any]) -> None:
            call_id = str(uuid4())
            pending_tool_call_ids.setdefault(name, deque()).append(call_id)
            self._emit_item(
                StreamEvent(
                    "subagent_tool_call_start",
                    {"call_id": call_id, "tool_name": name, "input": args, "parent_tool_name": self._tool_call_name},
                )
            )

        def on_tool_end(name: str, output: Any) -> None:
            cleaned_output = clean_tool_output_for_event(output) if isinstance(output, str) else output
            call_id = str(uuid4())
            pending_ids = pending_tool_call_ids.get(name)
            if pending_ids:
                pending_call_id = pending_ids.popleft()
                if pending_call_id:
                    call_id = pending_call_id
            self._emit_item(
                StreamEvent(
                    "subagent_tool_call_end",
                    {"call_id": call_id, "tool_name": name, "output": cleaned_output, "parent_tool_name": self._tool_call_name},
                )
            )

        try:
            result = run_agent(
                self._tool_call_name,
                self._tool_args,
                self._model_name,
                self._model,
                self._tokenizer,
                agent_profile=self._agent_profile,
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


def stream_agent_response(query: str, context_xml: str, agent_id: str | None = None) -> Iterable[str]:
    """
    Stream an agent response with tool-calling support.

    Args:
        query: The user's query
        context_xml: XML context (typically memories)

    Yields:
        SSE event strings
    """
    default_model_name = "mlx-community/Qwen2.5-14B-Instruct-1M-8bit"
    agentic_model_name = os.getenv("AGENTIC_MODEL_NAME", default_model_name)

    profile = get_agent_profile(agent_id)
    agent_tool_definitions = build_agent_profile_tool_definitions(get_specialized_agent_profiles())
    allowed_tool_definitions = agent_tool_definitions
    tool_usage_prompt = build_tool_usage_prompt(allowed_tool_definitions=allowed_tool_definitions)

    model_name = agentic_model_name
    cache_key = f"{model_name.split('/')[-1]}_memory_cache__{get_agent_cache_suffix(profile)}"

    messages: List[Dict[str, Any]] = []
    if cache_manager.is_initialized(cache_key):
        messages.extend(prompt_templates.get_vico_agent_template(query, tool_usage_prompt, False, extra_instructions=profile.system_instructions))
    else:
        messages = prompt_templates.get_vico_agent_template(query, tool_usage_prompt, extra_instructions=profile.system_instructions)

    if messages and messages[0]["role"] == "system":
        logger.info(f"[Assistant] system_instructions:\n{messages[0]['content']}")

    model, tokenizer, prompt_cache, prompt, max_tokens, max_kv_size, sampler, logits, tools = setup_generation_context(
        model_name,
        cache_key,
        context_xml,
        query,
        "Assistant:",
        tool_usage_prompt=tool_usage_prompt,
        allowed_tool_definitions=allowed_tool_definitions,
        extra_instructions=profile.system_instructions,
    )

    yield from run_streaming_generation_loop(
        model=model,
        tokenizer=tokenizer,
        prompt_cache=prompt_cache,
        messages=messages,
        prompt=prompt,
        cache_key=cache_key,
        max_tokens=max_tokens,
        max_kv_size=max_kv_size,
        sampler=sampler,
        logits=logits,
        tools=tools,
        model_name=model_name,
        tool_name="Assistant:",
        tool_call_handler=(
            build_agent_tool_call_handler(
                parent_label="Assistant:",
                model_name=model_name,
                model=model,
                tokenizer=tokenizer
            )
        ),
        agent_profile=profile,
    )

    cache_manager.mark_initialized(cache_key)


def stream_agent_response_with_memories(query: str, agent_id: str | None = None) -> Iterable[str]:
    """
    Stream an agent response with memory context automatically loaded.

    Args:
        query: The user's query

    Yields:
        SSE event strings
    """
    memories_xml = get_memories_xml()
    yield from stream_agent_response(query, memories_xml, agent_id=agent_id)
    yield make_sse("end")
