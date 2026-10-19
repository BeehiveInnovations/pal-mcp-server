"""Perplexity native provider — OpenAI-compatible direct API (Sonar models)."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.perplexity import PerplexityModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class PerplexityModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party Perplexity integration over its OpenAI-compatible API."""

    FRIENDLY_NAME = "Perplexity"
    REGISTRY_CLASS = PerplexityModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.perplexity.ai")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.PERPLEXITY


PerplexityModelProvider._ensure_registry()
