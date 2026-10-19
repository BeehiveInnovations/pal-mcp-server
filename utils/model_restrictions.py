"""
Model Restriction Service

This module provides centralized management of model usage restrictions
based on environment variables. It allows organizations to limit which
models can be used from each provider for cost control, compliance, or
standardization purposes.

Two complementary mechanisms are supported per provider:

Allow-lists (``*_ALLOWED_MODELS``) — if set, ONLY the listed models are usable:
- OPENAI_ALLOWED_MODELS: Comma-separated list of allowed OpenAI models
- GOOGLE_ALLOWED_MODELS: Comma-separated list of allowed Gemini models
- ANTHROPIC_ALLOWED_MODELS: Comma-separated list of allowed Anthropic (Claude) models
- XAI_ALLOWED_MODELS: Comma-separated list of allowed X.AI GROK models
- OPENROUTER_ALLOWED_MODELS: Comma-separated list of allowed OpenRouter models
- DIAL_ALLOWED_MODELS: Comma-separated list of allowed DIAL models

Block-lists (``*_DISALLOWED_MODELS``) — the listed models are rejected:
- OPENAI_DISALLOWED_MODELS, GOOGLE_DISALLOWED_MODELS, XAI_DISALLOWED_MODELS,
  OPENROUTER_DISALLOWED_MODELS, DIAL_DISALLOWED_MODELS

Precedence: a block-list match always wins. A model is allowed iff it is NOT
on the block-list AND (no allow-list is set OR it is on the allow-list). This
lets you keep a provider otherwise open while excluding a few models (e.g. very
expensive ones) without having to enumerate every permitted model.

Example:
    OPENAI_ALLOWED_MODELS=o3-mini,o4-mini      # only these two usable
    GOOGLE_ALLOWED_MODELS=flash
    OPENROUTER_DISALLOWED_MODELS=openai/gpt-5.5-pro,openai/gpt-5.4-pro  # block 2, allow the rest
"""

import logging
from collections import defaultdict
from typing import Optional

from providers.shared import ProviderType
from utils.env import get_env

logger = logging.getLogger(__name__)


