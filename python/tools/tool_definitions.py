get_full_topic_details_tool_name = "get_full_topic_details"
perform_research_tool_name = "perform_research"
search_memories_tool_name = "search_memories"

def get_tool_definitions():
    return [
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "voice_response",
    #         "description": "Generate a voice response",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "text": {
    #                     "type": "string",
    #                     "description": "The text to generate a voice response for"
    #                 }
    #             },
    #             "required": ["text"]
    #         }
    #     }
    # },
        {
        "type": "function",
        "function": {
            "name": "terminal_command",
            "description": "Execute a terminal command in a macos zsh shell environment",
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
    },
    {
        "type": "function",
        "function": {
            "name": f"{search_memories_tool_name}",
            "description": "When recalling personal facts or details (or explicit memories), perform a fulltext search on memories using multiple variations of simple terms (examples: 'cats', 'cat care', 'cat diet', 'cat health', 'cat nutrition', 'cat training')",
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of SIMPLE search term variations, usually not exceeding three words per term (up to 5 terms)",
                        "maxItems": 5,
                        "minItems": 1
                    }
                },
                "required": ["terms"]
            },
            "returns": {
                "type": "string",
                "description": "Memories matching the provided search terms, including a `memory_id` for each memory that can be used to get the full memory details"
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": f"{perform_research_tool_name}",
            "description": "When uncertain about a fact/subject/topic, perform a fulltext search on deeper knowledge using multiple variations of simple terms (examples: 'cats', 'cat care', 'cat diet', 'cat health', 'cat nutrition', 'cat training')",
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of SIMPLE search term variations, usually not exceeding three words per term (up to 5 terms)",
                        "maxItems": 5,
                        "minItems": 1
                    }
                },
                "required": ["terms"]
            },
            "returns": {
                "type": "string",
                "description": "Topics matching the provided search terms, including a `topic_id` for each topic that can be used to get the full topic details"
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": f"{get_full_topic_details_tool_name}",
            "description": "Get full information about the list of specific topics",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Required list of `topic_id`s to get full information about",
                        "minItems": 0,
                        "maxItems": 5
                    },
                },
                "required": ["topic_ids"]
            }
        }
    }
]