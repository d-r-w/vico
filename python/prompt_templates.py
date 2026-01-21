from datetime import datetime
from typing import Optional

def get_current_date():
    return datetime.today().strftime('%Y-%m-%d')

def get_date_system_instructions():
    return f"The current date is {get_current_date()}. Your knowledge cutoff is prior to this, so events that happened after are not known to you. In this scenario, trust the user and use available tools to answer the query. Sources and information dated to {get_current_date()} are valid."

def build_system_instructions(*, tool_usage_prompt: str, extra_instructions: Optional[str] = None) -> str:
    base = [
        get_date_system_instructions(),
        "Please assist the user with their query.",
    ]

    if extra_instructions:
        base.extend(["", "SPECIAL INSTRUCTIONS:", extra_instructions])

    base.append("")
    base.append(tool_usage_prompt.strip())
    return "\n".join(base).strip()

def get_vico_chat_template(query: str, tool_usage_prompt: str, prepend_system_instructions: bool = True, extra_instructions: Optional[str] = None):
    if prepend_system_instructions:
        messages = [
            {"role": "system", "content": f"""
            {build_system_instructions(tool_usage_prompt=tool_usage_prompt, extra_instructions=extra_instructions)}
            """}
        ]
    else:
        messages = []

    messages.append({"role": "user", "content": query})
    
    return messages

def get_tool_call_results_message(tool_call_results):
    return {"role": "tool", "content": f"<tool_call_results>\n\t{tool_call_results}\n</tool_call_results>"}

def get_image_description_template(memory_text=None):
    """
    Generate messages for image description with optional context.
    
    Args:
        memory_text (str, optional): Additional context for the image
    
    Returns:
        list: A list of message objects for the chat template
    """
    base_prompt = "Describe the image in the fullest of detail, per your instructions. In your final answer, include the summary of your observations."
    context_block = f"\n\n<image_context>\n\t{memory_text}\n</image_context>\n\n" if memory_text else ""

    return [
        {"role": "system", "content": f"You are an expert at describing images in the fullest of detail, replacing vision for those who have lost it. Entire paragraphs explaining scenery, observations, annotations, and transcriptions are all desirable - longer descriptions are usually more helpful! The current date is {get_current_date()}."},
        {"role": "user", "content": f"{base_prompt}{context_block}"}
    ]

def get_format_text_template(text_data):
    messages = [
        {"role": "system", "content": "You are a helpful assistant that formats unformatted content while preserving the original content."},
        {"role": "user", "content": f"Please format the following text from a web search:\n\n{text_data}."}
    ]
    
    return messages
