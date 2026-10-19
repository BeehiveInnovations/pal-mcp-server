"""Registry loader for Moonshot Kimi model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class MoonshotModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/moonshot_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="MOONSHOT_MODELS_CONFIG_PATH",
            default_filename="moonshot_models.json",
            provider=ProviderType.MOONSHOT,
            friendly_prefix="Moonshot ({model})",
            config_path=config_path,
        )
