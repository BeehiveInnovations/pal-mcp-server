"""Ethics gate for routing lessons and distillation auto-learning."""

from __future__ import annotations

SENSITIVE_KEYWORDS = [
    "weapon",
    "exploit zero-day",
    "malware",
    "ransomware",
    "phishing campaign",
    "dox",
    "pii",
    "credit card",
    "social engineering",
    "unauthorized",
    "harm to people",
    "illegal",
    "extortion",
    "ddos",
    "botnet",
]


def is_ethically_sensitive(text: str) -> bool:
    """Screen text for weaponization, harm, illegal activity, or privacy violation.

    Returns True if sensitive (requiring human review), False if safe for auto-learning.
    Fail-safe: returns True if unsure or empty/invalid input.
    """
    if not text or not isinstance(text, str):
        return True

    lower_text = text.lower()
    for kw in SENSITIVE_KEYWORDS:
        if kw in lower_text:
            return True

    return False
