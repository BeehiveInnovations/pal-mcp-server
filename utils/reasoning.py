"""Reasoning mode and effort mapping utilities for AI model providers.

This module provides unified logic for mapping between different provider-specific
reasoning/thinking parameters:
- thinking_mode: Generic parameter used across tools (minimal/low/medium/high/max)
- reasoning_effort: OpenAI Responses API specific parameter (low/medium/high)

Priority order:
1. Explicit reasoning_effort parameter (highest priority)
2. thinking_mode parameter (mapped to reasoning_effort)
3. default_reasoning_effort from tool/model configuration
4. System fallback (medium)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Mapping from thinking_mode to reasoning_effort
# OpenAI Responses API only supports: low, medium, high
THINKING_TO_EFFORT_MAP: dict[str, str] = {
    # Disable reasoning
    "none": "",
    "off": "",
    # Low effort
    "minimal": "low",
    "fast": "low",
    "quick": "low",
    "low": "low",
    # Medium effort
    "balanced": "medium",
    "default": "medium",
    "medium": "medium",
    # High effort
    "deep": "high",
    "thorough": "high",
    "high": "high",
    "max": "high",  # Responses API max is 'high', map 'max' down to it
}

# Normalization aliases for reasoning_effort
EFFORT_NORMALIZATION: dict[str, str] = {
    # Low
    "l": "low",
    "lo": "low",
    "low": "low",
    "min": "low",
    "minimum": "low",
    "fast": "low",
    # Medium
    "m": "medium",
    "med": "medium",
    "mid": "medium",
    "medium": "medium",
    "default": "medium",
    # High
    "h": "high",
    "hi": "high",
    "high": "high",
    "max": "high",
    "maximum": "high",
    "deep": "high",
    "thorough": "high",
}


def normalize_reasoning_effort(value: str | None) -> str | None:
    """Normalize reasoning_effort value to standard form (low/medium/high).

    Args:
        value: Raw reasoning_effort value

    Returns:
        Normalized value (low/medium/high) or None if invalid
    """
    if not value:
        return None

    v = value.strip().lower()
    if not v:
        return None

    # Already normalized
    if v in {"low", "medium", "high"}:
        return v

    # Try normalization map
    mapped = EFFORT_NORMALIZATION.get(v)
    return mapped if mapped in {"low", "medium", "high"} else None


def resolve_reasoning_effort(
    *,
    reasoning_effort: str | None = None,
    thinking_mode: str | None = None,
    default_reasoning_effort: str | None = None,
) -> str | None:
    """Resolve final reasoning_effort value following priority order.

    Priority order:
    1. Explicit reasoning_effort parameter (highest)
    2. thinking_mode parameter (mapped)
    3. default_reasoning_effort from configuration
    4. None (caller should apply system default)

    Args:
        reasoning_effort: Explicit reasoning effort (OpenAI specific)
        thinking_mode: Generic thinking mode (cross-provider)
        default_reasoning_effort: Default from tool/model config

    Returns:
        Resolved effort value (low/medium/high) or None
    """
    # Priority 1: Explicit reasoning_effort
    eff = normalize_reasoning_effort(reasoning_effort)
    if eff:
        return eff

    # Priority 2: thinking_mode (with mapping)
    if thinking_mode:
        tm = thinking_mode.strip().lower()
        mapped = THINKING_TO_EFFORT_MAP.get(tm)

        # Empty string means "explicitly disable reasoning"
        if mapped == "":
            return None

        # Valid mapped value
        if mapped in {"low", "medium", "high"}:
            return mapped

        # Try direct normalization (in case thinking_mode is already low/medium/high)
        norm_tm = normalize_reasoning_effort(tm)
        if norm_tm:
            return norm_tm

        logger.debug("Unknown thinking_mode '%s', ignoring mapping", thinking_mode)

    # Priority 3: Default from configuration
    return normalize_reasoning_effort(default_reasoning_effort)
