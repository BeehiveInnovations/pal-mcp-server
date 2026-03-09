"""MiniMax model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.minimax import MiniMaxModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class MiniMaxModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for MiniMax models exposed over an OpenAI-style API.

    Publishes capability metadata for the officially supported deployments and
    maps tool-category preferences to the appropriate MiniMax model.
    """

    FRIENDLY_NAME = "MiniMax"

    REGISTRY_CLASS = MiniMaxModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Canonical model identifiers used for category routing.
    PRIMARY_MODEL = "MiniMax-M2.5"
    FAST_MODEL = "MiniMax-M2.5-highspeed"

    def __init__(self, api_key: str, **kwargs):
        """Initialize MiniMax provider with API key."""
        # Set MiniMax base URL
        kwargs.setdefault("base_url", "https://api.minimax.io/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.MINIMAX

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get MiniMax's preferred model for a given category from allowed models.

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
            # Prefer M2.5 for advanced reasoning tasks
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            if self.FAST_MODEL in allowed_models:
                return self.FAST_MODEL
            return allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer M2.5-highspeed for speed
            if self.FAST_MODEL in allowed_models:
                return self.FAST_MODEL
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            return allowed_models[0]

        else:  # BALANCED or default
            # Prefer M2.5 for balanced use
            if self.PRIMARY_MODEL in allowed_models:
                return self.PRIMARY_MODEL
            if self.FAST_MODEL in allowed_models:
                return self.FAST_MODEL
            return allowed_models[0]


# Load registry data at import time
MiniMaxModelProvider._ensure_registry()
