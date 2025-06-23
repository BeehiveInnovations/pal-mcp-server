"""Base model provider interface and data classes."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported model provider types."""

    GOOGLE = "google"
    OPENAI = "openai"
    XAI = "xai"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"
    DIAL = "dial"


class TemperatureConstraint(ABC):
    """Abstract base class for temperature constraints."""

    @abstractmethod
    def validate(self, temperature: float) -> bool:
        """Check if temperature is valid."""
        pass

    @abstractmethod
    def get_corrected_value(self, temperature: float) -> float:
        """Get nearest valid temperature."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get human-readable description of constraint."""
        pass

    @abstractmethod
    def get_default(self) -> float:
        """Get model's default temperature."""
        pass


class FixedTemperatureConstraint(TemperatureConstraint):
    """For models that only support one temperature value (e.g., O3)."""

    def __init__(self, value: float):
        self.value = value

    def validate(self, temperature: float) -> bool:
        return abs(temperature - self.value) < 1e-6  # Handle floating point precision

    def get_corrected_value(self, temperature: float) -> float:
        return self.value

    def get_description(self) -> str:
        return f"Only supports temperature={self.value}"

    def get_default(self) -> float:
        return self.value


class RangeTemperatureConstraint(TemperatureConstraint):
    """For models supporting continuous temperature ranges."""

    def __init__(self, min_temp: float, max_temp: float, default: float = None):
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.default_temp = default or (min_temp + max_temp) / 2

    def validate(self, temperature: float) -> bool:
        return self.min_temp <= temperature <= self.max_temp

    def get_corrected_value(self, temperature: float) -> float:
        return max(self.min_temp, min(self.max_temp, temperature))

    def get_description(self) -> str:
        return f"Supports temperature range [{self.min_temp}, {self.max_temp}]"

    def get_default(self) -> float:
        return self.default_temp


