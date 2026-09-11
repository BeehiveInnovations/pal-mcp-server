"""Requesty provider implementation."""

import logging

from utils.env import get_env

from .openai_compatible import OpenAICompatibleProvider
from .registries.requesty import RequestyModelRegistry
from .shared import (
    ModelCapabilities,
    ProviderType,
    RangeTemperatureConstraint,
)


class RequestyProvider(OpenAICompatibleProvider):
    """Client for Requesty's OpenAI-compatible LLM router.

    Role
        Surface Requesty's model catalogue through the same interface as
        native providers so tools can reference Requesty models and aliases
        without special cases.

    Characteristics
        * Pulls model definitions from :class:`RequestyModelRegistry`
          (aliases, provider-specific metadata, capability hints)
        * Applies alias-aware restriction checks before exposing models to the
          registry or tooling
        * Reuses :class:`OpenAICompatibleProvider` infrastructure for request
          execution so Requesty endpoints behave like standard OpenAI-style
          APIs.
    """

    FRIENDLY_NAME = "Requesty"

    # Optional attribution headers (same shape as OpenRouter's)
    DEFAULT_HEADERS = {
        "HTTP-Referer": get_env("REQUESTY_REFERER", "https://github.com/BeehiveInnovations/pal-mcp-server")
        or "https://github.com/BeehiveInnovations/pal-mcp-server",
        "X-Title": get_env("REQUESTY_TITLE", "PAL MCP Server") or "PAL MCP Server",
    }

    # Model registry for managing configurations and aliases
    _registry: RequestyModelRegistry | None = None

    def __init__(self, api_key: str, **kwargs):
        """Initialize Requesty provider.

        Args:
            api_key: Requesty API key
            **kwargs: Additional configuration
        """
        base_url = get_env("REQUESTY_BASE_URL", "https://router.requesty.ai/v1") or "https://router.requesty.ai/v1"
        self._alias_cache: dict[str, str] = {}
        super().__init__(api_key, base_url=base_url, **kwargs)

        # Initialize model registry
        if RequestyProvider._registry is None:
            RequestyProvider._registry = RequestyModelRegistry()
            # Log loaded models and aliases only on first load
            models = self._registry.list_models()
            aliases = self._registry.list_aliases()
            logging.info(f"Requesty loaded {len(models)} models with {len(aliases)} aliases")

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: str | None = None,
    ) -> ModelCapabilities | None:
        """Fetch Requesty capabilities from the registry or build a generic fallback."""

        capabilities = self._registry.get_capabilities(canonical_name)
        if capabilities:
            return capabilities

        base_identifier = canonical_name.split(":", 1)[0]
        if "/" in base_identifier:
            logging.debug("Using generic Requesty capabilities for %s (provider/model format detected)", canonical_name)
            generic = ModelCapabilities(
                provider=ProviderType.REQUESTY,
                model_name=canonical_name,
                friendly_name=self.FRIENDLY_NAME,
                intelligence_score=9,
                context_window=32_768,
                max_output_tokens=32_768,
                supports_extended_thinking=False,
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=False,
                temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 1.0),
            )
            generic._is_generic = True
            return generic

        logging.debug(
            "Rejecting unknown Requesty model '%s' (no provider prefix); requires explicit configuration",
            canonical_name,
        )
        return None

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    def get_provider_type(self) -> ProviderType:
        """Identify this provider for restrictions and logging."""
        return ProviderType.REQUESTY

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    def list_models(
        self,
        *,
        respect_restrictions: bool = True,
        include_aliases: bool = True,
        lowercase: bool = False,
        unique: bool = False,
    ) -> list[str]:
        """Return formatted Requesty model names, respecting alias-aware restrictions."""

        if not self._registry:
            return []

        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        allowed_configs: dict[str, ModelCapabilities] = {}

        for model_name in self._registry.list_models():
            config = self._registry.resolve(model_name)
            if not config:
                continue

            if config.provider == ProviderType.CUSTOM:
                continue

            if restriction_service:
                allowed = restriction_service.is_allowed(self.get_provider_type(), model_name)

                if not allowed and config.aliases:
                    for alias in config.aliases:
                        if restriction_service.is_allowed(self.get_provider_type(), alias):
                            allowed = True
                            break

                if not allowed:
                    continue

            allowed_configs[model_name] = config

        if not allowed_configs:
            return []

        # When restrictions are in place, don't include aliases to avoid confusion
        actual_include_aliases = include_aliases and not respect_restrictions

        return ModelCapabilities.collect_model_names(
            allowed_configs,
            include_aliases=actual_include_aliases,
            lowercase=lowercase,
            unique=unique,
        )

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve aliases defined in the Requesty registry."""

        cache_key = model_name.lower()
        if cache_key in self._alias_cache:
            return self._alias_cache[cache_key]

        config = self._registry.resolve(model_name)
        if config:
            if config.model_name != model_name:
                logging.debug("Resolved model alias '%s' to '%s'", model_name, config.model_name)
            resolved = config.model_name
            self._alias_cache[cache_key] = resolved
            self._alias_cache.setdefault(resolved.lower(), resolved)
            return resolved

        logging.debug(f"Model '{model_name}' not found in registry, using as-is")
        self._alias_cache[cache_key] = model_name
        return model_name

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Expose registry-backed Requesty capabilities."""

        if not self._registry:
            return {}

        capabilities: dict[str, ModelCapabilities] = {}
        for model_name in self._registry.list_models():
            config = self._registry.resolve(model_name)
            if not config:
                continue

            if config.provider == ProviderType.CUSTOM:
                continue

            capabilities[model_name] = config
        return capabilities
