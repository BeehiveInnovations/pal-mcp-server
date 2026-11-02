"""Registry loader for llm.buzz model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class LLMBuzzModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/llmbuzz_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="LLMBUZZ_MODELS_CONFIG_PATH",
            default_filename="llmbuzz_models.json",
            provider=ProviderType.LLMBUZZ,
            friendly_prefix="llm.buzz ({model})",
            config_path=config_path,
        )
