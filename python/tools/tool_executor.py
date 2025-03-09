
import shlex
import subprocess
import re
import json

# TODO Can models call multiple tools at once? 
def get_tool_call_results(response_text, logger, memory_storage_service, cache_manager):
    try:
        tool_call_section = response_text.split("<tool_call>")[1].split("</tool_call>")[0]
        tool_name = tool_call_section.split("\n")[0].strip()
        
        json_match = re.search(r'\{.*\}', tool_call_section, re.DOTALL)
        if json_match:
            tool_call_json = json.loads(json_match.group(0))
            print(tool_call_json)
            tool_name = tool_call_json.get("name", "")
            
            match tool_name:
                case "voice_response":
                    arguments = tool_call_json.get("arguments", {})
                    text_to_speak = arguments.get("text", "")
                    if text_to_speak:
                        logger.info(f"Invoking voice response with: {text_to_speak}")
                        subprocess.Popen(["say", text_to_speak])
                        
                case "save_memory":
                    arguments = tool_call_json.get("arguments", {})
                    memory_text = arguments.get("memory_text", "")
                    logger.info(f"Saving memory: {memory_text}")
                    memory_storage_service.save_memory(memory_text)
                    cache_manager.invalidate_memory_caches()
                    
                case "edit_memory":
                    arguments = tool_call_json.get("arguments", {})
                    memory_id = arguments.get("memory_id", "")
                    new_memory_text = arguments.get("new_memory_text", "")
                    logger.info(f"Editing memory: {memory_id} with new text: {new_memory_text}")
                    # memory_storage_service.edit_memory(memory_id, new_memory_text) # Too scared to actually use without diff/approve
                    # cache_manager.invalidate_memory_caches()
                    
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
                            return
                        
                    try:
                        logger.info(f"Executing terminal command: {command}")
                        escaped_command = shlex.quote(command)
                        logger.info(f"Executing terminal command: {escaped_command}")
                        subprocess.Popen(["/bin/bash", "-c", command])
                    except Exception as e:
                        logger.error(f"Error executing command: {e}")
                        
    except Exception as e:
        logger.error(f"Error processing tool call: {e}")