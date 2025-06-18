"""
File type definitions and constants for file processing

This module centralizes all file type and extension definitions used
throughout the MCP server for consistent file handling.
"""

# Programming language file extensions - core code files
PROGRAMMING_LANGUAGES = {
    ".py",  # Python
    ".js",  # JavaScript
    ".ts",  # TypeScript
    ".jsx",  # React JavaScript
    ".tsx",  # React TypeScript
    ".java",  # Java
    ".cpp",  # C++
    ".c",  # C
    ".h",  # C/C++ Header
    ".hpp",  # C++ Header
    ".cs",  # C#
    ".go",  # Go
    ".rs",  # Rust
    ".rb",  # Ruby
    ".php",  # PHP
    ".swift",  # Swift
    ".kt",  # Kotlin
    ".scala",  # Scala
    ".r",  # R
    ".m",  # Objective-C
    ".mm",  # Objective-C++
}

# Script and shell file extensions
SCRIPTS = {
    ".sql",  # SQL
    ".sh",  # Shell
    ".bash",  # Bash
    ".zsh",  # Zsh
    ".fish",  # Fish shell
    ".ps1",  # PowerShell
    ".bat",  # Batch
    ".cmd",  # Command
}

# Configuration and data file extensions
CONFIGS = {
    ".yml",  # YAML
    ".yaml",  # YAML
    ".json",  # JSON
    ".xml",  # XML
    ".toml",  # TOML
    ".ini",  # INI
    ".cfg",  # Config
    ".conf",  # Config
    ".properties",  # Properties
    ".env",  # Environment
}

# Documentation and markup file extensions
DOCS = {
    ".txt",  # Text
    ".md",  # Markdown
    ".rst",  # reStructuredText
    ".tex",  # LaTeX
}

# Web development file extensions
WEB = {
    ".html",  # HTML
    ".css",  # CSS
    ".scss",  # Sass
    ".sass",  # Sass
    ".less",  # Less
}

# Additional text file extensions for logs and data
TEXT_DATA = {
    ".log",  # Log files
    ".csv",  # CSV
    ".tsv",  # TSV
    ".gitignore",  # Git ignore
    ".dockerfile",  # Dockerfile
    ".makefile",  # Make
    ".cmake",  # CMake
    ".gradle",  # Gradle
    ".sbt",  # SBT
    ".pom",  # Maven POM
    ".lock",  # Lock files
}

# Image file extensions - limited to what AI models actually support
# Based on OpenAI and Gemini supported formats: PNG, JPEG, GIF, WebP
IMAGES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# Binary executable and library extensions
BINARIES = {
    ".exe",  # Windows executable
    ".dll",  # Windows library
    ".so",  # Linux shared object
    ".dylib",  # macOS dynamic library
    ".bin",  # Binary
    ".class",  # Java class
}

# Archive and package file extensions
ARCHIVES = {
    ".jar",
    ".war",
    ".ear",  # Java archives
    ".zip",
    ".tar",
    ".gz",  # General archives
    ".7z",
    ".rar",  # Compression
    ".deb",
    ".rpm",  # Linux packages
    ".dmg",
    ".pkg",  # macOS packages
}

# Derived sets for different use cases
CODE_EXTENSIONS = PROGRAMMING_LANGUAGES | SCRIPTS | CONFIGS | DOCS | WEB
PROGRAMMING_EXTENSIONS = PROGRAMMING_LANGUAGES  # For line numbering
TEXT_EXTENSIONS = CODE_EXTENSIONS | TEXT_DATA
IMAGE_EXTENSIONS = IMAGES
BINARY_EXTENSIONS = BINARIES | ARCHIVES

# All extensions by category for easy access
FILE_CATEGORIES = {
    "programming": PROGRAMMING_LANGUAGES,
    "scripts": SCRIPTS,
    "configs": CONFIGS,
    "docs": DOCS,
    "web": WEB,
    "text_data": TEXT_DATA,
    "images": IMAGES,
    "binaries": BINARIES,
    "archives": ARCHIVES,
}


def get_file_category(file_path: str) -> str:
    """
    Determine the category of a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        Category name or "unknown" if not recognized
    """
    from pathlib import Path

    extension = Path(file_path).suffix.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "unknown"


