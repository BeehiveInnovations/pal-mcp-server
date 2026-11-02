"""llm.buzz provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.llmbuzz import LLMBuzzModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class LLMBuzzProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for llm.buzz multi-provider gateway.

    Exposes models from multiple providers through a unified OpenAI-compatible API.
    """

    FRIENDLY_NAME = "llm.buzz"
    REGISTRY_CLASS = LLMBuzzModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize llm.buzz provider with API key."""
        kwargs.setdefault("base_url", "https://api.llm.buzz/api/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.LLMBUZZ

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get llm.buzz's preferred model for a given category.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # Prefer Claude Opus 4.1 for advanced tasks
        if category == ToolModelCategory.EXTENDED_REASONING:
            if "claude-opus-4.1" in allowed_models:
                return "claude-opus-4.1"
            if "claude-sonnet-4" in allowed_models:
                return "claude-sonnet-4"
            return allowed_models[0]
        elif category == ToolModelCategory.FAST_RESPONSE:
            if "claude-sonnet-4" in allowed_models:
                return "claude-sonnet-4"
            if "claude-opus-4.1" in allowed_models:
                return "claude-opus-4.1"
            return allowed_models[0]
        else:  # BALANCED or default
            if "claude-opus-4.1" in allowed_models:
                return "claude-opus-4.1"
            if "claude-sonnet-4" in allowed_models:
                return "claude-sonnet-4"
            return allowed_models[0]


# Load registry data at import time
LLMBuzzProvider._ensure_registry()
