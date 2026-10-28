"""`pal models` -- inspect the capability catalog.

    pal models                     merged static+discovered catalog (TTL-cached)
    pal models --provider groq     one service (groq/openrouter/gemini/openai/xai/...) or adapter
    pal models --refresh           bypass the discovery cache TTL
    pal models --json              machine-readable
    pal models --all               also list services without credentials and
                                   vendor-listed models that are not curated
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from providers.router import catalog


def _flag(v) -> str:
    return "?" if v is None else ("y" if v else "-")


def _ctx(n: int) -> str:
    if not n:
        return "?"
    return f"{n // 1_000_000}M" if n >= 1_000_000 else f"{n // 1000}k"


def render(cat: catalog.Catalog, entries: list[catalog.CatalogEntry], hidden: int) -> str:
    rows = [("PROVIDER", "MODEL", "C", "T", "V", "S", "R", "CTX", "Q", "COST", "AVAIL", "SOURCE")]
    for e in entries:
        rows.append(
            (
                e.provider,
                e.model,
                _flag(e.chat),
                _flag(e.tools),
                _flag(e.vision),
                _flag(e.structured_output),
                _flag(e.reasoning),
                _ctx(e.context_limit),
                str(e.intelligence or "?"),
                f"{e.cost_profile.get('tier', '?')}/{e.cost_profile.get('basis', '?')}",
                e.availability,
                e.source,
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows]
    lines.append("")
    lines.append("C=chat T=tools V=vision S=structured-output R=reasoning  (y yes, - no, ? unknown)")
    for svc, st in sorted(cat.discovery.items()):
        detail = ", ".join(f"{k}={v}" for k, v in st.items() if v not in (None, ""))
        lines.append(f"discovery[{svc}]: {detail}")
    if hidden:
        lines.append(f"{hidden} vendor-listed model(s) hidden (uncurated or unauthenticated); use --all")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pal models", description="Capability-aware model catalog.")
    p.add_argument("--provider", help="filter by service (groq, openrouter, gemini, ...) or adapter")
    p.add_argument("--refresh", action="store_true", help="bypass the discovery cache TTL")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--all", action="store_true", help="include unauthenticated services and uncurated discovered models")
    args = p.parse_args(argv)

    # the registry/provider modules log at import; keep the table clean
    logging.disable(logging.WARNING)
    os.environ.setdefault("LOG_LEVEL", "ERROR")

    cat = catalog.build(refresh=args.refresh, discover=True, include_unavailable=args.all)
    entries = cat.entries
    if args.provider:
        want = args.provider.lower()
        known = sorted({e.provider for e in entries} | {e.adapter for e in entries})
        entries = [e for e in entries if want in (e.provider, e.adapter)]
        if not entries:
            print(f"no models for provider '{args.provider}'. known: {', '.join(known) or '(none configured)'}", file=sys.stderr)
            return 2

    total = len(entries)
    if not args.all:
        # default view: curated models only; vendor-listed extras are routing-inert
        entries = [e for e in entries if e.source != "discovered"]
    hidden = total - len(entries)

    if args.json:
        out = cat.to_dict()
        out["models"] = [e.to_dict() for e in entries]
        print(json.dumps(out, indent=2, sort_keys=True, default=str))
    else:
        print(render(cat, entries, hidden))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
