"""Registry loader for Zhipu GLM (Z.ai) model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class ZaiModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/zai_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="ZAI_MODELS_CONFIG_PATH",
            default_filename="zai_models.json",
            provider=ProviderType.ZAI,
            friendly_prefix="Z.ai ({model})",
            config_path=config_path,
        )
