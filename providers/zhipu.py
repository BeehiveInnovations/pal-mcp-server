"""GLM (Zhipu AI) model provider implementation using OpenAI-compatible API."""

from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.zhipu import ZhipuModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType


class ZhipuModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Integration for GLM models exposed over OpenAI-compatible API.

    Publishes capability metadata for officially supported GLM models
    and maps tool-category preferences to appropriate GLM model.
    """

    FRIENDLY_NAME = "GLM"
    REGISTRY_CLASS = ZhipuModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize GLM provider with API key."""
        # Set GLM base URL
        kwargs.setdefault("base_url", "https://api.z.ai/v1")
        super().__init__(api_key=api_key, **kwargs)
        self._ensure_registry()
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.ZHIPU

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get GLM's preferred model for a given category from allowed models."""
        # For now, prefer GLM-4.6 as default for all categories
        preferred_models = ["glm-4.6", "glm-4.5"]
        for model in preferred_models:
            if model in allowed_models:
                return model

        # Fall back to first allowed model
        return allowed_models[0] if allowed_models else None
