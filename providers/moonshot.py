"""Moonshot (Kimi) model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.moonshot import MoonshotModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class MoonshotModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for Moonshot's Kimi models exposed over an OpenAI-style API.

    Publishes capability metadata for the officially supported deployments and
    maps tool-category preferences to the appropriate Kimi model.
    """

    FRIENDLY_NAME = "Moonshot"

    REGISTRY_CLASS = MoonshotModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Canonical model identifiers used for category routing.
    PRIMARY_MODEL = "kimi-k2.5"
    FALLBACK_MODEL = "moonshot-v1-128k"

    def __init__(self, api_key: str, **kwargs):
        """Initialize Moonshot provider with API key."""
        # Set Moonshot base URL
        kwargs.setdefault("base_url", "https://api.moonshot.cn/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.MOONSHOT

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get Moonshot's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer Kimi K2.5 for advanced reasoning tasks
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            if self.FALLBACK_MODEL in allowed_models:
                return self.FALLBACK_MODEL
            return allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer smaller model for speed
            if self.FALLBACK_MODEL in allowed_models:
                return self.FALLBACK_MODEL
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            return allowed_models[0]

        else:  # BALANCED or default
            # Prefer Kimi K2.5 for balanced use
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            if self.FALLBACK_MODEL in allowed_models:
                return self.FALLBACK_MODEL
            return allowed_models[0]


# Load registry data at import time
MoonshotModelProvider._ensure_registry()
