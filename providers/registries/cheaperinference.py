"""Registry loader for Cheaper Inference model capabilities."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class CheaperInferenceModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/cheaperinference_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="CHEAPER_INFERENCE_MODELS_CONFIG_PATH",
            default_filename="cheaperinference_models.json",
            provider=ProviderType.CHEAPERINFERENCE,
            friendly_prefix="Cheaper Inference ({model})",
            config_path=config_path,
        )
