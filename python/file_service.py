import os
import re
import fnmatch
from pathlib import Path
from typing import Literal

EXCLUDE_DIRS = {
    ".git", "node_modules", "data", ".next", "__pycache__",
    "venv", ".venv", "env", "dist", "build", "target", "bin", "obj",
    ".idea", ".vscode", ".cursor", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", ".npm", ".cache", "__pypackages__", "node_modules",
    "site-packages", "venv", "env", ".tox", ".nox", ".egg-info"
}

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
                    # Return lines in the format "LINE_NUMBER|LINE_CONTENT"
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
                # Filter directories in-place to skip excluded ones
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')]
                dirs.sort()
                files.sort()
                
                # Get the relative path from the base_path
                try:
                    rel_root = os.path.relpath(root, base_path)
                except ValueError:
                    # Handle cases where path might be on different drive on Windows, though less likely here
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
            # Non-recursive listing
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

    # If file_path is provided, we search only that file
    if file_path:
        target = Path(file_path)
        if not target.is_file():
            return f"Error: '{file_path}' is not a valid file or does not exist."
        all_files = [target]
    else:
        # We will use os.walk but process files as we go
        all_files = None # Indicator to use os.walk

    if all_files:
        files_to_process = all_files
    else:
        # Generator for files to avoid loading all into memory
        def file_generator():
            nonlocal limit_reached, files_searched
            for root, dirs, files_in_dir in os.walk(current_dir):
                if limit_reached:
                    return
                dirs.sort()
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith('.')] # noqa
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
            # We already have enough matches for the current page
            # But we might need to continue to count total matches if we wanted accurate pagination
            # For performance, we'll stop early if we have enough results.
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
                                # Show context for the first match only
                                match = matches[0]
                                lines = content.splitlines()
                                line_num = content[:match.start()].count('\n') + 1
                                start_idx = max(0, line_num - 3)  # 2 lines before
                                end_idx = min(len(lines), line_num + 2) # 2 lines after
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
                        # In content mode or files mode (with context), we read lines
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
                                            # Context: 2 lines before, 2 lines after
                                            start_idx = max(0, i - 2)
                                            end_idx = min(len(lines), i + 3)
                                            context = []
                                            for j in range(start_idx, end_idx):
                                                prefix = ">>> " if j == i else "    "
                                                context.append(f"{prefix}{j+1:6d}|{lines[j].rstrip()}")
                                            results.append(f"\n{p}:\n" + "\n".join(context) + "\n")
                                        
                                        # For files mode, we stop after the first match
                                        # But we need to account for matches count?
                                        # Usually files mode implies we don't care about total matches count, 
                                        # but existing logic tried to track it.
                                        # However, for performance and standard behavior, stopping here is good.
                                        # We will count this as 1 match for total stats if we break early.
                                        total_matches_count += 1
                                        break
                                
                                # Content mode logic continues here if not broken above
                                total_matches_count += 1
                                if range_start < total_matches_count <= range_end:
                                    if len(results) < max_matches:
                                        # Context: 3 lines before, 3 lines after (standard content mode)
                                        start_idx = max(0, i - 3)
                                        end_idx = min(len(lines), i + 3)
                                        context = []
                                        for j in range(start_idx, end_idx):
                                            prefix = ">>> " if j == i else "    "
                                            context.append(f"{prefix}{j+1:6d}|{lines[j].rstrip()}")
                                        results.append(f"\n{p}:\n" + "\n".join(context) + "\n")
                    else:
                        # Count mode: just iterate lines for speed
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
    # We don't need file summary if output_mode is files because the main results ARE the files
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