"""Phase 6: multi tool-capable model pool.

Before this, qwen3 was the sole hardcoded tool executor in chat_repl.py --
``"qwen3" if _is_available("qwen3") else ...`` -- for both /tools and the
/debate file-reader. A single point of failure: if qwen is rate-limited,
unhealthy, or blacklisted for a run of refusals, tool execution had nowhere
to go. This module builds an ordered, filtered POOL of tool-capable models
instead of one name, so the ReAct loop can fail over across the whole pool.

Env:
    PAL_TOOLS_MODELS            comma list defining the candidate pool (else
                                 derived from the catalog's tools=True entries
                                 plus a legacy known-tool-format list).
    PAL_TOOLS_PRIMARY_MODEL     forced first candidate, if it survives the
                                 filters (falls back to PAL_CHAT_TOOLS_MODEL
                                 for backward compatibility).
    PAL_TOOLS_FALLBACK_MODELS   comma list appended after the pool, tried
                                 only once everything ahead of them is gone.
    PAL_TOOLS_BLOCKLIST         comma list of model ids never selected.

Roles (assigned by call-site, not hardcoded to one model):
    tool_executor   runs the ReAct tool loop (/tools, /debate reader)
    reviewer        verifies/critiques another model's output
    reasoner        the smart-tier reasoning slot
    fallback        least-strict pool, last resort so a role never returns
                    an empty list while ANY model is reachable

Pipeline per role: capability (tool-call format) -> availability ->
refusal-memory blacklist -> rate-limit headroom -> context/size-guard fit ->
blocklist -> bandit reorder -> ordered candidate list, same shape
fallback_chain expects (try [0], then [1], ...).
"""

from __future__ import annotations

import os
from typing import Callable

ROLES = ("tool_executor", "reviewer", "reasoner", "fallback")

# Models known to emit a tool-call shape providers/tooling/react.py can parse:
#   OpenAI/native   <tool_call>{"name":...,"arguments":{...}}</tool_call>
#   Hermes/Qwen     <tool_call><function=NAME>...</function></tool_call>
#                   or bare <function=NAME>...</function>
# even when the catalog has no `tools` flag for them (local/custom adapters
# rarely publish function-calling metadata). Kept small and explicit rather
# than assumed -- a model that free-texts instead of calling tools silently
# breaks the ReAct loop, so unknown models are excluded from tool_executor duty.
KNOWN_TOOL_FORMAT: tuple[str, ...] = (
    "qwen3",
    "qwen/qwen3.8-27b",
    "gpt-oss-120b",
    "openai/gpt-oss-120b",
    "gpt-oss-20b",
    "openai/gpt-oss-20b",
    "nemotron",
    "nvidia/nemotron-3.5-lightning:free",
    "gemini-3.6-flash",
    "flash",
    "gemini-3.1-pro-preview",
    "pro",
)


# Formats providers/tooling/react.py can parse. Anything else (or unknown) is
# incompatible and must never be handed a tool_executor task.
REACT_FORMATS = frozenset({"native", "openai", "hermes"})

_HERMES_HINTS = ("qwen", "hermes")


def declared_tool_format(model: str) -> str | None:
    """Tool-call format `model` declares, or None if unknown.

    Sources, in order: PAL_TOOLS_FORMATS ("model=fmt,model=fmt" override), a
    catalog entry's ``tool_format`` attribute, then the KNOWN_TOOL_FORMAT
    allow-list (qwen -> hermes, the rest -> openai/native). A bare catalog
    ``tools=True`` says nothing about the text format and is NOT enough.
    """
    for pair in _env_list("PAL_TOOLS_FORMATS"):
        name, _, fmt = pair.partition("=")
        if name.strip() == model:
            return fmt.strip().lower() or None
    try:
        from providers.router import catalog

        for e in catalog.routing_catalog().entries:
            if model in ({e.model, *e.aliases}):
                fmt = getattr(e, "tool_format", None)
                if fmt:
                    return str(fmt).lower()
    except Exception:
        pass
    if model in KNOWN_TOOL_FORMAT:
        return "hermes" if any(h in model.lower() for h in _HERMES_HINTS) else "openai"
    return None


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def blocklist() -> set[str]:
    return set(_env_list("PAL_TOOLS_BLOCKLIST"))


def is_tool_format_capable(model: str) -> bool:
    """True only if `model` declares a tool-call format react.py can parse.
    Unknown or incompatible formats are excluded from tool_executor duty."""
    return declared_tool_format(model) in REACT_FORMATS


def _default_pool() -> list[str]:
    """catalog tools=True entries (best first) + the legacy known-format
    list, de-duplicated -- used when PAL_TOOLS_MODELS is unset."""
    pool: list[str] = []
    try:
        from providers.router import catalog

        for e in catalog.select(catalog.Need(tools=True)):
            if e.model not in pool:
                pool.append(e.model)
    except Exception:
        pass
    for m in KNOWN_TOOL_FORMAT:
        if m not in pool:
            pool.append(m)
    return pool


def _fits_context(model: str, task: str) -> bool:
    try:
        from providers.router import size_guard

        ok, _hint = size_guard.check_or_reroute(model, task)
        return ok
    except Exception:
        return True


