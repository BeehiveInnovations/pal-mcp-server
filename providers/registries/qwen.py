"""Registry loader for Alibaba Qwen (DashScope) model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class QwenModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/qwen_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="QWEN_MODELS_CONFIG_PATH",
            default_filename="qwen_models.json",
            provider=ProviderType.QWEN,
            friendly_prefix="Qwen ({model})",
            config_path=config_path,
        )
