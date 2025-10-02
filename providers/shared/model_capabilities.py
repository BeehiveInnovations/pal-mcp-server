"""Dataclass describing the feature set of a model exposed by a provider."""

from dataclasses import dataclass, field
from typing import Optional

from .provider_type import ProviderType
from .temperature import RangeTemperatureConstraint, TemperatureConstraint

__all__ = ["ModelCapabilities"]


@dataclass
class ModelCapabilities:
    """Static capabilities and constraints for a provider-managed model."""

    provider: ProviderType
    model_name: str
    friendly_name: str
    context_window: int
    max_output_tokens: int
    supports_extended_thinking: bool = False
    supports_system_prompts: bool = True
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_images: bool = False
    max_image_size_mb: float = 0.0
    supports_temperature: bool = True
    description: str = ""
    aliases: list[str] = field(default_factory=list)
    supports_json_mode: bool = False
    max_thinking_tokens: int = 0
    is_custom: bool = False
    temperature_constraint: TemperatureConstraint = field(
        default_factory=lambda: RangeTemperatureConstraint(0.0, 2.0, 0.3)
    )

    def get_effective_temperature(self, requested_temperature: float) -> Optional[float]:
        """Return the temperature that should be sent to the provider.

        Models that do not support temperature return ``None`` so that callers
        can omit the parameter entirely.  For supported models, the configured
        constraint clamps the requested value into a provider-safe range.
        """

        if not self.supports_temperature:
            return None

        return self.temperature_constraint.get_corrected_value(requested_temperature)

    @staticmethod
    def collect_aliases(model_configs: dict[str, "ModelCapabilities"]) -> dict[str, list[str]]:
        """Build a mapping of model name to aliases from capability configs."""

        return {
            base_model: capabilities.aliases
            for base_model, capabilities in model_configs.items()
            if capabilities.aliases
        }
