"""
List Models Tool - Display all available models organized by provider

This tool provides a comprehensive view of all AI models available in the system,
organized by their provider (Gemini, OpenAI, X.AI, OpenRouter, Custom).
It shows which providers are configured and what models can be used.
"""

import logging
import os
from typing import Any, Optional

from mcp.types import TextContent

from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ListModelsTool(BaseTool):
    """
    Tool for listing all available AI models organized by provider.

    This tool helps users understand:
    - Which providers are configured (have API keys)
    - What models are available from each provider
    - Model aliases and their full names
    - Context window sizes and capabilities
    """

    def get_name(self) -> str:
        return "listmodels"

    def get_description(self) -> str:
        return (
            "LIST AVAILABLE MODELS - Display all AI models organized by provider. "
            "Shows which providers are configured, available models, their aliases, "
            "context windows, and capabilities. Useful for understanding what models "
            "can be used and their characteristics. MANDATORY: Must display full output to the user."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for the tool's input"""
        return {
            "type": "object",
            "properties": {"model": {"type": "string", "description": "Model to use (ignored by listmodels tool)"}},
            "required": [],
        }

    def get_system_prompt(self) -> str:
        """No AI model needed for this tool"""
        return ""

    def get_request_model(self):
        """Return the Pydantic model for request validation."""
        return ToolRequest

    async def prepare_prompt(self, request: ToolRequest) -> str:
        """Not used for this utility tool"""
        return ""

    def format_response(self, response: str, request: ToolRequest, model_info: Optional[dict] = None) -> str:
        """Not used for this utility tool"""
        return response

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        List all available models organized by provider.

        This overrides the base class execute to provide direct output without AI model calls.

        Args:
            arguments: Standard tool arguments (none required)

        Returns:
            Formatted list of models by provider
        """
        from providers.base import ProviderType
        from providers.openrouter_registry import OpenRouterModelRegistry
        from providers.registry import ModelProviderRegistry

        output_lines = ["# Available AI Models\n"]

        # Map provider types to friendly names and their models
        provider_info = {
            ProviderType.GOOGLE: {"name": "Google Gemini", "env_key": "GEMINI_API_KEY"},
            ProviderType.OPENAI: {"name": "OpenAI", "env_key": "OPENAI_API_KEY"},
            ProviderType.XAI: {"name": "X.AI (Grok)", "env_key": "XAI_API_KEY"},
            ProviderType.DIAL: {"name": "AI DIAL", "env_key": "DIAL_API_KEY"},
        }

        # Check each native provider type
        for provider_type, info in provider_info.items():
            # Check if provider is enabled
            provider = ModelProviderRegistry.get_provider(provider_type)
            is_configured = provider is not None

            output_lines.append(f"## {info['name']} {'✅' if is_configured else '❌'}")

            if is_configured:
                output_lines.append("**Status**: Configured and available")
                output_lines.append("\n**Models**:")

                # Get models from the provider's model configurations
                for model_name, capabilities in provider.get_model_configurations().items():
                    # Get description and context from the ModelCapabilities object
                    description = capabilities.description or "No description available"
                    context_window = capabilities.context_window

                    # Format context window
                    if context_window >= 1_000_000:
                        context_str = f"{context_window // 1_000_000}M context"
                    elif context_window >= 1_000:
                        context_str = f"{context_window // 1_000}K context"
                    else:
                        context_str = f"{context_window} context" if context_window > 0 else "unknown context"

                    output_lines.append(f"- `{model_name}` - {context_str}")

                    # Extract key capability from description
                    if "Ultra-fast" in description:
                        output_lines.append("  - Fast processing, quick iterations")
                    elif "Deep reasoning" in description:
                        output_lines.append("  - Extended reasoning with thinking mode")
                    elif "Strong reasoning" in description:
                        output_lines.append("  - Logical problems, systematic analysis")
                    elif "EXTREMELY EXPENSIVE" in description:
                        output_lines.append("  - ⚠️ Professional grade (very expensive)")
                    elif "Advanced reasoning" in description:
                        output_lines.append("  - Advanced reasoning and complex analysis")

                # Show aliases for this provider
                aliases = []
                for model_name, capabilities in provider.get_model_configurations().items():
                    if capabilities.aliases:
                        for alias in capabilities.aliases:
                            aliases.append(f"- `{alias}` → `{model_name}`")

                if aliases:
                    output_lines.append("\n**Aliases**:")
                    output_lines.extend(sorted(aliases))  # Sort for consistent output
            else:
                output_lines.append(f"**Status**: Not configured (set {info['env_key']})")

            output_lines.append("")

        # Check OpenRouter
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        is_openrouter_configured = openrouter_key and openrouter_key != "your_openrouter_api_key_here"

        output_lines.append(f"## OpenRouter {'✅' if is_openrouter_configured else '❌'}")

        if is_openrouter_configured:
            output_lines.append("**Status**: Configured and available")
            output_lines.append("**Description**: Access to multiple cloud AI providers via unified API")

            try:
                # Get OpenRouter provider from registry to properly apply restrictions
                from providers.base import ProviderType
                from providers.registry import ModelProviderRegistry

                provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
                if provider:
                    # Get models with restrictions applied
                    available_models = provider.list_models(respect_restrictions=True)
                    registry = OpenRouterModelRegistry()

                    # Group by provider for better organization
                    providers_models = {}
                    for model_name in available_models:  # Show ALL available models
                        # Try to resolve to get config details
                        config = registry.resolve(model_name)
                        if config:
                            # Extract provider from model_name
                            provider_name = config.model_name.split("/")[0] if "/" in config.model_name else "other"
                            if provider_name not in providers_models:
                                providers_models[provider_name] = []
                            providers_models[provider_name].append((model_name, config))
                        else:
                            # Model without config - add with basic info
                            provider_name = model_name.split("/")[0] if "/" in model_name else "other"
                            if provider_name not in providers_models:
                                providers_models[provider_name] = []
                            providers_models[provider_name].append((model_name, None))

                    output_lines.append("\n**Available Models**:")
                    for provider_name, models in sorted(providers_models.items()):
                        output_lines.append(f"\n*{provider_name.title()}:*")
                        for alias, config in models:  # Show ALL models from each provider
                            if config:
                                context_str = f"{config.context_window // 1000}K" if config.context_window else "?"
                                output_lines.append(f"- `{alias}` → `{config.model_name}` ({context_str} context)")
                            else:
                                output_lines.append(f"- `{alias}`")

                    total_models = len(available_models)
                    # Show all models - no truncation message needed

                    # Check if restrictions are applied
                    restriction_service = None
                    try:
                        from utils.model_restrictions import get_restriction_service

                        restriction_service = get_restriction_service()
                        if restriction_service.has_restrictions(ProviderType.OPENROUTER):
                            allowed_set = restriction_service.get_allowed_models(ProviderType.OPENROUTER)
                            output_lines.append(
                                f"\n**Note**: Restricted to models matching: {', '.join(sorted(allowed_set))}"
                            )
                    except Exception as e:
                        logger.warning(f"Error checking OpenRouter restrictions: {e}")
                else:
                    output_lines.append("**Error**: Could not load OpenRouter provider")

            except Exception as e:
                output_lines.append(f"**Error loading models**: {str(e)}")
        else:
            output_lines.append("**Status**: Not configured (set OPENROUTER_API_KEY)")
            output_lines.append("**Note**: Provides access to GPT-4, Claude, Mistral, and many more")

        output_lines.append("")

        # Check Custom API
        custom_url = os.getenv("CUSTOM_API_URL")

        output_lines.append(f"## Custom/Local API {'✅' if custom_url else '❌'}")

        if custom_url:
            output_lines.append("**Status**: Configured and available")
            output_lines.append(f"**Endpoint**: {custom_url}")
            output_lines.append("**Description**: Local models via Ollama, vLLM, LM Studio, etc.")

            try:
                registry = OpenRouterModelRegistry()
                custom_models = []

                for alias in registry.list_aliases():
                    config = registry.resolve(alias)
                    if config and config.is_custom:
                        custom_models.append((alias, config))

                if custom_models:
                    output_lines.append("\n**Custom Models**:")
                    for alias, config in custom_models:
                        context_str = f"{config.context_window // 1000}K" if config.context_window else "?"
                        output_lines.append(f"- `{alias}` → `{config.model_name}` ({context_str} context)")
                        if config.description:
                            output_lines.append(f"  - {config.description}")

            except Exception as e:
                output_lines.append(f"**Error loading custom models**: {str(e)}")
        else:
            output_lines.append("**Status**: Not configured (set CUSTOM_API_URL)")
            output_lines.append("**Example**: CUSTOM_API_URL=http://localhost:11434 (for Ollama)")

        output_lines.append("")

        # Add summary
        output_lines.append("## Summary")

        # Count configured providers
        configured_count = sum(
            [
                1
                for provider_type, info in provider_info.items()
                if ModelProviderRegistry.get_provider(provider_type) is not None
            ]
        )
        if is_openrouter_configured:
            configured_count += 1
        if custom_url:
            configured_count += 1

        output_lines.append(f"**Configured Providers**: {configured_count}")

        # Get total available models
        try:
            from providers.registry import ModelProviderRegistry

            # Get all available models respecting restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)
            total_models = len(available_models)
            output_lines.append(f"**Total Available Models**: {total_models}")
        except Exception as e:
            logger.warning(f"Error getting total available models: {e}")

        # Add usage tips
        output_lines.append("\n**Usage Tips**:")
        output_lines.append("- Use model aliases (e.g., 'flash', 'o3', 'opus') for convenience")
        output_lines.append("- In auto mode, Claude will select the best model for each task")
        output_lines.append("- Custom models are only available when CUSTOM_API_URL is set")
        output_lines.append("- OpenRouter provides access to many cloud models with one API key")

        # Format output
        content = "\n".join(output_lines)

        tool_output = ToolOutput(
            status="success",
            content=content,
            content_type="text",
            metadata={
                "tool_name": self.name,
                "configured_providers": configured_count,
            },
        )

        return [TextContent(type="text", text=tool_output.model_dump_json())]

    def get_model_category(self) -> ToolModelCategory:
        """Return the model category for this tool."""
        return ToolModelCategory.FAST_RESPONSE  # Simple listing, no AI needed
