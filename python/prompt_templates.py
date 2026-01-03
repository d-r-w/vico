from datetime import datetime

def get_current_date():
    return datetime.today().strftime('%Y-%m-%d')

def build_system_instructions(*, tool_usage_prompt: str) -> str:
    base = [
        f"The current date is {get_current_date()}.",
        "Please assist the user with their query.",
    ]

    base.append("")
    base.append(tool_usage_prompt.strip())
    return "\n".join(base).strip()

def get_vico_chat_template(context, query, is_deep=False, *, tool_usage_prompt: str):
    messages = [
        {"role": "system", "content": f"""
        {build_system_instructions(tool_usage_prompt=tool_usage_prompt)}
        """}
    ]

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
