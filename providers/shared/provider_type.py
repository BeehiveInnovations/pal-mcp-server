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
    REQUESTY = "requesty"
    CUSTOM = "custom"
    DIAL = "dial"
