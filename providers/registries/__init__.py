"""Registry implementations for provider capability manifests."""

from .azure import AzureModelRegistry
from .custom import CustomEndpointModelRegistry
from .dial import DialModelRegistry
from .gemini import GeminiModelRegistry
from .openai import OpenAIModelRegistry
from .openrouter import OpenRouterModelRegistry
from .xai import XAIModelRegistry
from .zai import ZAIModelRegistry

__all__ = [
    "AzureModelRegistry",
    "CustomEndpointModelRegistry",
    "DialModelRegistry",
    "GeminiModelRegistry",
    "OpenAIModelRegistry",
    "OpenRouterModelRegistry",
    "XAIModelRegistry",
    "ZAIModelRegistry",
]
