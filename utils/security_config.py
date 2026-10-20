"""
Security configuration and path validation constants

This module contains security-related constants and configurations
for file access control.
"""

from pathlib import Path

# Dangerous system paths - block these AND all their subdirectories
# These are system directories where user code should never reside
DANGEROUS_SYSTEM_PATHS = {
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/var",
    "/root",
    "/proc",
    "/sys",
    "C:\\Windows",
    "C:\\Program Files",
}

# User home container paths - block ONLY the exact path, not subdirectories
# Subdirectory access (e.g., /home/user/project) is controlled by is_home_directory_root()
# This allows users to work in their home subdirectories while blocking overly broad access
DANGEROUS_HOME_CONTAINERS = {
    "/home",
    "C:\\Users",
}

# Combined set for backward compatibility
DANGEROUS_PATHS = DANGEROUS_SYSTEM_PATHS | DANGEROUS_HOME_CONTAINERS

# Directories to exclude from recursive file search
# These typically contain generated code, dependencies, or build artifacts
EXCLUDED_DIRS = {
    # Python
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".env",
    "*.egg-info",
    ".eggs",
    "wheels",
    ".Python",
    ".mypy_cache",
    ".pytest_cache",
    ".tox",
    "htmlcov",
    ".coverage",
    "coverage",
    # Node.js / JavaScript
    "node_modules",
    ".next",
    ".nuxt",
    "bower_components",
    ".sass-cache",
    # Version Control
    ".git",
    ".svn",
    ".hg",
    # Build Output
    "build",
    "dist",
    "target",
    "out",
    # IDEs
    ".idea",
    ".vscode",
    ".sublime",
    ".atom",
    ".brackets",
    # Temporary / Cache
    ".cache",
    ".temp",
    ".tmp",
    "*.swp",
    "*.swo",
    "*~",
    # OS-specific
    ".DS_Store",
    "Thumbs.db",
    # Java / JVM
    ".gradle",
    ".m2",
    # Documentation build
    "_build",
    "site",
    # Mobile development
    ".expo",
    ".flutter",
    # Package managers
    "vendor",
}


def is_dangerous_path(path: Path) -> bool:
    """
    Check if a path is in or under a dangerous directory.

    This function handles two categories of dangerous paths differently:

    1. System paths (DANGEROUS_SYSTEM_PATHS): Block the path AND all subdirectories.
       Example: /etc is dangerous, so /etc/passwd is also blocked.

    2. Home containers (DANGEROUS_HOME_CONTAINERS): Block ONLY the exact path.
       Example: /home is blocked, but /home/user/project is allowed.
       Subdirectory access control is delegated to is_home_directory_root().

    Args:
        path: Path to check

    Returns:
        True if the path is dangerous and should not be accessed

    Security:
        Fixes path traversal vulnerability (CWE-22) while preserving
        user access to home subdirectories.
    """
    try:
        resolved = path.resolve()

        def _dangerous_variants(p: Path) -> set[Path]:
            variants = {p}
            # Only resolve paths that are absolute on the current platform.
            # This avoids turning Windows-style strings into nonsense absolute paths on POSIX.
            if p.is_absolute():
                try:
                    variants.add(p.resolve())
                except Exception:
                    pass
            return variants

        # Check 1: Root directory (filesystem root)
        if resolved.parent == resolved:
            return True

        # Check 2: System paths - block exact match AND all subdirectories
        for dangerous in DANGEROUS_SYSTEM_PATHS:
            # Skip root "/" - already handled above
            if dangerous == "/":
                continue

            for dangerous_path in _dangerous_variants(Path(dangerous)):
                # is_relative_to() correctly handles both exact matches and subdirectories.
                # Resolving the dangerous base path also handles platform symlinks
                # (e.g., macOS /etc -> /private/etc, /var -> /private/var).
                if resolved == dangerous_path or resolved.is_relative_to(dangerous_path):
                    return True

        # Check 3: Home containers - block ONLY exact match
        # Subdirectories like /home/user/project should pass through here
        # and be handled by is_home_directory_root() in resolve_and_validate_path()
        for container in DANGEROUS_HOME_CONTAINERS:
            for container_path in _dangerous_variants(Path(container)):
                if resolved == container_path:
                    return True

        return False

    except Exception:
        return True  # If we can't resolve, consider it dangerous
