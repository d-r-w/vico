import subprocess
import re
import json
import logging
from typing import Any, Dict, Tuple

from offline_wikipedia_service import offline_wikipedia_service
from tools.tool_definitions import get_full_topic_details_tool_name, perform_research_tool_name

# Set up logging for this module
logger = logging.getLogger(__name__)

MAX_TERMINAL_OUTPUT_LENGTH = 8000


def parse_tool_call(response_text: str) -> Tuple[str, Dict[str, Any]]:
    try:
        section = response_text.split("<tool_call>")[1].split("</tool_call>")[0]
    except Exception:
        return "", {}

    lines = [line for line in section.strip().split("\n")]
    tool_name = lines[0].strip() if lines else ""
    arguments: Dict[str, Any] = {}

    try:
        if tool_name.startswith("{") and tool_name.endswith("}"):
            payload = json.loads(tool_name)
            name = payload.get("name")
            if isinstance(name, str):
                tool_name = name
            json_arguments = payload.get("arguments")
            if isinstance(json_arguments, dict):
                arguments.update(json_arguments)
    except Exception:
        pass

    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("<arg_key>") and line.endswith("</arg_key>"):
            key = line[9:-10]
            i += 1
            if i < len(lines) and lines[i].strip().startswith("<arg_value>"):
                current = lines[i].strip()
                if current.endswith("</arg_value>"):
                    value = current[11:-12]
                else:
                    value_lines = []
                    first_line = current[11:]
                    if first_line:
                        value_lines.append(first_line)
                    i += 1
                    while i < len(lines):
                        current = lines[i]
                        if current.strip().endswith("</arg_value>"):
                            last_line = current.rstrip()[:-12]
                            if last_line:
                                value_lines.append(last_line)
                            break
                        value_lines.append(current)
                        i += 1
                    value = "\n".join(value_lines)

                trimmed = value.strip()
                if (trimmed.startswith("[") and trimmed.endswith("]")) or (
                    trimmed.startswith("{") and trimmed.endswith("}")
                ):
                    try:
                        arguments[key] = json.loads(trimmed)
                    except Exception:
                        arguments[key] = value
                else:
                    arguments[key] = value
                i += 1
            else:
                i += 1
        else:
            i += 1

    if not arguments:
        json_match = re.search(r"\{.*\}", section, re.DOTALL)
        if json_match:
            try:
                payload = json.loads(json_match.group(0))
                name = payload.get("name")
                if isinstance(name, str):
                    tool_name = name
                json_arguments = payload.get("arguments")
                if isinstance(json_arguments, dict):
                    arguments = json_arguments
            except Exception:
                pass

    return tool_name, arguments

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
        parsed_name, arguments = parse_tool_call(response_text)
        if not parsed_name:
            raise ValueError("Tool name missing in <tool_call> block")

        tool_name = parsed_name
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
