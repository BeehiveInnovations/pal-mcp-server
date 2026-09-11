"""Requesty model registry for managing model configurations and aliases."""

from __future__ import annotations

from ..shared import ModelCapabilities, ProviderType
from .base import CAPABILITY_FIELD_NAMES, CapabilityModelRegistry


class RequestyModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/requesty_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="REQUESTY_MODELS_CONFIG_PATH",
            default_filename="requesty_models.json",
            provider=ProviderType.REQUESTY,
            friendly_prefix="Requesty ({model})",
            config_path=config_path,
        )

    def _finalise_entry(self, entry: dict) -> tuple[ModelCapabilities, dict]:
        entry.setdefault("friendly_name", f"Requesty ({entry['model_name']})")

        filtered = {k: v for k, v in entry.items() if k in CAPABILITY_FIELD_NAMES}
        filtered.setdefault("provider", ProviderType.REQUESTY)
        capability = ModelCapabilities(**filtered)
        return capability, {}
