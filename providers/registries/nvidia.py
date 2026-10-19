"""Registry loader for NVIDIA (Nemotron) model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class NvidiaModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/nvidia_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="NVIDIA_MODELS_CONFIG_PATH",
            default_filename="nvidia_models.json",
            provider=ProviderType.NVIDIA,
            friendly_prefix="NVIDIA ({model})",
            config_path=config_path,
        )
