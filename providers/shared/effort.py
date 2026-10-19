"""Map PAL's ``thinking_mode`` to the reasoning-effort level a model accepts.

Tools pass a ``thinking_mode`` (minimal, low, medium, high, max). Providers whose API takes an explicit
effort send the mapped level, clamped to the levels the model declares in ``effort_levels``. A model
without ``effort_levels`` gets no effort parameter, so its request is unchanged.
"""

from typing import Optional

# Every effort name a provider uses, from least to most reasoning.
EFFORT_ORDER: tuple[str, ...] = ("none", "minimal", "low", "medium", "high", "xhigh", "max")

# The effort sent when a call carries no thinking_mode. It matches the tools' default thinking_mode.
DEFAULT_EFFORT = "medium"


def resolve_reasoning_effort(thinking_mode: Optional[str], capabilities) -> Optional[str]:
    """Return the effort level to send, or None when the model declares no effort levels.

    The requested level is the thinking_mode itself (or DEFAULT_EFFORT when it is absent or unknown).
    If the model does not accept that level, use the highest accepted level below it, or else the
    lowest accepted level. For example, ``max`` becomes ``xhigh`` on a model that stops at ``xhigh``,
    and ``minimal`` becomes ``low`` on a model that starts at ``low``.
    """
    levels = [level for level in (getattr(capabilities, "effort_levels", None) or []) if level in EFFORT_ORDER]
    if not levels:
        return None

    requested = thinking_mode if thinking_mode in EFFORT_ORDER else DEFAULT_EFFORT
    if requested in levels:
        return requested

    rank = EFFORT_ORDER.index
    ordered = sorted(levels, key=rank)
    below = [level for level in ordered if rank(level) < rank(requested)]
    return below[-1] if below else ordered[0]
