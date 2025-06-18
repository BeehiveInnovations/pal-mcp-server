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
    Check if a path is in the dangerous paths list.

    Args:
        path: Path to check

    Returns:
        True if the path is dangerous and should not be accessed
    """
    try:
        resolved = path.resolve()
        return str(resolved) in DANGEROUS_PATHS or resolved.parent == resolved
    except Exception:
        return True  # If we can't resolve, consider it dangerous
