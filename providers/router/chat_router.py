"""Cheap-vs-smart tier selector for the interactive `pal chat` REPL.

Not a new router -- it reuses the existing classifier (category signals) and the
model registry (availability), and maps a message to one of three lanes:

    cheap   greetings / short / simple  -> a low-budget model
    smart   code / long / reasoning / security / "why|design|debug" -> a big model
    debate  the user asked to compare / get consensus -> handled by the caller

The actual model call still goes through server.handle_call_tool, so routing,
bandit reordering, refusal-memory and episode logging all apply as normal.

Env overrides (else first available from the built-in tier lists is used):
    PAL_CHAT_CHEAP_MODEL   e.g. gpt-oss-20b / flash-lite
    PAL_CHAT_SMART_MODEL   e.g. gpt-oss-120b / gemini-3.1-pro-preview
"""

from __future__ import annotations

import os
import re

# Preferred candidates per tier, best first. The first one whose provider is
# configured wins, so this degrades gracefully to whatever keys are present.
CHEAP_TIER = ("gpt-oss-20b", "groq-fast", "flash-lite", "gemini-3.6-flash", "gpt-5-nano")
SMART_TIER = ("gpt-oss-120b", "gemini-3.1-pro-preview", "gpt-5.2", "grok-4.1-fast", "o3")

_GREETING_RE = re.compile(
    r"^(hi|hey+|hello|yo|sup|thanks?|thank you|ok(ay)?|cool|nice|got it|"
    r"good (morning|afternoon|evening|night)|how are you|what'?s up|bye|gg|"
    r"lol|nvm|great|awesome|ping)\b[\s!.?]*$",
    re.IGNORECASE,
)

# intent words that mean "think hard" -> smart tier
_HARD_RE = re.compile(
    r"\b(why|how come|design|architect|architecture|debug|analy[sz]e|compare|"
    r"trade-?off|prove|derive|optimi[sz]e|refactor|implement|algorithm|"
    r"explain (in )?detail|step[- ]by[- ]step|root cause|reason(ing|about)|"
    r"exploit|vulnerab|payload|threat model|strategy|plan\b|evaluate|"
    r"pros and cons|in depth|"
    # code-authoring intent (write/build/fix + a code noun or language)
    r"(write|build|create|fix|generate|code)\b.{0,30}\b(code|function|script|"
    r"program|class|regex|query|sql|api|quicksort|sort|parser|python|java(script)?|"
    r"c\+\+|rust|golang|\bgo\b|bash|shell|html|css|react))\b",
    re.IGNORECASE,
)

_HARD_LEN = int(os.getenv("PAL_CHAT_HARD_LEN", "280"))


def first_available(candidates, is_available) -> str | None:
    for c in candidates:
        if is_available(c):
            return c
    return None


def _resolve(is_available):
    """Env override > capability catalog > legacy name list.

    The catalog decides eligibility from capability flags (quality floor for
    smart, cost tier for cheap); CHEAP_TIER/SMART_TIER only break ties and are
    the fallback when the catalog is empty or disabled.
    """
    from providers.router import catalog

    cheap = (
        os.getenv("PAL_CHAT_CHEAP_MODEL")
        or catalog.pick_tier("cheap", is_available, priors=CHEAP_TIER)
        or first_available(CHEAP_TIER, is_available)
    )
    smart = (
        os.getenv("PAL_CHAT_SMART_MODEL")
        or catalog.pick_tier("smart", is_available, priors=SMART_TIER)
        or first_available(SMART_TIER, is_available)
    )
    return cheap, smart


def classify_difficulty(prompt: str) -> tuple[str, str]:
    """Return (tier, reason) for a prompt, where tier is 'cheap' or 'smart'.

    Reuses providers.router.classifier for category signals; adds length and
    intent heuristics. Pure text analysis, no model call.
    """
    text = (prompt or "").strip()
    if not text:
        return "cheap", "empty"
    if _GREETING_RE.match(text):
        return "cheap", "greeting/smalltalk"

    # a fired classifier category (security / bulk / structured / prose) is a
    # strong 'this is real work' signal -> smart
    try:
        from providers.router import classifier

        cat = classifier.classify(text, None, tool_default="")
        if cat:
            return "smart", f"category:{cat}"
    except Exception:
        pass

    if "```" in text or re.search(r"\bdef \w+\(|\bclass \w+\b|;\s*$|=>", text):
        return "smart", "contains code"
    if _HARD_RE.search(text):
        return "smart", "reasoning intent"
    if len(text) > _HARD_LEN or text.count("?") >= 3:
        return "smart", "long/multi-question"
    return "cheap", "short/simple"


def route(prompt: str, is_available) -> dict:
    """Full routing decision for one message.

    ``is_available(model_id) -> bool`` lets the caller inject
    ModelProviderRegistry.get_provider_for_model without importing it here.
    Returns {tier, model, reason, cheap, smart}.
    """
    tier, reason = classify_difficulty(prompt)
    cheap, smart = _resolve(is_available)
    model = (smart or cheap) if tier == "smart" else (cheap or smart)
    return {"tier": tier, "model": model, "reason": reason, "cheap": cheap, "smart": smart}
