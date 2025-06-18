"""
Git utilities for finding repositories and generating diffs.

This module provides Git integration functionality for the MCP server,
enabling tools to work with version control information. It handles
repository discovery, status checking, and diff generation.

Key Features:
- Recursive repository discovery with depth limits
- Safe command execution with timeouts
- Comprehensive status information extraction
- Support for staged and unstaged changes

Security Considerations:
- All git commands are run with timeouts to prevent hanging
- Repository discovery ignores common build/dependency directories
- Error handling for permission-denied scenarios
"""

import subprocess
from pathlib import Path

# Directories to ignore when searching for git repositories
# These are typically build artifacts, dependencies, or cache directories
# that don't contain source code and would slow down repository discovery
IGNORED_DIRS = {
    "node_modules",  # Node.js dependencies
    "__pycache__",  # Python bytecode cache
    "venv",  # Python virtual environment
    "env",  # Alternative virtual environment name
    "build",  # Common build output directory
    "dist",  # Distribution/release builds
    "target",  # Maven/Rust build output
    ".tox",  # Tox testing environments
    ".pytest_cache",  # Pytest cache directory
}


def find_git_repositories(start_path: str, max_depth: int = 5) -> list[str]:
    """
    Recursively find all git repositories starting from the given path.

    This function walks the directory tree looking for .git directories,
    which indicate the root of a git repository. It respects depth limits
    to prevent excessive recursion in deep directory structures.

    Args:
        start_path: Directory to start searching from (must be absolute)
        max_depth: Maximum depth to search (default 5 prevents excessive recursion)

    Returns:
        List of absolute paths to git repositories, sorted alphabetically
    """
    repositories = []

    try:
        # Create Path object - no need to resolve yet since the path might be
        # a translated path that doesn't exist
        start_path = Path(start_path)

        # Basic validation - must be absolute
        if not start_path.is_absolute():
            return []

        # Check if the path exists before trying to walk it
        if not start_path.exists():
            return []

    except Exception:
        # If there's any issue with the path, return empty list
        return []

    def _find_repos(current_path: Path, current_depth: int):
        # Stop recursion if we've reached maximum depth
        if current_depth > max_depth:
            return

        try:
            # Check if current directory contains a .git directory
            git_dir = current_path / ".git"
            if git_dir.exists() and git_dir.is_dir():
                repositories.append(str(current_path))
                # Don't search inside git repositories for nested repos
                # This prevents finding submodules which should be handled separately
                return

            # Search subdirectories for more repositories
            for item in current_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    # Skip common non-code directories to improve performance
                    if item.name in IGNORED_DIRS:
                        continue
                    _find_repos(item, current_depth + 1)

        except PermissionError:
            # Skip directories we don't have permission to read
            # This is common for system directories or other users' files
            pass

    _find_repos(start_path, 0)
    return sorted(repositories)


def run_git_command(repo_path: str, command: list[str]) -> tuple[bool, str]:
    """
    Run a git command in the specified repository.

    This function provides a safe way to execute git commands with:
    - Timeout protection (30 seconds) to prevent hanging
    - Proper error handling and output capture
    - Working directory context management

    Args:
        repo_path: Path to the git repository (working directory)
        command: Git command as a list of arguments (excluding 'git' itself)

    Returns:
        Tuple of (success, output/error)
        - success: True if command returned 0, False otherwise
        - output/error: stdout if successful, stderr or error message if failed
    """
    # Verify the repository path exists before trying to use it
    if not Path(repo_path).exists():
        return False, f"Repository path does not exist: {repo_path}"

    try:
        # Execute git command with safety measures
        result = subprocess.run(
            ["git"] + command,
            cwd=repo_path,  # Run in repository directory
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Return strings instead of bytes
            timeout=30,  # Prevent hanging on slow operations
        )

        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr

    except subprocess.TimeoutExpired:
        return False, "Command timed out after 30 seconds"
    except FileNotFoundError as e:
        # This can happen if git is not installed or repo_path issues
        return False, f"Git command failed - path not found: {str(e)}"
    except Exception as e:
        return False, f"Git command failed: {str(e)}"


def get_git_status(repo_path: str) -> dict[str, any]:
    """
    Get comprehensive git status information for a repository.

    This function gathers various pieces of repository state including:
    - Current branch name
    - Commits ahead/behind upstream
    - Lists of staged, unstaged, and untracked files

    The function is resilient to repositories without remotes or
    in detached HEAD state.

    Args:
        repo_path: Path to the git repository

    Returns:
        Dictionary with status information:
        - branch: Current branch name (empty if detached)
        - ahead: Number of commits ahead of upstream
        - behind: Number of commits behind upstream
        - staged_files: List of files with staged changes
        - unstaged_files: List of files with unstaged changes
        - untracked_files: List of untracked files
    """
    # Initialize status structure with default values
    status = {
        "branch": "",
        "ahead": 0,
        "behind": 0,
        "staged_files": [],
        "unstaged_files": [],
        "untracked_files": [],
    }

    # Get current branch name (empty if in detached HEAD state)
    success, branch = run_git_command(repo_path, ["branch", "--show-current"])
    if success:
        status["branch"] = branch.strip()

    # Get ahead/behind information relative to upstream branch
    if status["branch"]:
        success, ahead_behind = run_git_command(
            repo_path,
            [
                "rev-list",
                "--count",
                "--left-right",
                f"{status['branch']}@{{upstream}}...HEAD",
            ],
        )
        if success:
            if ahead_behind.strip():
                parts = ahead_behind.strip().split()
                if len(parts) == 2:
                    status["behind"] = int(parts[0])
                    status["ahead"] = int(parts[1])
        # Note: This will fail gracefully if branch has no upstream set

    # Get file status using porcelain format for machine parsing
    # Format: XY filename where X=staged status, Y=unstaged status
    success, status_output = run_git_command(repo_path, ["status", "--porcelain"])
    if success:
        for line in status_output.strip().split("\n"):
            if not line:
                continue

            status_code = line[:2]  # Two-character status code
            path_info = line[3:]  # Filename (after space)

            # Parse staged changes (first character of status code)
            if status_code[0] == "R":
                # Special handling for renamed files
                # Format is "old_path -> new_path"
                if " -> " in path_info:
                    _, new_path = path_info.split(" -> ", 1)
                    status["staged_files"].append(new_path)
                else:
                    status["staged_files"].append(path_info)
            elif status_code[0] in ["M", "A", "D", "C"]:
                # M=modified, A=added, D=deleted, C=copied
                status["staged_files"].append(path_info)

            # Parse unstaged changes (second character of status code)
            if status_code[1] in ["M", "D"]:
                # M=modified, D=deleted in working tree
                status["unstaged_files"].append(path_info)
            elif status_code == "??":
                # Untracked files have special marker "??"
                status["untracked_files"].append(path_info)

    return status
