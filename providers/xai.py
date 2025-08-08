"""X.AI (GROK) model provider implementation."""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .base import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class XAIModelProvider(OpenAICompatibleProvider):
    """X.AI GROK API provider (api.x.ai)."""

    FRIENDLY_NAME = "X.AI"

    # Model configurations using ModelCapabilities objects
    SUPPORTED_MODELS = {
        "grok-4": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-4",
            friendly_name="X.AI (Grok 4)",
            context_window=256_000,  # 256K tokens
            max_output_tokens=256_000,  # 256K tokens max output
            supports_extended_thinking=True,  # Grok-4 supports reasoning mode
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,  # Function calling supported
            supports_json_mode=True,  # Structured outputs supported
            supports_images=True,  # Multimodal capabilities
            max_image_size_mb=20.0,  # Standard image size limit
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="GROK-4 (256K context) - Frontier multimodal reasoning model with advanced capabilities",
            aliases=["grok", "grok4", "grok-4"],
        ),
        "grok-3": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-3",
            friendly_name="X.AI (Grok 3)",
            context_window=131_072,  # 131K tokens
            max_output_tokens=131072,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=False,  # Assuming GROK doesn't have JSON mode yet
            supports_images=False,  # Assuming GROK is text-only for now
            max_image_size_mb=0.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
            aliases=["grok3"],
        ),
        "grok-3-fast": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-3-fast",
            friendly_name="X.AI (Grok 3 Fast)",
            context_window=131_072,  # 131K tokens
            max_output_tokens=131072,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=False,  # Assuming GROK doesn't have JSON mode yet
            supports_images=False,  # Assuming GROK is text-only for now
            max_image_size_mb=0.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="GROK-3 Fast (131K context) - Higher performance variant, faster processing but more expensive",
            aliases=["grok3fast", "grokfast", "grok3-fast"],
        ),
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

        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported X.AI model: {model_name}")

        # Check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.XAI, resolved_name, model_name):
            raise ValueError(f"X.AI model '{model_name}' is not allowed by restriction policy.")

        # Return the ModelCapabilities object directly from SUPPORTED_MODELS
        return self.SUPPORTED_MODELS[resolved_name]

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.XAI

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported and allowed."""
        resolved_name = self._resolve_model_name(model_name)

        # First check if model is supported
        if resolved_name not in self.SUPPORTED_MODELS:
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
        temperature: float = 0.3,
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
        resolved_name = self._resolve_model_name(model_name)
        capabilities = self.SUPPORTED_MODELS.get(resolved_name)
        if capabilities:
            return capabilities.supports_extended_thinking
        return False

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
            # Prefer GROK-4 for advanced reasoning with thinking mode
            if "grok-4" in allowed_models:
                return "grok-4"
            elif "grok-3" in allowed_models:
                return "grok-3"
            # Fall back to any available model
            return allowed_models[0]

        elif category == ToolModelCategory.FAST_RESPONSE:
            # Prefer GROK-3-Fast for speed, then GROK-4
            if "grok-3-fast" in allowed_models:
                return "grok-3-fast"
            elif "grok-4" in allowed_models:
                return "grok-4"
            # Fall back to any available model
            return allowed_models[0]

        else:  # BALANCED or default
            # Prefer GROK-4 for balanced use (best overall capabilities)
            if "grok-4" in allowed_models:
                return "grok-4"
            elif "grok-3" in allowed_models:
                return "grok-3"
            elif "grok-3-fast" in allowed_models:
                return "grok-3-fast"
            # Fall back to any available model
            return allowed_models[0]
