"""DeepSeek native provider (OpenAI-compatible direct API).

DeepSeek's API (https://api.deepseek.com) is OpenAI-compatible, so this is a thin subclass of the
shared OpenAI-compatible base (mirrors providers/xai.py). Claude/OpenRouter also expose DeepSeek via
`deepseek/*` IDs; with a DEEPSEEK_API_KEY set this native provider ranks ahead of OpenRouter so bare
aliases resolve to the direct API.
"""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.deepseek import DeepSeekModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class DeepSeekModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party DeepSeek integration over its OpenAI-compatible API."""

    FRIENDLY_NAME = "DeepSeek"
    REGISTRY_CLASS = DeepSeekModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.deepseek.com")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.DEEPSEEK


# Load registry data at import time for registry consumers
DeepSeekModelProvider._ensure_registry()
