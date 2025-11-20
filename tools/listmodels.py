"""
List Models Tool - Display all available models organized by provider

This tool provides a comprehensive view of all AI models available in the system,
organized by their provider (Gemini, OpenAI, X.AI, OpenRouter, Custom).
It shows which providers are configured and what models can be used.
"""

import logging
from typing import Any, Optional

from mcp.types import TextContent

from providers.registries.custom import CustomEndpointModelRegistry
from providers.registries.openrouter import OpenRouterModelRegistry
from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool
from utils.env import get_env

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
        return "Shows which AI model providers are configured, available model names, their aliases and capabilities."

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for the tool's input"""
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    def get_annotations(self) -> Optional[dict[str, Any]]:
        """Return tool annotations indicating this is a read-only tool"""
        return {"readOnlyHint": True}

    def get_system_prompt(self) -> str:
        """No AI model needed for this tool"""
        return ""

    def get_request_model(self):
        """Return the Pydantic model for request validation."""
        return ToolRequest

    def requires_model(self) -> bool:
        return False

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
        from providers.registry import ModelProviderRegistry
        from providers.shared import ProviderType
        from utils.model_restrictions import get_restriction_service

        output_lines = ["# Available AI Models\n"]

        restriction_service = get_restriction_service()
        restricted_models_by_provider: dict[ProviderType, list[str]] = {}

        if restriction_service:
            restricted_map = ModelProviderRegistry.get_available_models(respect_restrictions=True)
            for model_name, provider_type in restricted_map.items():
                restricted_models_by_provider.setdefault(provider_type, []).append(model_name)

        # Map provider types to friendly names and their models
        provider_info = {
            ProviderType.GOOGLE: {"name": "Google Gemini", "env_key": "GEMINI_API_KEY"},
            ProviderType.VERTEX_AI: {"name": "Google Vertex AI", "env_key": "VERTEX_PROJECT_ID"},
            ProviderType.OPENAI: {"name": "OpenAI", "env_key": "OPENAI_API_KEY"},
            ProviderType.AZURE: {"name": "Azure OpenAI", "env_key": "AZURE_OPENAI_API_KEY"},
            ProviderType.XAI: {"name": "X.AI (Grok)", "env_key": "XAI_API_KEY"},
            ProviderType.DIAL: {"name": "AI DIAL", "env_key": "DIAL_API_KEY"},
        }

        def format_model_entry(provider, display_name: str) -> list[str]:
            try:
                capabilities = provider.get_capabilities(display_name)
            except ValueError:
                return [f"- `{display_name}` *(not recognized by provider)*"]

            canonical = capabilities.model_name
            if canonical.lower() == display_name.lower():
                header = f"- `{canonical}`"
            else:
                header = f"- `{display_name}` → `{canonical}`"

            try:
                context_value = capabilities.context_window or 0
            except AttributeError:
                context_value = 0
            try:
                context_value = int(context_value)
            except (TypeError, ValueError):
                context_value = 0

            if context_value >= 1_000_000:
                context_str = f"{context_value // 1_000_000}M context"
            elif context_value >= 1_000:
                context_str = f"{context_value // 1_000}K context"
            elif context_value > 0:
                context_str = f"{context_value} context"
            else:
                context_str = "unknown context"

            try:
                description = capabilities.description or "No description available"
            except AttributeError:
                description = "No description available"
            lines = [header, f"  - {context_str}", f"  - {description}"]
            if capabilities.allow_code_generation:
                lines.append("  - Supports structured code generation")
            return lines

        # Check each native provider type
        for provider_type, info in provider_info.items():
            # Check if provider is enabled
            provider = ModelProviderRegistry.get_provider(provider_type)
            is_configured = provider is not None

            output_lines.append(f"## {info['name']} {'✅' if is_configured else '❌'}")

            if is_configured:
                output_lines.append("**Status**: Configured and available")
                has_restrictions = bool(restriction_service and restriction_service.has_restrictions(provider_type))

                if has_restrictions:
                    restricted_names = sorted(set(restricted_models_by_provider.get(provider_type, [])))

                    if restricted_names:
                        output_lines.append("\n**Models (policy restricted)**:")
                        for model_name in restricted_names:
                            output_lines.extend(format_model_entry(provider, model_name))
                    else:
                        output_lines.append("\n*No models are currently allowed by restriction policy.*")
                else:
                    output_lines.append("\n**Models**:")

                    aliases = []
                    for model_name, capabilities in provider.get_capabilities_by_rank():
                        try:
                            description = capabilities.description or "No description available"
                        except AttributeError:
                            description = "No description available"

                        try:
                            context_window = capabilities.context_window or 0
                        except AttributeError:
                            context_window = 0

                        if context_window >= 1_000_000:
                            context_str = f"{context_window // 1_000_000}M context"
                        elif context_window >= 1_000:
                            context_str = f"{context_window // 1_000}K context"
                        else:
                            context_str = f"{context_window} context" if context_window > 0 else "unknown context"

                        output_lines.append(f"- `{model_name}` - {context_str}")
                        output_lines.append(f"  - {description}")
                        if capabilities.allow_code_generation:
                            output_lines.append("  - Supports structured code generation")

                        for alias in capabilities.aliases or []:
                            if alias != model_name:
                                aliases.append(f"- `{alias}` → `{model_name}`")

                    if aliases:
                        output_lines.append("\n**Aliases**:")
                        output_lines.extend(sorted(aliases))
            else:
                output_lines.append(f"**Status**: Not configured (set {info['env_key']})")

            output_lines.append("")

        # Check OpenRouter
        openrouter_key = get_env("OPENROUTER_API_KEY")
        is_openrouter_configured = openrouter_key and openrouter_key != "your_openrouter_api_key_here"

        output_lines.append(f"## OpenRouter {'✅' if is_openrouter_configured else '❌'}")

        if is_openrouter_configured:
            output_lines.append("**Status**: Configured and available")
            output_lines.append("**Description**: Access to multiple cloud AI providers via unified API")

            try:
                provider = ModelProviderRegistry.get_provider(ProviderType.OPENROUTER)
                if provider:
                    registry = OpenRouterModelRegistry()

                    def _format_context(tokens: int) -> str:
                        if not tokens:
                            return "?"
                        if tokens >= 1_000_000:
                            return f"{tokens // 1_000_000}M"
                        if tokens >= 1_000:
                            return f"{tokens // 1_000}K"
                        return str(tokens)

                    has_restrictions = bool(
                        restriction_service and restriction_service.has_restrictions(ProviderType.OPENROUTER)
                    )

                    if has_restrictions:
                        restricted_names = sorted(set(restricted_models_by_provider.get(ProviderType.OPENROUTER, [])))

                        output_lines.append("\n**Models (policy restricted)**:")
                        if restricted_names:
                            for model_name in restricted_names:
                                try:
                                    caps = provider.get_capabilities(model_name)
                                except ValueError:
                                    output_lines.append(f"- `{model_name}` *(not recognized by provider)*")
                                    continue

                                context_value = int(caps.context_window or 0)
                                context_str = _format_context(context_value)
                                suffix_parts = [f"{context_str} context"]
                                if caps.supports_extended_thinking:
                                    suffix_parts.append("thinking")
                                suffix = ", ".join(suffix_parts)

                                arrow = ""
                                if caps.model_name.lower() != model_name.lower():
                                    arrow = f" → `{caps.model_name}`"

                                score = caps.get_effective_capability_rank()
                                output_lines.append(f"- `{model_name}`{arrow} (score {score}, {suffix})")

                            allowed_set = restriction_service.get_allowed_models(ProviderType.OPENROUTER) or set()
                            if allowed_set:
                                output_lines.append(
                                    f"\n*OpenRouter models restricted by OPENROUTER_ALLOWED_MODELS: {', '.join(sorted(allowed_set))}*"
                                )
                        else:
                            output_lines.append("- *No models allowed by current restriction policy.*")
                    else:
                        available_models = provider.list_models(respect_restrictions=True)
                        providers_models: dict[str, list[tuple[int, str, Optional[Any]]]] = {}

                        for model_name in available_models:
                            config = registry.resolve(model_name)
                            provider_name = "other"
                            if config and "/" in config.model_name:
                                provider_name = config.model_name.split("/")[0]
                            elif "/" in model_name:
                                provider_name = model_name.split("/")[0]

                            providers_models.setdefault(provider_name, [])

                            rank = config.get_effective_capability_rank() if config else 0
                            providers_models[provider_name].append((rank, model_name, config))

                        output_lines.append("\n**Available Models**:")
                        for provider_name, models in sorted(providers_models.items()):
                            output_lines.append(f"\n*{provider_name.title()}:*")
                            for rank, alias, config in sorted(models, key=lambda item: (-item[0], item[1])):
                                if config:
                                    context_str = _format_context(getattr(config, "context_window", 0))
                                    suffix_parts = [f"{context_str} context"]
                                    if getattr(config, "supports_extended_thinking", False):
                                        suffix_parts.append("thinking")
                                    suffix = ", ".join(suffix_parts)

                                    arrow = ""
                                    if config.model_name.lower() != alias.lower():
                                        arrow = f" → `{config.model_name}`"

                                    output_lines.append(f"- `{alias}`{arrow} (score {rank}, {suffix})")
                                else:
                                    output_lines.append(f"- `{alias}` (score {rank})")
                else:
                    output_lines.append("**Error**: Could not load OpenRouter provider")

            except Exception as e:
                logger.exception("Error listing OpenRouter models: %s", e)
                output_lines.append(f"**Error loading models**: {str(e)}")
        else:
            output_lines.append("**Status**: Not configured (set OPENROUTER_API_KEY)")
            output_lines.append("**Note**: Provides access to GPT-5, O3, Mistral, and many more")

        output_lines.append("")

        # Check Custom API
        custom_url = get_env("CUSTOM_API_URL")

        output_lines.append(f"## Custom/Local API {'✅' if custom_url else '❌'}")

        if custom_url:
            output_lines.append("**Status**: Configured and available")
            output_lines.append(f"**Endpoint**: {custom_url}")
            output_lines.append("**Description**: Local models via Ollama, vLLM, LM Studio, etc.")

            try:
                registry = CustomEndpointModelRegistry()
                custom_models = []

                for alias in registry.list_aliases():
                    config = registry.resolve(alias)
                    if config:
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
        output_lines.append("- Use model aliases (e.g., 'flash', 'gpt5', 'opus') for convenience")
        output_lines.append("- In auto mode, the CLI Agent will select the best model for each task")
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
