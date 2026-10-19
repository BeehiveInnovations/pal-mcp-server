"""Registry loader for Mistral model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class MistralModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/mistral_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="MISTRAL_MODELS_CONFIG_PATH",
            default_filename="mistral_models.json",
            provider=ProviderType.MISTRAL,
            friendly_prefix="Mistral ({model})",
            config_path=config_path,
        )