def is_code_file(file_path: str) -> bool:
    """Check if a file is a code file (programming language)."""
    from pathlib import Path

    return Path(file_path).suffix.lower() in PROGRAMMING_LANGUAGES


def is_text_file(file_path: str) -> bool:
    """Check if a file is a text file."""
    from pathlib import Path

    return Path(file_path).suffix.lower() in TEXT_EXTENSIONS


def is_binary_file(file_path: str) -> bool:
    """Check if a file is a binary file."""
    from pathlib import Path

    return Path(file_path).suffix.lower() in BINARY_EXTENSIONS


# File-type specific token-to-byte ratios for accurate token estimation
# Based on empirical analysis of file compression characteristics and tokenization patterns
TOKEN_ESTIMATION_RATIOS = {
    # Programming languages
    ".py": 3.5,  # Python - moderate verbosity
    ".js": 3.2,  # JavaScript - compact syntax
    ".ts": 3.3,  # TypeScript - type annotations add tokens
    ".jsx": 3.1,  # React JSX - JSX tags are tokenized efficiently
    ".tsx": 3.0,  # React TSX - combination of TypeScript + JSX
    ".java": 3.6,  # Java - verbose syntax, long identifiers
    ".cpp": 3.7,  # C++ - preprocessor directives, templates
    ".c": 3.8,  # C - function definitions, struct declarations
    ".go": 3.9,  # Go - explicit error handling, package names
    ".rs": 3.5,  # Rust - similar to Python in verbosity
    ".php": 3.3,  # PHP - mixed HTML/code, variable prefixes
    ".rb": 3.6,  # Ruby - descriptive method names
    ".swift": 3.4,  # Swift - modern syntax, type inference
    ".kt": 3.5,  # Kotlin - similar to modern languages
    ".scala": 3.2,  # Scala - functional programming, concise
    # Scripts and configuration
    ".sh": 4.1,  # Shell scripts - commands and paths
    ".bat": 4.0,  # Batch files - similar to shell
    ".ps1": 3.8,  # PowerShell - more structured than bash
    ".sql": 3.8,  # SQL - keywords and table/column names
    # Data and configuration formats
    ".json": 2.5,  # JSON - lots of punctuation and quotes
    ".yaml": 3.0,  # YAML - structured but readable
    ".yml": 3.0,  # YAML (alternative extension)
    ".xml": 2.8,  # XML - tags and attributes
    ".toml": 3.2,  # TOML - similar to config files
    # Documentation and text
    ".md": 4.2,  # Markdown - natural language with formatting
    ".txt": 4.0,  # Plain text - mostly natural language
    ".rst": 4.1,  # reStructuredText - documentation format
    # Web technologies
    ".html": 2.9,  # HTML - tags and attributes
    ".css": 3.4,  # CSS - properties and selectors
    # Logs and data
    ".log": 4.5,  # Log files - timestamps, messages, stack traces
    ".csv": 3.1,  # CSV - data with delimiters
    # Infrastructure files
    ".dockerfile": 3.7,  # Dockerfile - commands and paths
    ".tf": 3.5,  # Terraform - infrastructure as code
}


def get_token_estimation_ratio(file_path: str) -> float:
    """
    Get the token estimation ratio for a file based on its extension.

    Args:
        file_path: Path to the file

    Returns:
        Token-to-byte ratio for the file type (default: 3.5 for unknown types)
    """
    from pathlib import Path

    extension = Path(file_path).suffix.lower()
    return TOKEN_ESTIMATION_RATIOS.get(extension, 3.5)  # Conservative default


# MIME type mappings for image files - limited to what AI models actually support
# Based on OpenAI and Gemini supported formats: PNG, JPEG, GIF, WebP
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def get_image_mime_type(extension: str) -> str:
    """
    Get the MIME type for an image file extension.

    Args:
        extension: File extension (with or without leading dot)

    Returns:
        MIME type string (default: image/jpeg for unknown extensions)
    """
    if not extension.startswith("."):
        extension = "." + extension
    extension = extension.lower()
    return IMAGE_MIME_TYPES.get(extension, "image/jpeg")
