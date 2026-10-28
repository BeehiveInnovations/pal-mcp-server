"""Prompt-size guard: pre-count tokens vs per-model input cap, hint reroute if over.

Providers publish wildly different input caps (Groq gpt-oss-120b: ~7.5k TPM,
Qwen3-27b: ~6.5k, Gemini pro/flash: ~1M, or-free: ~30k). Rather than send a
request the model definitely can't accept and burn a 413 round-trip, callers
can ask this module "will it fit?" and get a same-category peer suggestion
when the answer is no.
"""

from __future__ import annotations

import os

MODEL_INPUT_CAPS: dict[str, int] = {
    "openai/gpt-oss-120b": 7500,
    "groq": 7500,
    "gpt-oss-120b": 7500,
    "openai/gpt-oss-20b": 7500,
    "gpt-oss-20b": 7500,
    "groq-fast": 7500,
    "qwen/qwen3.8-27b": 6500,
    "qwen3": 6500,
    "gemini-3.6-flash": 900_000,
    "flash": 900_000,
    "gemini-3.1-pro-preview": 900_000,
    "pro": 900_000,
    "nemotron": 900_000,
    "nvidia/nemotron-3.5-lightning:free": 900_000,
    "or-free": 30_000,
    "openrouter/free": 30_000,
    "gpt-5-mini": 100_000,
    "gpt-5.2": 350_000,
    "gpt-5.1-codex": 400_000,
    "google/gemini-2.5-pro": 900_000,
    "x-ai/grok-4.3": 128_000,
}
_DEFAULT_CAP = 100_000

_CATEGORY_ALTS = {
    "security_permissive": ["grok-4-fast", "or-free", "gemini-3-pro-preview"],
    "long_context_bulk": ["nvidia/nemotron-3.5-lightning:free", "or-free"],
    "structured_extract": ["gemini-3.6-flash", "flash", "or-free"],
    "long_form_prose": ["gpt-oss-120b", "openai/gpt-oss-120b"],
}


def guess_input_tokens(prompt: str, files: list[str] | None = None) -> int:
    """Rough token estimate: 4 chars per token for prose, plus file bytes//4."""
    total = len(prompt or "") // 4
    for f in files or []:
        try:
            total += os.path.getsize(f) // 4
        except OSError:
            pass
    return total


def cap_for(model: str) -> int:
    return MODEL_INPUT_CAPS.get(model, _DEFAULT_CAP)


def _bigger_alt(model: str) -> str | None:
    my_cap = cap_for(model)
    for cat_models in _CATEGORY_ALTS.values():
        if model in cat_models:
            for alt in cat_models:
                if alt != model and cap_for(alt) > my_cap:
                    return alt
    return "nemotron" if cap_for("nemotron") > my_cap else None


def check_or_reroute(model: str, prompt: str, files: list[str] | None = None) -> tuple[bool, str | None]:
    """Return (True, None) if the request fits the model's cap. Otherwise
    (False, "route:<alt>") hinting a same-category (or global-fallback)
    model with a larger cap, or "route:none" when no bigger alt exists."""
    tokens = guess_input_tokens(prompt, files)
    if tokens <= cap_for(model):
        return True, None
    alt = _bigger_alt(model)
    return False, f"route:{alt}" if alt else "route:none"


class PayloadTooLarge(Exception):
    """Raised by the provider send path when the POST-compression payload
    still exceeds the model cap. ``status_code`` 413 makes
    ``fallback_chain.call_with_fallback`` retry against peer models."""

    status_code = 413

    def __init__(self, model: str, tokens: int, hint: str | None):
        self.model, self.tokens, self.hint = model, tokens, hint
        super().__init__(f"413 payload too large for {model}: ~{tokens} tokens > cap {cap_for(model)} ({hint})")


def payload_text(payload) -> str:
    if isinstance(payload, str):
        return payload
    try:
        import json

        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return str(payload)


def check_payload(model: str, payload) -> tuple[bool, str | None]:
    """Size check on the final outbound payload (call AFTER headroom)."""
    return check_or_reroute(model, payload_text(payload))
