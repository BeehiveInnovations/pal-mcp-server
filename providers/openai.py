"""OpenAI model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .registries.openai import OpenAIModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ProviderType

logger = logging.getLogger(__name__)


class OpenAIModelProvider(RegistryBackedProviderMixin, OpenAICompatibleProvider):
    """Implementation that talks to api.openai.com using rich model metadata.

    In addition to the built-in catalogue, the provider can surface models
    defined in ``conf/custom_models.json`` (for organisations running their own
    OpenAI-compatible gateways) while still respecting restriction policies.
    """

    REGISTRY_CLASS = OpenAIModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize OpenAI provider with API key."""
        self._ensure_registry()
        # Set default OpenAI base URL, allow override for regions/custom endpoints
        kwargs.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(api_key, **kwargs)
        self._invalidate_capability_cache()

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: Optional[str] = None,
    ) -> Optional[ModelCapabilities]:
        """Look up OpenAI capabilities from built-ins or the custom registry."""

        self._ensure_registry()
        builtin = super()._lookup_capabilities(canonical_name, requested_name)
        if builtin is not None:
            return builtin

        try:
            from .registries.openrouter import OpenRouterModelRegistry

            registry = OpenRouterModelRegistry()
            config = registry.get_model_config(canonical_name)

            if config and config.provider == ProviderType.OPENAI:
                return config

        except Exception as exc:  # pragma: no cover - registry failures are non-critical
            logger.debug(f"Could not resolve custom OpenAI model '{canonical_name}': {exc}")

        return None

    def _finalise_capabilities(
        self,
        capabilities: ModelCapabilities,
        canonical_name: str,
        requested_name: str,
    ) -> ModelCapabilities:
        """Ensure registry-sourced models report the correct provider type."""

        if capabilities.provider != ProviderType.OPENAI:
            capabilities.provider = ProviderType.OPENAI
        return capabilities

    def _raise_unsupported_model(self, model_name: str) -> None:
        raise ValueError(f"Unsupported OpenAI model: {model_name}")

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    # ------------------------------------------------------------------
    # Provider preferences
    # ------------------------------------------------------------------

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get OpenAI's preferred model for a given category from allowed models.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of models allowed by restrictions

        Returns:
            Preferred model name or None
        """
        from tools.models import ToolModelCategory

        if not allowed_models:
            return None

        # Helper to find first available from preference list
        def find_first(preferences: list[str]) -> Optional[str]:
            """Return first available model from preference list."""
            for model in preferences:
                if model in allowed_models:
                    return model
            return None

        if category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer models with extended thinking support
            # GPT-5.1 Codex first for coding tasks
            preferred = find_first(
                [
                    "gpt-5.1-codex",
                    "gpt-5.1",
                    "gpt-5-codex",
                    "gpt-5-pro",
                    "o3-pro",
                    "gpt-5",
                    "o3",
                ]
            )
            return preferred if preferred else allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer fast, cost-efficient models
            # GPT-5.1 models for speed, GPT-5.1-Codex after (premium pricing but cached)
            preferred = find_first(
                [
                    "gpt-5.1",
                    "gpt-5.1-codex-mini",
                    "gpt-5",
                    "gpt-5-mini",
                    "gpt-5-codex",
                    "o4-mini",
                    "o3-mini",
                ]
            )
            return preferred if preferred else allowed_models[0]

        else:  # BALANCED or default
            # Prefer balanced performance/cost models
            # Include GPT-5.1 family for latest capabilities
            preferred = find_first(
                [
                    "gpt-5.1",
                    "gpt-5.1-codex",
                    "gpt-5",
                    "gpt-5-codex",
                    "gpt-5-pro",
                    "gpt-5-mini",
                    "o4-mini",
                    "o3-mini",
                ]
            )
            return preferred if preferred else allowed_models[0]


# Load registry data at import time so dependent providers (Azure) can reuse it
OpenAIModelProvider._ensure_registry()
