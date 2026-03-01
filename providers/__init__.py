"""Model provider abstractions for supporting multiple AI providers."""

from .azure_openai import AzureOpenAIProvider
from .base import ModelProvider
from .gemini import GeminiModelProvider
from .minimax import MiniMaxModelProvider
from .openai import OpenAIModelProvider
from .openai_compatible import OpenAICompatibleProvider
from .openrouter import OpenRouterProvider
from .registry import ModelProviderRegistry
from .shared import ModelCapabilities, ModelResponse

__all__ = [
    "ModelProvider",
    "ModelResponse",
    "ModelCapabilities",
    "ModelProviderRegistry",
    "AzureOpenAIProvider",
    "GeminiModelProvider",
    "MiniMaxModelProvider",
    "OpenAIModelProvider",
    "OpenAICompatibleProvider",
    "OpenRouterProvider",
]
