def get_tool_definitions():
  return [
      {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and country, eg. San Francisco, USA"
                    },
                    "format": { "type": "string", "enum": ["celsius", "fahrenheit"] }
                },
                "required": ["location", "format"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "voice_response",
            "description": "Generate a voice response",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to generate a voice response for"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminal_command",
            "description": "Execute a terminal command in the macos environment",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_memory",
            "description": "Edit a memory",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "description": "The id of the memory to edit"},
                    "new_memory_text": {"type": "string", "description": "The fully adjustednew text for the memory"}
                },
                "required": ["memory_id", "new_memory_text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save a new memory to Vico",
            "parameters": {
                "type": "object",
                "properties": {"memory_text": {"type": "string", "description": "The text to save as a memory"}},
                "required": ["memory_text"]
            }
        }
    }
]