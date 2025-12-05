"""Registry loader for Zhipu AI provider capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class ZhipuModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/zhipu_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="ZHIPU_MODELS_CONFIG_PATH",
            default_filename="zhipu_models.json",
            provider=ProviderType.ZHIPU,
            friendly_prefix="GLM ({model})",
            config_path=config_path,
        )
