"""X.AI (GROK) model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.xai import XAIModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class XAIModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for X.AI's GROK models exposed over an OpenAI-style API.

    Publishes capability metadata for the officially supported deployments and
    maps tool-category preferences to the appropriate GROK model.
    """

    FRIENDLY_NAME = "X.AI"

    REGISTRY_CLASS = XAIModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize X.AI provider with API key."""
        # Set X.AI base URL
        kwargs.setdefault("base_url", "https://api.x.ai/v1")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.XAI

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get XAI's preferred model for a given category from allowed models.

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
            # Prefer GROK-4.1-Fast-Reasoning (latest), then GROK-4-Fast-Reasoning for cost-efficient reasoning, then GROK-4
            if "grok-4-1-fast-reasoning" in allowed_models:
                return "grok-4-1-fast-reasoning"
            elif "grok-4-fast-reasoning" in allowed_models:
                return "grok-4-fast-reasoning"
            elif "grok-4" in allowed_models:
                return "grok-4"
            elif "grok-3" in allowed_models:
                return "grok-3"
            # Fall back to any available model
            return allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer GROK-4.1-Fast-Non-Reasoning (latest) for fastest responses, then GROK-4-Fast-Non-Reasoning, then GROK-3-Fast
            if "grok-4-1-fast-non-reasoning" in allowed_models:
                return "grok-4-1-fast-non-reasoning"
            elif "grok-4-fast-non-reasoning" in allowed_models:
                return "grok-4-fast-non-reasoning"
            elif "grok-3-fast" in allowed_models:
                return "grok-3-fast"
            elif "grok-4" in allowed_models:
                return "grok-4"
            # Fall back to any available model
            return allowed_models[0]

        else:  # BALANCED or default
            # Prefer GROK-4 for balanced use (best overall capabilities)
            if "grok-4" in allowed_models:
                return "grok-4"
            elif "grok-4-1-fast-reasoning" in allowed_models:
                return "grok-4-1-fast-reasoning"
            elif "grok-code-fast-1" in allowed_models:
                return "grok-code-fast-1"
            elif "grok-4-fast-reasoning" in allowed_models:
                return "grok-4-fast-reasoning"
            elif "grok-3" in allowed_models:
                return "grok-3"
            elif "grok-3-fast" in allowed_models:
                return "grok-3-fast"
            # Fall back to any available model
            return allowed_models[0]


# Load registry data at import time
XAIModelProvider._ensure_registry()
