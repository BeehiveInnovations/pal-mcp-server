"""Smart-router diagnostics collector — the data behind `pal diag`.

Importable so both the `pal` CLI and scripts/pal-diag.py share one code path.
Every section is defensive: a missing optional dependency (e.g. toolbelt's
openai import) degrades to a note instead of crashing the whole dump.
"""

from __future__ import annotations

import json
import re

# Defense in depth: every value that reaches the dump passes through _scrub().
# Sections only ever collect counters / names / states, but a future snapshot
# that leaks a token, restore-map or prompt must still not reach the terminal.
_SECRET_KEY = re.compile(
    r"(key|secret|token|password|passwd|authorization|bearer|credential|cookie|restore|prompt|mapping|payload)", re.I
)
_SECRET_VAL = re.compile(
    r"(sk-[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9]{8,}|AIza[0-9A-Za-z_\-]{20,}|xox[abpr]-[A-Za-z0-9\-]{8,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    r"|Bearer\s+\S+)"
)
_MAX_STR = 200
# key names that look secret-ish but are plain counters/booleans in our snapshots
_SAFE_KEYS = frozenset(
    {
        "tokens_per_min",
        "tpm_used",
        "tpm_cap",
        "tokens",
        "prompt_tokens",
        "max_tokens",
        # key_pool stats: plain counters/booleans, never key values
        "key_pool",
        "keys",
        "cooling",
        "active_index",
    }
)


