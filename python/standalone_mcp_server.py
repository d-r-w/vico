#!/usr/bin/env -S uv run -q
# /// script
# dependencies = ["mcp[cli]", "duckdb"]
# ///
from mcp.server.fastmcp import FastMCP
import os
import logging
import re
import fnmatch
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Set up logging
MAX_LOG_LENGTH = 1000
EXCLUDE_DIRS = {
    ".git", "node_modules", "data", ".next", "__pycache__",
    "venv", ".venv", "env", "dist", "build", "target", "bin", "obj",
    ".idea", ".vscode", ".cursor", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".npm", ".cache", "__pypackages__", "node_modules",
    "site-packages", "venv", "env", ".tox", ".nox", ".egg-info"
}

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
    flags = 0 if case_sensitive else re.IGNORECASE
    if multiline:
        flags |= re.DOTALL | re.MULTILINE

    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        return f"Error: Invalid regex pattern: {str(e)}"

    current_dir = Path(directory)
    if not current_dir.is_dir():
        return f"Error: '{directory}' is not a directory or does not exist."

    results = []
    matching_files_list = []
    total_matches_count = 0
    total_files_with_matches = 0
    files_searched = 0

    range_start = match_start
    range_end = match_end if match_end > 0 else match_start + max_matches

    limit_reached = False
    max_files_limit = 50000

    if file_path:
        target = Path(file_path)
        if not target.is_file():
            return f"Error: '{file_path}' is not a valid file or does not exist."
        all_files = [target]
    else:
        all_files = None

    if all_files:
        files_to_process = all_files
    else:
        def file_generator():
            nonlocal limit_reached, files_searched
            for root, dirs, files_in_dir in os.walk(current_dir):
                if limit_reached:
                    return
                dirs.sort()
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
                files_in_dir.sort()
                for f_name in files_in_dir:
                    files_searched += 1
                    if files_searched > max_files_limit:
                        limit_reached = True
                        return
                    yield Path(root) / f_name
        files_to_process = file_generator()

    for p in files_to_process:
        if len(results) >= max_matches:
            limit_reached = True
            break

        if file_extension and p.suffix.lower() != file_extension.lower():
            continue
        if glob_pattern:
            if not fnmatch.fnmatch(str(p), glob_pattern) and not fnmatch.fnmatch(p.name, glob_pattern):
                continue

        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                if multiline:
                    content = f.read()
                    matches = list(regex.finditer(content))
                    if matches:
                        total_files_with_matches += 1
                        if len(matching_files_list) < 10:
                            matching_files_list.append(str(p))

                        file_match_count = len(matches)

                        if output_mode == "files":
                            if range_start < total_files_with_matches <= range_end:
                                match = matches[0]
                                lines = content.splitlines()
                                line_num = content[:match.start()].count('\n') + 1
                                start_idx = max(0, line_num - 3)
                                end_idx = min(len(lines), line_num + 2)
                                context = []
                                for i in range(start_idx, end_idx):
                                    prefix = ">>> " if i == line_num - 1 else "    "
                                    context.append(f"{prefix}{i+1:6d}|{lines[i]}")
                                results.append(f"\n{p}:\n" + "\n".join(context) + "\n")

                        elif output_mode == "count":
                            if range_start < total_files_with_matches <= range_end:
                                results.append(f"{file_match_count:4d}: {p}")
                        elif output_mode == "content":
                            lines = content.splitlines()
                            for match in matches:
                                total_matches_count += 1
                                if range_start < total_matches_count <= range_end:
                                    if len(results) < max_matches:
                                        line_num = content[:match.start()].count('\n') + 1
                                        start_idx = max(0, line_num - 4)
                                        end_idx = min(len(lines), line_num + 3)
                                        context = []
                                        for i in range(start_idx, end_idx):
                                            prefix = ">>> " if i == line_num - 1 else "    "
                                            context.append(f"{prefix}{i+1:6d}|{lines[i]}")
                                        results.append(f"\n{p}:\n" + "\n".join(context) + "\n")

                        if output_mode != "content":
                            total_matches_count += file_match_count
                else:
                    file_has_match = False
                    if output_mode in ["content", "files"]:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if regex.search(line):
                                if not file_has_match:
                                    file_has_match = True
                                    total_files_with_matches += 1
                                    if len(matching_files_list) < 10:
                                        matching_files_list.append(str(p))

                                    if output_mode == "files":
                                        if range_start < total_files_with_matches <= range_end:
                                            start_idx = max(0, i - 2)
                                            end_idx = min(len(lines), i + 3)
                                            context = []
                                            for j in range(start_idx, end_idx):
                                                prefix = ">>> " if j == i else "    "
                                                context.append(f"{prefix}{j+1:6d}|{lines[j].rstrip()}")
                                            results.append(f"\n{p}:\n" + "\n".join(context) + "\n")

                                        total_matches_count += 1
                                        break

                                total_matches_count += 1
                                if range_start < total_matches_count <= range_end:
                                    if len(results) < max_matches:
                                        start_idx = max(0, i - 3)
                                        end_idx = min(len(lines), i + 3)
                                        context = []
                                        for j in range(start_idx, end_idx):
                                            prefix = ">>> " if j == i else "    "
                                            context.append(f"{prefix}{j+1:6d}|{lines[j].rstrip()}")
                                        results.append(f"\n{p}:\n" + "\n".join(context) + "\n")
                    else:
                        match_count = 0
                        for line in f:
                            if regex.search(line):
                                match_count += 1
                        if match_count > 0:
                            total_files_with_matches += 1
                            if len(matching_files_list) < 10:
                                matching_files_list.append(str(p))
                            total_matches_count += match_count
                            if output_mode == "count":
                                if range_start < total_files_with_matches <= range_end:
                                    results.append(f"{match_count:4d}: {p}")
        except Exception:
            continue

    if not results:
        return f"No matches found for pattern: {pattern} (searched {files_searched} files)"

    total = total_matches_count if output_mode == "content" else total_files_with_matches
    unit = "matches" if output_mode == "content" else "files"
    plus = "+" if limit_reached else ""

    shown_start = match_start + 1
    shown_end = match_start + len(results)

    pagination_info = f" (showing {shown_start}-{shown_end} of {total}{plus} {unit})"

    file_summary = ""
    if matching_files_list and output_mode not in ["files", "count"]:
        file_summary = "Matching files:\n" + "\n".join(f"- {f}" for f in matching_files_list)
        if total_files_with_matches > 10:
            file_summary += f"\n(and {total_files_with_matches - 10}{plus} more..)"
        file_summary += "\n\n"

    if output_mode == "files":
        header = f"Found {total}{plus} files with pattern '{pattern}' (showing first match from each for files {shown_start}-{shown_end} of {total}{plus}):\n"
    elif output_mode == "count":
        header = f"Found {total_matches_count}{plus} matches in {total_files_with_matches}{plus} files for pattern '{pattern}'{pagination_info}:\n"
    else:
        header = f"Found {total}{plus} matches for pattern '{pattern}'{pagination_info}:\n"

    return file_summary + header + "\n".join(results)


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
    path = Path(file_path)
    if not path.is_file():
        return f"Error: '{file_path}' is not a valid file or does not exist."

    end_line = start_line + 24

    try:
        results = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if i >= start_line and i <= end_line:
                    results.append(f"{i:6d}|{line.rstrip()}")
                if i > end_line:
                    break

        if not results:
            return f"No lines found starting at {start_line} for file '{file_path}'."

        actual_end_line = start_line + len(results) - 1
        output = f"Lines {start_line}-{actual_end_line} of {file_path}:\n" + "\n".join(results)
        output += "\n\nLLM Reminder: 'grep_files' tool for more targeted results."
        return output
    except Exception as e:
        return f"Error reading file '{file_path}': {str(e)}"


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
    base_path = Path(directory)
    if not base_path.exists():
        return f"Error: Path '{directory}' does not exist."
    if not base_path.is_dir():
        return f"Error: Path '{directory}' is not a directory."

    results = []
    try:
        if recursive:
            for root, dirs, files in os.walk(base_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
                dirs.sort()
                files.sort()

                try:
                    rel_root = os.path.relpath(root, base_path)
                except ValueError:
                    rel_root = root

                if rel_root == ".":
                    rel_root = ""

                for d in dirs:
                    path = os.path.join(rel_root, d) if rel_root else d
                    results.append(f"[DIR]  {path}")
                for f in files:
                    if f.startswith('.'):
                        continue
                    path = os.path.join(rel_root, f) if rel_root else f
                    results.append(f"[FILE] {path}")
        else:
            items = sorted(os.listdir(base_path))
            for item in items:
                if item.startswith('.') or item in EXCLUDE_DIRS:
                    continue
                p = base_path / item
                if p.is_dir():
                    results.append(f"[DIR]  {item}")
                else:
                    results.append(f"[FILE] {item}")

        if not results:
            return f"Directory '{directory}' is empty (or contains only excluded items)."

        return f"Contents of '{directory}'{' (recursive)' if recursive else ''}:\n" + "\n".join(results)
    except Exception as e:
        return f"Error listing directory '{directory}': {str(e)}"


if __name__ == "__main__":
    m.run(transport="streamable-http")