class DiscreteTemperatureConstraint(TemperatureConstraint):
    """For models supporting only specific temperature values."""

    def __init__(self, allowed_values: list[float], default: float = None):
        self.allowed_values = sorted(allowed_values)
        self.default_temp = default or allowed_values[len(allowed_values) // 2]

    def validate(self, temperature: float) -> bool:
        return any(abs(temperature - val) < 1e-6 for val in self.allowed_values)

    def get_corrected_value(self, temperature: float) -> float:
        return min(self.allowed_values, key=lambda x: abs(x - temperature))

    def get_description(self) -> str:
        return f"Supports temperatures: {self.allowed_values}"

    def get_default(self) -> float:
        return self.default_temp


def create_temperature_constraint(constraint_type: str) -> TemperatureConstraint:
    """Create temperature constraint object from configuration string.

    Args:
        constraint_type: Type of constraint ("fixed", "range", "discrete")

    Returns:
        TemperatureConstraint object based on configuration
    """
    if constraint_type == "fixed":
        # Fixed temperature models (O3/O4) only support temperature=1.0
        return FixedTemperatureConstraint(1.0)
    elif constraint_type == "discrete":
        # For models with specific allowed values - using common OpenAI values as default
        return DiscreteTemperatureConstraint([0.0, 0.3, 0.7, 1.0, 1.5, 2.0], 0.7)
    else:
        # Default range constraint (for "range" or None)
        return RangeTemperatureConstraint(0.0, 2.0, 0.7)


@dataclass
class ModelCapabilities:
    """Capabilities and constraints for a specific model."""

    provider: ProviderType
    model_name: str
    friendly_name: str  # Human-friendly name like "Gemini" or "OpenAI"
    context_window: int  # Total context window size in tokens
    max_output_tokens: int  # Maximum output tokens per request
    supports_extended_thinking: bool = False
    supports_system_prompts: bool = True
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_images: bool = False  # Whether model can process images
    max_image_size_mb: float = 0.0  # Maximum total size for all images in MB
    supports_temperature: bool = True  # Whether model accepts temperature parameter in API calls

    # Additional fields for comprehensive model information
    description: str = ""  # Human-readable description of the model
    aliases: list[str] = field(default_factory=list)  # Alternative names/shortcuts for the model

    # JSON mode support (for providers that support structured output)
    supports_json_mode: bool = False

    # Thinking mode support (for models with thinking capabilities)
    max_thinking_tokens: int = 0  # Maximum thinking tokens for extended reasoning models

    # Custom model flag (for models that only work with custom endpoints)
    is_custom: bool = False  # Whether this model requires custom API endpoints

    # Temperature constraint object - preferred way to define temperature limits
    temperature_constraint: TemperatureConstraint = field(
        default_factory=lambda: RangeTemperatureConstraint(0.0, 2.0, 0.7)
    )

    # Backward compatibility property for existing code
    @property
    def temperature_range(self) -> tuple[float, float]:
        """Backward compatibility for existing code that uses temperature_range."""
        if isinstance(self.temperature_constraint, RangeTemperatureConstraint):
            return (self.temperature_constraint.min_temp, self.temperature_constraint.max_temp)
        elif isinstance(self.temperature_constraint, FixedTemperatureConstraint):
            return (self.temperature_constraint.value, self.temperature_constraint.value)
        elif isinstance(self.temperature_constraint, DiscreteTemperatureConstraint):
            values = self.temperature_constraint.allowed_values
            return (min(values), max(values))
        return (0.0, 2.0)  # Fallback


@dataclass
class ModelResponse:
    """Response from a model provider."""

    content: str
    usage: dict[str, int] = field(default_factory=dict)  # input_tokens, output_tokens, total_tokens
    model_name: str = ""
    friendly_name: str = ""  # Human-friendly name like "Gemini" or "OpenAI"
    provider: ProviderType = ProviderType.GOOGLE
    metadata: dict[str, Any] = field(default_factory=dict)  # Provider-specific metadata

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.usage.get("total_tokens", 0)


class ModelProvider(ABC):
    """Abstract base class for model providers."""

    # All concrete providers must define their supported models
    SUPPORTED_MODELS: dict[str, Any] = {}

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
        temperature: float = 0.7,
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

    @abstractmethod
    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text using the specified model's tokenizer."""
        pass

    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        pass

    @abstractmethod
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported by this provider."""
        pass

    def get_effective_temperature(self, model_name: str, requested_temperature: float) -> Optional[float]:
        """Get the effective temperature to use for a model given a requested temperature.

        This method handles:
        - Models that don't support temperature (returns None)
        - Fixed temperature models (returns the fixed value)
        - Clamping to min/max range for models with constraints

        Args:
            model_name: The model to get temperature for
            requested_temperature: The temperature requested by the user/tool

        Returns:
            The effective temperature to use, or None if temperature shouldn't be passed
        """
        try:
            capabilities = self.get_capabilities(model_name)

            # Check if model supports temperature at all
            if not capabilities.supports_temperature:
                return None

            # Get temperature range
            min_temp, max_temp = capabilities.temperature_range

            # Clamp to valid range
            if requested_temperature < min_temp:
                logger.debug(f"Clamping temperature from {requested_temperature} to {min_temp} for model {model_name}")
                return min_temp
            elif requested_temperature > max_temp:
                logger.debug(f"Clamping temperature from {requested_temperature} to {max_temp} for model {model_name}")
                return max_temp
            else:
                return requested_temperature

        except Exception as e:
            logger.debug(f"Could not determine effective temperature for {model_name}: {e}")
            # If we can't get capabilities, return the requested temperature
            return requested_temperature

    def validate_parameters(self, model_name: str, temperature: float, **kwargs) -> None:
        """Validate model parameters against capabilities.

        Raises:
            ValueError: If parameters are invalid
        """
        capabilities = self.get_capabilities(model_name)

        # Validate temperature
        min_temp, max_temp = capabilities.temperature_range
        if not min_temp <= temperature <= max_temp:
            raise ValueError(f"Temperature {temperature} out of range [{min_temp}, {max_temp}] for model {model_name}")

    @abstractmethod
    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode."""
        pass

    def get_model_configurations(self) -> dict[str, ModelCapabilities]:
        """Get model configurations for this provider.

        This is a hook method that subclasses can override to provide
        their model configurations from different sources.

        Returns:
            Dictionary mapping model names to their ModelCapabilities objects
        """
        # Return SUPPORTED_MODELS if it exists (must contain ModelCapabilities objects)
        if hasattr(self, "SUPPORTED_MODELS"):
            return {k: v for k, v in self.SUPPORTED_MODELS.items() if isinstance(v, ModelCapabilities)}
        return {}

    def get_all_model_aliases(self) -> dict[str, list[str]]:
        """Get all model aliases for this provider.

        This is a hook method that subclasses can override to provide
        aliases from different sources.

        Returns:
            Dictionary mapping model names to their list of aliases
        """
        # Default implementation extracts from ModelCapabilities objects
        aliases = {}
        for model_name, capabilities in self.get_model_configurations().items():
            if capabilities.aliases:
                aliases[model_name] = capabilities.aliases
        return aliases

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

        # Check aliases from the hook method
        all_aliases = self.get_all_model_aliases()
        for base_model, aliases in all_aliases.items():
            if any(alias.lower() == model_name_lower for alias in aliases):
                return base_model

        # If not found, return as-is
        return model_name

    def list_models(self, respect_restrictions: bool = True) -> list[str]:
        """Return a list of model names supported by this provider.

        This implementation uses the get_model_configurations() hook
        to support different model configuration sources.

        Args:
            respect_restrictions: Whether to apply provider-specific restriction logic.

        Returns:
            List of model names available from this provider
        """
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        models = []

        # Get model configurations from the hook method
        model_configs = self.get_model_configurations()

        for model_name in model_configs:
            # Check restrictions if enabled
            if restriction_service and not restriction_service.is_allowed(self.get_provider_type(), model_name):
                continue

            # Add the base model
            models.append(model_name)

        # Get aliases from the hook method
        all_aliases = self.get_all_model_aliases()
        for model_name, aliases in all_aliases.items():
            # Only add aliases for models that passed restriction check
            if model_name in models:
                models.extend(aliases)

        return models

    def list_all_known_models(self) -> list[str]:
        """Return all model names known by this provider, including alias targets.

        This is used for validation purposes to ensure restriction policies
        can validate against both aliases and their target model names.

        Returns:
            List of all model names and alias targets known by this provider
        """
        all_models = set()

        # Get model configurations from the hook method
        model_configs = self.get_model_configurations()

        # Add all base model names
        for model_name in model_configs:
            all_models.add(model_name.lower())

        # Get aliases from the hook method and add them
        all_aliases = self.get_all_model_aliases()
        for _model_name, aliases in all_aliases.items():
            for alias in aliases:
                all_models.add(alias.lower())

        return list(all_models)

    def close(self):
        """Clean up any resources held by the provider.

        Default implementation does nothing.
        Subclasses should override if they hold resources that need cleanup.
        """
        # Base implementation: no resources to clean up
        return
