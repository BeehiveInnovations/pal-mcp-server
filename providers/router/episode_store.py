"""Durable episode store: PAL's cross-session learning substrate.

Every ephemeral router module (refusal_memory, rate_limit, response_cache)
is wiped on restart. This module is the one piece that *persists*: it appends
one JSONL line per tool invocation to ``~/.pal/episodes.jsonl`` so PAL can,
over time, learn which (category -> model) choices actually work.

This is deliberately observability-only and side-effect-free with respect to
routing. Nothing here changes a routing decision; it only *records* outcomes.
Phase-1 bandit seeding and Phase-2 offline distillation read this file. Turning
those consumers on is a separate, human-gated step -- see CHANGELOG.

Complements, does not replace, ``provider_stats.jsonl`` (quota_probe.py):
    provider_stats.jsonl = provider *health* (is the endpoint up?)
    episodes.jsonl       = per-interaction *outcome* (did this call succeed?)

Schema (one JSON object per line)::

    {"ts": 1730136721.4, "model": "gpt-oss-120b", "category": "debug",
     "prompt_hash": "sha256:ab12...", "outcome": "success",
     "err_class": null, "latency_ms": 423, "reward": null,
     "tool": "chat", "reason": null}

``outcome`` is one of success | refusal | error. ``err_class`` (when not a
success) is the coarse failure bucket from refusal_memory.classify_class:
policy | availability | client | unknown -- so distillation can tell a real
model refusal apart from a transient 5xx. ``reward`` stays null until a
trustworthy signal is wired in (Phase 2); the field exists now so the schema
is stable.

Env:
    PAL_EPISODE_STORE=0        disable entirely (default on)
    PAL_EPISODES_JSONL=<path>  override the JSONL location
    PAL_EPISODE_MEM_CAP=<int>  in-memory ring size for get_recent (default 500)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

EPISODE_PATH = Path(
    os.getenv("PAL_EPISODES_JSONL", str(Path.home() / ".pal" / "episodes.jsonl"))
)
MEM_CAP = int(os.getenv("PAL_EPISODE_MEM_CAP", "500"))

_VALID_OUTCOMES = ("success", "refusal", "error")

_LOCK = threading.Lock()
_MEM: deque[Episode] = deque(maxlen=MEM_CAP)


def is_enabled() -> bool:
    return os.getenv("PAL_EPISODE_STORE", "1") not in ("0", "false", "no")


@dataclass
class Episode:
    model: str
    category: str
    outcome: str  # success | refusal | error
    latency_ms: int = 0
    prompt_hash: str | None = None
    err_class: str | None = None  # policy | availability | client | unknown | None
    reward: float | None = None  # reserved for Phase 2; null today
    tool: str | None = None
    reason: str | None = None
    ts: float = field(default_factory=time.time)


def hash_prompt(text: str | None) -> str | None:
    """Stable, privacy-preserving prompt fingerprint (no raw prompt on disk)."""
    if not text:
        return None
    return "sha256:" + hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16]


def record_episode(ep: Episode) -> None:
    """Append one episode to the in-memory ring and the durable JSONL file.

    Never raises: a learning-substrate write must not break a tool call.
    """
    if not is_enabled():
        return
    if ep.outcome not in _VALID_OUTCOMES:
        ep.outcome = "error"
    with _LOCK:
        _MEM.append(ep)
    try:
        EPISODE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with EPISODE_PATH.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(asdict(ep), separators=(",", ":")) + "\n")
    except OSError as exc:
        log.warning("episode store write failed (%s): %s", EPISODE_PATH, exc)


def record(
    model: str,
    category: str,
    outcome: str,
    *,
    latency_ms: int = 0,
    prompt: str | None = None,
    err_class: str | None = None,
    reward: float | None = None,
    tool: str | None = None,
    reason: str | None = None,
) -> None:
    """Convenience wrapper: build an Episode and persist it."""
    record_episode(
        Episode(
            model=model,
            category=category,
            outcome=outcome,
            latency_ms=int(latency_ms),
            prompt_hash=hash_prompt(prompt),
            err_class=err_class,
            reward=reward,
            tool=tool,
            reason=(reason[:160] if reason else None),
        )
    )


def get_recent(limit: int = 50) -> list[Episode]:
    """Most-recent-first view of the in-memory ring (this process only)."""
    with _LOCK:
        items = list(_MEM)
    return items[-1:-(limit + 1):-1]


def success_rate(model: str, category: str, *, window: int = 200) -> float | None:
    """Empirical success rate for (model, category) over the recent ring.

    Returns None when there is no data. This is the read side Phase-1 bandit
    seeding will consume; it makes no routing decision on its own.
    """
    with _LOCK:
        items = [e for e in list(_MEM)[-window:] if e.model == model and e.category == category]
    if not items:
        return None
    good = sum(1 for e in items if e.outcome == "success")
    return good / len(items)


def observed(model: str, category: str, *, window: int = 200) -> tuple[int, int]:
    """Return (n, successes) for (model, category) over the recent ring.

    The read side the Phase-1 bandit consumes. Availability failures still
    count toward n here; the bandit's exploration bonus keeps a briefly-flaky
    model from being starved, and the distiller (offline) is what separates
    transient failures from genuine quality using ``err_class``.
    """
    with _LOCK:
        items = [
            e for e in list(_MEM)[-window:] if e.model == model and e.category == category
        ]
    n = len(items)
    good = sum(1 for e in items if e.outcome == "success")
    return n, good


def iter_file(path=None):
    """Yield episode dicts from the durable JSONL (for offline distillation).

    Tolerant of partial/corrupt trailing lines: a bad line is skipped, not
    fatal. Reads from disk, independent of the in-memory ring, so it sees the
    full cross-session history.
    """
    p = path or EPISODE_PATH
    try:
        with open(p, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue
    except OSError:
        return


def clear() -> None:
    """Drop the in-memory ring (does not touch the JSONL on disk)."""
    with _LOCK:
        _MEM.clear()
