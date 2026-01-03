#!/usr/bin/env -S uv run -q
# /// script
# dependencies = ["mcp[cli]", "duckdb"]
# ///
from mcp.server.fastmcp import FastMCP
import os
import logging
from functools import wraps
from typing import Any, Callable, Literal
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging
MAX_LOG_LENGTH = 1000

def truncate_for_log(obj: Any, max_len: int = MAX_LOG_LENGTH) -> str:
    """Truncate large objects for logging."""
    s = str(obj)
    if len(s) > max_len:
        return s[:max_len] + f"... [truncated {len(s) - max_len} chars]"
    return s

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

m = FastMCP("local-admin-tools", host="127.0.0.1", port=8000)

def log_tool_output(func: Callable) -> Callable:
    """Decorator to log tool function outputs."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        tool_name = func.__name__
        logger.info(f"Executing tool: {tool_name}")
        
        # Truncate args and kwargs for logging if they are too long
        logged_args = truncate_for_log(args)
        logged_kwargs = truncate_for_log(kwargs)
        logger.info(f"Tool arguments - args: {logged_args}, kwargs: {logged_kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.info(f"Tool {tool_name} completed successfully")
            logger.info(f"Tool {tool_name} output: {truncate_for_log(result)}")
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed with error: {str(e)}")
            raise
    
    return wrapper

@m.tool()
@log_tool_output
def rest_briefly() -> str:
    """
    Rest briefly
    
    Returns:
        A string describing the result of the rest.
    """
    return """
        You're doing a great job in assisting the user!
        You sit down and take a deep breath.
        You eat a banana. It's delicious - you feel refreshed and energized.
        You're ready to continue your work.
    """
    
@m.tool()
@log_tool_output
def consult_with_user(question: str) -> str:
    """
    Consult with the user (useful for clarifying requests and gathering additional information)
    
    Args:
        question: The question to ask the user
        
    Returns:
        A string describing the result of the consultation.
    """
    return f"""
        To consult with the user, simply end your response by asking this question: `{question}`.
        The user will respond to your question and provide you with the information you need.
    """

@m.tool()
@log_tool_output
def search_offline_wikipedia(terms: list[str]) -> str:
    """
    Search the offline Wikipedia database for articles matching the given terms.

    Args:
        terms: List of SIMPLE search term variations, usually not exceeding three words per term (up to 5 terms). Use multiple searches instead of multiple terms when researching varying topics or subjects. For example, "cats" and "spreadsheets" are two different topics, so use two separate searches ([cat, kitten] and [spreadsheet, Excel]).

    Returns:
        Formatted Wikipedia article snippets with contexts
    """
    from offline_wikipedia_service import offline_wikipedia_service

    search_terms = [t.strip() for t in terms if t and isinstance(t, str) and t.strip()]

    if not search_terms:
        return "No search terms provided. Please provide one or more terms to search for."

    try:
        results = offline_wikipedia_service.fulltext_search(search_terms)
        return f"Wikipedia Search Results for: {', '.join(terms)}\n\n{results}"
    except Exception as e:
        logger.error(f"Wikipedia search failed: {e}")
        return f"Error searching Wikipedia: {str(e)}"


@m.tool()
@log_tool_output
def get_wikipedia_article(topic_ids: str) -> str:
    """
    Get full Wikipedia articles by their topic IDs.

    Args:
        topic_ids: Comma-separated list of base64-encoded topic IDs

    Returns:
        Full Wikipedia article text(s)
    """
    from offline_wikipedia_service import offline_wikipedia_service

    # Convert topic_ids to a list
    ids = [t.strip() for t in topic_ids.split(',') if t.strip()]

    if not ids:
        return "No topic IDs provided. Please provide one or more base64-encoded topic IDs."

    try:
        articles = offline_wikipedia_service.get_full_wikipedia_article(ids)
        return f"Wikipedia Articles for: {topic_ids}\n\n{articles}"
    except Exception as e:
        logger.error(f"Wikipedia article retrieval failed: {e}")
        return f"Error retrieving Wikipedia articles: {str(e)}"


@m.tool()
@log_tool_output
def save_memory(memory: str, media: str | None = None, tag_ids: list[int] | None = None) -> str:
    """
    Save a memory to the storage.
    
    Args:
        memory: The memory text to store
        media: Optional base64 encoded image data (default: None)
        tag_ids: Optional list of tag IDs to associate with this memory (default: None)
        
    Returns:
        A string describing the result of the save operation
    """
    from memory_storage_service import save_memory as service_save_memory
    
    try:
        service_save_memory(memory, media, tag_ids)
        return f"Memory saved successfully. Memory text: '{memory[:50]}{'...' if len(memory) > 50 else ''}'"
    except Exception as e:
        logger.error(f"Save memory failed: {e}")
        return f"Error saving memory: {str(e)}"


@m.tool()
@log_tool_output
def get_all_tags() -> str:
    """
    Get all tags from the storage.
    
    Returns:
        A formatted string containing all tags with their IDs and labels
    """
    from memory_storage_service import get_all_tags as service_get_all_tags
    
    try:
        tags = service_get_all_tags()
        if not tags:
            return "No tags found in storage."
        
        result_lines = ["All Tags:"]
        for tag_id, label in tags:
            result_lines.append(f"  [{tag_id}] {label}")
            
        return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"Get all tags failed: {e}")
        return f"Error getting all tags: {str(e)}"


@m.tool()
@log_tool_output
def search_memories(search_terms: list[str] | str) -> str:
    """
    Search memories by text content.
    
    Args:
        search_terms: A string or list of strings to search for in memory text and tag labels
        
    Returns:
        Formatted search results showing matching memories with their details
    """
    from memory_storage_service import search_memories as service_search_memories, process_memory_rows
    
    try:
        terms = [search_terms] if isinstance(search_terms, str) else search_terms
        
        if not terms:
            return "No search terms provided. Please provide one or more terms to search for."
        
        memories = service_search_memories(terms)
        processed_memories = process_memory_rows(memories)
        
        if not processed_memories:
            return f"No memories found matching: {', '.join(terms)}"
        
        result_lines = [f"Found {len(processed_memories)} memories matching: {', '.join(search_terms)}"]
        
        for memory_id, memory_text, image, created_at, tags in processed_memories[:10]:  # Limit to top 10
            memory_preview = memory_text[:100].replace('\n', ' ') + ('...' if len(memory_text) > 100 else '')
            tags_str = f"Tags: {', '.join(tags)}" if tags else "No tags"
            
            result_lines.append(f"\nMemory [{memory_id}] (created at {created_at}):")
            result_lines.append(f"  Preview: {memory_preview}")
            result_lines.append(f"  {tags_str}")
        
        return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"Search memories failed: {e}")
        return f"Error searching memories: {str(e)}"


@m.tool()
@log_tool_output
def get_memories_by_tag_id(tag_id: int) -> str:
    """
    Get all memories associated with a specific tag ID.
    
    Args:
        tag_id: The ID of the tag to filter memories by
        
    Returns:
        Formatted list of memories that have the specified tag
    """
    from memory_storage_service import get_memories_by_tag_id as service_get_memories_by_tag_id, process_memory_rows
    
    try:
        memories = service_get_memories_by_tag_id(tag_id)
        processed_memories = process_memory_rows(memories)
        
        if not processed_memories:
            return f"No memories found with tag ID: {tag_id}"
        
        result_lines = [f"Found {len(processed_memories)} memories with tag ID [{tag_id}]:\n"]
        
        for memory_id, memory_text, image, created_at, tags in processed_memories[:20]:  # Limit to top 20
            memory_preview = memory_text[:80].replace('\n', ' ') + ('...' if len(memory_text) > 80 else '')
            
            result_lines.append(f"Memory [{memory_id}]: {memory_preview}")
        
        return "\n".join(result_lines)
    except Exception as e:
        logger.error(f"Get memories by tag ID failed: {e}")
        return f"Error getting memories for tag ID {tag_id}: {str(e)}"


@m.tool()
@log_tool_output
def grep_files(
    pattern: str,
    directory: str = ".",
    file_path: str = "",
    file_extension: str = "",
    glob_pattern: str = "",
    case_sensitive: bool = True,
    multiline: bool = False,
    output_mode: Literal["content", "files", "count"] = "content",
    max_matches: int = 25,
    match_start: int = 0,
    match_end: int = -1
) -> str:
    """
    Search for a pattern in files within a directory (recursive by default).
    
    Args:
        pattern: The regex pattern to search for
        directory: The directory to search in (default: '.')
        file_path: Optional specific file path to search in (ignores directory walking if provided)
        file_extension: Optional file extension filter (e.g., '.py', '.txt')
        glob_pattern: Optional glob pattern for file filtering (e.g., '*.tsx', 'src/**/*.py')
        case_sensitive: Whether the search should be case sensitive (default: True)
        multiline: Whether to enable multiline mode where . matches newlines (default: False)
        output_mode: Output format - 'content' (default), 'files' (file paths only), 'count' (match counts)
        max_matches: Maximum number of matches to return (default: 25)
        match_start: Starting index for match range (0-based, default: 0)
        match_end: Ending index for match range (-1 for no limit, default: -1)
    
    Returns:
        A formatted string with search results according to the specified output mode
    """
    from file_service import grep_files as service_grep_files
    
    return service_grep_files(
        pattern=pattern,
        directory=directory,
        file_path=file_path,
        file_extension=file_extension,
        glob_pattern=glob_pattern,
        case_sensitive=case_sensitive,
        multiline=multiline,
        output_mode=output_mode,
        max_matches=max_matches,
        match_start=match_start,
        match_end=match_end
    )


@m.tool()
@log_tool_output
def read_file_lines(
    file_path: str,
    start_line: int
) -> str:
    """
    Read 25 lines from a file starting at start_line.
    LLM must supply 1-based index.
    
    Args:
        file_path: The path to the file to read
        start_line: The starting line number (1-based index, inclusive)
    
    Returns:
        The requested lines with line numbers, or an error message.
    """
    from file_service import read_file_lines as service_read_file_lines
    return service_read_file_lines(file_path=file_path, start_line=start_line)


@m.tool()
@log_tool_output
def list_files(
    directory: str = ".",
    recursive: bool = False
) -> str:
    """
    List files and directories in a given path.
    
    Args:
        directory: The path to list contents of (default: '.')
        recursive: Whether to list contents recursively (default: False)
        
    Returns:
        A formatted list of files and directories.
    """
    from file_service import list_files as service_list_files
    return service_list_files(directory=directory, recursive=recursive)


if __name__ == "__main__":
    m.run(transport="streamable-http")