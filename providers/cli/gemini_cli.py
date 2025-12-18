"""Gemini CLI model provider.

This provider uses the Gemini CLI tool for inference instead of API keys.
The CLI authenticates via OAuth and may have subscription-based unlimited usage.
"""

import logging
from typing import Any

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

from .base import CLIModelProvider

logger = logging.getLogger(__name__)

# Gemini CLI supported flags (as of Dec 2024):
# -m, --model: Model selection
# -o, --output-format: Output format (text, json, stream-json)
# -s, --sandbox: Run in sandbox mode
# Note: No direct temperature or max_output_tokens flags currently available
GEMINI_UNSUPPORTED_PARAMS = ["temperature", "max_output_tokens", "thinking_mode"]


class GeminiCLIProvider(CLIModelProvider):
    """Model provider using the Gemini CLI.

    This provider leverages the locally installed `gemini` CLI tool
    which authenticates via OAuth. This is useful for users with
    Gemini subscriptions who want unlimited usage without per-request API costs.

    The Gemini CLI supports:
    - Multiple Gemini models (flash, pro, etc.)
    - Text-based prompts and responses
    - Web search integration
    - JSON output format

    Note: Image input is not supported through the CLI interface.
    """

    FRIENDLY_NAME = "Gemini CLI"

    def get_provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.GEMINI_CLI

    def get_cli_name(self) -> str:
        """Return the CLI name."""
        return "gemini"

    def get_supported_models(self) -> dict[str, ModelCapabilities]:
        """Return models available through Gemini CLI.

        The Gemini CLI typically uses the default model configured in the CLI,
        but we expose common model names for compatibility with the provider interface.
        """
        # Temperature constraint for Gemini models (min=0.0, max=2.0, default=0.7)
        temp_constraint = RangeTemperatureConstraint(0.0, 2.0, 0.7)

        return {
            "gemini-cli": ModelCapabilities(
                provider=ProviderType.GEMINI_CLI,
                model_name="gemini-cli",
                friendly_name="Gemini CLI (Default)",
                context_window=1_000_000,  # Gemini 1.5 has 1M context
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=15,
                aliases=["gemini-cli-default", "gcli"],
            ),
            "gemini-2.5-flash-cli": ModelCapabilities(
                provider=ProviderType.GEMINI_CLI,
                model_name="gemini-2.5-flash-cli",
                friendly_name="Gemini 2.5 Flash (CLI)",
                context_window=1_000_000,
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=14,
                aliases=["flash-cli", "gemini-flash-cli"],
            ),
            "gemini-2.5-pro-cli": ModelCapabilities(
                provider=ProviderType.GEMINI_CLI,
                model_name="gemini-2.5-pro-cli",
                friendly_name="Gemini 2.5 Pro (CLI)",
                context_window=1_000_000,
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=17,
                aliases=["pro-cli", "gemini-pro-cli"],
            ),
        }

    def _get_cli_specific_args(
        self,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        thinking_mode: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Convert model parameters to Gemini CLI arguments.

        Currently supported flags:
        - Model selection is handled separately via clink configuration

        Not yet supported by Gemini CLI (will log warning):
        - temperature
        - max_output_tokens
        - thinking_mode

        Args:
            temperature: Model temperature (not supported)
            max_output_tokens: Maximum output tokens (not supported)
            thinking_mode: Thinking mode (not supported)
            **kwargs: Additional parameters

        Returns:
            List of CLI argument strings
        """
        args: list[str] = []

        # Log warnings for unsupported parameters
        unsupported = []
        if temperature is not None and temperature != 0.3:
            unsupported.append(f"temperature={temperature}")
        if max_output_tokens is not None:
            unsupported.append(f"max_output_tokens={max_output_tokens}")
        if thinking_mode is not None:
            unsupported.append(f"thinking_mode={thinking_mode}")

        if unsupported:
            logger.warning(
                f"Gemini CLI does not support dynamic parameters: {', '.join(unsupported)}. "
                f"These will be ignored. Using CLI defaults."
            )

        return args
