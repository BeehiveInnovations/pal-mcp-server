"""
Model resolution utilities for Zen MCP Server.

This module provides shared model resolution logic used by both:
1. MCP server mode (server.py)
2. Skills standalone mode (zen_skill_runner.py)

This ensures consistent behavior across both execution paths.
"""

import logging
from typing import Optional

from providers import ModelProviderRegistry
from tools.models import ToolModelCategory

logger = logging.getLogger(__name__)


class ModelResolutionError(Exception):
    """Raised when model resolution fails."""

    def __init__(self, message: str, available_models: list[str], suggested_model: Optional[str] = None):
        super().__init__(message)
        self.available_models = available_models
        self.suggested_model = suggested_model


def resolve_model(
    model_name: str,
    tool_category: ToolModelCategory,
    tool_name: str = "unknown",
) -> str:
    """
    Resolve model name, handling 'auto' mode by selecting an appropriate model.

    This function provides consistent model resolution across MCP and Skills modes.

    Args:
        model_name: The requested model name (may be 'auto')
        tool_category: The tool's model category for fallback selection
        tool_name: Name of the tool (for logging)

    Returns:
        Resolved model name (never 'auto')

    Raises:
        ModelResolutionError: If model cannot be resolved or is unavailable
    """
    # Handle auto mode - resolve to specific model
    if model_name.lower() == "auto":
        resolved_model = ModelProviderRegistry.get_preferred_fallback_model(tool_category)
        if not resolved_model:
            available_models = list(ModelProviderRegistry.get_available_models(respect_restrictions=True).keys())
            raise ModelResolutionError(
                f"Cannot resolve 'auto' model - no models available for category '{tool_category.value}'. "
                f"Please configure API keys or specify a model explicitly.",
                available_models=available_models,
            )
        logger.info(f"Auto mode resolved to {resolved_model} for {tool_name} (category: {tool_category.value})")
        return resolved_model

    # Validate explicit model is available
    provider = ModelProviderRegistry.get_provider_for_model(model_name)
    if not provider:
        available_models = list(ModelProviderRegistry.get_available_models(respect_restrictions=True).keys())
        suggested_model = ModelProviderRegistry.get_preferred_fallback_model(tool_category)
        raise ModelResolutionError(
            f"Model '{model_name}' is not available with current API keys. "
            f"Available models: {', '.join(available_models)}. "
            f"Suggested model for {tool_name}: '{suggested_model}' (category: {tool_category.value})",
            available_models=available_models,
            suggested_model=suggested_model,
        )

    return model_name


def get_available_models_text() -> str:
    """
    Get a formatted string of available models.

    Returns:
        Comma-separated list of available model names, or a helpful message if none.
    """
    available_models = list(ModelProviderRegistry.get_available_models(respect_restrictions=True).keys())
    if available_models:
        return ", ".join(available_models)
    return "No models detected. Configure provider credentials or set DEFAULT_MODEL to a valid option."
