"""OpenAI model provider implementation."""

import logging
from typing import Optional

from .base import (
    FixedTemperatureConstraint,
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class OpenAIModelProvider(OpenAICompatibleProvider):
    """Official OpenAI API provider (api.openai.com)."""

    # Model configurations
    SUPPORTED_MODELS = {
        "o3": {
            "context_window": 200_000,  # 200K tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # O3 models support vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        "o3-mini": {
            "context_window": 200_000,  # 200K tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # O3 models support vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        "o3-pro-2025-06-10": {
            "context_window": 200_000,  # 200K tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # O3 models support vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        # Aliases
        "o3-pro": "o3-pro-2025-06-10",
        "o4-mini": {
            "context_window": 200_000,  # 200K tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # O4 models support vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        "o4-mini-high": {
            "context_window": 200_000,  # 200K tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # O4 models support vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        "gpt-4.1-2025-04-14": {
            "context_window": 1_000_000,  # 1M tokens
            "supports_extended_thinking": False,
            "supports_images": True,  # GPT-4.1 supports vision
            "max_image_size_mb": 20.0,  # 20MB per OpenAI docs
        },
        # Shorthands
        "mini": "o4-mini",  # Default 'mini' to latest mini model
        "o3mini": "o3-mini",
        "o4mini": "o4-mini",
        "o4minihigh": "o4-mini-high",
        "o4minihi": "o4-mini-high",
        "gpt4.1": "gpt-4.1-2025-04-14",
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize OpenAI provider with API key."""
        # Set default OpenAI base URL, allow override for regions/custom endpoints
        kwargs.setdefault("base_url", "https://api.openai.com/v1")
        super().__init__(api_key, **kwargs)

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific OpenAI model."""
        # Resolve shorthand
        resolved_name = self._resolve_model_name(model_name)

        if resolved_name not in self.SUPPORTED_MODELS or isinstance(self.SUPPORTED_MODELS[resolved_name], str):
            raise ValueError(f"Unsupported OpenAI model: {model_name}")

        # Check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.OPENAI, resolved_name, model_name):
            raise ValueError(f"OpenAI model '{model_name}' is not allowed by restriction policy.")

        config = self.SUPPORTED_MODELS[resolved_name]

        # Define temperature constraints per model
        if resolved_name in ["o3", "o3-mini", "o3-pro", "o3-pro-2025-06-10", "o4-mini", "o4-mini-high"]:
            # O3 and O4 reasoning models only support temperature=1.0
            temp_constraint = FixedTemperatureConstraint(1.0)
        else:
            # Other OpenAI models (including GPT-4.1) support 0.0-2.0 range
            temp_constraint = RangeTemperatureConstraint(0.0, 2.0, 0.7)

        return ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name=model_name,
            friendly_name="OpenAI",
            context_window=config["context_window"],
            supports_extended_thinking=config["supports_extended_thinking"],
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_images=config.get("supports_images", False),
            max_image_size_mb=config.get("max_image_size_mb", 0.0),
            temperature_constraint=temp_constraint,
        )

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported and allowed."""
        resolved_name = self._resolve_model_name(model_name)

        # First check if model is supported
        if resolved_name not in self.SUPPORTED_MODELS or not isinstance(self.SUPPORTED_MODELS[resolved_name], dict):
            return False

        # Then check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.OPENAI, resolved_name, model_name):
            logger.debug(f"OpenAI model '{model_name}' -> '{resolved_name}' blocked by restrictions")
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
        """Generate content using OpenAI API with proper model name resolution."""
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
        # Currently no OpenAI models support extended thinking
        # This may change with future O3 models
        return False

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model shorthand to full name."""
        # Check if it's a shorthand
        shorthand_value = self.SUPPORTED_MODELS.get(model_name)
        if isinstance(shorthand_value, str):
            return shorthand_value
        return model_name