def _scrub(obj, key: str | None = None):
    if (
        key
        and key not in _SAFE_KEYS
        and _SECRET_KEY.search(key)
        and not isinstance(obj, (bool, int, float, type(None)))
    ):
        return "<redacted>"
    if isinstance(obj, dict):
        return {str(k): _scrub(v, str(k)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        obj = _SECRET_VAL.sub("<redacted>", obj)
        return obj if len(obj) <= _MAX_STR else obj[:_MAX_STR] + "...<truncated>"
    return obj


def _safe(fn, default):
    try:
        return fn()
    except Exception as exc:  # diagnostics must never crash
        return {"error": f"{type(exc).__name__}: {exc}"} if default is None else default


def _key_pool_view():
    from providers.router import key_pool
    return {"enabled": key_pool.is_enabled(), "providers": key_pool.stats()}


def collect() -> dict:
    from providers.router import (
        bandit,
        classifier,
        debate,
        episode_store,
        fallback_chain,
        guardrail,
        headroom_adapter,
        health_probe,
        quota_probe,
        rate_limit,
        refusal_memory,
        response_cache,
        self_heal,
        size_guard,
        tools_pool,
    )

    def _toolbelt():
        from providers.tooling import toolbelt as tb_mod

        if not tb_mod.is_enabled():
            return {"note": "PAL_TOOLBELT=0"}
        tb = tb_mod.get_toolbelt()
        return tb.snapshot() if tb else {"note": "toolbelt unavailable"}

    # per-category bandit view: how PAL would currently order each category
    def _bandit_view():
        out = {}
        for cat, cands in classifier.CATEGORY_PREFERENCES.items():
            out[cat] = {
                "enabled": bandit.is_enabled(),
                "ranking": bandit.explain(cat, list(cands)),
            }
        return out

    def _episodes_view():
        recent = episode_store.get_recent(limit=20)
        return {
            "enabled": episode_store.is_enabled(),
            "path": str(episode_store.EPISODE_PATH),
            "in_memory_recent": len(recent),
            "last": [
                {
                    "model": e.model,
                    "category": e.category,
                    "outcome": e.outcome,
                    "err_class": e.err_class,
                    "latency_ms": e.latency_ms,
                }
                for e in recent[:5]
            ],
        }

    def _quota_view():
        # newest record per provider from the probe stats file; never the URL/keys
        latest: dict[str, dict] = {}
        try:
            lines = quota_probe.STATS_PATH.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {"note": "no probe data", "freshness_s": quota_probe.DEFAULT_FRESHNESS_S}
        for raw in lines:
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("provider"):
                latest[rec["provider"]] = rec
        allowed = ("available", "status", "status_code", "latency_ms", "checked_at", "reason")
        return {
            "freshness_s": quota_probe.DEFAULT_FRESHNESS_S,
            "providers": {
                p: {**{k: r[k] for k in allowed if k in r}, "usable": quota_probe.is_available(p)}
                for p, r in sorted(latest.items())
            },
        }

    def _fallback_view():
        cats = fallback_chain._load_categories()
        return {
            "enabled": fallback_chain.is_enabled(),
            "max_attempts": fallback_chain._max_attempts(),
            "categories": {c: list(m) for c, m in cats.items()},
        }

    def _size_guard_view():
        return {
            "default_cap_tokens": size_guard._DEFAULT_CAP,
            "model_caps": dict(size_guard.MODEL_INPUT_CAPS),
        }

    def _guardrail_view():
        return {
            "enabled": guardrail.is_enabled(),
            "inbound_mode": guardrail.inbound_mode(),
            "stats": guardrail.stats(),  # kind -> count only
        }

    def _headroom_view():
        st = headroom_adapter.stats()
        return {"enabled": headroom_adapter.is_enabled(), **st}

    def _catalog_view():
        from providers.router import catalog

        cat = catalog.routing_catalog()  # cache-only, no network
        by_service: dict[str, dict[str, int]] = {}
        for e in cat.entries:
            by_service.setdefault(e.provider, {}).setdefault(e.availability, 0)
            by_service[e.provider][e.availability] += 1
        return {
            "routing_enabled": catalog.is_routing_enabled(),
            "models": len(cat.entries),
            "routable": sum(1 for e in cat.entries if e.routable),
            "by_service": by_service,
            "discovery": cat.discovery,
            "cache_path": str(catalog.CACHE_PATH),
        }

    def _tool_pool_view():
        # the registry is empty in a bare CLI process; load providers once (quiet)
        try:
            import logging

            logging.disable(logging.CRITICAL)
            from server import configure_providers

            configure_providers()
        except BaseException:  # noqa: BLE001 - SystemExit when no keys configured
            pass
        finally:
            logging.disable(logging.NOTSET)
        out = {"blocklist": sorted(tools_pool.blocklist()), "roles": {}}
        for role in tools_pool.ROLES:
            out["roles"][role] = tools_pool.select_pool(role)
        return out

    def _debate_view():
        return {
            "enabled": debate.is_enabled(),
            "max_iterations": debate.max_iterations(),
            "stages": list(debate.STAGES),
        }

    return _scrub(
        {
            "flags": {
                "PAL_SELF_HEAL": _safe(self_heal.is_enabled, False),
                "PAL_HEALTH_PROBE": _safe(health_probe.is_enabled, False),
                "PAL_RATE_LIMIT": _safe(rate_limit.is_enabled, False),
                "PAL_CACHE": _safe(response_cache.is_enabled, False),
                "PAL_REFUSAL_MEMORY": _safe(refusal_memory.is_enabled, False),
                "PAL_CLASSIFIER": _safe(classifier.is_enabled, False),
                "PAL_EPISODE_STORE": _safe(episode_store.is_enabled, False),
                "PAL_BANDIT": _safe(bandit.is_enabled, False),
                "PAL_FALLBACK": _safe(fallback_chain.is_enabled, False),
                "PAL_GUARDRAIL": _safe(guardrail.is_enabled, False),
                "PAL_HEADROOM": _safe(headroom_adapter.is_enabled, False),
                "PAL_DEBATE": _safe(debate.is_enabled, False),
            },
            "self_heal_alias_log": str(self_heal.DRIFT_LOG),
            "health": _safe(health_probe.snapshot, {}),
            "quota": _safe(_quota_view, None),
            "rate_limit": _safe(rate_limit.snapshot, {}),
            "breaker": _safe(refusal_memory.snapshot, {}),
            "fallback": _safe(_fallback_view, None),
            "size_guard": _safe(_size_guard_view, None),
            "guardrail": _safe(_guardrail_view, None),
            "headroom": _safe(_headroom_view, None),
            "catalog": _safe(_catalog_view, None),
            "tool_pool": _safe(_tool_pool_view, None),
            "key_pool": _safe(_key_pool_view, None),
            "debate": _safe(_debate_view, None),
            "cache": _safe(response_cache.snapshot, {}),
            "refusals": _safe(refusal_memory.snapshot, {}),
            "episodes": _safe(_episodes_view, None),
            "bandit": _safe(_bandit_view, None),
            "toolbelt": _safe(_toolbelt, {"note": "toolbelt import failed"}),
        }
    )


SECTIONS = (
    "health",
    "quota",
    "rate_limit",
    "cache",
    "breaker",
    "refusals",
    "fallback",
    "size_guard",
    "guardrail",
    "headroom",
    "catalog",
    "tool_pool",
    "key_pool",
    "debate",
    "episodes",
    "bandit",
    "toolbelt",
)


def render(data: dict) -> str:
    lines = ["=" * 60, "PAL smart-router diag", "=" * 60]
    for k, v in data["flags"].items():
        lines.append(f"  {k:<22} {'on' if v else 'off'}")
    lines.append("-" * 60)
    for section in SECTIONS:
        lines.append(f"[{section}]")
        lines.append(json.dumps(_scrub(data.get(section)), indent=2, sort_keys=True, default=str))
    lines.append(f"\ndrift log: {data['self_heal_alias_log']}")
    return "\n".join(lines)
