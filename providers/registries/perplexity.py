"""Registry loader for Perplexity model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class PerplexityModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/perplexity_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="PERPLEXITY_MODELS_CONFIG_PATH",
            default_filename="perplexity_models.json",
            provider=ProviderType.PERPLEXITY,
            friendly_prefix="Perplexity ({model})",
            config_path=config_path,
        )
