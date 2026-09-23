"""Model metadata for the optional LLM Proxy provider."""

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class LLMProxyModelRegistry(CapabilityModelRegistry):
    """Reuse PAL's model catalog format without assuming a tenant's models."""

    def __init__(self) -> None:
        super().__init__(
            env_var_name="LLM_PROXY_MODELS_CONFIG_PATH",
            default_filename="llm_proxy_models.json",
            provider=ProviderType.LLM_PROXY,
            friendly_prefix="LLM Proxy ({model})",
        )
