from datetime import datetime
from tools.tool_definitions import search_deeper_knowledge_tool_name

def get_current_date():
    return datetime.today().strftime('%Y-%m-%d')

updated_instructions = f"""
The current date is {get_current_date()}.
Please assist the user with their query.
Use tool calls in succession until the task is complete.
You have the ability to iterate on your responses using tool calls to gain new information.
Do not fabricate memories or information - when uncertain about a fact/subject/topic, use the <{search_deeper_knowledge_tool_name}> tool.
Favor long, detailed responses and numerous tool calls/attempts when appropriate.
"""

def get_vico_chat_template(context, query, is_deep=False):
    messages = [
        {"role": "system", "content": f"""
        {updated_instructions}
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

def get_summarize_x_posts_template(text_data, example_block=None):
    example_block = example_block or """
    DESIRED OUTPUT
    ### 1. Artemis Moon Mission Clears Milestone
    *Summary:* NASA’s Artemis rocket launched successfully, advancing plans for a lunar gateway.  
    *Supporting Tweets:* 111 (@space_agency); 112 (@astro_fan)  

    ### 2. Bitcoin Hits New All-Time High
    *Summary:* Bitcoin price surpassed \$120 000, prompting celebration across crypto-Twitter.  
    *Supporting Tweets:* 113 (@markets)
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an investigative journalist specializing in social-media analysis.\n"
                "TASK:\n"
                "1. **Silently read and cluster** the X.com posts by topic (do NOT output this thinking).\n"
                "2. Output significant stories in order of importance.\n"
                "   - For each story give:\n"
                "     • A 5-8 word headline (Title Case).\n"
                "     • A 1-2 sentence factual summary.\n"
                "     • A list of tweet IDs and handles that support the story, merged if they are near-duplicates or simple reposts.\n"
                "3. Cite only facts that appear verbatim in the tweets. No speculation.\n"
                "4. Format exactly in markdown using the template shown below."
            )
        },
        {
            "role": "assistant",
            "content": example_block.strip()
        },
        {
            "role": "user",
            "content": (
                "POSTS TO ANALYZE:\n"
                f"{text_data}\n"
            )
        }
    ]
    return messages