"""Cerebras Inference model provider implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.cerebras import CerebrasModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class CerebrasModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for Cerebras Inference API.

    Publishes capability metadata for the officially supported deployments and
    maps tool-category preferences to the appropriate Cerebras model.

    Model routing by category:
      BALANCED           → zai-glm-4.7   (default; only model on Cerebras Code plan)
      EXTENDED_REASONING → gpt-oss-120b  (strongest reasoning, ~3000 tok/s; paid tier)
      FAST_RESPONSE      → llama3.1-8b   (fastest small model, ~2200 tok/s; paid tier)
    """

    FRIENDLY_NAME = "Cerebras"

    REGISTRY_CLASS = CerebrasModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Category routing — ordered preference lists (first available wins).
    # zai-glm-4.7 is the default: it is the only model on the Cerebras Code
    # (free) plan and must always be the BALANCED fallback.
    _REASONING_PREFERENCE = ["gpt-oss-120b", "qwen-3-235b-a22b-instruct-2507", "zai-glm-4.7", "llama3.1-8b"]
    _BALANCED_PREFERENCE = ["zai-glm-4.7", "qwen-3-235b-a22b-instruct-2507", "gpt-oss-120b", "llama3.1-8b"]
    _FAST_PREFERENCE = ["llama3.1-8b", "zai-glm-4.7", "qwen-3-235b-a22b-instruct-2507", "gpt-oss-120b"]

    def __init__(self, api_key: str, **kwargs):
        """Initialize Cerebras provider with API key."""
        kwargs.setdefault("base_url", "https://api.cerebras.ai/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.CEREBRAS

    def get_preferred_model(self, category: ToolModelCategory, allowed_models: list[str]) -> str | None:
        """Get Cerebras's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        if not allowed_models:
            return None

        from tools.models import ToolModelCategory

        if category == ToolModelCategory.EXTENDED_REASONING:
            preference = self._REASONING_PREFERENCE
        elif category == ToolModelCategory.FAST_RESPONSE:
            preference = self._FAST_PREFERENCE
        else:  # BALANCED or default
            preference = self._BALANCED_PREFERENCE

        for model in preference:
            if model in allowed_models:
                return model
        return allowed_models[0]


# Load registry data at import time
CerebrasModelProvider._ensure_registry()
