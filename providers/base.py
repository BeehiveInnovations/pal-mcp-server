"""Base interfaces and common behaviour for model providers."""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from .shared import ModelCapabilities, ModelResponse, ProviderType

logger = logging.getLogger(__name__)


class ModelProvider(ABC):
    """Abstract base class for all model backends in the MCP server.

    Role
        Defines the interface every provider must implement so the registry,
        restriction service, and tools have a uniform surface for listing
        models, resolving aliases, and executing requests.

    Responsibilities
        * expose static capability metadata for each supported model via
          :class:`ModelCapabilities`
        * accept user prompts, forward them to the underlying SDK, and wrap
          responses in :class:`ModelResponse`
        * report tokenizer counts for budgeting and validation logic
        * advertise provider identity (``ProviderType``) so restriction
          policies can map environment configuration onto providers
        * validate whether a model name or alias is recognised by the provider

    Shared helpers like temperature validation, alias resolution, and
    restriction-aware ``list_models`` live here so concrete subclasses only
    need to supply their catalogue and wire up SDK-specific behaviour.
    """

    # All concrete providers must define their supported models
    MODEL_CAPABILITIES: dict[str, Any] = {}

    def __init__(self, api_key: str, **kwargs):
        """Initialize the provider with API key and optional configuration."""
        self.api_key = api_key
        self.config = kwargs

    @abstractmethod
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model."""
        pass

    @abstractmethod
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the model.

        Args:
            prompt: User prompt to send to the model
            model_name: Name of the model to use
            system_prompt: Optional system prompt for model behavior
            temperature: Sampling temperature (0-2)
            max_output_tokens: Maximum tokens to generate
            **kwargs: Provider-specific parameters

        Returns:
            ModelResponse with generated content and metadata
        """
        pass

    def count_tokens(self, text: str, model_name: str) -> int:
        """Estimate token usage for a piece of text.

        Providers can rely on this shared implementation or override it when
        they expose a more accurate tokenizer. This default uses a simple
        character-based heuristic so it works even without provider-specific
        tooling.
        """

        resolved_model = self._resolve_model_name(model_name)

        if not text:
            return 0

        # Rough estimation: ~4 characters per token for English text
        estimated = max(1, len(text) // 4)
        logger.debug("Estimating %s tokens for model %s via character heuristic", estimated, resolved_model)
        return estimated

    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        pass

    @abstractmethod
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported by this provider."""
        pass

    def validate_parameters(self, model_name: str, temperature: float, **kwargs) -> None:
        """Validate model parameters against capabilities.

        Raises:
            ValueError: If parameters are invalid
        """
        capabilities = self.get_capabilities(model_name)

        # Validate temperature using constraint
        if not capabilities.temperature_constraint.validate(temperature):
            constraint_desc = capabilities.temperature_constraint.get_description()
            raise ValueError(f"Temperature {temperature} is invalid for model {model_name}. {constraint_desc}")

    def get_model_configurations(self) -> dict[str, ModelCapabilities]:
        """Get model configurations for this provider.

        This is a hook method that subclasses can override to provide
        their model configurations from different sources.

        Returns:
            Dictionary mapping model names to their ModelCapabilities objects
        """
        model_map = getattr(self, "MODEL_CAPABILITIES", None)
        if isinstance(model_map, dict) and model_map:
            return {k: v for k, v in model_map.items() if isinstance(v, ModelCapabilities)}
        return {}

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model shorthand to full name.

        This implementation uses the hook methods to support different
        model configuration sources.

        Args:
            model_name: Model name that may be an alias

        Returns:
            Resolved model name
        """
        # Get model configurations from the hook method
        model_configs = self.get_model_configurations()

        # First check if it's already a base model name (case-sensitive exact match)
        if model_name in model_configs:
            return model_name

        # Check case-insensitively for both base models and aliases
        model_name_lower = model_name.lower()

        # Check base model names case-insensitively
        for base_model in model_configs:
            if base_model.lower() == model_name_lower:
                return base_model

        # Check aliases from the model configurations
        alias_map = ModelCapabilities.collect_aliases(model_configs)
        for base_model, aliases in alias_map.items():
            if any(alias.lower() == model_name_lower for alias in aliases):
                return base_model

        # If not found, return as-is
        return model_name

    def list_models(
        self,
        *,
        respect_restrictions: bool = True,
        include_aliases: bool = True,
        lowercase: bool = False,
        unique: bool = False,
    ) -> list[str]:
        """Return formatted model names supported by this provider."""

        model_configs = self.get_model_configurations()
        if not model_configs:
            return []

        restriction_service = None
        if respect_restrictions:
            from utils.model_restrictions import get_restriction_service

            restriction_service = get_restriction_service()

        if restriction_service:
            allowed_configs = {}
            for model_name, config in model_configs.items():
                if restriction_service.is_allowed(self.get_provider_type(), model_name):
                    allowed_configs[model_name] = config
            model_configs = allowed_configs

        if not model_configs:
            return []

        return ModelCapabilities.collect_model_names(
            model_configs,
            include_aliases=include_aliases,
            lowercase=lowercase,
            unique=unique,
        )

    def close(self):
        """Clean up any resources held by the provider.

        Default implementation does nothing.
        Subclasses should override if they hold resources that need cleanup.
        """
        # Base implementation: no resources to clean up
        return

    def get_preferred_model(self, category: "ToolModelCategory", allowed_models: list[str]) -> Optional[str]:
        """Get the preferred model from this provider for a given category.

        Args:
            category: The tool category requiring a model
            allowed_models: Pre-filtered list of model names that are allowed by restrictions

        Returns:
            Model name if this provider has a preference, None otherwise
        """
        # Default implementation - providers can override with specific logic
        return None

    def get_model_registry(self) -> Optional[dict[str, Any]]:
        """Get the model registry for providers that maintain one.

        This is a hook method for providers like CustomProvider that maintain
        a dynamic model registry.

        Returns:
            Model registry dict or None if not applicable
        """
        # Default implementation - most providers don't have a registry
        return None
