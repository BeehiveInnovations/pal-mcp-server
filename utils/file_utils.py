"""
File reading utilities with directory support and token management

This module provides secure file access functionality for the MCP server.
It implements critical security measures to prevent unauthorized file access
and manages token limits to ensure efficient API usage.

Key Features:
- Path validation and sandboxing to prevent directory traversal attacks
- Support for both individual files and recursive directory reading
- Token counting and management to stay within API limits
- Automatic file type detection and filtering
- Comprehensive error handling with informative messages

Security Model:
- All file access is restricted to PROJECT_ROOT and its subdirectories
- Absolute paths are required to prevent ambiguity
- Symbolic links are resolved to ensure they stay within bounds

CONVERSATION MEMORY INTEGRATION:
This module works with the conversation memory system to support efficient
multi-turn file handling:

1. DEDUPLICATION SUPPORT:
   - File reading functions are called by conversation-aware tools
   - Supports newest-first file prioritization by providing accurate token estimation
   - Enables efficient file content caching and token budget management

2. TOKEN BUDGET OPTIMIZATION:
   - Provides accurate token estimation for file content before reading
   - Supports the dual prioritization strategy by enabling precise budget calculations
   - Enables tools to make informed decisions about which files to include

3. CROSS-TOOL FILE PERSISTENCE:
   - File reading results are used across different tools in conversation chains
   - Consistent file access patterns support conversation continuation scenarios
   - Error handling preserves conversation flow when files become unavailable
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from .file_types import BINARY_EXTENSIONS, CODE_EXTENSIONS, IMAGE_EXTENSIONS, TEXT_EXTENSIONS
from .security_config import EXCLUDED_DIRS, is_dangerous_path
from .token_utils import DEFAULT_CONTEXT_WINDOW, estimate_tokens


def _is_builtin_custom_models_config(path_str: str) -> bool:
    """
    Check if path points to the server's built-in custom_models.json config file.

    This only matches the server's internal config, not user-specified CUSTOM_MODELS_CONFIG_PATH.
    We identify the built-in config by checking if it resolves to the server's conf directory.

    Args:
        path_str: Path to check

    Returns:
        True if this is the server's built-in custom_models.json config file
    """
    try:
        path = Path(path_str)

        # Get the server root by going up from this file: utils/file_utils.py -> server_root
        server_root = Path(__file__).parent.parent
        builtin_config = server_root / "conf" / "custom_models.json"

        # Check if the path resolves to the same file as our built-in config
        # This handles both relative and absolute paths to the same file
        return path.resolve() == builtin_config.resolve()

    except Exception:
        # If path resolution fails, it's not our built-in config
        return False


logger = logging.getLogger(__name__)


def is_mcp_directory(path: Path) -> bool:
    """
    Check if a directory is the MCP server's own directory.

    This prevents the MCP from including its own code when scanning projects
    where the MCP has been cloned as a subdirectory.

    Args:
        path: Directory path to check

    Returns:
        True if this is the MCP server directory or a subdirectory
    """
    if not path.is_dir():
        return False

    # Get the directory where the MCP server is running from
    # __file__ is utils/file_utils.py, so parent.parent is the MCP root
    mcp_server_dir = Path(__file__).parent.parent.resolve()

    # Check if the given path is the MCP server directory or a subdirectory
    try:
        path.resolve().relative_to(mcp_server_dir)
        logger.info(f"Detected MCP server directory at {path}, will exclude from scanning")
        return True
    except ValueError:
        # Not a subdirectory of MCP server
        return False


def get_user_home_directory() -> Optional[Path]:
    """
    Get the user's home directory.

    Returns:
        User's home directory path
    """
    return Path.home()


def is_home_directory_root(path: Path) -> bool:
    """
    Check if the given path is the user's home directory root.

    This prevents scanning the entire home directory which could include
    sensitive data and non-project files.

    Args:
        path: Directory path to check

    Returns:
        True if this is the home directory root
    """
    user_home = get_user_home_directory()
    if not user_home:
        return False

    try:
        resolved_path = path.resolve()
        resolved_home = user_home.resolve()

        # Check if this is exactly the home directory
        if resolved_path == resolved_home:
            logger.warning(
                f"Attempted to scan user home directory root: {path}. Please specify a subdirectory instead."
            )
            return True

        # Also check common home directory patterns
        path_str = str(resolved_path).lower()
        home_patterns = [
            "/users/",  # macOS
            "/home/",  # Linux
            "c:\\users\\",  # Windows
            "c:/users/",  # Windows with forward slashes
        ]

        for pattern in home_patterns:
            if pattern in path_str:
                # Extract the user directory path
                # e.g., /Users/fahad or /home/username
                parts = path_str.split(pattern)
                if len(parts) > 1:
                    # Get the part after the pattern
                    after_pattern = parts[1]
                    # Check if we're at the user's root (no subdirectories)
                    if "/" not in after_pattern and "\\" not in after_pattern:
                        logger.warning(
                            f"Attempted to scan user home directory root: {path}. "
                            f"Please specify a subdirectory instead."
                        )
                        return True

    except Exception as e:
        logger.debug(f"Error checking if path is home directory: {e}")

    return False


def detect_file_type(file_path: str) -> str:
    """
    Detect file type for appropriate processing strategy.

    This function is intended for specific file type handling (e.g., image processing,
    binary file analysis, or enhanced file filtering).

    Args:
        file_path: Path to the file to analyze

    Returns:
        str: "text", "binary", or "image"
    """
    path = Path(file_path)

    # Check extension first (fast)
    extension = path.suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return "text"
    elif extension in IMAGE_EXTENSIONS:
        return "image"
    elif extension in BINARY_EXTENSIONS:
        return "binary"

    # Fallback: check magic bytes for text vs binary
    # This is helpful for files without extensions or unknown extensions
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
            # Simple heuristic: if we can decode as UTF-8, likely text
            chunk.decode("utf-8")
            return "text"
    except UnicodeDecodeError:
        return "binary"
    except (FileNotFoundError, PermissionError) as e:
        logger.warning(f"Could not access file {file_path} for type detection: {e}")
        return "unknown"


def should_add_line_numbers(file_path: str, include_line_numbers: Optional[bool] = None) -> bool:
    """
    Determine if line numbers should be added to a file.

    Args:
        file_path: Path to the file
        include_line_numbers: Explicit preference, or None for auto-detection

    Returns:
        bool: True if line numbers should be added
    """
    if include_line_numbers is not None:
        return include_line_numbers

    # Default: DO NOT add line numbers
    # Tools that want line numbers must explicitly request them
    return False


def _normalize_line_endings(content: str) -> str:
    """
    Normalize line endings for consistent line numbering.

    Args:
        content: File content with potentially mixed line endings

    Returns:
        str: Content with normalized LF line endings
    """
    # Normalize all line endings to LF for consistent counting
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _add_line_numbers(content: str) -> str:
    """
    Add line numbers to text content for precise referencing.

    Args:
        content: Text content to number

    Returns:
        str: Content with line numbers in format "  45│ actual code line"
        Supports files up to 99,999 lines with dynamic width allocation
    """
    # Normalize line endings first
    normalized_content = _normalize_line_endings(content)
    lines = normalized_content.split("\n")

    # Dynamic width allocation based on total line count
    # This supports files of any size by computing required width
    total_lines = len(lines)
    width = len(str(total_lines))
    width = max(width, 4)  # Minimum padding for readability

    # Format with dynamic width and clear separator
    numbered_lines = [f"{i + 1:{width}d}│ {line}" for i, line in enumerate(lines)]

    return "\n".join(numbered_lines)


def resolve_and_validate_path(path_str: str) -> Path:
    """
    Resolves and validates a path against security policies.

    This function ensures safe file access by:
    1. Requiring absolute paths (no ambiguity)
    2. Resolving symlinks to prevent deception
    3. Blocking access to dangerous system directories

    Args:
        path_str: Path string (must be absolute)

    Returns:
        Resolved Path object that is safe to access

    Raises:
        ValueError: If path is not absolute or otherwise invalid
        PermissionError: If path is in a dangerous location
    """
    # Step 1: Create a Path object
    user_path = Path(path_str)

    # Step 2: Security Policy - Require absolute paths
    # Relative paths could be interpreted differently depending on working directory
    if not user_path.is_absolute():
        raise ValueError(f"Relative paths are not supported. Please provide an absolute path.\nReceived: {path_str}")

    # Step 3: Resolve the absolute path (follows symlinks, removes .. and .)
    # This is critical for security as it reveals the true destination of symlinks
    resolved_path = user_path.resolve()

    # Step 4: Check against dangerous paths
    if is_dangerous_path(resolved_path):
        logger.warning(f"Access denied - dangerous path: {resolved_path}")
        raise PermissionError(f"Access to system directory denied: {path_str}")

    # Step 5: Check if it's the home directory root
    if is_home_directory_root(resolved_path):
        raise PermissionError(
            f"Cannot scan entire home directory: {path_str}\n" f"Please specify a subdirectory within your home folder."
        )

    return resolved_path


def expand_paths(paths: list[str], extensions: Optional[set[str]] = None) -> list[str]:
    """
    Expand paths to individual files, handling both files and directories.

    This function recursively walks directories to find all matching files.
    It automatically filters out hidden files and common non-code directories
    like __pycache__ to avoid including generated or system files.

    Args:
        paths: List of file or directory paths (must be absolute)
        extensions: Optional set of file extensions to include (defaults to CODE_EXTENSIONS)

    Returns:
        List of individual file paths, sorted for consistent ordering
    """
    if extensions is None:
        extensions = CODE_EXTENSIONS

    expanded_files = []
    seen = set()

    for path in paths:
        try:
            # Validate each path for security before processing
            path_obj = resolve_and_validate_path(path)
        except (ValueError, PermissionError):
            # Skip invalid paths silently to allow partial success
            continue

        if not path_obj.exists():
            continue

        # Safety checks for directory scanning
        if path_obj.is_dir():
            # Check 1: Prevent scanning user's home directory root
            if is_home_directory_root(path_obj):
                logger.warning(f"Skipping home directory root: {path}. Please specify a project subdirectory instead.")
                continue

            # Check 2: Skip if this is the MCP's own directory
            if is_mcp_directory(path_obj):
                logger.info(
                    f"Skipping MCP server directory: {path}. The MCP server code is excluded from project scans."
                )
                continue

        if path_obj.is_file():
            # Add file directly
            if str(path_obj) not in seen:
                expanded_files.append(str(path_obj))
                seen.add(str(path_obj))

        elif path_obj.is_dir():
            # Walk directory recursively to find all files
            for root, dirs, files in os.walk(path_obj):
                # Filter directories in-place to skip hidden and excluded directories
                # This prevents descending into .git, .venv, __pycache__, node_modules, etc.
                original_dirs = dirs[:]
                dirs[:] = []
                for d in original_dirs:
                    # Skip hidden directories
                    if d.startswith("."):
                        continue
                    # Skip excluded directories
                    if d in EXCLUDED_DIRS:
                        continue
                    # Skip MCP directories found during traversal
                    dir_path = Path(root) / d
                    if is_mcp_directory(dir_path):
                        logger.debug(f"Skipping MCP directory during traversal: {dir_path}")
                        continue
                    dirs.append(d)

                for file in files:
                    # Skip hidden files (e.g., .DS_Store, .gitignore)
                    if file.startswith("."):
                        continue

                    file_path = Path(root) / file

                    # Filter by extension if specified
                    if not extensions or file_path.suffix.lower() in extensions:
                        full_path = str(file_path)
                        # Use set to prevent duplicates
                        if full_path not in seen:
                            expanded_files.append(full_path)
                            seen.add(full_path)

    # Sort for consistent ordering across different runs
    # This makes output predictable and easier to debug
    expanded_files.sort()
    return expanded_files


def read_file_content(
    file_path: str, max_size: int = 1_000_000, *, include_line_numbers: Optional[bool] = None
) -> tuple[str, int]:
    """
    Read a single file and format it for inclusion in AI prompts.

    This function handles various error conditions gracefully and always
    returns formatted content, even for errors. This ensures the AI model
    gets context about what files were attempted but couldn't be read.

    Args:
        file_path: Path to file (must be absolute)
        max_size: Maximum file size to read (default 1MB to prevent memory issues)
        include_line_numbers: Whether to add line numbers. If None, auto-detects based on file type

    Returns:
        Tuple of (formatted_content, estimated_tokens)
        Content is wrapped with clear delimiters for AI parsing
    """
    logger.debug(f"[FILES] read_file_content called for: {file_path}")
    try:
        # Validate path security before any file operations
        path = resolve_and_validate_path(file_path)
        logger.debug(f"[FILES] Path validated and resolved: {path}")
    except (ValueError, PermissionError) as e:
        # Return error in a format that provides context to the AI
        logger.debug(f"[FILES] Path validation failed for {file_path}: {type(e).__name__}: {e}")
        error_msg = str(e)
        content = f"\n--- ERROR ACCESSING FILE: {file_path} ---\nError: {error_msg}\n--- END FILE ---\n"
        tokens = estimate_tokens(content)
        logger.debug(f"[FILES] Returning error content for {file_path}: {tokens} tokens")
        return content, tokens

    try:
        # Validate file existence and type
        if not path.exists():
            logger.debug(f"[FILES] File does not exist: {file_path}")
            content = f"\n--- FILE NOT FOUND: {file_path} ---\nError: File does not exist\n--- END FILE ---\n"
            return content, estimate_tokens(content)

        if not path.is_file():
            logger.debug(f"[FILES] Path is not a file: {file_path}")
            content = f"\n--- NOT A FILE: {file_path} ---\nError: Path is not a file\n--- END FILE ---\n"
            return content, estimate_tokens(content)

        # Check file size to prevent memory exhaustion
        file_size = path.stat().st_size
        logger.debug(f"[FILES] File size for {file_path}: {file_size:,} bytes")
        if file_size > max_size:
            logger.debug(f"[FILES] File too large: {file_path} ({file_size:,} > {max_size:,} bytes)")
            content = f"\n--- FILE TOO LARGE: {file_path} ---\nFile size: {file_size:,} bytes (max: {max_size:,})\n--- END FILE ---\n"
            return content, estimate_tokens(content)

        # Determine if we should add line numbers
        add_line_numbers = should_add_line_numbers(file_path, include_line_numbers)
        logger.debug(f"[FILES] Line numbers for {file_path}: {'enabled' if add_line_numbers else 'disabled'}")

        # Read the file with UTF-8 encoding, replacing invalid characters
        # This ensures we can handle files with mixed encodings
        logger.debug(f"[FILES] Reading file content for {file_path}")
        with open(path, encoding="utf-8", errors="replace") as f:
            file_content = f.read()

        logger.debug(f"[FILES] Successfully read {len(file_content)} characters from {file_path}")

        # Add line numbers if requested or auto-detected
        if add_line_numbers:
            file_content = _add_line_numbers(file_content)
            logger.debug(f"[FILES] Added line numbers to {file_path}")
        else:
            # Still normalize line endings for consistency
            file_content = _normalize_line_endings(file_content)

        # Format with clear delimiters that help the AI understand file boundaries
        # Using consistent markers makes it easier for the model to parse
        # NOTE: These markers ("--- BEGIN FILE: ... ---") are distinct from git diff markers
        # ("--- BEGIN DIFF: ... ---") to allow AI to distinguish between complete file content
        # vs. partial diff content when files appear in both sections
        formatted = f"\n--- BEGIN FILE: {file_path} ---\n{file_content}\n--- END FILE: {file_path} ---\n"
        tokens = estimate_tokens(formatted)
        logger.debug(f"[FILES] Formatted content for {file_path}: {len(formatted)} chars, {tokens} tokens")
        return formatted, tokens

    except Exception as e:
        logger.debug(f"[FILES] Exception reading file {file_path}: {type(e).__name__}: {e}")
        content = f"\n--- ERROR READING FILE: {file_path} ---\nError: {str(e)}\n--- END FILE ---\n"
        tokens = estimate_tokens(content)
        logger.debug(f"[FILES] Returning error content for {file_path}: {tokens} tokens")
        return content, tokens


def read_files(
    file_paths: list[str],
    code: Optional[str] = None,
    max_tokens: Optional[int] = None,
    reserve_tokens: int = 50_000,
    *,
    include_line_numbers: bool = False,
) -> str:
    """
    Read multiple files and optional direct code with smart token management.

    This function implements intelligent token budgeting to maximize the amount
    of relevant content that can be included in an AI prompt while staying
    within token limits. It prioritizes direct code and reads files until
    the token budget is exhausted.

    Args:
        file_paths: List of file or directory paths (absolute paths required)
        code: Optional direct code to include (prioritized over files)
        max_tokens: Maximum tokens to use (defaults to DEFAULT_CONTEXT_WINDOW)
        reserve_tokens: Tokens to reserve for prompt and response (default 50K)
        include_line_numbers: Whether to add line numbers to file content

    Returns:
        str: All file contents formatted for AI consumption
    """
    if max_tokens is None:
        max_tokens = DEFAULT_CONTEXT_WINDOW

    logger.debug(f"[FILES] read_files called with {len(file_paths)} paths")
    logger.debug(
        f"[FILES] Token budget: max={max_tokens:,}, reserve={reserve_tokens:,}, available={max_tokens - reserve_tokens:,}"
    )

    content_parts = []
    total_tokens = 0
    available_tokens = max_tokens - reserve_tokens

    files_skipped = []

    # Priority 1: Handle direct code if provided
    # Direct code is prioritized because it's explicitly provided by the user
    if code:
        formatted_code = f"\n--- BEGIN DIRECT CODE ---\n{code}\n--- END DIRECT CODE ---\n"
        code_tokens = estimate_tokens(formatted_code)

        if code_tokens <= available_tokens:
            content_parts.append(formatted_code)
            total_tokens += code_tokens
            available_tokens -= code_tokens

    # Priority 2: Process file paths
    if file_paths:
        # Expand directories to get all individual files
        logger.debug(f"[FILES] Expanding {len(file_paths)} file paths")
        all_files = expand_paths(file_paths)
        logger.debug(f"[FILES] After expansion: {len(all_files)} individual files")

        if not all_files and file_paths:
            # No files found but paths were provided
            logger.debug("[FILES] No files found from provided paths")
            content_parts.append(f"\n--- NO FILES FOUND ---\nProvided paths: {', '.join(file_paths)}\n--- END ---\n")
        else:
            # Read files sequentially until token limit is reached
            logger.debug(f"[FILES] Reading {len(all_files)} files with token budget {available_tokens:,}")
            for i, file_path in enumerate(all_files):
                if total_tokens >= available_tokens:
                    logger.debug(f"[FILES] Token budget exhausted, skipping remaining {len(all_files) - i} files")
                    files_skipped.extend(all_files[i:])
                    break

                file_content, file_tokens = read_file_content(file_path, include_line_numbers=include_line_numbers)
                logger.debug(f"[FILES] File {file_path}: {file_tokens:,} tokens")

                # Check if adding this file would exceed limit
                if total_tokens + file_tokens <= available_tokens:
                    content_parts.append(file_content)
                    total_tokens += file_tokens
                    logger.debug(f"[FILES] Added file {file_path}, total tokens: {total_tokens:,}")
                else:
                    # File too large for remaining budget
                    logger.debug(
                        f"[FILES] File {file_path} too large for remaining budget ({file_tokens:,} tokens, {available_tokens - total_tokens:,} remaining)"
                    )
                    files_skipped.append(file_path)

    # Add informative note about skipped files to help users understand
    # what was omitted and why
    if files_skipped:
        logger.debug(f"[FILES] {len(files_skipped)} files skipped due to token limits")
        skip_note = "\n\n--- SKIPPED FILES (TOKEN LIMIT) ---\n"
        skip_note += f"Total skipped: {len(files_skipped)}\n"
        # Show first 10 skipped files as examples
        for _i, file_path in enumerate(files_skipped[:10]):
            skip_note += f"  - {file_path}\n"
        if len(files_skipped) > 10:
            skip_note += f"  ... and {len(files_skipped) - 10} more\n"
        skip_note += "--- END SKIPPED FILES ---\n"
        content_parts.append(skip_note)

    result = "\n\n".join(content_parts) if content_parts else ""
    logger.debug(f"[FILES] read_files complete: {len(result)} chars, {total_tokens:,} tokens used")
    return result


def estimate_file_tokens(file_path: str) -> int:
    """
    Estimate tokens for a file using file-type aware ratios.

    Args:
        file_path: Path to the file

    Returns:
        Estimated token count for the file
    """
    try:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return 0

        file_size = os.path.getsize(file_path)

        # Get the appropriate ratio for this file type
        from .file_types import get_token_estimation_ratio

        ratio = get_token_estimation_ratio(file_path)

        return int(file_size / ratio)
    except Exception:
        return 0


def check_files_size_limit(files: list[str], max_tokens: int, threshold_percent: float = 1.0) -> tuple[bool, int, int]:
    """
    Check if a list of files would exceed token limits.

    Args:
        files: List of file paths to check
        max_tokens: Maximum allowed tokens
        threshold_percent: Percentage of max_tokens to use as threshold (0.0-1.0)

    Returns:
        Tuple of (within_limit, total_estimated_tokens, file_count)
    """
    if not files:
        return True, 0, 0

    total_estimated_tokens = 0
    file_count = 0
    threshold = int(max_tokens * threshold_percent)

    for file_path in files:
        try:
            estimated_tokens = estimate_file_tokens(file_path)
            total_estimated_tokens += estimated_tokens
            if estimated_tokens > 0:  # Only count accessible files
                file_count += 1
        except Exception:
            # Skip files that can't be accessed for size check
            continue

    within_limit = total_estimated_tokens <= threshold
    return within_limit, total_estimated_tokens, file_count


class LogTailer:
    """
    General-purpose log file tailer with rotation detection.

    This class provides a reusable way to monitor log files for new content,
    automatically handling log rotation and maintaining position tracking.
    """

    def __init__(self, file_path: str, initial_seek_end: bool = True):
        """
        Initialize log tailer for a specific file.

        Args:
            file_path: Path to the log file to monitor
            initial_seek_end: If True, start monitoring from end of file
        """
        self.file_path = file_path
        self.position = 0
        self.last_size = 0
        self.initial_seek_end = initial_seek_end

        # Ensure file exists and initialize position
        Path(self.file_path).touch()
        if self.initial_seek_end and os.path.exists(self.file_path):
            self.last_size = os.path.getsize(self.file_path)
            self.position = self.last_size

    def read_new_lines(self) -> list[str]:
        """
        Read new lines since last call, handling rotation.

        Returns:
            List of new lines from the file
        """
        if not os.path.exists(self.file_path):
            return []

        try:
            current_size = os.path.getsize(self.file_path)

            # Check for log rotation (file size decreased)
            if current_size < self.last_size:
                self.position = 0
                self.last_size = current_size

            with open(self.file_path, encoding="utf-8", errors="ignore") as f:
                f.seek(self.position)
                new_lines = f.readlines()
                self.position = f.tell()
                self.last_size = current_size

                # Strip whitespace from each line
                return [line.strip() for line in new_lines if line.strip()]

        except OSError:
            return []

    def monitor_continuously(
        self,
        line_handler: Callable[[str], None],
        check_interval: float = 0.5,
        stop_condition: Optional[Callable[[], bool]] = None,
    ):
        """
        Monitor file continuously and call handler for each new line.

        Args:
            line_handler: Function to call for each new line
            check_interval: Seconds between file checks
            stop_condition: Optional function that returns True to stop monitoring
        """
        while True:
            try:
                if stop_condition and stop_condition():
                    break

                new_lines = self.read_new_lines()
                for line in new_lines:
                    line_handler(line)

                time.sleep(check_interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.warning(f"Error monitoring log file {self.file_path}: {e}")
                time.sleep(1)


def read_json_file(file_path: str) -> Optional[dict]:
    """
    Read and parse a JSON file with proper error handling.

    Args:
        file_path: Path to the JSON file

    Returns:
        Parsed JSON data as dict, or None if file doesn't exist or invalid
    """
    try:
        if not os.path.exists(file_path):
            return None

        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def write_json_file(file_path: str, data: dict, indent: int = 2) -> bool:
    """
    Write data to a JSON file with proper formatting.

    Args:
        file_path: Path to write the JSON file
        data: Dictionary data to serialize
        indent: JSON indentation level

    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except (OSError, TypeError):
        return False


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes with proper error handling.

    Args:
        file_path: Path to the file

    Returns:
        File size in bytes, or 0 if file doesn't exist or error
    """
    try:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return os.path.getsize(file_path)
        return 0
    except OSError:
        return 0


def ensure_directory_exists(file_path: str) -> bool:
    """
    Ensure the parent directory of a file path exists.

    Args:
        file_path: Path to file (directory will be created for parent)

    Returns:
        True if directory exists or was created, False on error
    """
    try:
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        return True
    except OSError:
        return False


def is_text_file(file_path: str) -> bool:
    """
    Check if a file is likely a text file based on extension and content.

    Args:
        file_path: Path to the file

    Returns:
        True if file appears to be text, False otherwise
    """
    from .file_types import is_text_file as check_text_type

    return check_text_type(file_path)


def read_file_safely(file_path: str, max_size: int = 10 * 1024 * 1024) -> Optional[str]:
    """
    Read a file with size limits and encoding handling.

    Args:
        file_path: Path to the file
        max_size: Maximum file size in bytes (default 10MB)

    Returns:
        File content as string, or None if file too large or unreadable
    """
    try:
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return None

        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            return None

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except OSError:
        return None


def check_total_file_size(files: list[str], model_name: str) -> Optional[dict]:
    """
    Check if total file sizes would exceed token threshold before embedding.

    IMPORTANT: This performs STRICT REJECTION at MCP boundary.
    No partial inclusion - either all files fit or request is rejected.
    This forces Claude to make better file selection decisions.

    This function MUST be called with the effective model name (after resolution).
    It should never receive 'auto' or None - model resolution happens earlier.

    Args:
        files: List of file paths to check
        model_name: The resolved model name for context-aware thresholds (required)

    Returns:
        Dict with `code_too_large` response if too large, None if acceptable
    """
    if not files:
        return None

    # Validate we have a proper model name (not auto or None)
    if not model_name or model_name.lower() == "auto":
        raise ValueError(
            f"check_total_file_size called with unresolved model: '{model_name}'. "
            "Model must be resolved before file size checking."
        )

    logger.info(f"File size check: Using model '{model_name}' for token limit calculation")

    from utils.model_context import ModelContext

    model_context = ModelContext(model_name)
    token_allocation = model_context.calculate_token_allocation()

    # Dynamic threshold based on model capacity
    context_window = token_allocation.total_tokens
    if context_window >= 1_000_000:  # Gemini-class models
        threshold_percent = 0.8  # Can be more generous
    elif context_window >= 500_000:  # Mid-range models
        threshold_percent = 0.7  # Moderate
    else:  # OpenAI-class models (200K)
        threshold_percent = 0.6  # Conservative

    max_file_tokens = int(token_allocation.file_tokens * threshold_percent)

    # Use centralized file size checking (threshold already applied to max_file_tokens)
    within_limit, total_estimated_tokens, file_count = check_files_size_limit(files, max_file_tokens)

    if not within_limit:
        return {
            "status": "code_too_large",
            "content": (
                f"The selected files are too large for analysis "
                f"(estimated {total_estimated_tokens:,} tokens, limit {max_file_tokens:,}). "
                f"Please select fewer, more specific files that are most relevant "
                f"to your question, then invoke the tool again."
            ),
            "content_type": "text",
            "metadata": {
                "total_estimated_tokens": total_estimated_tokens,
                "limit": max_file_tokens,
                "file_count": file_count,
                "threshold_percent": threshold_percent,
                "model_context_window": context_window,
                "model_name": model_name,
                "instructions": "Reduce file selection and try again - all files must fit within budget. If this persists, please use a model with a larger context window where available.",
            },
        }

    return None  # Proceed with ALL files
