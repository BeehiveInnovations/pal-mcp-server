"""OpenRouter model registry for managing model configurations and aliases."""

from __future__ import annotations

from ..shared import ModelCapabilities, ProviderType
from .base import CAPABILITY_FIELD_NAMES, CapabilityModelRegistry


class OpenRouterModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/openrouter_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="OPENROUTER_MODELS_CONFIG_PATH",
            default_filename="openrouter_models.json",
            provider=ProviderType.OPENROUTER,
            friendly_prefix="OpenRouter ({model})",
            config_path=config_path,
        )

    def _extra_keys(self) -> set[str]:
        """Allow metadata fields for image limits documentation."""
        return {
            "_limits_source",  # Official documentation URL
            "_limits_verified",  # Date when limits were verified
            "_limits_note",  # Additional notes about limits
        }

    def _finalise_entry(self, entry: dict) -> tuple[ModelCapabilities, dict]:
        provider_override = entry.get("provider")
        if isinstance(provider_override, str):
            entry_provider = ProviderType(provider_override.lower())
        elif isinstance(provider_override, ProviderType):
            entry_provider = provider_override
        else:
            entry_provider = ProviderType.OPENROUTER

        if entry_provider == ProviderType.CUSTOM:
            entry.setdefault("friendly_name", f"Custom ({entry['model_name']})")
        else:
            entry.setdefault("friendly_name", f"OpenRouter ({entry['model_name']})")

        filtered = {k: v for k, v in entry.items() if k in CAPABILITY_FIELD_NAMES}
        filtered.setdefault("provider", entry_provider)
        capability = ModelCapabilities(**filtered)
        return capability, {}
