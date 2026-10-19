"""Alibaba Qwen (DashScope) native provider — OpenAI-compatible direct API."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.qwen import QwenModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class QwenModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """First-party Qwen integration over Alibaba DashScope's OpenAI-compatible API."""

    FRIENDLY_NAME = "Qwen"
    REGISTRY_CLASS = QwenModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.QWEN


QwenModelProvider._ensure_registry()
