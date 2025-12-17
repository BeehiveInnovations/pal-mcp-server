"""Codex CLI model provider.

This provider uses the Codex CLI tool for inference instead of API keys.
The CLI authenticates via OAuth and may have subscription-based unlimited usage.
"""

import logging

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

from .base import CLIModelProvider

logger = logging.getLogger(__name__)


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
                supports_images=True,
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
                supports_images=True,
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
                supports_images=True,
                temperature_constraint=temp_constraint,
                intelligence_score=16,
                aliases=["o4-mini-codex-cli"],
            ),
        }
