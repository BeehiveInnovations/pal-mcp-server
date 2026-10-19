"""Moonshot Kimi native provider — OpenAI-compatible direct API."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.moonshot import MoonshotModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class MoonshotModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party Moonshot Kimi integration over its OpenAI-compatible API."""

    FRIENDLY_NAME = "Moonshot"
    REGISTRY_CLASS = MoonshotModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.moonshot.ai/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.MOONSHOT


MoonshotModelProvider._ensure_registry()
