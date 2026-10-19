"""NVIDIA (Nemotron) native provider — OpenAI-compatible direct API (NIM / build.nvidia.com)."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.nvidia import NvidiaModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class NvidiaModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party NVIDIA integration over the NIM OpenAI-compatible API."""

    FRIENDLY_NAME = "NVIDIA"
    REGISTRY_CLASS = NvidiaModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.NVIDIA


NvidiaModelProvider._ensure_registry()
