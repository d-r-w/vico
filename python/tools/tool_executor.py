import subprocess
import re
import json

from offline_wikipedia_service import offline_wikipedia_service
from tools.tool_definitions import get_full_topic_details_tool_name, search_deeper_knowledge_tool_name

def get_tool_call_results(response_text, logger, memory_storage_service=None, cache_manager=None):
    try:
        tool_call_section = response_text.split("<tool_call>")[1].split("</tool_call>")[0]
        tool_name = tool_call_section.split("\n")[0].strip()
        
        json_match = re.search(r'\{.*\}', tool_call_section, re.DOTALL)
        if json_match:
            tool_call_json = json.loads(json_match.group(0))
            print(tool_call_json)
            tool_name = tool_call_json.get("name", "")
            result = None
            
            match tool_name:
                case "voice_response":
                    arguments = tool_call_json.get("arguments", {})
                    text_to_speak = arguments.get("text", "")
                    if text_to_speak:
                        logger.info(f"Invoking voice response with: {text_to_speak}")
                        subprocess.Popen(["say", text_to_speak])
                        result = f"Voice response initiated with text: {text_to_speak}"
                        
                case "save_memory":
                    arguments = tool_call_json.get("arguments", {})
                    memory_text = arguments.get("memory_text", "")
                    logger.info(f"Saving memory: {memory_text}")
                    memory_storage_service.save_memory(memory_text)
                    cache_manager.invalidate_memory_caches()
                    result = f"Memory saved: {memory_text}"
                    
                case "edit_memory":
                    arguments = tool_call_json.get("arguments", {})
                    memory_id = arguments.get("memory_id", "")
                    new_memory_text = arguments.get("new_memory_text", "")
                    logger.info(f"Editing memory: {memory_id} with new text: {new_memory_text}")
                    memory_storage_service.edit_memory(memory_id, new_memory_text)
                    cache_manager.invalidate_memory_caches()
                    result = f"Memory {memory_id} edited with new text: {new_memory_text}"
                    
                case "search_deeper_knowledge":
                    arguments = tool_call_json.get("arguments", {})
                    terms = arguments.get("terms", [])
                    logger.info(f"Searching Wikipedia for terms: {terms}")
                    result = offline_wikipedia_service.fulltext_search(terms)
                    if result:
                        result += f"""
                        
To unlock full topic details, use the `{get_full_topic_details_tool_name}(['topic_id'])` tool for up to 5 of the above topics.

If these matches aren't useful, simply attempt different keywords in a new `{search_deeper_knowledge_tool_name}` tool call.
"""
                    else:
                        result = "No results found, try different keywords."
                    memories = memory_storage_service.search_memories(terms)
                    print(memories)
                    logger.info(f"Wikipedia search result: {result}")
                
                case "get_full_topic_details":
                    arguments = tool_call_json.get("arguments", {})
                    topic_ids = arguments.get("topic_ids", [])
                    logger.info(f"Getting Wikipedia article: {topic_ids}")
                    result = offline_wikipedia_service.get_full_wikipedia_article(topic_ids)
                    
                case "terminal_command":
                    arguments = tool_call_json.get("arguments", {})
                    command = arguments.get("command", "")
                    
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
                                subprocess.Popen(["/bin/bash", "-c", command])
                                result = f"Command executed: {command}"
                            else:
                                logger.error(f"Invalid command format: {command}")
                                result = f"Error: Invalid command format"
                        except Exception as e:
                            logger.error(f"Error executing command: {e}")
                            result = f"Error executing command: {str(e)}"
            
            logger.info(f"Tool call ({tool_name}) result: {result}")
            
            return [tool_name, result]
                        
    except Exception as e:
        logger.error(f"Error processing tool call: {e}")
        return [tool_name, f"JSON syntax error. Please adjust fix syntax: `{tool_call_section}`"]