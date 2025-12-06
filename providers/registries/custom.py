"""Registry loader for custom OpenAI-compatible endpoints."""

from __future__ import annotations

import logging

from utils.env import get_env

from ..shared import ModelCapabilities, ProviderType
from .base import CAPABILITY_FIELD_NAMES, CapabilityModelRegistry


# Default capabilities for dynamically injected CUSTOM_MODEL_NAME
_DEFAULT_CONTEXT_WINDOW = 128_000
_DEFAULT_MAX_OUTPUT_TOKENS = 16_000
_DEFAULT_INTELLIGENCE_SCORE = 6  # Matches llama3.2 in custom_models.json


class CustomEndpointModelRegistry(CapabilityModelRegistry):
    """Capability registry backed by ``conf/custom_models.json``.

    Automatically injects CUSTOM_MODEL_NAME into the registry if specified,
    ensuring all instances can see user-defined custom models.
    See: https://github.com/BeehiveInnovations/zen-mcp-server/issues/327
    """

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__(
            env_var_name="CUSTOM_MODELS_CONFIG_PATH",
            default_filename="custom_models.json",
            provider=ProviderType.CUSTOM,
            friendly_prefix="Custom ({model})",
            config_path=config_path,
        )
        # Inject CUSTOM_MODEL_NAME after loading config
        self._inject_custom_model_if_needed()

    def reload(self) -> None:
        """Reload config from file and re-inject CUSTOM_MODEL_NAME.

        Overrides base class to ensure CUSTOM_MODEL_NAME is preserved
        after configuration hot-reload.
        """
        super().reload()
        self._inject_custom_model_if_needed()

    def _inject_custom_model_if_needed(self) -> None:
        """Inject CUSTOM_MODEL_NAME into registry if not already present.

        This ensures listmodels and other tools can see user-defined models
        even if they're not declared in custom_models.json.
        """
        custom_model_name = (get_env("CUSTOM_MODEL_NAME", "") or "").strip()
        if not custom_model_name:
            return

        # Check if model already exists in registry
        if self.resolve(custom_model_name):
            logging.debug(f"Model '{custom_model_name}' already in registry, skipping injection")
            return

        # Create a basic capability entry for the custom model
        capability = ModelCapabilities(
            provider=ProviderType.CUSTOM,
            model_name=custom_model_name,
            friendly_name=f"Custom ({custom_model_name})",
            description="Custom model via CUSTOM_MODEL_NAME environment variable",
            context_window=_DEFAULT_CONTEXT_WINDOW,
            max_output_tokens=_DEFAULT_MAX_OUTPUT_TOKENS,
            intelligence_score=_DEFAULT_INTELLIGENCE_SCORE,
            supports_extended_thinking=False,
            supports_json_mode=False,
            supports_function_calling=False,
            supports_images=False,
        )

        # Inject into registry maps
        self.model_map[custom_model_name] = capability
        self.alias_map[custom_model_name.lower()] = custom_model_name

        logging.debug(
            f"Injected CUSTOM_MODEL_NAME '{custom_model_name}' into registry "
            f"(listmodels and auto mode will now include this model)"
        )

    def _finalise_entry(self, entry: dict) -> tuple[ModelCapabilities, dict]:
        filtered = {k: v for k, v in entry.items() if k in CAPABILITY_FIELD_NAMES}
        filtered.setdefault("provider", ProviderType.CUSTOM)
        capability = ModelCapabilities(**filtered)
        return capability, {}
