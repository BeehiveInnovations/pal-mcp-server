"""
Shared provider configuration logic.

This module provides a unified entry point for configuring AI providers,
used by both MCP server mode and Skills standalone mode to ensure consistency.

IMPORTANT: When adding a new provider, update PROVIDER_CONFIGS below.
Both server.py and zen_skill_runner.py will automatically pick it up.

DESIGN PRINCIPLE:
- MCP server mode uses configure_providers() in server.py (with full logging/validation)
- Skills mode uses register_providers() from this module (lightweight)
- Both share the same PROVIDER_CONFIGS registry to ensure consistency
"""

from typing import Callable, Optional

from .registry import ModelProviderRegistry
from .shared import ProviderType

# =============================================================================
# Provider Configuration Registry
# =============================================================================

# Each entry defines how to check and register a provider
# Format: (ProviderType, env_key, placeholder_value, provider_import_path, extra_check)
# Priority: Native APIs (Google, OpenAI, XAI, DIAL) → Azure → Custom → OpenRouter
PROVIDER_CONFIGS = [
    # Native APIs first (most direct and efficient)
    (ProviderType.GOOGLE, "GEMINI_API_KEY", "your_gemini_api_key_here", "providers.gemini:GeminiModelProvider", None),
    (ProviderType.OPENAI, "OPENAI_API_KEY", "your_openai_api_key_here", "providers.openai:OpenAIModelProvider", None),
    (ProviderType.XAI, "XAI_API_KEY", "your_xai_api_key_here", "providers.xai:XAIModelProvider", None),
    (ProviderType.DIAL, "DIAL_API_KEY", "your_dial_api_key_here", "providers.dial:DIALModelProvider", None),
    # OpenRouter last (catch-all for everything else)
    (
        ProviderType.OPENROUTER,
        "OPENROUTER_API_KEY",
        "your_openrouter_api_key_here",
        "providers.openrouter:OpenRouterProvider",
        None,
    ),
    # Azure and Custom have special handling below
]


def _import_provider_class(import_path: str):
    """Dynamically import a provider class from import path like 'providers.gemini:GeminiModelProvider'."""
    module_path, class_name = import_path.split(":")
    from importlib import import_module

    module = import_module(module_path)
    return getattr(module, class_name)


def register_providers(
    get_env: Callable[[str, Optional[str]], Optional[str]],
    verbose: bool = False,
    logger=None,
    require_at_least_one: bool = False,
) -> list[str]:
    """
    Register all available providers based on environment variables.

    This is the shared provider registration logic used by Skills mode.
    MCP server mode uses its own configure_providers() in server.py which has
    additional logging, validation, and cleanup logic.

    Both modes share the same PROVIDER_CONFIGS registry to ensure the same
    providers are available in both modes.

    Args:
        get_env: Function to get environment variables (e.g., os.getenv or utils.env.get_env)
        verbose: Whether to log registration details
        logger: Optional logger for verbose output
        require_at_least_one: If True, raise ValueError when no providers are registered

    Returns:
        List of successfully registered provider names

    Raises:
        ValueError: If require_at_least_one=True and no providers were registered
    """
    registered = []

    def log(msg: str, level: str = "info"):
        if verbose and logger:
            log_fn = getattr(logger, level, logger.info)
            log_fn(msg)

    # Register standard providers (in priority order from PROVIDER_CONFIGS)
    # Note: OpenRouter is last in the list for catch-all behavior
    for provider_type, env_key, placeholder, import_path, _ in PROVIDER_CONFIGS:
        api_key = get_env(env_key, None)
        if api_key and api_key != placeholder:
            try:
                provider_class = _import_provider_class(import_path)
                ModelProviderRegistry.register_provider(provider_type, provider_class)
                registered.append(provider_type.value)
                log(f"{provider_type.value} provider registered")
            except Exception as e:
                log(f"Failed to register {provider_type.value}: {e}", "warning")

    # Handle Azure OpenAI (requires endpoint + model registry check)
    azure_key = get_env("AZURE_OPENAI_API_KEY", None)
    azure_endpoint = get_env("AZURE_OPENAI_ENDPOINT", None)
    if azure_key and azure_key != "your_azure_openai_key_here" and azure_endpoint:
        try:
            from providers.registries.azure import AzureModelRegistry

            azure_registry = AzureModelRegistry()
            # Check if models are configured (list_models or get_models)
            models = getattr(azure_registry, "list_models", azure_registry.get_models)()
            if models:
                from providers.azure_openai import AzureOpenAIProvider

                ModelProviderRegistry.register_provider(ProviderType.AZURE, AzureOpenAIProvider)
                registered.append("Azure OpenAI")
                log("Azure OpenAI provider registered")
        except Exception as e:
            log(f"Failed to register Azure OpenAI: {e}", "warning")

    # Handle Custom provider (Ollama, vLLM, etc.)
    # Note: Custom is registered after native APIs but before OpenRouter in priority
    custom_url = get_env("CUSTOM_API_URL", None)
    if custom_url:
        try:
            from providers.custom import CustomProvider

            # Create factory that captures get_env
            def custom_provider_factory(api_key=None):
                base_url = get_env("CUSTOM_API_URL", "") or ""
                custom_key = get_env("CUSTOM_API_KEY", "") or ""
                return CustomProvider(api_key=api_key or custom_key, base_url=base_url)

            ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)
            registered.append("Custom")
            log("Custom provider registered")
        except Exception as e:
            log(f"Failed to register Custom provider: {e}", "warning")

    # Validate at least one provider is registered (if required)
    if require_at_least_one and not registered:
        raise ValueError(
            "At least one API configuration is required. Please set either:\n"
            "- GEMINI_API_KEY for Gemini models\n"
            "- OPENAI_API_KEY for OpenAI models\n"
            "- XAI_API_KEY for X.AI GROK models\n"
            "- DIAL_API_KEY for DIAL models\n"
            "- OPENROUTER_API_KEY for OpenRouter (multiple models)\n"
            "- CUSTOM_API_URL for local models (Ollama, vLLM, etc.)"
        )

    if verbose and logger and registered:
        logger.info(f"Registered providers: {', '.join(registered)}")

    # Check and log model restrictions (same logic as server.py:590-613)
    # NOTE: Always validate restrictions regardless of verbose setting to match MCP behavior
    from utils.model_restrictions import get_restriction_service

    restriction_service = get_restriction_service()
    restrictions = restriction_service.get_restriction_summary()

    if restrictions:
        if verbose and logger:
            logger.info("Model restrictions configured:")
            for provider_name, allowed_models in restrictions.items():
                if isinstance(allowed_models, list):
                    logger.info(f"  {provider_name}: {', '.join(allowed_models)}")
                else:
                    logger.info(f"  {provider_name}: {allowed_models}")

        # Validate restrictions against known models (always, not just when verbose)
        provider_instances = {}
        provider_types_to_validate = [ProviderType.GOOGLE, ProviderType.OPENAI, ProviderType.XAI, ProviderType.DIAL]
        for provider_type in provider_types_to_validate:
            provider = ModelProviderRegistry.get_provider(provider_type)
            if provider:
                provider_instances[provider_type] = provider

        if provider_instances:
            restriction_service.validate_against_known_models(provider_instances)
    elif verbose and logger:
        logger.info("No model restrictions configured - all models allowed")

    # Check if auto mode has any models available after restrictions (same as server.py:615-628)
    from config import IS_AUTO_MODE

    if IS_AUTO_MODE:
        available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)
        if not available_models:
            raise ValueError(
                "No models available for auto mode due to restrictions. "
                "Please adjust your allowed model settings or disable auto mode."
            )

    return registered
