"""Registry loader for DeepSeek model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class DeepSeekModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/deepseek_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="DEEPSEEK_MODELS_CONFIG_PATH",
            default_filename="deepseek_models.json",
            provider=ProviderType.DEEPSEEK,
            friendly_prefix="DeepSeek ({model})",
            config_path=config_path,
        )
