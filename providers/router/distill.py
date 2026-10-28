"""Phase-2 offline distiller: turn episode history into a *proposed* routing order.

Reads the durable ``episodes.jsonl`` and, per category, computes which models
have actually been succeeding, then proposes a re-ordered ``CATEGORY_PREFERENCES``
list. The proposal is written to ``~/.pal/distill/proposal-<ts>.json`` and
printed as a report. It is **never auto-applied** -- adopting it means a human
hand-edits ``classifier.CATEGORY_PREFERENCES`` (or reviews a PR). This is the
"stop line" the multi-model debate drew: PAL proposes, a human disposes.

Two signals are kept separate on purpose:
  * quality_rate = success / (success + policy_refusals)
        Does this model *do the task* for this category? Availability/transient
        errors are excluded so a flaky provider is not judged on capability.
  * reliability  = 1 - availability_failures / n
        How often did the provider hiccup (5xx/429)? Reported, used only as a
        tie-breaker, never the primary demotion reason.

A model is only moved on >= MIN_SAMPLES episodes of evidence; below that it
keeps its hand-tuned prior rank. This mirrors bandit.py's runtime logic but
without the exploration bonus (offline distillation exploits what is known).

CLI::

    python -m providers.router.distill                 # analyze + write proposal
    python -m providers.router.distill --print-only    # report, no file
    python -m providers.router.distill --min-samples 10 --episodes /path.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from providers.router import episode_store
from providers.router.classifier import CATEGORY_PREFERENCES

MIN_SAMPLES = int(os.getenv("PAL_DISTILL_MIN_SAMPLES", "5"))
PROPOSAL_DIR = Path(os.getenv("PAL_DISTILL_DIR", str(Path.home() / ".pal" / "distill")))


def aggregate(episodes) -> dict[tuple[str, str], dict]:
    """Fold an episode iterable into per-(category, model) counters."""
    agg: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "n": 0,
            "success": 0,
            "policy_refusal": 0,
            "avail_fail": 0,
            "other_err": 0,
            "latency_sum": 0,
            "latency_n": 0,
        }
    )
    for ep in episodes:
        model = ep.get("model")
        cat = ep.get("category")
        if not model or cat is None:
            continue
        rec = agg[(cat, model)]
        rec["n"] += 1
        outcome = ep.get("outcome")
        err_class = ep.get("err_class")
        if outcome == "success":
            rec["success"] += 1
            lat = ep.get("latency_ms")
            if isinstance(lat, (int, float)):
                rec["latency_sum"] += lat
                rec["latency_n"] += 1
        elif outcome == "refusal":
            rec["policy_refusal"] += 1
        elif err_class == "availability":
            rec["avail_fail"] += 1
        else:
            rec["other_err"] += 1
    return agg


def _stats(rec: dict) -> dict:
    n = rec["n"]
    quality_denom = rec["success"] + rec["policy_refusal"]
    quality_rate = (rec["success"] / quality_denom) if quality_denom else None
    reliability = (1 - rec["avail_fail"] / n) if n else None
    avg_latency = (rec["latency_sum"] / rec["latency_n"]) if rec["latency_n"] else None
    return {
        "n": n,
        "success": rec["success"],
        "policy_refusal": rec["policy_refusal"],
        "avail_fail": rec["avail_fail"],
        "other_err": rec["other_err"],
        "quality_rate": quality_rate,
        "reliability": reliability,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency is not None else None,
    }


def _prior(i: int, length: int) -> float:
    return 1.0 if length <= 1 else 1.0 - i / length


# how strongly a max-trust lesson nudges a model's effective quality. At 1.0 a
# top-trust orchestrator lesson (trust*conf ≈ 1) can reorder on top of the prior
# ordering when telemetry is thin; but a model with strong measured quality (a
# high success rate over many samples) still beats a low-trust lesson, so
# evidence wins over a weak teacher. Every result is a proposal a human gates.
LESSON_NUDGE = float(os.getenv("PAL_DISTILL_LESSON_NUDGE", "1.0"))


def recommend(
    category: str,
    candidates: tuple[str, ...] | list[str],
    agg: dict,
    min_samples: int,
    lessons: list | None = None,
):
    """Return (recommended_order, per_model_stats, emerging_models, lessons_applied).

    ``lessons`` (routing-scoped, from lesson_store) nudge a model's effective
    quality by ± trust_weight * LESSON_NUDGE, always attributed. They bias the
    proposal; a human still approves it. Telemetry-only when lessons is None.
    """
    length = len(candidates)
    # map target_model -> signed nudge, remembering which lessons applied
    nudges: dict[str, float] = {}
    lessons_applied = []
    for les in lessons or []:
        if les.target_model not in candidates:
            continue  # a lesson can't introduce an unknown model into routing
        sign = 1.0 if les.action == "prefer" else -1.0
        delta = sign * les.trust_weight() * LESSON_NUDGE
        nudges[les.target_model] = nudges.get(les.target_model, 0.0) + delta
        lessons_applied.append(
            {
                "lesson_id": les.lesson_id,
                "teacher_id": les.teacher_id,
                "target_model": les.target_model,
                "action": les.action,
                "confidence": les.confidence,
                "delta": round(delta, 3),
            }
        )

    stats = {}
    ranked = []
    for i, model in enumerate(candidates):
        rec = agg.get((category, model))
        st = _stats(rec) if rec else _stats(aggregate([])[(category, model)])
        stats[model] = st
        if st["n"] >= min_samples and st["quality_rate"] is not None:
            eff_quality = st["quality_rate"]
        else:
            eff_quality = _prior(i, length)  # insufficient data -> keep prior
        eff_quality += nudges.get(model, 0.0)  # teacher lesson bias (attributed)
        reliability = st["reliability"] if st["reliability"] is not None else 1.0
        # sort desc by (quality, reliability), prior index breaks ties
        ranked.append(((-eff_quality, -reliability, i), model))
    ranked.sort()
    recommended = [m for _, m in ranked]

    # models seen for this category that are NOT in the current preference list
    listed = set(candidates)
    emerging = []
    for (cat, model), rec in agg.items():
        if cat != category or model in listed:
            continue
        st = _stats(rec)
        if st["n"] >= min_samples and (st["quality_rate"] or 0) >= 0.8:
            emerging.append({"model": model, **{k: st[k] for k in ("n", "quality_rate", "reliability")}})
    emerging.sort(key=lambda r: (-(r["quality_rate"] or 0), -r["n"]))
    return recommended, stats, emerging, lessons_applied


def build_proposal(
    episodes,
    preferences: dict | None = None,
    min_samples: int = MIN_SAMPLES,
    use_lessons: bool = False,
) -> dict:
    prefs = preferences if preferences is not None else CATEGORY_PREFERENCES
    episodes = list(episodes)
    agg = aggregate(episodes)
    categories = {}
    for cat, cands in prefs.items():
        current = list(cands)
        cat_lessons = None
        if use_lessons:
            from providers.router import lesson_store

            cat_lessons = lesson_store.routing_lessons(cat)
        recommended, stats, emerging, lessons_applied = recommend(
            cat, current, agg, min_samples, lessons=cat_lessons
        )
        categories[cat] = {
            "current_order": current,
            "recommended_order": recommended,
            "changed": recommended != current,
            "stats": stats,
            "emerging": emerging,
            "lessons_applied": lessons_applied,
        }
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "episodes_analyzed": len(episodes),
        "min_samples": min_samples,
        "lessons_used": use_lessons,
        "categories": categories,
        "apply_hint": (
            "HUMAN-GATED: review, then hand-edit classifier.CATEGORY_PREFERENCES "
            "or open a PR. This proposal is never auto-applied."
        ),
    }


def write_proposal(proposal: dict, out_dir: Path | None = None) -> Path:
    d = out_dir or PROPOSAL_DIR
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = d / f"proposal-{ts}.json"
    path.write_text(json.dumps(proposal, indent=2), encoding="utf-8")
    return path


def render_report(proposal: dict) -> str:
    lines = [
        f"PAL routing distillation — {proposal['generated']}",
        f"episodes analyzed: {proposal['episodes_analyzed']}  (min_samples={proposal['min_samples']})",
        "",
    ]
    any_change = False
    for cat, info in proposal["categories"].items():
        flag = "  ⟵ CHANGE PROPOSED" if info["changed"] else ""
        any_change = any_change or info["changed"]
        lines.append(f"[{cat}]{flag}")
        lines.append(f"  current:     {info['current_order']}")
        if info["changed"]:
            lines.append(f"  recommended: {info['recommended_order']}")
        for model in info["current_order"]:
            st = info["stats"].get(model, {})
            qr = st.get("quality_rate")
            qr_s = f"{qr:.2f}" if isinstance(qr, (int, float)) else "  -"
            lines.append(
                f"    - {model:<32} n={st.get('n', 0):<4} quality={qr_s} "
                f"avail_fail={st.get('avail_fail', 0)}"
            )
        if info["emerging"]:
            lines.append(f"  emerging (unlisted, quality>=0.8): {info['emerging']}")
        for la in info.get("lessons_applied", []):
            lines.append(
                f"    · lesson {la['lesson_id']} [{la['teacher_id']}] "
                f"{la['action']} {la['target_model']} (delta {la['delta']:+})"
            )
        lines.append("")
    if not any_change:
        lines.append("No changes proposed — current ordering matches the evidence.")
    if proposal.get("lessons_used"):
        lines.append("Teacher lessons biased this proposal (see · lines); still human-gated.")
    lines.append("Nothing was applied. This is a proposal for human review.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Distill PAL episode history into a routing proposal.")
    ap.add_argument("--episodes", help="path to episodes.jsonl (default: episode_store location)")
    ap.add_argument("--out", help="proposal output dir (default: ~/.pal/distill)")
    ap.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    ap.add_argument("--print-only", action="store_true", help="print report, do not write a file")
    ap.add_argument(
        "--with-lessons",
        action="store_true",
        help="also fold in routing-scoped teacher lessons (attributed, still human-gated)",
    )
    args = ap.parse_args(argv)

    ep_path = Path(args.episodes) if args.episodes else None
    proposal = build_proposal(
        episode_store.iter_file(ep_path),
        min_samples=args.min_samples,
        use_lessons=args.with_lessons,
    )
    print(render_report(proposal))
    if not args.print_only:
        out = write_proposal(proposal, Path(args.out) if args.out else None)
        print(f"\nProposal written to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