class ModelRestrictionService:
    """Central authority for environment-driven model allow/block lists.

    Role
        Interpret ``*_ALLOWED_MODELS`` and ``*_DISALLOWED_MODELS`` environment
        variables, keep their entries normalised (lowercase), and answer
        whether a provider/model pairing is permitted.

    Responsibilities
        * Parse, cache, and expose per-provider allow/block sets
        * Validate configuration by cross-checking each entry against the
          provider's alias-aware model list
        * Offer helper methods such as ``is_allowed`` and ``filter_models`` to
          enforce policy everywhere model names appear (tool selection, CLI
          commands, etc.).
    """

    # Environment variable names
    ENV_VARS = {
        ProviderType.OPENAI: "OPENAI_ALLOWED_MODELS",
        ProviderType.GOOGLE: "GOOGLE_ALLOWED_MODELS",
        ProviderType.ANTHROPIC: "ANTHROPIC_ALLOWED_MODELS",
        ProviderType.XAI: "XAI_ALLOWED_MODELS",
        ProviderType.DEEPSEEK: "DEEPSEEK_ALLOWED_MODELS",
        ProviderType.QWEN: "QWEN_ALLOWED_MODELS",
        ProviderType.ZAI: "ZAI_ALLOWED_MODELS",
        ProviderType.MOONSHOT: "MOONSHOT_ALLOWED_MODELS",
        ProviderType.MINIMAX: "MINIMAX_ALLOWED_MODELS",
        ProviderType.MISTRAL: "MISTRAL_ALLOWED_MODELS",
        ProviderType.NVIDIA: "NVIDIA_ALLOWED_MODELS",
        ProviderType.PERPLEXITY: "PERPLEXITY_ALLOWED_MODELS",
        ProviderType.CHATGPT: "CHATGPT_ALLOWED_MODELS",
        ProviderType.OPENROUTER: "OPENROUTER_ALLOWED_MODELS",
        ProviderType.DIAL: "DIAL_ALLOWED_MODELS",
    }

    # Block-list environment variable names (parallel to ENV_VARS)
    DISALLOWED_ENV_VARS = {
        ProviderType.OPENAI: "OPENAI_DISALLOWED_MODELS",
        ProviderType.GOOGLE: "GOOGLE_DISALLOWED_MODELS",
        ProviderType.ANTHROPIC: "ANTHROPIC_DISALLOWED_MODELS",
        ProviderType.XAI: "XAI_DISALLOWED_MODELS",
        ProviderType.DEEPSEEK: "DEEPSEEK_DISALLOWED_MODELS",
        ProviderType.QWEN: "QWEN_DISALLOWED_MODELS",
        ProviderType.ZAI: "ZAI_DISALLOWED_MODELS",
        ProviderType.MOONSHOT: "MOONSHOT_DISALLOWED_MODELS",
        ProviderType.MINIMAX: "MINIMAX_DISALLOWED_MODELS",
        ProviderType.MISTRAL: "MISTRAL_DISALLOWED_MODELS",
        ProviderType.NVIDIA: "NVIDIA_DISALLOWED_MODELS",
        ProviderType.PERPLEXITY: "PERPLEXITY_DISALLOWED_MODELS",
        ProviderType.CHATGPT: "CHATGPT_DISALLOWED_MODELS",
        ProviderType.OPENROUTER: "OPENROUTER_DISALLOWED_MODELS",
        ProviderType.DIAL: "DIAL_DISALLOWED_MODELS",
    }

    def __init__(self):
        """Initialize the restriction service by loading from environment."""
        self.restrictions: dict[ProviderType, set[str]] = {}
        self.disallowed: dict[ProviderType, set[str]] = {}
        self._alias_resolution_cache: dict[ProviderType, dict[str, str]] = defaultdict(dict)
        self._load_from_env()

    @staticmethod
    def _parse_csv(env_value: str) -> set[str]:
        """Parse a comma-separated env value into a normalised (lowercase) set."""
        models = set()
        for model in env_value.split(","):
            cleaned = model.strip().lower()
            if cleaned:
                models.add(cleaned)
        return models

    def _load_from_env(self) -> None:
        """Load allow- and block-lists from environment variables."""
        for provider_type, env_var in self.ENV_VARS.items():
            env_value = get_env(env_var)
            if env_value is None or env_value == "":
                logger.debug(f"{env_var} not set or empty - no allow-list for {provider_type.value}")
                continue
            models = self._parse_csv(env_value)
            if models:
                self.restrictions[provider_type] = models
                self._alias_resolution_cache[provider_type] = {}
                logger.info(f"{provider_type.value} allowed models: {sorted(models)}")
            else:
                logger.debug(f"{env_var} contains only whitespace - no allow-list for {provider_type.value}")

        for provider_type, env_var in self.DISALLOWED_ENV_VARS.items():
            env_value = get_env(env_var)
            if env_value is None or env_value == "":
                continue
            models = self._parse_csv(env_value)
            if models:
                self.disallowed[provider_type] = models
                logger.info(f"{provider_type.value} disallowed models: {sorted(models)}")

    def validate_against_known_models(self, provider_instances: dict[ProviderType, any]) -> None:
        """
        Validate allow/block entries against known models from providers.

        This should be called after providers are initialized to warn about
        typos or invalid model names in the restriction lists.

        Args:
            provider_instances: Dictionary of provider type to provider instance
        """
        for label, store in (("allowed", self.restrictions), ("disallowed", self.disallowed)):
            for provider_type, entries in store.items():
                provider = provider_instances.get(provider_type)
                if not provider:
                    continue
                try:
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

                env_name = (self.ENV_VARS if label == "allowed" else self.DISALLOWED_ENV_VARS)[provider_type]
                for entry in entries:
                    if entry not in supported_models:
                        logger.warning(
                            f"Model '{entry}' in {env_name} "
                            f"is not a recognized {provider_type.value} model. "
                            f"Please check for typos. Known models: {sorted(supported_models)}"
                        )

    def _set_matches(self, provider_type: ProviderType, names_to_check: set[str], target_set: set[str]) -> bool:
        """Return True if any of ``names_to_check`` is in ``target_set``.

        Matching is alias-aware: entries in ``target_set`` that are aliases are
        resolved to their canonical model name (via provider metadata) and
        compared against the names being checked. Resolved names are cached and
        folded back into ``target_set`` for speed.
        """
        if not target_set:
            return False

        if any(name in target_set for name in names_to_check):
            return True

        try:
            from providers.registry import ModelProviderRegistry

            provider = ModelProviderRegistry.get_provider(provider_type)
        except Exception:  # pragma: no cover - registry lookup failure shouldn't break validation
            provider = None

        if not provider:
            return False

        cache = self._alias_resolution_cache.setdefault(provider_type, {})
        for entry in list(target_set):
            normalized_resolved = cache.get(entry)
            if not normalized_resolved:
                try:
                    resolved = provider._resolve_model_name(entry)
                except Exception:  # pragma: no cover - resolution failures are treated as non-matches
                    continue
                if not resolved:
                    continue
                normalized_resolved = resolved.lower()
                cache[entry] = normalized_resolved

            if normalized_resolved in names_to_check:
                target_set.add(normalized_resolved)
                cache[normalized_resolved] = normalized_resolved
                return True

        return False

    def is_allowed(self, provider_type: ProviderType, model_name: str, original_name: Optional[str] = None) -> bool:
        """
        Check if a model is allowed for a specific provider.

        A model is allowed iff it is NOT on the provider's block-list AND
        (the provider has no allow-list OR the model is on the allow-list).
        A block-list match always wins.

        Args:
            provider_type: The provider type (OPENAI, GOOGLE, etc.)
            model_name: The canonical model name (after alias resolution)
            original_name: The original model name before alias resolution (optional)

        Returns:
            True if allowed, False if restricted
        """
        # Names to check: the resolved canonical name plus the original (if different)
        names_to_check = {model_name.lower()}
        if original_name and original_name.lower() != model_name.lower():
            names_to_check.add(original_name.lower())

        # Block-list takes precedence over everything else
        disallowed_set = self.disallowed.get(provider_type)
        if disallowed_set and self._set_matches(provider_type, names_to_check, disallowed_set):
            return False

        # Allow-list: if none configured, the model is allowed (subject to block-list above)
        allowed_set = self.restrictions.get(provider_type)
        if not allowed_set:
            return True

        return self._set_matches(provider_type, names_to_check, allowed_set)

    def get_allowed_models(self, provider_type: ProviderType) -> Optional[set[str]]:
        """
        Get the set of allowed models for a provider.

        Args:
            provider_type: The provider type

        Returns:
            Set of allowed model names, or None if no allow-list
        """
        return self.restrictions.get(provider_type)

    def get_disallowed_models(self, provider_type: ProviderType) -> Optional[set[str]]:
        """
        Get the set of blocked models for a provider.

        Args:
            provider_type: The provider type

        Returns:
            Set of blocked model names, or None if no block-list
        """
        return self.disallowed.get(provider_type)

    def has_restrictions(self, provider_type: ProviderType) -> bool:
        """
        Check if a provider has any restrictions (allow-list or block-list).

        Args:
            provider_type: The provider type

        Returns:
            True if restrictions exist, False otherwise
        """
        return provider_type in self.restrictions or provider_type in self.disallowed

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
            Dictionary with provider names and their allow/block lists
        """
        summary = {}
        for provider_type, allowed_set in self.restrictions.items():
            if allowed_set:
                summary[provider_type.value] = sorted(allowed_set)
            else:
                summary[provider_type.value] = "none (provider disabled)"

        for provider_type, blocked_set in self.disallowed.items():
            if blocked_set:
                summary.setdefault(f"{provider_type.value} (disallowed)", sorted(blocked_set))

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
