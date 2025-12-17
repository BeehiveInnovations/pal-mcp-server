"""Enumeration describing which backend owns a given model."""

from enum import Enum

__all__ = ["ProviderType"]


class ProviderType(Enum):
    """Canonical identifiers for every supported provider backend."""

    GOOGLE = "google"
    OPENAI = "openai"
    AZURE = "azure"
    XAI = "xai"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"
    DIAL = "dial"
    # CLI-based providers (use locally installed CLI tools instead of API keys)
    GEMINI_CLI = "gemini_cli"
    CLAUDE_CLI = "claude_cli"
    CODEX_CLI = "codex_cli"
