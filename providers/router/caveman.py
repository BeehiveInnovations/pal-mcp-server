from __future__ import annotations

import os


def is_enabled() -> bool:
    val = os.getenv("PAL_CAVEMAN", "").lower()
    return val in ("1", "on", "true", "lite", "full", "ultra")


def level() -> str:
    val = os.getenv("PAL_CAVEMAN", "").lower()
    if val in ("1", "on", "true"):
        return "ultra"
    return val or "ultra"


def system_prefix() -> str:
    if not is_enabled():
        return ""
    lvl = level()
    if lvl == "ultra":
        return (
            "CAVEMAN STYLE ULTRA: Answer in maximally compressed caveman style. "
            "Drop articles, filler words, and pleasantries. Keep ALL facts, numbers, code, file paths, and evidence byte-exact. "
            "Prefer fragments over sentences. Cut roughly 60 percent of words."
        )
    return (
            "CAVEMAN STYLE: Answer in compressed caveman style. "
            "Drop articles and filler words. Keep all facts, numbers, code, and file paths exact."
        )
