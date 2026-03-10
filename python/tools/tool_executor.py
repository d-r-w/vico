import subprocess
import re
import json
import logging
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from offline_wikipedia_service import offline_wikipedia_service
from tools.tool_definitions import get_full_topic_details_tool_name, perform_research_tool_name

# Set up logging for this module
logger = logging.getLogger(__name__)

MAX_TERMINAL_OUTPUT_LENGTH = 8000


class ToolCall(NamedTuple):
    name: str
    arguments: Dict[str, Any]


class ToolCallParseError(Exception):
    """Raised when a ``<tool_call>`` block cannot be parsed."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


_TOOL_CALL_PATTERN = re.compile(r"<tool_call>(?P<body>.*?)</tool_call>", re.DOTALL)
_ARGUMENT_PATTERN = re.compile(
    r"<arg_key>(?P<key>.*?)</arg_key>[\s\r\n]*<arg_value>(?P<value>.*?)</arg_value>",
    re.DOTALL,
)
_FUNCTION_PATTERN = re.compile(r"<function\s*=\s*(?P<quote>\"?)(?P<name>[^\">\s]+)(?P=quote)\s*>", re.IGNORECASE)
_PARAMETER_PATTERN = re.compile(
    r"<parameter\s*=\s*(?P<quote>\"?)(?P<key>[^\">\s]+)(?P=quote)\s*>(?P<value>.*?)"
    r"</parameter(?:\s*=\s*(?P<end_quote>\"?)(?P<end_key>[^\">\s]+)(?P=end_quote)\s*)?\s*>",
    re.DOTALL | re.IGNORECASE,
)


def parse_tool_call(response_text: str) -> ToolCall:
    parsed_calls = parse_tool_calls(response_text)
    if len(parsed_calls) > 1:
        logger.debug("Multiple <tool_call> blocks detected; using the first occurrence")
    return parsed_calls[0]


def parse_tool_calls(response_text: str) -> List[ToolCall]:
    if not isinstance(response_text, str):
        raise ToolCallParseError("Response text must be a string")

    if not response_text.strip():
        raise ToolCallParseError("Response text is empty")

    matches = list(_TOOL_CALL_PATTERN.finditer(response_text))
    if not matches:
        raise ToolCallParseError("Missing <tool_call> block")

    parsed_calls: List[ToolCall] = []
    for index, match in enumerate(matches):
        body = match.group("body").strip()
        if not body:
            raise ToolCallParseError(f"Empty <tool_call> block at index {index}")
        parsed_calls.append(_parse_tool_call_body(body))

    return parsed_calls


def _parse_tool_call_body(body: str) -> ToolCall:
    first_line = _first_non_empty_line(body)
    if not first_line:
        raise ToolCallParseError("Tool call block contains no content")

    if _looks_like_json(first_line):
        return _parse_json_tool_call(body)

    function_name = _parse_function_name(body)
    if function_name:
        arguments = _parse_parameter_pairs(body)
        if not arguments:
            arguments, inferred_name = _parse_embedded_arguments(body)
            if inferred_name:
                function_name = inferred_name.strip()
        return ToolCall(function_name, arguments)

    tool_name = first_line.strip()
    arguments = _parse_argument_pairs(body)

    if not arguments:
        arguments, inferred_name = _parse_embedded_arguments(body)
        if inferred_name:
            tool_name = inferred_name.strip()

    if not tool_name:
        raise ToolCallParseError("Tool name missing in <tool_call> block")

    return ToolCall(tool_name, arguments)


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _looks_like_json(value: str) -> bool:
    if not value:
        return False
    starts = value[0]
    ends = value[-1]
    return (starts == "{" and ends == "}") or (starts == "[" and ends == "]")


def _parse_json_tool_call(body: str) -> ToolCall:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ToolCallParseError(f"Invalid JSON tool call payload: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ToolCallParseError("JSON tool call payload must be an object")

    raw_name = payload.get("name")
    if not isinstance(raw_name, str) or not raw_name.strip():
        raise ToolCallParseError("JSON tool call payload missing 'name'")

    raw_arguments = payload.get("arguments", {})
    if raw_arguments is None:
        arguments: Dict[str, Any] = {}
    elif isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        raise ToolCallParseError("JSON tool call 'arguments' must be an object")

    return ToolCall(raw_name.strip(), dict(arguments))


def _parse_argument_pairs(body: str) -> Dict[str, Any]:
    arguments: Dict[str, Any] = {}

    for match in _ARGUMENT_PATTERN.finditer(body):
        key = match.group("key").strip()
        if not key:
            continue

        raw_value = match.group("value")
        if raw_value is None:
            continue

        arguments[key] = _coerce_argument_value(raw_value)

    return arguments


def _parse_function_name(body: str) -> Optional[str]:
    match = _FUNCTION_PATTERN.search(body)
    if not match:
        return None
    tool_name = match.group("name").strip()
    return tool_name if tool_name else None


def _parse_parameter_pairs(body: str) -> Dict[str, Any]:
    arguments: Dict[str, Any] = {}
    for match in _PARAMETER_PATTERN.finditer(body):
        key = (match.group("key") or "").strip()
        if not key:
            continue
        raw_value = match.group("value")
        if raw_value is None:
            continue
        arguments[key] = _coerce_argument_value(raw_value)
    return arguments


def _parse_embedded_arguments(body: str) -> Tuple[Dict[str, Any], Optional[str]]:
    json_match = re.search(r"\{.*\}", body, re.DOTALL)
    if not json_match:
        return {}, None

    candidate = json_match.group(0)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return {}, None

    if not isinstance(payload, dict):
        return {}, None

    nested_arguments = payload.get("arguments")
    if isinstance(nested_arguments, dict):
        return _drop_name_key(dict(nested_arguments)), _safe_extract_name(payload)

    return _drop_name_key(dict(payload)), _safe_extract_name(payload)


def _safe_extract_name(payload: Dict[str, Any]) -> Optional[str]:
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name
    return None


def _drop_name_key(arguments: Dict[str, Any]) -> Dict[str, Any]:
    if "name" in arguments:
        arguments = {k: v for k, v in arguments.items() if k != "name"}
    return arguments


def _coerce_argument_value(raw_value: str) -> Any:
    value = raw_value.strip()
    if not value:
        return ""

    if _looks_like_json(value):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.debug("Failed to parse argument value as JSON", exc_info=True)

    return value

def _truncate_terminal_output(text: str, max_length: int = MAX_TERMINAL_OUTPUT_LENGTH) -> str:
    """Truncate terminal output to prevent context overflow."""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n[Output truncated to avoid exceeding context window]"


def execute_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    *,
    allowed_tool_names: Optional[set[str]] = None,
    memory_storage_service=None,
    cache_manager=None,
) -> str:
    if allowed_tool_names is not None and tool_name not in allowed_tool_names:
        allowed = ", ".join(sorted(allowed_tool_names)) if allowed_tool_names else "(none)"
        logger.warning("Disallowed tool call attempted: %s (allowed: %s)", tool_name, allowed)
        return f"Error: Tool `{tool_name}` is not permitted for this agent. Allowed tools: {allowed}"

    result = None

    match tool_name:
        case "voice_response":
            text_to_speak = arguments.get("text", "")
            if text_to_speak:
                logger.info("Invoking voice response with text length: %s characters", len(text_to_speak))
                subprocess.Popen(["say", text_to_speak])
                result = "Voice response was successful."

        case "save_memory":
            memory_text = arguments.get("memory_text", "")
            tags = arguments.get("tags", None)
            if memory_storage_service is None or cache_manager is None:
                return "Error: memory storage service is unavailable."
            logger.info("Saving memory with length: %s characters", len(memory_text))
            memory_storage_service.save_memory(memory_text, tag_ids=tags)
            result = "Memory saved."

        case "edit_memory":
            memory_id = arguments.get("memory_id", "")
            new_memory_text = arguments.get("new_memory_text", "")
            if memory_storage_service is None or cache_manager is None:
                return "Error: memory storage service is unavailable."
            logger.info("Editing memory ID: %s", memory_id)
            memory_storage_service.edit_memory(memory_id, new_memory_text)
            result = f"Memory `{memory_id}` edited with new memory text."

        case "search_memories":
            terms = arguments.get("terms", [])
            if memory_storage_service is None:
                return "Error: memory storage service is unavailable."
            logger.info("Searching memories for terms: %s", terms)
            memories = memory_storage_service.search_memories(terms)
            if memories:
                formatted = []
                for memory_id, memory_text, image, created_at, tags in memories:
                    formatted.append(
                        "\n".join(
                            [
                                f"Memory ID: {memory_id}",
                                f"Created: {created_at}",
                                f"Tags: {', '.join(tags) if tags else 'None'}",
                                f"Content: {memory_text}",
                                "[Contains image]" if image else "",
                                "-" * 40,
                            ]
                        ).strip()
                    )
                result = "\n".join(formatted).strip()
            else:
                result = "No memories found, try different keywords."

        case "perform_research":
            terms = arguments.get("terms", [])
            logger.info("Searching Wikipedia for terms: %s", terms)
            result = offline_wikipedia_service.fulltext_search(terms)
            if result:
                result += f"""
                    
