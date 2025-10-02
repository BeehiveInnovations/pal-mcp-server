"""X.AI (GROK) model provider implementation."""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .openai_compatible import OpenAICompatibleProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType, TemperatureConstraint

logger = logging.getLogger(__name__)


class XAIModelProvider(OpenAICompatibleProvider):
    """Integration for X.AI's GROK models exposed over an OpenAI-style API.

    Publishes capability metadata for the officially supported deployments and
    maps tool-category preferences to the appropriate GROK model.
    """

    FRIENDLY_NAME = "X.AI"

    # Model configurations using ModelCapabilities objects
    MODEL_CAPABILITIES = {
        "grok-4": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-4",
            friendly_name="X.AI (Grok 4)",
            intelligence_score=16,
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
            temperature_constraint=TemperatureConstraint.create("range"),
            description="GROK-4 (256K context) - Frontier multimodal reasoning model with advanced capabilities",
            aliases=["grok", "grok4", "grok-4"],
        ),
        "grok-3": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-3",
            friendly_name="X.AI (Grok 3)",
            intelligence_score=13,
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
            temperature_constraint=TemperatureConstraint.create("range"),
            description="GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
            aliases=["grok3"],
        ),
        "grok-3-fast": ModelCapabilities(
            provider=ProviderType.XAI,
            model_name="grok-3-fast",
            friendly_name="X.AI (Grok 3 Fast)",
            intelligence_score=12,
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
            temperature_constraint=TemperatureConstraint.create("range"),
            description="GROK-3 Fast (131K context) - Higher performance variant, faster processing but more expensive",
            aliases=["grok3fast", "grokfast", "grok3-fast"],
        ),
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize X.AI provider with API key."""
        # Set X.AI base URL
        kwargs.setdefault("base_url", "https://api.x.ai/v1")
        super().__init__(api_key, **kwargs)

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.XAI

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
