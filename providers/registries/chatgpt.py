"""Registry loader for models reachable with a ChatGPT plan login (via the Codex CLI)."""

from __future__ import annotations

from ..shared import ProviderType
from .base import CapabilityModelRegistry


class ChatGPTModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/chatgpt_models.json``."""

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="CHATGPT_MODELS_CONFIG_PATH",
            default_filename="chatgpt_models.json",
            provider=ProviderType.CHATGPT,
            friendly_prefix="ChatGPT ({model})",
            config_path=config_path,
        )
