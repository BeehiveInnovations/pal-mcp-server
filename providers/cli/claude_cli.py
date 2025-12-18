"""Claude CLI model provider.

This provider uses the Claude Code CLI tool for inference instead of API keys.
The CLI authenticates via OAuth and may have subscription-based unlimited usage.
"""

import logging
from typing import Any

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

from .base import CLIModelProvider

logger = logging.getLogger(__name__)

# Claude CLI supported flags (as of Dec 2024):
# --model: Model selection (e.g., 'sonnet', 'opus')
# --system-prompt, --append-system-prompt: System prompts
# --output-format: Output format (text, json, stream-json)
# Note: No direct temperature or max_output_tokens flags currently available
CLAUDE_UNSUPPORTED_PARAMS = ["temperature", "max_output_tokens", "thinking_mode"]


class ClaudeCLIProvider(CLIModelProvider):
    """Model provider using the Claude Code CLI.

    This provider leverages the locally installed `claude` CLI tool
    which authenticates via OAuth. This is useful for users with
    Claude subscriptions who want unlimited usage without per-request API costs.

    The Claude CLI supports:
    - Multiple Claude models (Sonnet, Opus, Haiku)
    - File processing
    - MCP tool integration
    - Print mode for non-interactive use
    """

    FRIENDLY_NAME = "Claude CLI"

    def get_provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.CLAUDE_CLI

    def get_cli_name(self) -> str:
        """Return the CLI name."""
        return "claude"

    def get_supported_models(self) -> dict[str, ModelCapabilities]:
        """Return models available through Claude CLI.

        The Claude CLI uses the model configured in the user's subscription,
        but we expose common model names for compatibility.
        """
        # Temperature constraint for Claude models (min=0.0, max=1.0, default=0.7)
        temp_constraint = RangeTemperatureConstraint(0.0, 1.0, 0.7)

        return {
            "claude-cli": ModelCapabilities(
                provider=ProviderType.CLAUDE_CLI,
                model_name="claude-cli",
                friendly_name="Claude CLI (Default)",
                context_window=200_000,
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=18,
                aliases=["claude-cli-default", "ccli"],
            ),
            "claude-sonnet-cli": ModelCapabilities(
                provider=ProviderType.CLAUDE_CLI,
                model_name="claude-sonnet-cli",
                friendly_name="Claude Sonnet (CLI)",
                context_window=200_000,
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=17,
                aliases=["sonnet-cli"],
            ),
            "claude-opus-cli": ModelCapabilities(
                provider=ProviderType.CLAUDE_CLI,
                model_name="claude-opus-cli",
                friendly_name="Claude Opus (CLI)",
                context_window=200_000,
                max_output_tokens=8192,
                supports_extended_thinking=True,
                supports_streaming=True,
                supports_images=False,
                temperature_constraint=temp_constraint,
                intelligence_score=20,
                aliases=["opus-cli"],
            ),
        }

    def _get_cli_specific_args(
        self,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        thinking_mode: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Convert model parameters to Claude CLI arguments.

        Currently supported flags:
        - Model selection is handled separately via clink configuration
        - System prompts are handled via --append-system-prompt in clink

        Not yet supported by Claude CLI (will log warning):
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
                f"Claude CLI does not support dynamic parameters: {', '.join(unsupported)}. "
                f"These will be ignored. Using CLI defaults."
            )

        return args
