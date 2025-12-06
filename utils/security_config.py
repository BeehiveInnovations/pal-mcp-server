"""
Security configuration and path validation constants

This module contains security-related constants and configurations
for file access control.
"""

from pathlib import Path

# Dangerous paths that should never be scanned
# These would give overly broad access and pose security risks
DANGEROUS_PATHS = {
    "/",
    "/etc",
    "/usr",
    "/bin",
    "/var",
    "/root",
    "/home",
    "C:\\",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Users",
}

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

    Uses Path.is_relative_to() to block dangerous directories AND their subdirectories.
    For example, if "/etc" is in DANGEROUS_PATHS, both "/etc" and "/etc/passwd"
    will be blocked.

    Args:
        path: Path to check

    Returns:
        True if the path is dangerous and should not be accessed

    Security:
        Fixes path traversal vulnerability (CWE-22)
    """
    try:
        resolved = path.resolve()

        # Check 1: Root directory (filesystem root)
        if resolved.parent == resolved:
            return True

        # Check 2: Exact match or subdirectory of dangerous paths
        # Use Path.is_relative_to() for correct cross-platform path comparison
        for dangerous in DANGEROUS_PATHS:
            # Skip root "/" - already handled above
            if dangerous == "/":
                continue

            dangerous_path = Path(dangerous)
            # is_relative_to() correctly handles both exact matches and subdirectories
            # Works properly on Windows with paths like "C:\" and "C:\Users"
            if resolved == dangerous_path or resolved.is_relative_to(dangerous_path):
                return True

        return False

    except Exception:
        return True  # If we can't resolve, consider it dangerous
