"""Centralized environment variable access for PAL MCP Server."""

from __future__ import annotations

import contextvars
import os
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

# ---------------------------------------------------------------------------
# Per-call tool context (TASK-20260619-397-P2 — RC-5 TOCTOU fix)
# ---------------------------------------------------------------------------
# The active PAL tool name (e.g. "precommit", "codereview") must be visible to
# the Gemma API-key adapter so it routes to that tool's dedicated key. It was
# previously stored in os.environ["PAL_TOOL_CONTEXT"] — a PROCESS-GLOBAL that is
# a TOCTOU race: PAL runs tool calls concurrently in one asyncio loop and the
# adapter reads the value later inside an asyncio.to_thread worker. Tool B could
# overwrite the global before tool A's worker reached _get_api_key(), routing A
# through B's key / wrong keep_thoughts (RC-5, TASK-20260619-395 deep-dive).
#
# A ContextVar gives per-call isolation: each tool call sets it in its own
# logical context, and asyncio.to_thread COPIES the caller's contextvars.Context
# into the worker thread (Python 3.9+), so the worker reads the value that was
# set for ITS call — never a concurrent call's value. No cross-request bleed.
_PAL_TOOL_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "PAL_TOOL_CONTEXT", default=""
)


def set_tool_context(name: str) -> contextvars.Token:
    """Set the active PAL tool name for the current logical context.

    Returns the Token so callers may restore the prior value via
    reset_tool_context() once the tool call completes.
    """

    return _PAL_TOOL_CONTEXT.set(name or "")


def reset_tool_context(token: contextvars.Token) -> None:
    """Restore the tool context to the value held before set_tool_context()."""

    try:
        _PAL_TOOL_CONTEXT.reset(token)
    except (ValueError, LookupError):
        # Token created in a different Context (rare cross-context teardown);
        # safe to ignore — the ContextVar default already isolates per call.
        pass


def get_tool_context() -> str:
    """Return the active PAL tool name for the current context ("" if unset)."""

    return _PAL_TOOL_CONTEXT.get()

try:
    from dotenv import dotenv_values, load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    dotenv_values = None  # type: ignore[assignment]
    load_dotenv = None  # type: ignore[assignment]

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

_DOTENV_VALUES: dict[str, str | None] = {}
_FORCE_ENV_OVERRIDE = False


def _read_dotenv_values() -> dict[str, str | None]:
    if dotenv_values is not None and _ENV_PATH.exists():
        loaded = dotenv_values(_ENV_PATH)
        return dict(loaded)
    return {}


def _compute_force_override(values: Mapping[str, str | None]) -> bool:
    raw = (values.get("PAL_MCP_FORCE_ENV_OVERRIDE") or "false").strip().lower()
    return raw == "true"


def reload_env(dotenv_mapping: Mapping[str, str | None] | None = None) -> None:
    """Reload .env values and recompute override semantics.

    Args:
        dotenv_mapping: Optional mapping used instead of reading the .env file.
            Intended for tests; when provided, load_dotenv is not invoked.
    """

    global _DOTENV_VALUES, _FORCE_ENV_OVERRIDE

    if dotenv_mapping is not None:
        _DOTENV_VALUES = dict(dotenv_mapping)
        _FORCE_ENV_OVERRIDE = _compute_force_override(_DOTENV_VALUES)
        return

    _DOTENV_VALUES = _read_dotenv_values()
    _FORCE_ENV_OVERRIDE = _compute_force_override(_DOTENV_VALUES)

    if load_dotenv is not None and _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=_FORCE_ENV_OVERRIDE)


reload_env()


def env_override_enabled() -> bool:
    """Return True when PAL_MCP_FORCE_ENV_OVERRIDE is enabled via the .env file."""

    return _FORCE_ENV_OVERRIDE


def get_env(key: str, default: str | None = None) -> str | None:
    """Retrieve environment variables respecting PAL_MCP_FORCE_ENV_OVERRIDE."""

    if env_override_enabled():
        if key in _DOTENV_VALUES:
            value = _DOTENV_VALUES[key]
            return value if value is not None else default
        return default

    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """Boolean helper that respects override semantics."""

    raw_default = "true" if default else "false"
    raw_value = get_env(key, raw_default)
    return (raw_value or raw_default).strip().lower() == "true"


def get_all_env() -> dict[str, str | None]:
    """Expose the loaded .env mapping for diagnostics/logging."""

    return dict(_DOTENV_VALUES)


@contextmanager
def suppress_env_vars(*names: str):
    """Temporarily remove environment variables during the context.

    Args:
        names: Environment variable names to remove. Empty or falsy names are ignored.
    """

    removed: dict[str, str] = {}
    try:
        for name in names:
            if not name:
                continue
            if name in os.environ:
                removed[name] = os.environ[name]
                del os.environ[name]
        yield
    finally:
        for name, value in removed.items():
            os.environ[name] = value
