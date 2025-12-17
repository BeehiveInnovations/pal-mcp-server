"""Gemini CLI model provider.

This provider uses the Gemini CLI tool for inference instead of API keys.
The CLI authenticates via OAuth and may have subscription-based unlimited usage.
"""

import logging

from providers.shared import ModelCapabilities, ProviderType, RangeTemperatureConstraint

from .base import CLIModelProvider

logger = logging.getLogger(__name__)


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