To unlock full topic details, use the `{get_full_topic_details_tool_name}(['topic_id'])` tool for up to 5 of the above topics.

If these matches aren't useful, simply attempt different keywords in a new `{perform_research_tool_name}` tool call.
"""
            else:
                result = "No results found, try different keywords."

        case "get_full_topic_details":
            topic_ids = arguments.get("topic_ids", [])
            logger.info("Getting full Wikipedia article details for topic IDs: %s", topic_ids)
            result = offline_wikipedia_service.get_full_wikipedia_article(topic_ids)
            if result:
                result += f"""
                    
Retreived full topic details for [{topic_ids}]
"""

        case "terminal_command":
            command = arguments.get("command", "")
            logger.info("Processing terminal command: %s", command)

            forbidden_patterns = [
                r"rm\s+-rf\s+[/~]",  # Prevent dangerous rm commands
                r">[>]?\s*(?!/dev/null\b)[/~]",  # Prevent writing to root/home, allow /dev/null
                r"\|\s*rm",  # Prevent piping to rm
                r"sudo",  # Prevent sudo usage
                r"chmod\s+[0-7]*7\b",  # Prevent adding execute permissions
            ]

            for pattern in forbidden_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    logger.error("Forbidden command pattern detected: %s", command)
                    return "Error: You are not allowed to use this command. If this prevents you from completing the task, immediately stop attempting to complete the task and return this message."

            try:
                if command.strip() and not command.strip()[0].isdigit():
                    process = subprocess.run(
                        ["/bin/bash", "-c", command], capture_output=True, text=True, timeout=3600
                    )
                    result_lines = [f"Command executed: {command}", f"Exit code: {process.returncode}"]
                    if process.stdout:
                        result_lines.append(f"Output:\n{_truncate_terminal_output(process.stdout)}")
                    if process.stderr:
                        result_lines.append(f"Error output:\n{_truncate_terminal_output(process.stderr)}")
                    if not process.stdout and not process.stderr:
                        result_lines.append("Command completed with no output.")
                    result = "\n".join(result_lines).strip()
                else:
                    result = "Error: Invalid command format"
            except subprocess.TimeoutExpired:
                result = "Error: Command timed out after 30 seconds"
            except Exception as e:
                result = f"Error executing command: {str(e)}"

    if result is None:
        return f"Error: Unknown tool `{tool_name}`."
    return result


def get_tool_call_results(response_text, passed_logger, memory_storage_service=None, cache_manager=None, allowed_tool_names=None):
    """
    Process tool call results from response text and execute the appropriate tool.
    
    Args:
        response_text: The response text containing tool call information
        passed_logger: Logger instance passed from calling module
        memory_storage_service: Service for memory operations
        cache_manager: Cache manager for invalidating caches
    
    Returns:
        List containing [tool_name, result]
    """
    logger.info(f"Processing tool call from response text")
    logger.debug(f"Response text length: {len(response_text)} characters")
    
    tool_name: str = "unknown"
    try:
        parsed_call = parse_tool_call(response_text)
    except ToolCallParseError as exc:
        logger.error(f"Error parsing tool call: {exc.message}")
        return [tool_name, f"Tool call parsing error. Please check syntax: {exc.message}"]

    parsed_name, arguments = parsed_call
    tool_name = parsed_name

    try:
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Parsed arguments: {arguments}")
        result = execute_tool_call(
            tool_name,
            arguments,
            allowed_tool_names=allowed_tool_names,
            memory_storage_service=memory_storage_service,
            cache_manager=cache_manager,
        )
        
        logger.info(f"Tool call ({tool_name}) result: {result}")
        return [tool_name, result]
                        
    except Exception as e:
        logger.error(f"Error processing tool call: {e}")
        return [tool_name, f"Tool call parsing error. Please check syntax: {str(e)}"]
