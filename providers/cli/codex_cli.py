"""Codex CLI model provider.

This provider uses the Codex CLI tool for inference instead of API keys.
The CLI authenticates via OAuth and may have subscription-based unlimited usage.
"""

import logging
from typing import Any

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

from .base import CLIModelProvider

logger = logging.getLogger(__name__)

# Codex CLI supported flags (as of Dec 2024):
# -m, --model: Model selection
# -c, --config <key=value>: Override config values (could potentially support temperature)
# -s, --sandbox: Sandbox policy
# Note: Temperature could potentially be set via -c flag, but not yet tested
CODEX_UNSUPPORTED_PARAMS = ["temperature", "max_output_tokens", "thinking_mode"]


class CodexCLIProvider(CLIModelProvider):
    """Model provider using the Codex CLI.

    This provider leverages the locally installed `codex` CLI tool
    which authenticates via OAuth. This is useful for users with
    OpenAI subscriptions who want unlimited usage without per-request API costs.

    The Codex CLI supports:
    - Multiple OpenAI models (o3, o4-mini, etc.)
    - File processing
    - Code execution sandbox
    - Review mode for code analysis
    """

    FRIENDLY_NAME = "Codex CLI"

    def get_provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.CODEX_CLI

    def get_cli_name(self) -> str:
        """Return the CLI name."""
        return "codex"

    def get_supported_models(self) -> dict[str, ModelCapabilities]:
        """Return models available through Codex CLI.

        The Codex CLI uses the model configured in the user's subscription,
        but we expose common model names for compatibility.
        """
        # Temperature constraint for OpenAI models (min=0.0, max=2.0, default=0.7)
        temp_constraint = RangeTemperatureConstraint(0.0, 2.0, 0.7)

        return {
            "codex-cli": ModelCapabilities(
                provider=ProviderType.CODEX_CLI,
                model_name="codex-cli",
                friendly_name="Codex CLI (Default)",
                context_window=128_000,
                max_output_tokens=16384,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=18,
                aliases=["codex-cli-default", "ocli"],
            ),
            "o3-cli": ModelCapabilities(
                provider=ProviderType.CODEX_CLI,
                model_name="o3-cli",
                friendly_name="OpenAI O3 (CLI)",
                context_window=200_000,
                max_output_tokens=100_000,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=20,
                aliases=["o3-codex-cli"],
            ),
            "o4-mini-cli": ModelCapabilities(
                provider=ProviderType.CODEX_CLI,
                model_name="o4-mini-cli",
                friendly_name="OpenAI O4-Mini (CLI)",
                context_window=128_000,
                max_output_tokens=16384,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=16,
                aliases=["o4-mini-codex-cli"],
            ),
        }

    def _get_cli_specific_args(
        self,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        thinking_mode: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Convert model parameters to Codex CLI arguments.

        Currently supported flags:
        - Model selection is handled separately via clink configuration
        - Temperature could potentially be set via -c flag, but not yet tested

        Not yet supported by Codex CLI (will log warning):
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
                f"Codex CLI does not support dynamic parameters: {', '.join(unsupported)}. "
                f"These will be ignored. Using CLI defaults."
            )

        return args
