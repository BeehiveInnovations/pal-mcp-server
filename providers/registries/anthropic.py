"""Registry loader for Anthropic (Claude) model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class AnthropicModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/anthropic_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="ANTHROPIC_MODELS_CONFIG_PATH",
            default_filename="anthropic_models.json",
            provider=ProviderType.ANTHROPIC,
            friendly_prefix="Claude ({model})",
            config_path=config_path,
        )
