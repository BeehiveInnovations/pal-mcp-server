"""Zhipu GLM (Z.ai) native provider — OpenAI-compatible direct API."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.zai import ZaiModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class ZaiModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party Zhipu GLM integration over the Z.ai OpenAI-compatible API."""

    FRIENDLY_NAME = "Z.ai"
    REGISTRY_CLASS = ZaiModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.z.ai/api/paas/v4")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.ZAI


ZaiModelProvider._ensure_registry()
