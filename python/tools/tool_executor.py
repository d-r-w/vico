import subprocess
import re
import json
import logging
from typing import Any, Dict, NamedTuple, Optional, Tuple

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


def parse_tool_call(response_text: str) -> ToolCall:
    if not isinstance(response_text, str):
        raise ToolCallParseError("Response text must be a string")

    if not response_text.strip():
        raise ToolCallParseError("Response text is empty")

    matches = list(_TOOL_CALL_PATTERN.finditer(response_text))
    if not matches:
        raise ToolCallParseError("Missing <tool_call> block")

    if len(matches) > 1:
        logger.debug("Multiple <tool_call> blocks detected; using the first occurrence")

    body = matches[0].group("body").strip()
    if not body:
        raise ToolCallParseError("Empty <tool_call> block")

    first_line = _first_non_empty_line(body)
    if not first_line:
        raise ToolCallParseError("Tool call block contains no content")

    if _looks_like_json(first_line):
        return _parse_json_tool_call(body)

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

def get_tool_call_results(response_text, passed_logger, memory_storage_service=None, cache_manager=None):
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
        result = None
            
        match tool_name:
            case "voice_response":
                text_to_speak = arguments.get("text", "")
                if text_to_speak:
                    logger.info(f"Invoking voice response with text length: {len(text_to_speak)} characters")
                    logger.debug(f"Voice response text: {text_to_speak}")
                    subprocess.Popen(["say", text_to_speak])
                    result = f"Voice response was successful."
                    logger.info("Voice response completed successfully")
                    
            case "save_memory":
                memory_text = arguments.get("memory_text", "")
                logger.info(f"Saving memory with length: {len(memory_text)} characters")
                logger.debug(f"Memory text: {memory_text}")
                memory_storage_service.save_memory(memory_text)
                cache_manager.invalidate_memory_caches()
                result = "Memory saved."
                logger.info("Memory saved successfully")
                
            case "edit_memory":
                memory_id = arguments.get("memory_id", "")
                new_memory_text = arguments.get("new_memory_text", "")
                logger.info(f"Editing memory ID: {memory_id} with new text length: {len(new_memory_text)} characters")
                logger.debug(f"New memory text: {new_memory_text}")
                memory_storage_service.edit_memory(memory_id, new_memory_text)
                cache_manager.invalidate_memory_caches()
                result = f"Memory `{memory_id}` edited with new memory text."
                logger.info(f"Memory {memory_id} edited successfully")
                
            case "search_memories":
                terms = arguments.get("terms", [])
                logger.info(f"Searching memories for terms: {terms}")
                memories = memory_storage_service.search_memories(terms)
                logger.debug(f"Found {len(memories)} related memories")
                logger.info(f"Memories search completed for terms: {terms}")
                if memories:
                    result = ""
                    for memory_id, memory_text, image, created_at in memories:
                        result += f"\nMemory ID: {memory_id}\n"
                        result += f"Created: {created_at}\n"
                        result += f"Content: {memory_text}\n"
                        if image:
                            result += f"[Contains image]\n"
                        result += "-" * 40 + "\n"
                else:
                    logger.info(f"No memories found for terms: {terms}")
                    result = "No memories found, try different keywords."
                
            case "perform_research":
                terms = arguments.get("terms", [])
                logger.info(f"Searching Wikipedia for terms: {terms}")
                result = offline_wikipedia_service.fulltext_search(terms)
                memories = memory_storage_service.search_memories(terms)
                logger.debug(f"Found {len(memories)} related memories")
                
                if result:
                    logger.info(f"Wikipedia search returned {len(result)} characters of results")
                    result += f"""
                    
To unlock full topic details, use the `{get_full_topic_details_tool_name}(['topic_id'])` tool for up to 5 of the above topics.

If these matches aren't useful, simply attempt different keywords in a new `{perform_research_tool_name}` tool call.
"""
                else:
                    logger.info("Wikipedia search returned no results")
                    result = "No results found, try different keywords."
                
                logger.info(f"Wikipedia search completed for terms: {terms}")
            
            case "get_full_topic_details":
                topic_ids = arguments.get("topic_ids", [])
                logger.info(f"Getting full Wikipedia article details for topic IDs: {topic_ids}")
                result = offline_wikipedia_service.get_full_wikipedia_article(topic_ids)
                if result:
                    logger.info(f"Successfully retrieved full topic details for {len(topic_ids)} topics, {len(result)} characters")
                    result += f"""
                    
                    Retreived full topic details for [{topic_ids}]
"""
                else:
                    logger.warning(f"No topic details found for topic IDs: {topic_ids}")
                
            case "terminal_command":
                command = arguments.get("command", "")
                logger.info(f"Processing terminal command: {command}")
                
                forbidden_patterns = [
                    r'rm\s+-rf\s+[/~]',  # Prevent dangerous rm commands
                    r'>[>]?\s*[/~]',      # Prevent writing to root/home
                    r'\|\s*rm',           # Prevent piping to rm
                    r'sudo',              # Prevent sudo usage
                    r'chmod\s+[0-7]*7\b'  # Prevent adding execute permissions
                ]
                
                # Check for forbidden patterns
                for pattern in forbidden_patterns:
                    if re.search(pattern, command, re.IGNORECASE):
                        logger.error(f"Forbidden command pattern detected: {command}")
                        result = f"Error: Forbidden command pattern detected"
                        break
                else:
                    try:
                        logger.info(f"Executing terminal command: {command}")
                        if command.strip() and not command.strip()[0].isdigit():
                            # Use subprocess.run to capture output
                            process = subprocess.run(["/bin/bash", "-c", command], 
                                                capture_output=True, text=True, timeout=30)
                            
                            result = f"Command executed: {command}\n"
                            result += f"Exit code: {process.returncode}\n"
                            
                            if process.stdout:
                                truncated_stdout = _truncate_terminal_output(process.stdout)
                                result += f"Output:\n{truncated_stdout}\n"
                            
                            if process.stderr:
                                truncated_stderr = _truncate_terminal_output(process.stderr)
                                result += f"Error output:\n{truncated_stderr}\n"
                            
                            if not process.stdout and not process.stderr:
                                result += "Command completed with no output."
                        else:
                            logger.error(f"Invalid command format: {command}")
                            result = f"Error: Invalid command format"
                    except subprocess.TimeoutExpired:
                        logger.error(f"Command timed out: {command}")
                        result = f"Error: Command timed out after 30 seconds"
                    except Exception as e:
                        logger.error(f"Error executing command '{command}': {str(e)}")
                        result = f"Error executing command: {str(e)}"
        
        logger.info(f"Tool call ({tool_name}) result: {result}")
        return [tool_name, result]
                        
    except Exception as e:
        logger.error(f"Error processing tool call: {e}")
        return [tool_name, f"Tool call parsing error. Please check syntax: {str(e)}"]
