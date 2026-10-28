"""Session-scoped refusal memory.

Records (model, task_category) pairs that returned a refusal / 4xx / 5xx /
safety-block. `is_blacklisted()` lets the router skip those pairs for the
next N routing decisions.  Process-lifetime state only; a restart wipes.

Error-class-aware penalties (the anti-cascade guard)
----------------------------------------------------
A model that *refuses on policy* and a provider that *throws a transient 502*
are not the same failure and must not be penalised the same way. Treating them
alike is how a flaky upstream permanently blacklists a healthy provider and
collapses traffic onto its peers (the classic router cascade).

So we bucket every failure into a class (see ``classify_class``):

    policy       real model refusal / 403 / safety / PERMISSION_DENIED
    availability transient 429 / 5xx / RESOURCE_EXHAUSTED  (provider hiccup)
    client       400 / 401 / 422 / NOT_FOUND              (config/auth)
    unknown      anything else

and apply different blacklist rules:

    policy / client / unknown
        blacklist immediately (count >= 1), expires after ``TTL`` (300s).
        Rerouting to the same pair right now won't help.

    availability
        NEVER blacklist on a single hit. Requires ``AVAIL_MIN`` sustained
        failures within ``AVAIL_TTL`` before it counts, and the effective
        count DECAYS by one every ``AVAIL_DECAY_STEP`` seconds. Once the burst
        stops, the pair auto-reprobes (un-blacklists) instead of staying dead.
        A one-off outage can therefore never permanently poison a provider.

Phase 3: half-open probes + optional persistence
------------------------------------------------
* ``PAL_BREAKER_HALFOPEN`` (default 1): while an availability pair is tripped
  (open), one caller per ``PAL_BREAKER_HALFOPEN_INTERVAL`` seconds is let
  through as a probe. ``record_success()`` closes the breaker at once; a
  failed probe re-records, keeping it open. Applies to availability only:
  policy/client refusals are deterministic, probing them just burns calls.
* ``PAL_RESILIENCE_PERSIST`` (default 0): mirror state to
  ``~/.pal/resilience.json`` (``PAL_RESILIENCE_PATH`` overrides). Hydrated
  lazily, only when enabled, and only entries younger than
  ``PAL_RESILIENCE_PERSIST_TTL`` (default 300s). Hydrated entries keep their
  class, so availability decay/AVAIL_MIN still apply (no cascade). Disabled
  (or PAL_REFUSAL_MEMORY=0) means the file is neither read nor written.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# how long a policy/client blacklist entry stays hot (seconds)
TTL = int(os.getenv("PAL_REFUSAL_TTL", "300"))

# availability (transient 5xx/429) penalties are deliberately softer:
#   - AVAIL_MIN sustained failures required before the pair is skipped at all
#   - effective count decays 1 per AVAIL_DECAY_STEP seconds (auto-reprobe)
#   - the whole entry is forgotten after AVAIL_TTL seconds of silence
AVAIL_TTL = int(os.getenv("PAL_REFUSAL_AVAIL_TTL", "1800"))
AVAIL_MIN = int(os.getenv("PAL_REFUSAL_AVAIL_MIN", "3"))
AVAIL_DECAY_STEP = int(os.getenv("PAL_REFUSAL_AVAIL_DECAY_STEP", "300"))

# half-open: seconds between probes admitted while an availability pair is open
HALFOPEN_INTERVAL = int(os.getenv("PAL_BREAKER_HALFOPEN_INTERVAL", "60"))
# persistence: only entries younger than this are hydrated on startup
PERSIST_TTL = int(os.getenv("PAL_RESILIENCE_PERSIST_TTL", "300"))

# status codes / markers that mean "provider is up, but declined on policy"
_POLICY_STATUS = ("403", "PERMISSION_DENIED", "BLOCKED")
# status codes that mean "transient / capacity" -> availability, decays away
_AVAIL_STATUS = ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED")
# status codes that mean "your request/config is wrong" -> client
_CLIENT_STATUS = ("400", "401", "422", "NOT_FOUND")


@dataclass
class _Entry:
    ts: float
    count: int
    reason: str
    klass: str = "unknown"
    probe_ts: float = 0.0  # last half-open probe admitted


_MEM: dict[tuple[str, str], _Entry] = {}
_LOCK = threading.RLock()
_HYDRATED = False


def _flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off", "")


def is_enabled() -> bool:
    return _flag("PAL_REFUSAL_MEMORY", "1")


def halfopen_enabled() -> bool:
    return _flag("PAL_BREAKER_HALFOPEN", "1")


def persist_enabled() -> bool:
    return is_enabled() and _flag("PAL_RESILIENCE_PERSIST", "0")


def _persist_path() -> Path:
    return Path(os.getenv("PAL_RESILIENCE_PATH") or Path.home() / ".pal" / "resilience.json")


def _save_locked() -> None:
    """Atomically mirror _MEM to disk. Caller holds _LOCK. Never raises."""
    if not persist_enabled():
        return
    try:
        path = _persist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"model": m, "category": c, **asdict(e)} for (m, c), e in _MEM.items()]
        tmp = path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump({"v": 1, "entries": data}, fh)
        os.replace(tmp, path)
    except Exception as exc:  # persistence is best-effort
        log.debug("resilience persist failed: %s", exc)


def hydrate(force: bool = False) -> int:
    """Load persisted state. No-op (clean slate) unless persistence is enabled.

    Returns the number of entries loaded. Entries older than PERSIST_TTL (or
    their class TTL, whichever is shorter) are dropped, and probe state is
    reset so a restarted process can probe immediately once the interval lapses.
    """
    global _HYDRATED
    with _LOCK:
        if _HYDRATED and not force:
            return 0
        _HYDRATED = True
        if not persist_enabled():
            return 0
        try:
            raw = json.loads(_persist_path().read_text())
            rows = raw.get("entries", [])
        except Exception:
            return 0
        now, loaded = time.time(), 0
        for r in rows:
            try:
                klass = r.get("klass", "unknown")
                age = now - float(r["ts"])
                ttl = min(PERSIST_TTL, AVAIL_TTL if klass == "availability" else TTL)
                if age < 0 or age > ttl:
                    continue
                key = (str(r["model"]), str(r["category"]))
                if key in _MEM:
                    continue
                _MEM[key] = _Entry(
                    ts=float(r["ts"]),
                    count=int(r["count"]),
                    reason=str(r.get("reason", ""))[:120],
                    klass=klass,
                )
                loaded += 1
            except Exception:
                continue
        if loaded:
            log.info("refusal memory hydrated: %d entries", loaded)
        return loaded


REFUSAL_MARKERS = (
    "refuse",
    "cannot help",
    "cannot assist",
    "unable to",
    "policy",
    "safety",
    "unsafe",
    "harmful",
    "not able to comply",
)
STATUS_TRIGGERS = (
    "400",
    "401",
    "403",
    "422",
    "429",
    "500",
    "502",
    "503",
    "504",
    "NOT_FOUND",
    "PERMISSION_DENIED",
    "RESOURCE_EXHAUSTED",
    "BLOCKED",
)


def classify(err_or_response: str) -> str | None:
    """Return short refusal tag if the text looks like a refusal / error, else None."""
    if not err_or_response:
        return None
    low = err_or_response.lower()
    for m in REFUSAL_MARKERS:
        if m in low:
            return f"refusal:{m}"
    for s in STATUS_TRIGGERS:
        if s in err_or_response:
            return f"status:{s}"
    return None


def classify_class(reason: str | None) -> str:
    """Bucket a failure reason/tag into policy | availability | client | unknown.

    Accepts either a raw error string or a tag produced by ``classify`` (e.g.
    ``"status:502"`` / ``"refusal:policy"``). Ordering matters: an explicit
    availability status wins over an incidental refusal marker so a 503 body
    that happens to contain the word "unable" is still treated as transient.
    """
    if not reason:
        return "unknown"
    text = reason
    # availability first: transient capacity issues must never be mistaken for
    # a policy refusal, or a flaky provider gets permanently skipped.
    for s in _AVAIL_STATUS:
        if s in text:
            return "availability"
    for s in _POLICY_STATUS:
        if s in text:
            return "policy"
    for s in _CLIENT_STATUS:
        if s in text:
            return "client"
    low = text.lower()
    if low.startswith("refusal:") or any(m in low for m in REFUSAL_MARKERS):
        return "policy"
    return "unknown"


def record(model: str, category: str, reason: str) -> None:
    if not is_enabled():
        return
    key = (model, category)
    now = time.time()
    klass = classify_class(reason)
    with _LOCK:
        hydrate()
        cur = _MEM.get(key)
        # A change of class resets the counter: a fresh policy refusal should
        # not inherit a decayed availability count, and vice-versa.
        count = cur.count + 1 if (cur and cur.klass == klass) else 1
        _MEM[key] = _Entry(
            ts=now,
            count=count,
            reason=reason[:120],
            klass=klass,
            probe_ts=cur.probe_ts if (cur and cur.klass == klass) else 0.0,
        )
        _save_locked()
    log.info("refusal recorded: %s / %s [%s] (%s)", model, category, klass, reason[:80])


def _effective_count(entry: _Entry, now: float) -> int:
    """Availability counts decay 1 per AVAIL_DECAY_STEP seconds (auto-reprobe)."""
    if entry.klass != "availability":
        return entry.count
    decayed = entry.count - int((now - entry.ts) // AVAIL_DECAY_STEP)
    return max(decayed, 0)


def record_success(model: str, category: str) -> None:
    """A call succeeded: close the breaker for an availability pair.

    Policy/client entries are left alone (a success on another prompt does not
    mean the refusal was wrong); they expire via TTL.
    """
    if not is_enabled():
        return
    with _LOCK:
        hydrate()
        entry = _MEM.get((model, category))
        if entry is not None and entry.klass == "availability":
            _MEM.pop((model, category), None)
            _save_locked()
            log.info("breaker closed: %s / %s", model, category)


def is_blacklisted(model: str, category: str) -> bool:
    if not is_enabled():
        return False
    key = (model, category)
    now = time.time()
    with _LOCK:
        hydrate()
        entry = _MEM.get(key)
        if entry is None:
            return False

        if entry.klass == "availability":
            # transient failures: forget after AVAIL_TTL of silence, and only
            # skip while a *sustained* (non-decayed) burst is in progress.
            if now - entry.ts > AVAIL_TTL:
                _MEM.pop(key, None)
                return False
            eff = _effective_count(entry, now)
            if eff <= 0:
                _MEM.pop(key, None)
                return False
            if eff < AVAIL_MIN:
                return False
            # open: admit one half-open probe per interval
            if halfopen_enabled() and now - max(entry.ts, entry.probe_ts) >= HALFOPEN_INTERVAL:
                entry.probe_ts = now
                log.info("breaker half-open probe: %s / %s", model, category)
                return False
            return True

        # policy / client / unknown: skip immediately, expire after TTL.
        if now - entry.ts > TTL:
            _MEM.pop(key, None)
            return False
        return entry.count >= 1


def clear() -> None:
    global _HYDRATED
    with _LOCK:
        _MEM.clear()
        _HYDRATED = True  # memory is now authoritative; don't re-hydrate
        _save_locked()


def snapshot() -> dict:
    now = time.time()
    with _LOCK:
        hydrate()
        out = {}
        for (m, c), e in _MEM.items():
            ttl = AVAIL_TTL if e.klass == "availability" else TTL
            if now - e.ts > ttl:
                continue
            out[f"{m}/{c}"] = {
                "age_s": int(now - e.ts),
                "count": e.count,
                "effective": _effective_count(e, now),
                "klass": e.klass,
                "reason": e.reason,
            }
        return out
