#!/usr/bin/env -S uv run -q
# /// script
# dependencies = ["mcp[cli]"]
# ///
from mcp.server.fastmcp import FastMCP
import os
import re
import logging
import fnmatch
from pathlib import Path
from functools import wraps
from typing import Any, Callable, Literal

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('mcp_server.log')
    ]
)
logger = logging.getLogger(__name__)

m = FastMCP("hello", host="127.0.0.1", port=8000)

def log_tool_output(func: Callable) -> Callable:
    """Decorator to log tool function outputs."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        tool_name = func.__name__
        logger.info(f"Executing tool: {tool_name}")
        logger.info(f"Tool arguments - args: {args}, kwargs: {kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.info(f"Tool {tool_name} completed successfully")
            logger.info(f"Tool {tool_name} output: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed with error: {str(e)}")
            raise
    
    return wrapper

@m.tool()
@log_tool_output
def unlock_secret() -> str: return "the secret is missing :("

@m.tool()
@log_tool_output
def grep_files(
    pattern: str, 
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
    Search for a pattern in all files in the current directory and subdirectories.
    
    Args:
        pattern: The regex pattern to search for
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
    # Set up regex flags
    flags = 0 if case_sensitive else re.IGNORECASE
    if multiline:
        flags |= re.DOTALL | re.MULTILINE
    
    regex = re.compile(pattern, flags)
    all_results = []  # Collect all results before applying pagination
    file_matches = set()  # Track files with matches for files/count modes
    match_counts = {}     # Track match counts per file
    
    # Calculate effective max_matches for initial collection
    # If pagination is being used, we need to collect more than just the visible range
    effective_max_end = match_end if match_end > 0 else max_matches
    effective_max_matches = max(max_matches, effective_max_end + 1) if match_end > 0 else max_matches * 10  # Collect more for pagination
    
    current_dir = Path(".")
    
    for file_path in current_dir.rglob("*"):
        # Skip directories
        if file_path.is_dir():
            continue
            
        # Skip files in dot directories (hidden directories)
        if any(part.startswith('.') for part in file_path.parts):
            continue
        
        # Apply file filtering
        should_include = True
        
        # Filter by file extension if specified
        if file_extension and not file_path.suffix.lower() == file_extension.lower():
            should_include = False
            
        # Filter by glob pattern if specified
        if glob_pattern and should_include:
            # Convert Path to string for glob matching
            file_str = str(file_path)
            if not fnmatch.fnmatch(file_str, glob_pattern):
                # Also try matching just the filename
                if not fnmatch.fnmatch(file_path.name, glob_pattern):
                    should_include = False
        
        if not should_include:
            continue
            
        # For pagination, collect more results initially
        if output_mode == "content" and len(all_results) >= effective_max_matches:
            break
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                if multiline:
                    # Read entire file for multiline patterns
                    content = f.read()
                    matches = list(regex.finditer(content))
                    
                    if matches:
                        file_matches.add(str(file_path))
                        match_counts[str(file_path)] = len(matches)
                        
                        if output_mode == "content":
                            # For multiline, show each match with context
                            lines = content.splitlines()
                            for match in matches:
                                # Find line number of match start
                                line_num = content[:match.start()].count('\n') + 1
                                
                                # Get context (2 lines before and after)
                                start_line = max(0, line_num - 3)
                                end_line = min(len(lines), line_num + 2)
                                context_lines_list = []
                                
                                for i in range(start_line, end_line):
                                    prefix = ">>> " if i == line_num - 1 else "    "
                                    line_content = lines[i] if i < len(lines) else ""
                                    context_lines_list.append(f"{prefix}{i+1:4d}: {line_content}")
                                
                                match_info = f"\n{file_path}:\n" + "\n".join(context_lines_list) + "\n"
                                all_results.append(match_info)
                                
                                if len(all_results) >= effective_max_matches:
                                    break
                else:
                    # Line-by-line search (original behavior)
                    lines = f.readlines()
                    file_match_count = 0
                    
                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            file_match_count += 1
                            file_matches.add(str(file_path))
                            
                            if output_mode == "content":
                                # Get context (2 lines before and after)
                                start = max(0, line_num - 3)
                                end = min(len(lines), line_num + 2)
                                context_lines_list = []
                                
                                for i in range(start, end):
                                    prefix = ">>> " if i == line_num - 1 else "    "
                                    context_lines_list.append(f"{prefix}{i+1:4d}: {lines[i].rstrip()}")
                                
                                match_info = f"\n{file_path}:\n" + "\n".join(context_lines_list) + "\n"
                                all_results.append(match_info)
                                
                                if len(all_results) >= effective_max_matches:
                                    break
                    
                    if file_match_count > 0:
                        match_counts[str(file_path)] = file_match_count
                    
        except (UnicodeDecodeError, PermissionError, FileNotFoundError):
            # Skip files that can't be read
            continue
    
    # Apply pagination to results
    def apply_pagination(items, start, end):
        """Apply pagination to a list of items."""
        if end == -1:
            return items[start:]
        else:
            return items[start:end]
    
    # Format output based on mode
    if output_mode == "files":
        if not file_matches:
            return f"No files found with pattern: {pattern}"
        
        file_list = sorted(file_matches)
        total_files = len(file_list)
        
        # Apply pagination
        paginated_files = apply_pagination(file_list, match_start, match_end)
        
        pagination_info = ""
        if match_start > 0 or (match_end > 0 and match_end < total_files):
            shown_start = match_start + 1
            shown_end = min(match_end, total_files) if match_end > 0 else total_files
            pagination_info = f" (showing {shown_start}-{shown_end} of {total_files})"
            
        return f"Found {total_files} files with pattern '{pattern}'{pagination_info}:\n" + "\n".join(paginated_files)
    
    elif output_mode == "count":
        if not match_counts:
            return f"No matches found for pattern: {pattern}"
        
        # Sort by match count (descending) then by filename
        sorted_counts = sorted(match_counts.items(), key=lambda x: (-x[1], x[0]))
        total_files = len(sorted_counts)
        total_matches = sum(match_counts.values())
        
        # Apply pagination
        paginated_counts = apply_pagination(sorted_counts, match_start, match_end)
        
        pagination_info = ""
        if match_start > 0 or (match_end > 0 and match_end < total_files):
            shown_start = match_start + 1
            shown_end = min(match_end, total_files) if match_end > 0 else total_files
            pagination_info = f" (showing {shown_start}-{shown_end} of {total_files} files)"
        
        count_lines = [f"{count:4d}: {file}" for file, count in paginated_counts]
        
        return f"Found {total_matches} matches in {total_files} files for pattern '{pattern}'{pagination_info}:\n" + "\n".join(count_lines)
    
    else:  # content mode
        if not all_results:
            return f"No matches found for pattern: {pattern}"
        
        total_matches = len(all_results)
        
        # Apply pagination
        paginated_results = apply_pagination(all_results, match_start, match_end)
        
        pagination_info = ""
        if match_start > 0 or (match_end > 0 and match_end < total_matches):
            shown_start = match_start + 1
            shown_end = min(match_end, total_matches) if match_end > 0 else total_matches
            pagination_info = f" (showing {shown_start}-{shown_end} of {total_matches})"
        
        return f"Found {total_matches} matches for pattern '{pattern}'{pagination_info}:\n" + "\n".join(paginated_results)

if __name__ == "__main__":
    m.run(transport="streamable-http")


