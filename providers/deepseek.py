"""DeepSeek model provider implementation."""

import logging
from typing import TYPE_CHECKING, ClassVar, Optional

from .openai_compatible import OpenAICompatibleProvider
from .shared import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    TemperatureConstraint,
)

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

logger = logging.getLogger(__name__)


class DeepSeekModelProvider(OpenAICompatibleProvider):
    """Provider for DeepSeek's OpenAI-compatible API."""

    FRIENDLY_NAME = "DeepSeek"

    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {
        "deepseek-chat": ModelCapabilities(
            provider=ProviderType.DEEPSEEK,
            model_name="deepseek-chat",
            friendly_name="DeepSeek (Chat)",
            context_window=128_000,
            max_output_tokens=16_000,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("range"),
            description="DeepSeek V3.1 chat model (non-reasoning mode)",
            aliases=["deepseek", "chat"],
        ),
        "deepseek-reasoner": ModelCapabilities(
            provider=ProviderType.DEEPSEEK,
            model_name="deepseek-reasoner",
            friendly_name="DeepSeek (Reasoner)",
            context_window=128_000,
            max_output_tokens=16_000,
            supports_extended_thinking=True,
            max_thinking_tokens=16_000,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=False,
            supports_temperature=True,
            temperature_constraint=TemperatureConstraint.create("range"),
            description="DeepSeek V3.1 reasoning model with thinking tokens",
            aliases=["reasoner"],
        ),
    }

    def __init__(self, api_key: str, **kwargs):
        """Initialize DeepSeek provider with API key and optional settings."""
        kwargs.setdefault("base_url", "https://api.deepseek.com")
        super().__init__(api_key, **kwargs)

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.DEEPSEEK

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using DeepSeek API with alias resolution."""
        resolved_model_name = self._resolve_model_name(model_name)
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
        resolved = self._resolve_model_name(model_name)
        capabilities = self.MODEL_CAPABILITIES.get(resolved)
        return bool(capabilities and capabilities.supports_extended_thinking)

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Simple preference for DeepSeek models based on category."""
        if not allowed_models:
            return None
        # Currently no special preferences beyond first allowed model
        return allowed_models[0]
