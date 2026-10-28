"""Toolbelt — a registry of local capabilities PAL exposes to delegate models.

Design (P4b MVP):
    * Each Tool declares a JSON-schema descriptor and a Python callable.
    * The Toolbelt is loaded from ~/.pal/toolbelt.json (env-overridable),
      which declares which tools are ON, their sandbox (readonly|write),
      and per-provider blocklists.
    * PAL's provider adapters (P4b-integrated) request `openai_schema()`
      when the provider supports native function-calling, or `react_schema()`
      for a text-parseable fallback.
    * PAL executes the tool locally with args from the model, logs the
      call, and feeds the result back into the conversation.

Everything is opt-in behind PAL_TOOLBELT=1; default off so existing
delegate calls stay text-only until the user explicitly enables tools.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON-schema for arguments
    handler: Callable[[dict], str]  # returns text result
    sandbox: str = "readonly"  # "readonly" | "write"
    provider_blocklist: tuple[str, ...] = field(default_factory=tuple)


class Toolbelt:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}
        self._enabled: set[str] = set()
        self._log_path = Path(os.getenv("PAL_TOOL_LOG", str(Path.home() / ".cache/pal/tool-calls.log")))

    # ---- registration ---------------------------------------------------
    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def enable(self, name: str) -> None:
        if name in self._tools:
            self._enabled.add(name)

    def load_config(self, path: Path | None = None) -> None:
        p = path or Path(os.getenv("PAL_TOOLBELT_CONFIG", str(Path.home() / ".pal/toolbelt.json")))
        if not p.exists():
            log.info("toolbelt config not found at %s; leaving all tools disabled", p)
            return
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("toolbelt config unreadable %s: %s", p, exc)
            return
        for tool_cfg in data.get("tools", []):
            name = tool_cfg.get("name")
            if name and tool_cfg.get("enabled") and name in self._tools:
                # apply optional sandbox / blocklist overrides
                spec = self._tools[name]
                spec.sandbox = tool_cfg.get("sandbox", spec.sandbox)
                spec.provider_blocklist = tuple(tool_cfg.get("provider_blocklist", spec.provider_blocklist))
                self._enabled.add(name)

    # ---- schema exports -------------------------------------------------
    def openai_schema(self, provider: str = "") -> list[dict]:
        """OpenAI/Groq/OpenRouter function-calling schema."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
            if t.name in self._enabled and provider not in t.provider_blocklist
        ]

    def gemini_schema(self, provider: str = "google") -> list[dict]:
        """Gemini function_declarations schema."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
            if t.name in self._enabled and provider not in t.provider_blocklist
        ]

    def react_schema(self, provider: str = "") -> str:
        """Human-readable schema block for models without native FC.
        Model is asked to emit  <tool_call>{"name":"...", "args":{...}}</tool_call> ."""
        entries = []
        for t in self._tools.values():
            if t.name not in self._enabled or provider in t.provider_blocklist:
                continue
            entries.append(f"- {t.name}({json.dumps(t.parameters.get('properties', {}))}) — {t.description}")
        if not entries:
            return ""
        return (
            "You may call local tools. Emit exactly one <tool_call>...</tool_call> "
            "JSON block per turn to invoke a tool; the runtime will reply with a "
            "<tool_result> block. Available:\n" + "\n".join(entries)
        )

    # ---- execution ------------------------------------------------------
    def execute(self, name: str, args: dict, caller_model: str = "") -> str:
        if name not in self._enabled:
            return f"error: tool '{name}' is not enabled"
        spec = self._tools[name]
        args = args or {}
        started = time.time()
        # HARD AUTHORIZATION BOUNDARY — enforced below the LLM. Whatever the
        # model reasoned, if this call exceeds the authorized scope (git scope
        # expansion, publishing secrets, writing credentials) it NEVER runs.
        try:
            from providers.tooling import authz

            denial = authz.enforce(name, args, authz.current_scope())
        except Exception as exc:  # enforcement must never crash the call path
            log.warning("authz gate error on %s: %s", name, exc)
            denial = None
        if denial:
            self._audit(caller_model, name, args, denial, time.time() - started)
            return denial
        try:
            out = spec.handler(args)
        except Exception as exc:
            out = f"error: {exc.__class__.__name__}: {exc}"
        dur = time.time() - started
        self._audit(caller_model, name, args, out, dur)
        return out

    def _audit(self, model: str, tool: str, args: dict, result: str, dur: float) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a", encoding="utf-8") as fp:
                from providers.router import guardrail

                line = json.dumps(
                    {
                        "ts": time.time(),
                        "model": model,
                        "tool": tool,
                        "args": args,
                        "result_head": guardrail.redact_text(result or "")[:400],
                        "duration_s": round(dur, 3),
                    },
                    ensure_ascii=False,
                )
                fp.write(guardrail.redact_text(line) + "\n")
        except OSError as exc:
            log.debug("audit log write failed: %s", exc)

    def snapshot(self) -> dict:
        return {
            "registered": sorted(self._tools),
            "enabled": sorted(self._enabled),
            "log": str(self._log_path),
        }


_INSTANCE: Toolbelt | None = None


def get_toolbelt() -> Toolbelt:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Toolbelt()
        # bootstrap built-in adapters
        from providers.tooling.adapters import bash, filesystem, gh, webfetch  # noqa: F401

        _INSTANCE.load_config()
    return _INSTANCE


def is_enabled() -> bool:
    return os.getenv("PAL_TOOLBELT", "0") in ("1", "true", "yes")