def _not_rate_limited(model: str) -> bool:
    try:
        from providers.registry import ModelProviderRegistry
        from providers.router import rate_limit

        prov = ModelProviderRegistry.get_provider_for_model(model)
        provider_name = (getattr(prov, "FRIENDLY_NAME", None) or type(prov).__name__ or "").lower()
        down, _reason = rate_limit.should_downshift(provider_name, model, est_tokens=1000)
        return not down
    except Exception:
        return True


def _not_blacklisted(model: str, category: str) -> bool:
    try:
        from providers.router import refusal_memory

        return not refusal_memory.is_blacklisted(model, category)
    except Exception:
        return True


def _default_is_available() -> Callable[[str], bool]:
    from providers.registry import ModelProviderRegistry

    def is_available(m: str) -> bool:
        try:
            return ModelProviderRegistry.get_provider_for_model(m) is not None
        except Exception:
            return False

    return is_available


def select_pool(
    role: str,
    task: str = "",
    *,
    is_available: Callable[[str], bool] | None = None,
    category: str = "tools",
) -> list[str]:
    """Ordered candidate list for ``role`` (best first), all filters applied.

    ``role`` changes only the capability requirement: tool_executor requires
    a parseable tool-call format; reviewer/reasoner/fallback don't (they
    speak plain text, no <tool_call> needed). ``fallback`` is the least
    strict pool, used both as its own role and as the widen-out when a
    stricter role's pool comes back empty.
    """
    is_available = is_available or _default_is_available()

    primary = os.getenv("PAL_TOOLS_PRIMARY_MODEL", "").strip() or os.getenv("PAL_CHAT_TOOLS_MODEL", "").strip()
    explicit_pool = _env_list("PAL_TOOLS_MODELS")
    fallbacks = _env_list("PAL_TOOLS_FALLBACK_MODELS")
    blocked = blocklist()

    base = explicit_pool or _default_pool()
    candidates = ([primary] if primary else []) + base + fallbacks
    seen: set[str] = set()
    ordered: list[str] = []
    for m in candidates:
        if m and m not in seen:
            seen.add(m)
            ordered.append(m)

    def passes(m: str) -> bool:
        if m in blocked:
            return False
        if role == "tool_executor" and not is_tool_format_capable(m):
            return False
        if not is_available(m):
            return False
        if not _not_blacklisted(m, category):
            return False
        if not _not_rate_limited(m):
            return False
        if task and not _fits_context(m, task):
            return False
        return True

    filtered = [m for m in ordered if passes(m)]

    if not filtered and role not in ("fallback", "tool_executor"):
        # nothing survived the role-specific filter -> widen to the generic
        # fallback pool so the caller still gets *something* to try.
        # (never for tool_executor: a model that can't emit a parseable
        # tool-call format would silently break the ReAct loop.)
        return select_pool("fallback", task, is_available=is_available, category=category)

    try:
        from providers.router import bandit

        filtered = bandit.reorder(f"tools_pool:{role}", filtered)
    except Exception:
        pass

    return filtered


def assign_roles(pool: list[str]) -> dict[str, str]:
    """Best-effort role labels for introspection (`pal diag`-style dumps):
    first candidate is tool_executor, remainder rotate through the rest.
    Call sites should prefer select_pool(role=...) directly for real use."""
    if not pool:
        return {}
    labels = ["tool_executor", "reviewer", "reasoner", "fallback"]
    out: dict[str, str] = {}
    for i, m in enumerate(pool):
        out.setdefault(labels[min(i, len(labels) - 1)], m)
    return out


def pick(role: str, task: str = "", is_available: Callable[[str], bool] | None = None) -> str | None:
    """Single best model id for ``role`` -- convenience for callers that
    just need one name (a full pool is still what the ReAct loop should
    fail over across; see chat_repl._tools_loop_pool)."""
    pool = select_pool(role, task, is_available=is_available)
    return pool[0] if pool else None


# --- Tool transport resolution (universal tool execution) -------------------
# Which wire format a model uses to emit tool calls:
#   "text"         -> ReAct text tags <tool_call>{...}</tool_call> (qwen/hermes)
#   "openai_tools" -> structured function-calling (gpt-oss, gpt-5, o3, mistral, grok)
#   "gemini_tools" -> Gemini functionDeclarations (handled by the gemini provider)
_TRANSPORT_KNOWN = (
    ("gemini", "gemini_tools"),
)


def tool_transport_for(model: str) -> str:
    """Resolve the tool-call transport for a model.

    Every model is made execution-capable: OpenAI-compatible providers (Groq,
    OpenRouter, OpenAI, xAI) use structured function-calling ("openai_tools"),
    Gemini uses its function-declarations path ("gemini_tools"). "text" is only
    used when explicitly forced via PAL_TOOLS_TRANSPORTS, for a model whose
    endpoint cannot do structured tool calls.

    Order: PAL_TOOLS_TRANSPORTS override ("model=transport,..."), then the known
    substring map, else "openai_tools".
    """
    m = (model or "").lower()
    for pair in _env_list("PAL_TOOLS_TRANSPORTS"):
        if "=" in pair:
            name, transport = pair.split("=", 1)
            if name.strip().lower() in m:
                return transport.strip()
    for needle, transport in _TRANSPORT_KNOWN:
        if needle in m:
            return transport
    return "openai_tools"
