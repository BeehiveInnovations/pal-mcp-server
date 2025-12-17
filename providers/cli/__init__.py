"""CLI-based model providers that use locally installed CLI tools.

This module provides model providers that leverage locally installed CLI tools
(Gemini CLI, Claude Code CLI, Codex CLI) instead of API keys. These tools
authenticate via OAuth and often have subscription-based unlimited usage,
making them preferable to pay-per-request API access.

The providers leverage the existing `clink` infrastructure for CLI execution,
which handles command building, process management, and output parsing.
"""

from .base import CLIModelProvider, get_available_cli_tools, is_cli_available
from .claude_cli import ClaudeCLIProvider
from .codex_cli import CodexCLIProvider
from .gemini_cli import GeminiCLIProvider

__all__ = [
    "CLIModelProvider",
    "GeminiCLIProvider",
    "ClaudeCLIProvider",
    "CodexCLIProvider",
    "is_cli_available",
    "get_available_cli_tools",
]
