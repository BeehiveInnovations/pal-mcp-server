"""Registry loader for MiniMax model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class MiniMaxModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/minimax_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="MINIMAX_MODELS_CONFIG_PATH",
            default_filename="minimax_models.json",
            provider=ProviderType.MINIMAX,
            friendly_prefix="MiniMax ({model})",
            config_path=config_path,
        )
