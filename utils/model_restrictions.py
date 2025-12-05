"""
Model Restriction Service

This module provides centralized management of model usage restrictions
based on environment variables. It allows organizations to limit which
models can be used from each provider for cost control, compliance, or
standardization purposes.

Environment Variables:
- OPENAI_ALLOWED_MODELS: Comma-separated list of allowed OpenAI models
- GOOGLE_ALLOWED_MODELS: Comma-separated list of allowed Gemini/Vertex AI models
- XAI_ALLOWED_MODELS: Comma-separated list of allowed X.AI GROK models
- OPENROUTER_ALLOWED_MODELS: Comma-separated list of allowed OpenRouter models
- DIAL_ALLOWED_MODELS: Comma-separated list of allowed DIAL models

Example:
    OPENAI_ALLOWED_MODELS=o3-mini,o4-mini
    GOOGLE_ALLOWED_MODELS=flash
    XAI_ALLOWED_MODELS=grok-3,grok-3-fast
    OPENROUTER_ALLOWED_MODELS=opus,sonnet,mistral
"""

import logging
from collections import defaultdict
from typing import Optional

from providers.shared import ProviderType
from utils.env import get_env

logger = logging.getLogger(__name__)


class ModelRestrictionService:
    """Central authority for environment-driven model allowlists.

    Role
        Interpret ``*_ALLOWED_MODELS`` environment variables, keep their
        entries normalised (lowercase), and answer whether a provider/model
        pairing is permitted.

    Responsibilities
        * Parse, cache, and expose per-provider restriction sets
        * Validate configuration by cross-checking each entry against the
          provider’s alias-aware model list
        * Offer helper methods such as ``is_allowed`` and ``filter_models`` to
          enforce policy everywhere model names appear (tool selection, CLI
          commands, etc.).
    """

    # Environment variable names
    ENV_VARS = {
        ProviderType.OPENAI: "OPENAI_ALLOWED_MODELS",
        ProviderType.GOOGLE: "GOOGLE_ALLOWED_MODELS",
        ProviderType.VERTEX_AI: "GOOGLE_ALLOWED_MODELS",  # Vertex AI uses same models as Google
        ProviderType.XAI: "XAI_ALLOWED_MODELS",
        ProviderType.OPENROUTER: "OPENROUTER_ALLOWED_MODELS",
        ProviderType.DIAL: "DIAL_ALLOWED_MODELS",
    }

    def __init__(self):
        """Initialize the restriction service by loading from environment."""
        self.restrictions: dict[ProviderType, set[str]] = {}
        self._alias_resolution_cache: dict[ProviderType, dict[str, str]] = defaultdict(dict)
        self._load_from_env()

    def _load_from_env(self) -> None:
        """Load restrictions from environment variables."""
        for provider_type, env_var in self.ENV_VARS.items():
            env_value = get_env(env_var)

            if env_value is None or env_value == "":
                # Not set or empty - no restrictions (allow all models)
                logger.debug(f"{env_var} not set or empty - all {provider_type.value} models allowed")
                continue

            # Parse comma-separated list
            models = set()
            for model in env_value.split(","):
                cleaned = model.strip().lower()
                if cleaned:
                    models.add(cleaned)

            if models:
                self.restrictions[provider_type] = models
                self._alias_resolution_cache[provider_type] = {}
                logger.info(f"{provider_type.value} allowed models: {sorted(models)}")
            else:
                # All entries were empty after cleaning - treat as no restrictions
                logger.debug(f"{env_var} contains only whitespace - all {provider_type.value} models allowed")

    def validate_against_known_models(self, provider_instances: dict[ProviderType, any]) -> None:
        """
        Validate restrictions against known models from providers.

        This should be called after providers are initialized to warn about
        typos or invalid model names in the restriction lists.

        Args:
            provider_instances: Dictionary of provider type to provider instance
        """
        for provider_type, allowed_models in self.restrictions.items():
            provider = provider_instances.get(provider_type)
            if not provider:
                continue

            # Get all supported models using the clean polymorphic interface
            try:
                # Gather canonical models and aliases with consistent formatting
                all_models = provider.list_models(
                    respect_restrictions=False,
                    include_aliases=True,
                    lowercase=True,
                    unique=True,
                )
                supported_models = set(all_models)
            except Exception as e:
                logger.debug(f"Could not get model list from {provider_type.value} provider: {e}")
                supported_models = set()

            # Check each allowed model
            for allowed_model in allowed_models:
                if allowed_model not in supported_models:
                    logger.warning(
                        f"Model '{allowed_model}' in {self.ENV_VARS[provider_type]} "
                        f"is not a recognized {provider_type.value} model. "
                        f"Please check for typos. Known models: {sorted(supported_models)}"
                    )

    def is_allowed(self, provider_type: ProviderType, model_name: str, original_name: Optional[str] = None) -> bool:
        """
        Check if a model is allowed for a specific provider.

        Args:
            provider_type: The provider type (OPENAI, GOOGLE, etc.)
            model_name: The canonical model name (after alias resolution)
            original_name: The original model name before alias resolution (optional)

        Returns:
            True if allowed (or no restrictions), False if restricted
        """
        if provider_type not in self.restrictions:
            # No restrictions for this provider
            return True

        allowed_set = self.restrictions[provider_type]

        if len(allowed_set) == 0:
            # Empty set - allowed
            return True

        # Check both the resolved name and original name (if different)
        names_to_check = {model_name.lower()}
        if original_name and original_name.lower() != model_name.lower():
            names_to_check.add(original_name.lower())

        # If any of the names is in the allowed set, it's allowed
        if any(name in allowed_set for name in names_to_check):
            return True

        # Attempt to resolve canonical names for allowed aliases using provider metadata.
        try:
            from providers.registry import ModelProviderRegistry

            provider = ModelProviderRegistry.get_provider(provider_type)
        except Exception:  # pragma: no cover - registry lookup failure shouldn't break validation
            provider = None

        if provider:
            cache = self._alias_resolution_cache.setdefault(provider_type, {})

            for allowed_entry in list(allowed_set):
                normalized_resolved = cache.get(allowed_entry)

                if not normalized_resolved:
                    try:
                        resolved = provider._resolve_model_name(allowed_entry)
                    except Exception:  # pragma: no cover - resolution failures are treated as non-matches
                        continue

                    if not resolved:
                        continue

                    normalized_resolved = resolved.lower()
                    cache[allowed_entry] = normalized_resolved

                if normalized_resolved in names_to_check:
                    allowed_set.add(normalized_resolved)
                    cache[normalized_resolved] = normalized_resolved
                    return True

        return False

    def get_allowed_models(self, provider_type: ProviderType) -> Optional[set[str]]:
        """
        Get the set of allowed models for a provider.

        Args:
            provider_type: The provider type

        Returns:
            Set of allowed model names, or None if no restrictions
        """
        return self.restrictions.get(provider_type)

    def has_restrictions(self, provider_type: ProviderType) -> bool:
        """
        Check if a provider has any restrictions.

        Args:
            provider_type: The provider type

        Returns:
            True if restrictions exist, False otherwise
        """
        return provider_type in self.restrictions

    def filter_models(self, provider_type: ProviderType, models: list[str]) -> list[str]:
        """
        Filter a list of models based on restrictions.

        Args:
            provider_type: The provider type
            models: List of model names to filter

        Returns:
            Filtered list containing only allowed models
        """
        if not self.has_restrictions(provider_type):
            return models

        return [m for m in models if self.is_allowed(provider_type, m)]

    def get_restriction_summary(self) -> dict[str, any]:
        """
        Get a summary of all restrictions for logging/debugging.

        Returns:
            Dictionary with provider names and their restrictions
        """
        summary = {}
        for provider_type, allowed_set in self.restrictions.items():
            if allowed_set:
                summary[provider_type.value] = sorted(allowed_set)
            else:
                summary[provider_type.value] = "none (provider disabled)"

        return summary


# Global instance (singleton pattern)
_restriction_service: Optional[ModelRestrictionService] = None


def get_restriction_service() -> ModelRestrictionService:
    """
    Get the global restriction service instance.

    Returns:
        The singleton ModelRestrictionService instance
    """
    global _restriction_service
    if _restriction_service is None:
        _restriction_service = ModelRestrictionService()
    return _restriction_service
