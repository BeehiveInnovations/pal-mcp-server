"""Mistral native provider — OpenAI-compatible direct API (la Plateforme)."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.mistral import MistralModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class MistralModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party Mistral integration over la Plateforme's OpenAI-compatible API."""

    FRIENDLY_NAME = "Mistral"
    REGISTRY_CLASS = MistralModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.mistral.ai/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.MISTRAL


MistralModelProvider._ensure_registry()
