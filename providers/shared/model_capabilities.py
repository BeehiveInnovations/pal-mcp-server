"""Dataclass describing the feature set of a model exposed by a provider."""

import math
from dataclasses import dataclass, field
from typing import Optional

from .provider_type import ProviderType
from .temperature import RangeTemperatureConstraint, TemperatureConstraint

__all__ = ["ModelCapabilities"]


@dataclass
class ModelCapabilities:
    """Static description of what a model can do within a provider.

    Role
        Acts as the canonical record for everything the server needs to know
        about a model—its provider, token limits, feature switches, aliases,
        and temperature rules. Providers populate these objects so tools and
        higher-level services can rely on a consistent schema.

    Typical usage
        * Provider subclasses declare `MODEL_CAPABILITIES` maps containing these
          objects (for example ``OpenAIModelProvider``)
        * Helper utilities (e.g. restriction validation, alias expansion) read
          these objects to build model lists for tooling and policy enforcement
        * Tool selection logic inspects attributes such as
          ``supports_extended_thinking`` or ``context_window`` to choose an
          appropriate model for a task.
        * The ``allow_code_generation`` flag enables structured code generation
          in the chat tool for models more capable than the primary CLI.
    """

    provider: ProviderType
    model_name: str
    friendly_name: str
    intelligence_score: int = 10  # Human-curated 1–20 score reflecting general capability
    description: str = ""
    aliases: list[str] = field(default_factory=list)

    # Capacity limits / resource budgets
    context_window: int = 0
    max_output_tokens: int = 0
    max_thinking_tokens: int = 0

    # Capability flags
    supports_extended_thinking: bool = False
    supports_system_prompts: bool = True
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_images: bool = False
    supports_json_mode: bool = False
    supports_temperature: bool = True
    use_openai_response_api: bool = False
    default_reasoning_effort: Optional[str] = None
    allow_code_generation: bool = (
        False  # Enables structured code generation in chat tool for substantial implementations
    )

    # Additional attributes
    max_image_size_mb: float = 0.0  # Maximum size per individual image in MB (0 = no limit)
    max_image_count: Optional[int] = None  # Maximum number of images per request (None = no limit)
    max_total_image_size_mb: float = 0.0  # Maximum total size of all images in request in MB (0 = no limit)
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

    def get_effective_capability_rank(self) -> int:
        """Calculate the runtime capability rank from intelligence + capabilities."""

        # Human signal drives the baseline (1–20 → 5–100 after scaling)
        base_intelligence = self.intelligence_score if self.intelligence_score else 10
        base_intelligence = max(1, min(20, base_intelligence))
        score = base_intelligence * 5

        # Context window bonus with gentle diminishing returns
        ctx_bonus = 0
        ctx = max(self.context_window, 0)
        if ctx > 0:
            ctx_bonus = int(min(5, max(0.0, math.log10(ctx) - 3)))
        score += ctx_bonus

        # Output token capacity adds a small bonus
        if self.max_output_tokens >= 65_000:
            score += 2
        elif self.max_output_tokens >= 32_000:
            score += 1

        # Feature-level boosts
        if self.supports_extended_thinking:
            score += 3
        if self.supports_function_calling:
            score += 1
        if self.supports_json_mode:
            score += 1
        if self.supports_images:
            score += 1

        return max(0, min(100, score))

    @staticmethod
    def collect_aliases(model_configs: dict[str, "ModelCapabilities"]) -> dict[str, list[str]]:
        """Build a mapping of model name to aliases from capability configs."""

        return {
            base_model: capabilities.aliases
            for base_model, capabilities in model_configs.items()
            if capabilities.aliases
        }

    @staticmethod
    def collect_model_names(
        model_configs: dict[str, "ModelCapabilities"],
        *,
        include_aliases: bool = True,
        lowercase: bool = False,
        unique: bool = False,
    ) -> list[str]:
        """Build an ordered list of model names and aliases.

        Args:
            model_configs: Mapping of canonical model names to capabilities.
            include_aliases: When True, include aliases for each model.
            lowercase: When True, normalize names to lowercase.
            unique: When True, ensure each returned name appears once (after formatting).

        Returns:
            Ordered list of model names (and optionally aliases) formatted per options.
        """

        formatted_names: list[str] = []
        seen: set[str] | None = set() if unique else None

        def append_name(name: str) -> None:
            formatted = name.lower() if lowercase else name

            if seen is not None:
                if formatted in seen:
                    return
                seen.add(formatted)

            formatted_names.append(formatted)

        # Sort models by capability rank (descending) then by name for deterministic ordering
        sorted_items = sorted(
            model_configs.items(),
            key=lambda item: (-item[1].get_effective_capability_rank(), item[0]),
        )

        for base_model, capabilities in sorted_items:
            append_name(base_model)

            if include_aliases and capabilities.aliases:
                for alias in capabilities.aliases:
                    append_name(alias)

        return formatted_names
