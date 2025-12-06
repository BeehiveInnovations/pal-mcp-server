"""OpenRouter provider implementation."""

import logging

from config import OPENAI_IMAGE_DETAIL
from utils import openai_token_estimator
from utils.env import get_env

from .openai_compatible import OpenAICompatibleProvider
from .registries.openrouter import OpenRouterModelRegistry
from .shared import (
    ModelCapabilities,
    ProviderType,
    RangeTemperatureConstraint,
)


class OpenRouterProvider(OpenAICompatibleProvider):
    """Client for OpenRouter's multi-model aggregation service.

    Role
        Surface OpenRouter’s dynamic catalogue through the same interface as
        native providers so tools can reference OpenRouter models and aliases
        without special cases.

    Characteristics
        * Pulls live model definitions from :class:`OpenRouterModelRegistry`
          (aliases, provider-specific metadata, capability hints)
        * Applies alias-aware restriction checks before exposing models to the
          registry or tooling
        * Reuses :class:`OpenAICompatibleProvider` infrastructure for request
          execution so OpenRouter endpoints behave like standard OpenAI-style
          APIs.
    """

    FRIENDLY_NAME = "OpenRouter"

    # Custom headers required by OpenRouter
    DEFAULT_HEADERS = {
        "HTTP-Referer": get_env("OPENROUTER_REFERER", "https://github.com/BeehiveInnovations/pal-mcp-server")
        or "https://github.com/BeehiveInnovations/pal-mcp-server",
        "X-Title": get_env("OPENROUTER_TITLE", "PAL MCP Server") or "PAL MCP Server",
    }

    # Model registry for managing configurations and aliases
    _registry: OpenRouterModelRegistry | None = None

    def __init__(self, api_key: str, **kwargs):
        """Initialize OpenRouter provider.

        Args:
            api_key: OpenRouter API key
            **kwargs: Additional configuration
        """
        base_url = "https://openrouter.ai/api/v1"
        self._alias_cache: dict[str, str] = {}
        super().__init__(api_key, base_url=base_url, **kwargs)

        # Initialize model registry
        if OpenRouterProvider._registry is None:
            OpenRouterProvider._registry = OpenRouterModelRegistry()
            # Log loaded models and aliases only on first load
            models = self._registry.list_models()
            aliases = self._registry.list_aliases()
            logging.info(f"OpenRouter loaded {len(models)} models with {len(aliases)} aliases")

    # ------------------------------------------------------------------
    # Capability surface
    # ------------------------------------------------------------------

    def _lookup_capabilities(
        self,
        canonical_name: str,
        requested_name: str | None = None,
    ) -> ModelCapabilities | None:
        """Fetch OpenRouter capabilities from the registry or build a generic fallback."""

        capabilities = self._registry.get_capabilities(canonical_name)
        if capabilities:
            return capabilities

        base_identifier = canonical_name.split(":", 1)[0]
        if "/" in base_identifier:
            logging.debug(
                "Using generic OpenRouter capabilities for %s (provider/model format detected)", canonical_name
            )
            generic = ModelCapabilities(
                provider=ProviderType.OPENROUTER,
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
            "Rejecting unknown OpenRouter model '%s' (no provider prefix); requires explicit configuration",
            canonical_name,
        )
        return None

    # ------------------------------------------------------------------
    # Provider identity
    # ------------------------------------------------------------------

    def get_provider_type(self) -> ProviderType:
        """Identify this provider for restrictions and logging."""
        return ProviderType.OPENROUTER

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
        """Return formatted OpenRouter model names, respecting alias-aware restrictions."""

        if not self._registry:
            return []

        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        allowed_configs: dict[str, ModelCapabilities] = {}

        for model_name in self._registry.list_models():
            config = self._registry.resolve(model_name)
            if not config:
                continue

            # Custom models belong to CustomProvider; skip them here so the two
            # providers don't race over the same registrations (important for tests
            # that stub the registry with minimal objects lacking attrs).
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
        # Only return the canonical model names that are actually allowed
        actual_include_aliases = include_aliases and not respect_restrictions

        return ModelCapabilities.collect_model_names(
            allowed_configs,
            include_aliases=actual_include_aliases,
            lowercase=lowercase,
            unique=unique,
        )

    # ------------------------------------------------------------------
    # Registry helpers
    # ------------------------------------------------------------------

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve aliases defined in the OpenRouter registry."""

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
        """Expose registry-backed OpenRouter capabilities."""

        if not self._registry:
            return {}

        capabilities: dict[str, ModelCapabilities] = {}
        for model_name in self._registry.list_models():
            config = self._registry.resolve(model_name)
            if not config:
                continue

            # See note in list_models: respect the CustomProvider boundary.
            if config.provider == ProviderType.CUSTOM:
                continue

            capabilities[model_name] = config
        return capabilities

    # ------------------------------------------------------------------
    # Token estimation with multi-provider routing
    # ------------------------------------------------------------------

    def _calculate_text_tokens(self, model_name: str, content: str) -> int:
        """Route text token calculation to the appropriate provider estimator.

        For OpenAI models (openai/*, gpt-*, o3*, o4*), uses openai_token_estimator.
        For other models, falls back to simple character-based estimation.

        Args:
            model_name: Model name to calculate tokens for
            content: Text content to count tokens for

        Returns:
            Estimated token count
        """
        if openai_token_estimator.is_openai_model(model_name):
            return openai_token_estimator.calculate_text_tokens(model_name, content)

        # Fallback for non-OpenAI models
        return len(content) // 4

    def _calculate_image_tokens(self, file_path: str, model_name: str, detail: str = None) -> int:
        """Route image token calculation to the appropriate provider estimator.

        For OpenAI models, uses accurate openai_token_estimator with tile-based calculation.
        For other models, uses conservative fallback estimation.

        Args:
            file_path: Path to the image file
            model_name: Model name to estimate tokens for
            detail: Detail level ("LOW", "HIGH", or "AUTO").
                    If None, uses module-level OPENAI_IMAGE_DETAIL configuration (PR 302 pattern)

        Returns:
            Estimated token count

        Raises:
            ValueError: If file cannot be accessed
        """
        if openai_token_estimator.is_openai_model(model_name):
            # Use explicit parameter or fall back to module-level config (Gemini PR 302 pattern)
            detail_value = detail if detail is not None else OPENAI_IMAGE_DETAIL
            return openai_token_estimator.estimate_image_tokens(file_path, model_name, detail_value)

        # Fallback for non-OpenAI models: conservative fixed estimate
        return 1000

    def estimate_tokens_for_files(self, model_name: str, files: list[dict], image_detail: str = None) -> int:
        """Route file token estimation to the appropriate provider estimator.

        For OpenAI models, uses accurate openai_token_estimator.
        For other models, uses conservative file-size-based estimation.

        Current Limitations:
        - OpenRouter supports PDF through /chat/completions using type:"file" format
        - However, programmatic PDF support via files parameter is not yet implemented
        - PDF token estimation is available but actual PDF API calls require manual formatting
        - Images are fully supported via the standard image format

        Args:
            model_name: Model name to estimate tokens for
            files: List of file dicts with 'path' and 'mime_type' keys
            image_detail: Detail level for images ("LOW", "HIGH", or "AUTO").
                          If None, uses module-level OPENAI_IMAGE_DETAIL configuration (PR 302 pattern)

        Returns:
            Estimated token count

        Raises:
            UnsupportedContentTypeError: If PDF files are included (not yet supported)
        """
        if not files:
            return 0

        if openai_token_estimator.is_openai_model(model_name):
            # Use explicit parameter or fall back to module-level config (Gemini PR 302 pattern)
            detail = image_detail if image_detail is not None else OPENAI_IMAGE_DETAIL

            # Note: use_responses_api=False because OpenRouter doesn't use /responses endpoint
            # This will raise UnsupportedContentTypeError for PDFs, which is correct behavior
            # until we implement OpenRouter's type:"file" format
            return openai_token_estimator.estimate_tokens_for_files(model_name, files, detail, use_responses_api=False)

        # Fallback for non-OpenAI models: use generic file estimation
        from utils.file_utils import estimate_file_tokens

        total = 0
        for file_info in files:
            file_path = file_info.get("path", "")
            if file_path:
                try:
                    total += estimate_file_tokens(file_path)
                except Exception as e:
                    logging.warning("Failed to estimate tokens for %s: %s, using fallback", file_path, e, exc_info=True)
                    total += 1000  # Conservative fallback
        return total
