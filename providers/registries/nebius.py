"""Registry loader for Nebius Token Factory model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class NebiusModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/nebius_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="NEBIUS_MODELS_CONFIG_PATH",
            default_filename="nebius_models.json",
            provider=ProviderType.NEBIUS,
            friendly_prefix="Nebius ({model})",
            config_path=config_path,
        )
