#!/usr/bin/env python3
"""pal-diag — dump smart-router + toolbelt state for troubleshooting.

Usage:
    python scripts/pal-diag.py            # human-readable
    python scripts/pal-diag.py --json     # machine-readable
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def collect() -> dict:
    from providers.router import (
        classifier, health_probe, rate_limit, refusal_memory, response_cache, self_heal,
    )
    from providers.tooling import toolbelt as tb_mod

    tb = tb_mod.get_toolbelt() if tb_mod.is_enabled() else None
    return {
        "flags": {
            "PAL_SELF_HEAL":       self_heal.is_enabled(),
            "PAL_HEALTH_PROBE":    health_probe.is_enabled(),
            "PAL_RATE_LIMIT":      rate_limit.is_enabled(),
            "PAL_CACHE":           response_cache.is_enabled(),
            "PAL_REFUSAL_MEMORY":  refusal_memory.is_enabled(),
            "PAL_CLASSIFIER":      classifier.is_enabled(),
            "PAL_TOOLBELT":        tb_mod.is_enabled(),
        },
        "self_heal_alias_log": str(self_heal.DRIFT_LOG),
        "health":         health_probe.snapshot(),
        "rate_limit":     rate_limit.snapshot(),
        "cache":          response_cache.snapshot(),
        "refusals":       refusal_memory.snapshot(),
        "toolbelt":       tb.snapshot() if tb else {"note": "PAL_TOOLBELT=0"},
    }


def main() -> None:
    data = collect()
    if "--json" in sys.argv:
        print(json.dumps(data, indent=2, sort_keys=True))
        return
    print("=" * 60)
    print("PAL smart-router diag")
    print("=" * 60)
    for k, v in data["flags"].items():
        print(f"  {k:<22} {'on' if v else 'off'}")
    print("-" * 60)
    for section in ("health", "rate_limit", "cache", "refusals", "toolbelt"):
        print(f"[{section}]")
        print(json.dumps(data[section], indent=2, sort_keys=True))
    print(f"\ndrift log: {data['self_heal_alias_log']}")


if __name__ == "__main__":
    main()
