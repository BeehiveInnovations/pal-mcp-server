"""X.AI (GROK) model provider implementation."""

import logging
from typing import Optional

from .base import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class XAIModelProvider(OpenAICompatibleProvider):
    """X.AI GROK API provider (api.x.ai)."""

    FRIENDLY_NAME = "X.AI"

    # Model configurations
    SUPPORTED_MODELS = {
        "grok-3": {
            "context_window": 131_072,  # 131K tokens
            "supports_extended_thinking": False,
        },
        "grok-3-fast": {
            "context_window": 131_072,  # 131K tokens
            "supports_extended_thinking": False,
        },
        # Shorthands for convenience
        "grok": "grok-3",  # Default to grok-3
        "grok3": "grok-3",
        "grok3fast": "grok-3-fast",
        "grokfast": "grok-3-fast",
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize X.AI provider with API key."""
        # Set X.AI base URL
        kwargs.setdefault("base_url", "https://api.x.ai/v1")
        super().__init__(api_key, **kwargs)

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific X.AI model."""
        # Resolve shorthand
        resolved_name = self._resolve_model_name(model_name)

        if resolved_name not in self.SUPPORTED_MODELS or isinstance(self.SUPPORTED_MODELS[resolved_name], str):
            raise ValueError(f"Unsupported X.AI model: {model_name}")

        # Check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.XAI, resolved_name, model_name):
            raise ValueError(f"X.AI model '{model_name}' is not allowed by restriction policy.")

        config = self.SUPPORTED_MODELS[resolved_name]

        # Define temperature constraints for GROK models
        # GROK supports the standard OpenAI temperature range
        temp_constraint = RangeTemperatureConstraint(0.0, 2.0, 0.7)

        return ModelCapabilities(
            provider=ProviderType.XAI,
            model_name=resolved_name,
            friendly_name=self.FRIENDLY_NAME,
            context_window=config["context_window"],
            supports_extended_thinking=config["supports_extended_thinking"],
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            temperature_constraint=temp_constraint,
        )

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.XAI

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported and allowed."""
        resolved_name = self._resolve_model_name(model_name)

        # First check if model is supported
        if resolved_name not in self.SUPPORTED_MODELS or not isinstance(self.SUPPORTED_MODELS[resolved_name], dict):
            return False

        # Then check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.XAI, resolved_name, model_name):
            logger.debug(f"X.AI model '{model_name}' -> '{resolved_name}' blocked by restrictions")
            return False

        return True

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using X.AI API with proper model name resolution."""
        # Resolve model alias before making API call
        resolved_model_name = self._resolve_model_name(model_name)

        # Call parent implementation with resolved model name
        return super().generate_content(
            prompt=prompt,
            model_name=resolved_model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode."""
        # Currently GROK models do not support extended thinking
        # This may change with future GROK model releases
        return False

    def list_models(self, respect_restrictions: bool = True) -> list[str]:
        """Return a list of model names supported by this provider.

        Args:
            respect_restrictions: Whether to apply provider-specific restriction logic.

        Returns:
            List of model names available from this provider
        """
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        models = []

        for model_name, config in self.SUPPORTED_MODELS.items():
            # Handle both base models (dict configs) and aliases (string values)
            if isinstance(config, str):
                # This is an alias - check if the target model would be allowed
                target_model = config
                if restriction_service and not restriction_service.is_allowed(self.get_provider_type(), target_model):
                    continue
                # Allow the alias
                models.append(model_name)
            else:
                # This is a base model with config dict
                # Check restrictions if enabled
                if restriction_service and not restriction_service.is_allowed(self.get_provider_type(), model_name):
                    continue
                models.append(model_name)

        return models

    def list_all_known_models(self) -> list[str]:
        """Return all model names known by this provider, including alias targets.

        Returns:
            List of all model names and alias targets known by this provider
        """
        all_models = set()

        for model_name, config in self.SUPPORTED_MODELS.items():
            # Add the model name itself
            all_models.add(model_name.lower())

            # If it's an alias (string value), add the target model too
            if isinstance(config, str):
                all_models.add(config.lower())

        return list(all_models)

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model shorthand to full name."""
        # Check if it's a shorthand
        shorthand_value = self.SUPPORTED_MODELS.get(model_name)
        if isinstance(shorthand_value, str):
            return shorthand_value
        return model_name
