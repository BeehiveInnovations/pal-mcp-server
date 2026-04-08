"""Registry loader for Cerebras model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class CerebrasModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/cerebras_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="CEREBRAS_MODELS_CONFIG_PATH",
            default_filename="cerebras_models.json",
            provider=ProviderType.CEREBRAS,
            friendly_prefix="Cerebras ({model})",
            config_path=config_path,
        )
