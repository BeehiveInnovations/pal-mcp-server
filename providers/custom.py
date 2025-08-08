"""Custom API provider implementation."""

import logging
import os
from typing import Optional

from .base import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)
from .openai_compatible import OpenAICompatibleProvider
from .openrouter_registry import OpenRouterModelRegistry


class CustomProvider(OpenAICompatibleProvider):
    """Custom API provider for local models.

    Supports local inference servers like Ollama, vLLM, LM Studio,
    and any OpenAI-compatible API endpoint.
    """

    FRIENDLY_NAME = "Custom API"

    # Model registry for managing configurations and aliases (shared with OpenRouter)
    _registry: Optional[OpenRouterModelRegistry] = None

    def __init__(self, api_key: str = "", base_url: str = "", **kwargs):
        """Initialize Custom provider for local/self-hosted models.

        This provider supports any OpenAI-compatible API endpoint including:
        - Ollama (typically no API key required)
        - vLLM (may require API key)
        - LM Studio (may require API key)
        - Text Generation WebUI (may require API key)
        - Enterprise/self-hosted APIs (typically require API key)

        Args:
            api_key: API key for the custom endpoint. Can be empty string for
                    providers that don't require authentication (like Ollama).
                    Falls back to CUSTOM_API_KEY environment variable if not provided.
            base_url: Base URL for the custom API endpoint (e.g., 'http://localhost:11434/v1').
                     Falls back to CUSTOM_API_URL environment variable if not provided.
            **kwargs: Additional configuration passed to parent OpenAI-compatible provider

        Raises:
            ValueError: If no base_url is provided via parameter or environment variable
        """
        # Fall back to environment variables only if not provided
        if not base_url:
            base_url = os.getenv("CUSTOM_API_URL", "")
        if not api_key:
            api_key = os.getenv("CUSTOM_API_KEY", "")

        if not base_url:
            raise ValueError(
                "Custom API URL must be provided via base_url parameter or CUSTOM_API_URL environment variable"
            )

        # For Ollama and other providers that don't require authentication,
        # set a dummy API key to avoid OpenAI client header issues
        if not api_key:
            api_key = "dummy-key-for-unauthenticated-endpoint"
            logging.debug("Using dummy API key for unauthenticated custom endpoint")

        logging.info(f"Initializing Custom provider with endpoint: {base_url}")

        super().__init__(api_key, base_url=base_url, **kwargs)

        # Initialize model registry (shared with OpenRouter for consistent aliases)
        if CustomProvider._registry is None:
            CustomProvider._registry = OpenRouterModelRegistry()
            # Log loaded models and aliases only on first load
            models = self._registry.list_models()
            aliases = self._registry.list_aliases()
            logging.info(f"Custom provider loaded {len(models)} models with {len(aliases)} aliases")

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model aliases to actual model names.

        For Ollama-style models, strips version tags (e.g., 'llama3.2:latest' -> 'llama3.2')
        since the base model name is what's typically used in API calls.

        Args:
            model_name: Input model name or alias

        Returns:
            Resolved model name with version tags stripped if applicable
        """
        # First, try to resolve through registry as-is
        config = self._registry.resolve(model_name)

        if config:
            if config.model_name != model_name:
                logging.info(f"Resolved model alias '{model_name}' to '{config.model_name}'")
            return config.model_name
        else:
            # If not found in registry, handle version tags for local models
            # Strip version tags (anything after ':') for Ollama-style models
            if ":" in model_name:
                base_model = model_name.split(":")[0]
                logging.debug(f"Stripped version tag from '{model_name}' -> '{base_model}'")

                # Try to resolve the base model through registry
                base_config = self._registry.resolve(base_model)
                if base_config:
                    logging.info(f"Resolved base model '{base_model}' to '{base_config.model_name}'")
                    return base_config.model_name
                else:
                    return base_model
            else:
                # If not found in registry and no version tag, return as-is
                logging.debug(f"Model '{model_name}' not found in registry, using as-is")
                return model_name

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a custom model.

        Args:
            model_name: Name of the model (or alias)

        Returns:
            ModelCapabilities from registry or generic defaults
        """
        # Try to get from registry first
        capabilities = self._registry.get_capabilities(model_name)

        if capabilities:
            # Check if this is an OpenRouter model and apply restrictions
            config = self._registry.resolve(model_name)
            if config and not config.is_custom:
                # This is an OpenRouter model, check restrictions
                from utils.model_restrictions import get_restriction_service

                restriction_service = get_restriction_service()
                if not restriction_service.is_allowed(ProviderType.OPENROUTER, config.model_name, model_name):
                    raise ValueError(f"OpenRouter model '{model_name}' is not allowed by restriction policy.")

                # Update provider type to OPENROUTER for OpenRouter models
                capabilities.provider = ProviderType.OPENROUTER
            else:
                # Update provider type to CUSTOM for local custom models
                capabilities.provider = ProviderType.CUSTOM
            return capabilities
        else:
            # Resolve any potential aliases and create generic capabilities
            resolved_name = self._resolve_model_name(model_name)

            logging.debug(
                f"Using generic capabilities for '{resolved_name}' via Custom API. "
                "Consider adding to custom_models.json for specific capabilities."
            )

            # Create generic capabilities with conservative defaults
            capabilities = ModelCapabilities(
                provider=ProviderType.CUSTOM,
                model_name=resolved_name,
                friendly_name=f"{self.FRIENDLY_NAME} ({resolved_name})",
                context_window=32_768,  # Conservative default
                max_output_tokens=32_768,  # Conservative default max output
                supports_extended_thinking=False,  # Most custom models don't support this
                supports_system_prompts=True,
                supports_streaming=True,
                supports_function_calling=False,  # Conservative default
                supports_temperature=True,  # Most custom models accept temperature parameter
                temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
            )

            # Mark as generic for validation purposes
            capabilities._is_generic = True

            return capabilities

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.CUSTOM

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is allowed.

        For custom endpoints, only accept models that are explicitly intended for
        local/custom usage. This provider should NOT handle OpenRouter or cloud models.

        Args:
            model_name: Model name to validate

        Returns:
            True if model is intended for custom/local endpoint
        """
        # logging.debug(f"Custom provider validating model: '{model_name}'")

        # Try to resolve through registry first
        config = self._registry.resolve(model_name)
        if config:
            model_id = config.model_name
            # Use explicit is_custom flag for clean validation
            if config.is_custom:
                logging.debug(f"... [Custom] Model '{model_name}' -> '{model_id}' validated via registry")
                return True
            else:
                # This is a cloud/OpenRouter model - CustomProvider should NOT handle these
                # Let OpenRouter provider handle them instead
                # logging.debug(f"... [Custom] Model '{model_name}' -> '{model_id}' not custom (defer to OpenRouter)")
                return False

        # Handle version tags for unknown models (e.g., "my-model:latest")
        clean_model_name = model_name
        if ":" in model_name:
            clean_model_name = model_name.split(":")[0]
            logging.debug(f"Stripped version tag from '{model_name}' -> '{clean_model_name}'")
            # Try to resolve the clean name
            config = self._registry.resolve(clean_model_name)
            if config:
                return self.validate_model_name(clean_model_name)  # Recursively validate clean name

        # For unknown models (not in registry), only accept if they look like local models
        # This maintains backward compatibility for custom models not yet in the registry

        # Accept models with explicit local indicators in the name
        if any(indicator in clean_model_name.lower() for indicator in ["local", "ollama", "vllm", "lmstudio"]):
            logging.debug(f"Model '{clean_model_name}' validated via local indicators")
            return True

        # Accept simple model names without vendor prefix (likely local/custom models)
        if "/" not in clean_model_name:
            logging.debug(f"Model '{clean_model_name}' validated as potential local model (no vendor prefix)")
            return True

        # Reject everything else (likely cloud models not in registry)
        logging.debug(f"Model '{model_name}' rejected by custom provider (appears to be cloud model)")
        return False

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the custom API.

        Args:
            prompt: User prompt to send to the model
            model_name: Name of the model to use
            system_prompt: Optional system prompt for model behavior
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with generated content and metadata
        """
        # Resolve model alias to actual model name
        resolved_model = self._resolve_model_name(model_name)

        # Call parent method with resolved model name
        return super().generate_content(
            prompt=prompt,
            model_name=resolved_model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode.

        Args:
            model_name: Model to check

        Returns:
            True if model supports thinking mode, False otherwise
        """
        # Check if model is in registry
        config = self._registry.resolve(model_name) if self._registry else None
        if config and config.is_custom:
            # Trust the config from custom_models.json
            return config.supports_extended_thinking

        # Default to False for unknown models
        return False

    def get_model_configurations(self) -> dict[str, ModelCapabilities]:
        """Get model configurations from the registry.

        For CustomProvider, we convert registry configurations to ModelCapabilities objects.

        Returns:
            Dictionary mapping model names to their ModelCapabilities objects
        """

        configs = {}

        if self._registry:
            # Get all models from registry
            for model_name in self._registry.list_models():
                # Only include custom models that this provider validates
                if self.validate_model_name(model_name):
                    config = self._registry.resolve(model_name)
                    if config and config.is_custom:
                        # Use ModelCapabilities directly from registry
                        configs[model_name] = config

        return configs

    def get_all_model_aliases(self) -> dict[str, list[str]]:
        """Get all model aliases from the registry.

        Returns:
            Dictionary mapping model names to their list of aliases
        """
        # Since aliases are now included in the configurations,
        # we can use the base class implementation
        return super().get_all_model_aliases()
