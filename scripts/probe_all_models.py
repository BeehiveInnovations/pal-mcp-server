#!/usr/bin/env python3
"""Probe every /model-menu model with a trivial prompt and report PASS/EMPTY/FAIL.

Run with the real runtime venv:  .pal_venv/bin/python scripts/probe_all_models.py
Never raises on a single model's failure; always exits 0.
"""
from __future__ import annotations

import logging
import os
import sys
import time

os.environ.setdefault("LOG_LEVEL", "ERROR")
logging.disable(logging.WARNING)

# repo root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    from server import configure_providers

    configure_providers()
    from providers.registry import ModelProviderRegistry as R
    from providers.router import chat_repl

    models = chat_repl._available_models()
    print(f"probing {len(models)} menu models\n")

    rows = []
    for m in models:
        prov = R.get_provider_for_model(m)
        pcls = type(prov).__name__ if prov else "None"
        status, ans, lat = "FAIL:no provider", "", 0
        if prov is not None:
            t0 = time.time()
            try:
                resp = prov.generate_content(
                    "reply with the single word WORKS",
                    m,
                    "",
                    0.0,
                    max_output_tokens=32,
                )
                lat = int((time.time() - t0) * 1000)
                content = (getattr(resp, "content", "") or "").strip()
                status = "PASS" if content else "EMPTY"
                ans = content.replace("\n", " ")[:40]
            except Exception as exc:
                lat = int((time.time() - t0) * 1000)
                status = "FAIL:" + f"{type(exc).__name__}: {exc}"[:120]
        rows.append((m, pcls, status, lat, ans))

    w_m = max((len(r[0]) for r in rows), default=5)
    w_p = max((len(r[1]) for r in rows), default=8)
    print(f"{'model':<{w_m}}  {'provider':<{w_p}}  {'status':<8}  {'ms':>6}  answer")
    print("-" * (w_m + w_p + 8 + 6 + 12))
    for m, p, s, lat, a in rows:
        s_short = s if len(s) <= 8 else s[:8]
        print(f"{m:<{w_m}}  {p:<{w_p}}  {s_short:<8}  {lat:>6}  {a}")
        if s.startswith("FAIL") and len(s) > 8:
            print(f"    └─ {s}")

    npass = sum(1 for r in rows if r[2] == "PASS")
    print(f"\nPASS {npass}/{len(rows)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never hard-fail the harness
        print(f"harness error: {type(exc).__name__}: {exc}")
        sys.exit(0)
