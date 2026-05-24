"""Model provider abstractions for supporting multiple AI providers."""

from .azure_openai import AzureOpenAIProvider
from .base import ModelProvider
from .gemini import GeminiModelProvider
from .openai import OpenAIModelProvider
from .openai_compatible import OpenAICompatibleProvider
from .openrouter import OpenRouterProvider
from .registry import ModelProviderRegistry
from .shared import ModelCapabilities, ModelResponse


class GeminiAccountExhausted(Exception):
    """Raised when both gemini-2.5-flash and gemini-2.5-flash-lite are daily-exhausted
    on the current OAuth account and the caller should trigger account rotation.

    Attributes:
        account_email: Email address of the exhausted account (for logging/alerting).
    """

    def __init__(self, account_email: str) -> None:
        self.account_email = account_email
        super().__init__(f"Gemini account exhausted: {account_email}")


__all__ = [
    "ModelProvider",
    "ModelResponse",
    "ModelCapabilities",
    "ModelProviderRegistry",
    "AzureOpenAIProvider",
    "GeminiModelProvider",
    "GeminiAccountExhausted",
    "OpenAIModelProvider",
    "OpenAICompatibleProvider",
    "OpenRouterProvider",
]
