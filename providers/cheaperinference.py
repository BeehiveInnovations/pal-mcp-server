"""Cheaper Inference model provider implementation."""

import logging
from typing import ClassVar

from .openai_compatible import OpenAICompatibleProvider
from .registries.cheaperinference import CheaperInferenceModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class CheaperInferenceModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Client for the Cheaper Inference OpenAI-compatible gateway.

    Cheaper Inference exposes models from several labs behind a single
    OpenAI-compatible endpoint. This provider publishes capability metadata
    for the models listed in ``conf/cheaperinference_models.json``.
    """

    FRIENDLY_NAME = "Cheaper Inference"

    REGISTRY_CLASS = CheaperInferenceModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    DEFAULT_BASE_URL = "https://api.cheaperinference.com/v1"

    def __init__(self, api_key: str, **kwargs):
        """Initialize Cheaper Inference provider with API key."""
        kwargs.setdefault("base_url", self.DEFAULT_BASE_URL)
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.CHEAPERINFERENCE


# Load registry data at import time
CheaperInferenceModelProvider._ensure_registry()
