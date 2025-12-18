"""Model provider registry for managing available providers."""

import logging
from typing import TYPE_CHECKING, Optional

from utils.env import get_env

from .base import ModelProvider
from .shared import ProviderType

if TYPE_CHECKING:
    from tools.models import ToolModelCategory


class ModelProviderRegistry:
    """Central catalogue of provider implementations used by the MCP server.

    Role
        Holds the mapping between :class:`ProviderType` values and concrete
        :class:`ModelProvider` subclasses/factories.  At runtime the registry
        is responsible for instantiating providers, caching them for reuse, and
        mediating lookup of providers and model names in provider priority
        order.

    Core responsibilities
        * Resolve API keys and other runtime configuration for each provider
        * Lazily create provider instances so unused backends incur no cost
        * Expose convenience methods for enumerating available models and
          locating which provider can service a requested model name or alias
        * Honour the project-wide provider priority policy so namespaces (or
          alias collisions) are resolved deterministically.
    """

    _instance = None

    # Provider priority order for model selection
    # Native APIs first, then custom endpoints, then catch-all providers
    # Note: Vertex AI before Gemini API to enforce "Vertex Precedence" in fallback selection
    PROVIDER_PRIORITY_ORDER = [
        ProviderType.VERTEX_AI,  # Google Vertex AI access (takes precedence over Gemini API)
        ProviderType.GOOGLE,  # Direct Gemini API access
        ProviderType.OPENAI,  # Direct OpenAI access
        ProviderType.AZURE,  # Azure-hosted OpenAI deployments
        ProviderType.XAI,  # Direct X.AI GROK access
        ProviderType.DIAL,  # DIAL unified API access
        ProviderType.CUSTOM,  # Local/self-hosted models
        ProviderType.OPENROUTER,  # Catch-all for cloud models
    ]

    def __new__(cls):
        """Singleton pattern for registry."""
        if cls._instance is None:
            logging.debug("REGISTRY: Creating new registry instance")
            cls._instance = super().__new__(cls)
            # Initialize instance dictionaries on first creation
            cls._instance._providers = {}
            cls._instance._initialized_providers = {}
            logging.debug(f"REGISTRY: Created instance {cls._instance}")
        return cls._instance

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class: type[ModelProvider]) -> None:
        """Register a new provider class.

        Args:
            provider_type: Type of the provider (e.g., ProviderType.GOOGLE)
            provider_class: Class that implements ModelProvider interface
        """
        instance = cls()
        instance._providers[provider_type] = provider_class
        # Invalidate any cached instance so subsequent lookups use the new registration
        instance._initialized_providers.pop(provider_type, None)

    @classmethod
    def get_provider(cls, provider_type: ProviderType, force_new: bool = False) -> Optional[ModelProvider]:
        """Get an initialized provider instance.

        Args:
            provider_type: Type of provider to get
            force_new: Force creation of new instance instead of using cached

        Returns:
            Initialized ModelProvider instance or None if not available
        """
        instance = cls()

        # Return cached instance if available and not forcing new
        if not force_new and provider_type in instance._initialized_providers:
            return instance._initialized_providers[provider_type]

        # Check if provider class is registered
        if provider_type not in instance._providers:
            return None

        # Get API key from environment
        api_key = cls._get_api_key_for_provider(provider_type)

        # Get provider class or factory function
        provider_class = instance._providers[provider_type]

        # For special providers, handle custom initialization requirements
        if provider_type == ProviderType.CUSTOM:
            # Check if it's a factory function (callable but not a class)
            if callable(provider_class) and not isinstance(provider_class, type):
                # Factory function - call it with api_key parameter
                provider = provider_class(api_key=api_key)
            else:
                # Regular class - need to handle URL requirement
                custom_url = get_env("CUSTOM_API_URL", "") or ""
                if not custom_url:
                    if api_key:  # Key is set but URL is missing
                        logging.warning("CUSTOM_API_KEY set but CUSTOM_API_URL missing – skipping Custom provider")
                    return None
                # Use empty string as API key for custom providers that don't need auth (e.g., Ollama)
                # This allows the provider to be created even without CUSTOM_API_KEY being set
                api_key = api_key or ""
                # Initialize custom provider with both API key and base URL
                provider = provider_class(api_key=api_key, base_url=custom_url)
        elif provider_type == ProviderType.GOOGLE:
            # For Gemini, check if custom base URL is configured
            if not api_key:
                return None
            gemini_base_url = get_env("GEMINI_BASE_URL")
            provider_kwargs = {"api_key": api_key}
            if gemini_base_url:
                provider_kwargs["base_url"] = gemini_base_url
                logging.info(f"Initialized Gemini provider with custom endpoint: {gemini_base_url}")
            provider = provider_class(**provider_kwargs)
        elif provider_type == ProviderType.AZURE:
            if not api_key:
                return None

            azure_endpoint = get_env("AZURE_OPENAI_ENDPOINT")
            if not azure_endpoint:
                logging.warning("AZURE_OPENAI_ENDPOINT missing – skipping Azure OpenAI provider")
                return None

            azure_version = get_env("AZURE_OPENAI_API_VERSION")
            provider = provider_class(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=azure_version,
            )
        elif provider_type == ProviderType.VERTEX_AI:
            # Vertex AI uses project_id and region instead of API key
            project_id = get_env("VERTEX_PROJECT_ID")
            if not project_id:
                logging.debug("VERTEX_PROJECT_ID not set – skipping Vertex AI provider")
                return None
            region = get_env("VERTEX_REGION") or "us-central1"
            # Initialize Vertex AI provider with project_id and region
            try:
                provider = provider_class(project_id=project_id, region=region)
                # Validate credentials early to prevent late-stage runtime failures
                _ = provider.credentials  # Force ADC check
                logging.debug("Vertex AI credentials validated successfully")
            except ValueError as e:
                logging.debug(f"Vertex AI credentials not available: {e}")
                return None  # Skip provider if credentials not usable
        else:
            if not api_key:
                return None
            # Initialize standard provider with just API key
            provider = provider_class(api_key=api_key)

        # Cache the instance
        instance._initialized_providers[provider_type] = provider

        return provider

    @classmethod
    def _has_vertex_credentials(cls) -> bool:
        """Check if Vertex AI credentials are configured.

        Returns:
            True if VERTEX_PROJECT_ID is set and valid, False otherwise
        """
        project_id = get_env("VERTEX_PROJECT_ID")
        # Normalize to stripped value for validation
        normalized_id = project_id.strip() if project_id else ""
        # Reject common placeholder values
        invalid_placeholders = {"your_vertex_project_id_here", "your-gcp-project-id", "your_gcp_project_id"}
        return bool(normalized_id and normalized_id not in invalid_placeholders)

    @classmethod
    def _has_gemini_api_key(cls) -> bool:
        """Check if Gemini API key is configured.

        Returns:
            True if GEMINI_API_KEY is set and valid, False otherwise
        """
        api_key = get_env("GEMINI_API_KEY")
        normalized_key = api_key.strip() if api_key else ""
        return bool(normalized_key and normalized_key != "your_gemini_api_key_here")

    @classmethod
    def _configure_gemini_access(cls) -> Optional[ProviderType]:
        """Configure Gemini access via Vertex AI or API key (mutually exclusive).

        Implements "Vertex Precedence" pattern:
        - If Vertex AI credentials exist, use Vertex AI provider (GCP billing)
        - Otherwise, use Gemini API provider (API key billing)
        - Both providers support the same Gemini models

        Returns:
            ProviderType.VERTEX_AI if Vertex credentials configured,
            ProviderType.GOOGLE if Gemini API key configured,
            None if neither configured

        Note:
            This enforces mutual exclusivity to prevent billing confusion.
            Users specify model names like "gemini-2.5-pro" and credentials
            determine the billing method, not alias-based routing.
        """
        has_vertex = cls._has_vertex_credentials()
        has_gemini_api = cls._has_gemini_api_key()

        # Vertex AI takes precedence
        if has_vertex:
            provider = cls.get_provider(ProviderType.VERTEX_AI)
            if provider:
                logging.info("✓ Using Vertex AI for Gemini models (GCP billing)")
                if has_gemini_api:
                    logging.info(
                        "  ℹ️  Gemini API key detected but ignored (Vertex AI takes precedence). "
                        "Remove VERTEX_PROJECT_ID to use API key billing instead."
                    )
                return ProviderType.VERTEX_AI

        # Fallback to Gemini API
        if has_gemini_api:
            provider = cls.get_provider(ProviderType.GOOGLE)
            if provider:
                logging.info("✓ Using Gemini API for Gemini models (API key billing)")
                return ProviderType.GOOGLE

        # No Gemini access configured
        logging.info("No Gemini access configured (neither Vertex AI nor GEMINI_API_KEY)")
        return None

    @classmethod
    def get_provider_for_model(cls, model_name: str) -> Optional[ModelProvider]:
        """Get provider instance for a specific model name.

        For Gemini models, implements "Vertex Precedence":
        - Vertex AI takes priority if configured (GCP billing)
        - Falls back to Gemini API if available (API key billing)

        For other providers, uses priority order:
        1. Native APIs (OPENAI, XAI, etc.) - Most direct and efficient
        2. CUSTOM - For local/private models with specific endpoints
        3. OPENROUTER - Catch-all for cloud models via unified API

        Args:
            model_name: Name of the model (e.g., "gemini-2.5-flash", "gpt5")

        Returns:
            ModelProvider instance that supports this model
        """
        logging.debug(f"get_provider_for_model called with model_name='{model_name}'")

        instance = cls()
        logging.debug(f"Registry instance: {instance}")
        logging.debug(f"Available providers in registry: {list(instance._providers.keys())}")

        # Check Gemini providers first using Vertex Precedence logic
        # This ensures Vertex AI takes priority over Gemini API when both are configured
        gemini_provider_type = cls._configure_gemini_access()
        if gemini_provider_type:
            provider = cls.get_provider(gemini_provider_type)
            if provider and provider.validate_model_name(model_name):
                logging.debug(f"Model '{model_name}' validated by Gemini provider: {gemini_provider_type}")
                return provider

        # For non-Gemini models, check providers in priority order
        for provider_type in cls.PROVIDER_PRIORITY_ORDER:
            # Skip Gemini providers since we handled them above with precedence logic
            if provider_type in (ProviderType.GOOGLE, ProviderType.VERTEX_AI):
                continue

            if provider_type in instance._providers:
                logging.debug(f"Found {provider_type} in registry")
                # Get or create provider instance
                provider = cls.get_provider(provider_type)
                if provider and provider.validate_model_name(model_name):
                    logging.debug(f"{provider_type} validates model {model_name}")
                    return provider
                else:
                    logging.debug(f"{provider_type} does not validate model {model_name}")
            else:
                logging.debug(f"{provider_type} not found in registry")

        logging.debug(f"No provider found for model {model_name}")
        return None

    @classmethod
    def get_available_providers(cls) -> list[ProviderType]:
        """Get list of registered provider types."""
        instance = cls()
        return list(instance._providers.keys())

    @classmethod
    def get_available_models(cls, respect_restrictions: bool = True) -> dict[str, ProviderType]:
        """Get mapping of all available models to their providers.

        Args:
            respect_restrictions: If True, filter out models not allowed by restrictions

        Returns:
            Dict mapping model names to provider types
        """
        # Import here to avoid circular imports
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        models: dict[str, ProviderType] = {}
        instance = cls()

        for provider_type in instance._providers:
            provider = cls.get_provider(provider_type)
            if not provider:
                continue

            try:
                available = provider.list_models(respect_restrictions=respect_restrictions)
            except NotImplementedError:
                logging.warning("Provider %s does not implement list_models", provider_type)
                continue

            if restriction_service and restriction_service.has_restrictions(provider_type):
                restricted_display = cls._collect_restricted_display_names(
                    provider,
                    provider_type,
                    available,
                    restriction_service,
                )
                if restricted_display:
                    for model_name in restricted_display:
                        models[model_name] = provider_type
                    continue

            for model_name in available:
                # =====================================================================================
                # CRITICAL: Prevent double restriction filtering (Fixed Issue #98)
                # =====================================================================================
                # Previously, both the provider AND registry applied restrictions, causing
                # double-filtering that resulted in "no models available" errors.
                #
                # Logic: If respect_restrictions=True, provider already filtered models,
                # so registry should NOT filter them again.
                # TEST COVERAGE: tests/test_provider_routing_bugs.py::TestOpenRouterAliasRestrictions
                # =====================================================================================
                if (
                    restriction_service
                    and not respect_restrictions  # Only filter if provider didn't already filter
                    and not restriction_service.is_allowed(provider_type, model_name)
                ):
                    logging.debug("Model %s filtered by restrictions", model_name)
                    continue
                models[model_name] = provider_type

        return models

    @classmethod
    def _collect_restricted_display_names(
        cls,
        provider: ModelProvider,
        provider_type: ProviderType,
        available: list[str],
        restriction_service,
    ) -> list[str] | None:
        """Derive the human-facing model list when restrictions are active."""

        allowed_models = restriction_service.get_allowed_models(provider_type)
        if not allowed_models:
            return None

        allowed_details: list[tuple[str, int]] = []

        for model_name in sorted(allowed_models):
            try:
                capabilities = provider.get_capabilities(model_name)
            except (AttributeError, ValueError):
                continue

            try:
                rank = capabilities.get_effective_capability_rank()
                rank_value = float(rank)
            except (AttributeError, TypeError, ValueError):
                rank_value = 0.0

            allowed_details.append((model_name, rank_value))

        if allowed_details:
            allowed_details.sort(key=lambda item: (-item[1], item[0]))
            return [name for name, _ in allowed_details]

        # Fallback: intersect the allowlist with the provider-advertised names.
        available_lookup = {name.lower(): name for name in available}
        display_names: list[str] = []
        for model_name in sorted(allowed_models):
            lowered = model_name.lower()
            if lowered in available_lookup:
                display_names.append(available_lookup[lowered])

        return display_names

    @classmethod
    def get_available_model_names(cls, provider_type: Optional[ProviderType] = None) -> list[str]:
        """Get list of available model names, optionally filtered by provider.

        This respects model restrictions automatically.

        Args:
            provider_type: Optional provider to filter by

        Returns:
            List of available model names
        """
        available_models = cls.get_available_models(respect_restrictions=True)

        if provider_type:
            # Filter by specific provider
            return [name for name, ptype in available_models.items() if ptype == provider_type]
        else:
            # Return all available models
            return list(available_models.keys())

    @classmethod
    def _get_api_key_for_provider(cls, provider_type: ProviderType) -> Optional[str]:
        """Get API key for a provider from environment variables.

        Args:
            provider_type: Provider type to get API key for

        Returns:
            API key string or None if not found
        """
        key_mapping = {
            ProviderType.GOOGLE: "GEMINI_API_KEY",
            ProviderType.OPENAI: "OPENAI_API_KEY",
            ProviderType.AZURE: "AZURE_OPENAI_API_KEY",
            ProviderType.XAI: "XAI_API_KEY",
            ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
            ProviderType.CUSTOM: "CUSTOM_API_KEY",  # Can be empty for providers that don't need auth
            ProviderType.DIAL: "DIAL_API_KEY",
        }

        env_var = key_mapping.get(provider_type)
        if not env_var:
            return None

        return get_env(env_var)

    @classmethod
    def _get_allowed_models_for_provider(cls, provider: ModelProvider, provider_type: ProviderType) -> list[str]:
        """Get a list of allowed canonical model names for a given provider.

        Args:
            provider: The provider instance to get models for
            provider_type: The provider type for restriction checking

        Returns:
            List of model names that are both supported and allowed
        """
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()

        allowed_models = []

        # Get the provider's supported models
        try:
            # Use list_models to get all supported models (handles both regular and custom providers)
            supported_models = provider.list_models(respect_restrictions=False)
        except (NotImplementedError, AttributeError):
            # Fallback to provider-declared capability maps if list_models not implemented
            model_map = getattr(provider, "MODEL_CAPABILITIES", None)
            supported_models = list(model_map.keys()) if isinstance(model_map, dict) else []

        # Filter by restrictions
        for model_name in supported_models:
            if restriction_service.is_allowed(provider_type, model_name):
                allowed_models.append(model_name)

        return allowed_models

    @classmethod
    def get_preferred_fallback_model(cls, tool_category: Optional["ToolModelCategory"] = None) -> str:
        """Get the preferred fallback model based on provider priority and tool category.

        This method orchestrates model selection by:
        1. Getting allowed models for each provider (respecting restrictions)
        2. Asking providers for their preference from the allowed list
        3. Falling back to first available model if no preference given

        Args:
            tool_category: Optional category to influence model selection

        Returns:
            Model name string for fallback use
        """
        from tools.models import ToolModelCategory

        effective_category = tool_category or ToolModelCategory.BALANCED
        first_available_model = None

        # Ask each provider for their preference in priority order
        for provider_type in cls.PROVIDER_PRIORITY_ORDER:
            provider = cls.get_provider(provider_type)
            if provider:
                # 1. Registry filters the models first
                allowed_models = cls._get_allowed_models_for_provider(provider, provider_type)

                if not allowed_models:
                    continue

                # 2. Keep track of the first available model as fallback
                if not first_available_model:
                    first_available_model = sorted(allowed_models)[0]

                # 3. Ask provider to pick from allowed list
                preferred_model = provider.get_preferred_model(effective_category, allowed_models)

                if preferred_model:
                    logging.debug(
                        f"Provider {provider_type.value} selected '{preferred_model}' for category '{effective_category.value}'"
                    )
                    return preferred_model

        # If no provider returned a preference, use first available model
        if first_available_model:
            logging.debug(f"No provider preference, using first available: {first_available_model}")
            return first_available_model

        # Ultimate fallback if no providers have models
        logging.warning("No models available from any provider, using default fallback")
        return "gemini-2.5-flash"

    @classmethod
    def get_available_providers_with_keys(cls) -> list[ProviderType]:
        """Get list of provider types that have valid API keys.

        Returns:
            List of ProviderType values for providers with valid API keys
        """
        available = []
        instance = cls()
        for provider_type in instance._providers:
            if cls.get_provider(provider_type) is not None:
                available.append(provider_type)
        return available

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances."""
        instance = cls()
        instance._initialized_providers.clear()

    @classmethod
    def reset_for_testing(cls) -> None:
        """Reset the registry to a clean state for testing.

        This provides a safe, public API for tests to clean up registry state
        without directly manipulating private attributes.

        Note: Setting cls._instance = None is sufficient. The next call to
        ModelProviderRegistry() will trigger __new__ which creates a fresh instance
        with empty _providers and _initialized_providers dictionaries.
        """
        cls._instance = None

    @classmethod
    def unregister_provider(cls, provider_type: ProviderType) -> None:
        """Unregister a provider (mainly for testing)."""
        instance = cls()
        instance._providers.pop(provider_type, None)
        instance._initialized_providers.pop(provider_type, None)
