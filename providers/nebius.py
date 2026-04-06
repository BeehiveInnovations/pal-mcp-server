"""Nebius Token Factory model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.nebius import NebiusModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class NebiusModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for Nebius Token Factory's OpenAI-compatible API.

    Nebius Token Factory provides access to open-source models like Qwen3, DeepSeek,
    Llama, GLM, and GPT-OSS through an OpenAI-compatible API endpoint.

    Features:
        - Text and vision model support
        - Extended thinking/reasoning for models like DeepSeek-R1
        - Function calling capabilities
        - JSON mode support
    """

    FRIENDLY_NAME = "Nebius"

    REGISTRY_CLASS = NebiusModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    # Canonical model identifiers used for category routing
    PRIMARY_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"
    FALLBACK_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"

    def __init__(self, api_key: str, **kwargs):
        """Initialize Nebius provider with API key."""
        # Set Nebius Token Factory base URL
        kwargs.setdefault("base_url", "https://api.studio.nebius.com/v1/")
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.NEBIUS

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get Nebius's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # Model preferences by category
        reasoning_models = [
            "deepseek-ai/DeepSeek-R1-0528",
            "Qwen/Qwen3-235B-A22B-Thinking-2507",
            "moonshotai/Kimi-K2-Instruct",
        ]
        fast_models = [
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "Qwen/Qwen3-30B-A3B-Instruct-2507",
            "google/gemma-3-27b-it",
        ]
        balanced_models = [
            "Qwen/Qwen3-235B-A22B-Instruct-2507",
            "deepseek-ai/DeepSeek-V3.2",
            "meta-llama/Llama-3.3-70B-Instruct",
            "zai-org/GLM-4.5",
        ]

        if category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer reasoning models for advanced tasks
            for model in reasoning_models:
                if model in allowed_models:
                    return model
            # Fallback to balanced
            for model in balanced_models:
                if model in allowed_models:
                    return model

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer smaller/faster models
            for model in fast_models:
                if model in allowed_models:
                    return model

        else:  # BALANCED or default
            for model in balanced_models:
                if model in allowed_models:
                    return model

        # Ultimate fallback: first available
        return allowed_models[0] if allowed_models else None


# Load registry data at import time
NebiusModelProvider._ensure_registry()
