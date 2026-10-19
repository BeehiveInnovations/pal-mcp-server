"""MiniMax native provider — OpenAI-compatible direct API."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.minimax import MiniMaxModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class MiniMaxModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party MiniMax integration over its OpenAI-compatible API."""

    FRIENDLY_NAME = "MiniMax"
    REGISTRY_CLASS = MiniMaxModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.minimax.io/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.MINIMAX


MiniMaxModelProvider._ensure_registry()
