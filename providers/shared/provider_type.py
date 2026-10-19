"""Enumeration describing which backend owns a given model."""

from enum import Enum

__all__ = ["ProviderType"]


class ProviderType(Enum):
    """Canonical identifiers for every supported provider backend."""

    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    XAI = "xai"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    ZAI = "zai"
    MOONSHOT = "moonshot"
    MINIMAX = "minimax"
    MISTRAL = "mistral"
    NVIDIA = "nvidia"
    PERPLEXITY = "perplexity"
    CHATGPT = "chatgpt"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"
    DIAL = "dial"
