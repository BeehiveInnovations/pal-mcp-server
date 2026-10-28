"""Phase 7: stateful executor -> reviewers -> judge pipeline (`pal debate`).

Each iteration runs strictly in sequence:

    executor   does / revises the work, emits a Handoff
    reviewer_i critiques the latest Handoff, emits a Handoff (findings/corrections)
    judge      rules COMPLETE or CONTINUE

State travels between stages as one JSON Handoff (see ``HANDOFF_FIELDS``).
Every model call goes through ``dispatch.generate`` (size-guard, fallback
chain, refusal/episode recording) — no provider is ever called directly.
Prior-iteration handoffs are Headroom-compressed before being re-sent; the
newest handoff is marked canonical and sent verbatim.

Judge contract (enforced in code, not trusted to the model): COMPLETE requires
``completion_status == "review_ready"`` AND zero unverified acceptance criteria
AND no open ``findings`` with severity high/critical. Otherwise the verdict is
downgraded to CONTINUE.

Anti-loop: hard ``PAL_DEBATE_MAX_ITER`` cap (clamped to ``_HARD_CEILING``) and
no-progress detection (state fingerprint unchanged for
``PAL_DEBATE_NO_PROGRESS_N`` consecutive iterations -> halt).

Flags (all optional):
    PAL_DEBATE                 1/0 master switch (default 1)
    PAL_DEBATE_MAX_ITER        default 4, ceiling 10
    PAL_DEBATE_NO_PROGRESS_N   default 2
    PAL_DEBATE_EXECUTOR        model (default PAL_CHAT_SMART_MODEL / router)
    PAL_DEBATE_REVIEWERS       comma list of models (default: 2 from router)
    PAL_DEBATE_JUDGE           model (default: first reviewer or executor)
    PAL_DEBATE_COMPRESS        1/0 Headroom-compress prior handoffs (default 1)
    PAL_DEBATE_MIN_CONFIDENCE  judge confidence floor for COMPLETE (default 0.0)
    PAL_DEBATE_STATE_DIR       persist per-mission handoffs as JSONL (default off)
    PAL_DEBATE_TEMPERATURE     default 0.2
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

_HARD_CEILING = 10
STAGES = ("executor", "reviewer", "judge")
STATUSES = ("in_progress", "review_ready", "blocked")
_BLOCKING_SEV = {"high", "critical"}

HANDOFF_FIELDS = (
    "mission_id",
    "iteration",
    "stage",
    "model",
    "role",
    "objective",
    "actions_taken",
    "files_changed",
    "commands_executed",
    "tests_executed",
    "evidence",
    "findings",
    "corrections",
    "remaining_risks",
    "open_questions",
    "completion_criteria",
    "completion_status",
    "confidence",
    "recommended_next_stage",
)
_LIST_FIELDS = {
    "actions_taken",
    "files_changed",
    "commands_executed",
    "tests_executed",
    "evidence",
    "findings",
    "corrections",
    "remaining_risks",
    "open_questions",
    "completion_criteria",
}


# ── flags ────────────────────────────────────────────────────────────────
def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in ("0", "false", "no", "off", "")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def is_enabled() -> bool:
    return _flag("PAL_DEBATE", "1")


def max_iterations() -> int:
    return max(1, min(_int("PAL_DEBATE_MAX_ITER", 4), _HARD_CEILING))


def _no_progress_n() -> int:
    return max(1, _int("PAL_DEBATE_NO_PROGRESS_N", 2))


def _csv(name: str) -> list[str]:
    return [m.strip() for m in os.getenv(name, "").split(",") if m.strip()]


# ── handoff ──────────────────────────────────────────────────────────────
@dataclass
class Handoff:
    mission_id: str = ""
    iteration: int = 0
    stage: str = "executor"
    model: str = ""
    role: str = ""
    objective: str = ""
    actions_taken: list = field(default_factory=list)
    files_changed: list = field(default_factory=list)
    commands_executed: list = field(default_factory=list)
    tests_executed: list = field(default_factory=list)
    evidence: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    corrections: list = field(default_factory=list)
    remaining_risks: list = field(default_factory=list)
    open_questions: list = field(default_factory=list)
    completion_criteria: list = field(default_factory=list)  # [{id,text,verified,evidence}]
    completion_status: str = "in_progress"
    confidence: float = 0.0
    recommended_next_stage: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def unverified(self) -> list[dict]:
        return [c for c in self.completion_criteria if not c.get("verified")]

    def blocking_findings(self) -> list[Any]:
        return [f for f in self.findings if _is_blocking(f)]


def _is_blocking(f: Any) -> bool:
    if isinstance(f, dict):
        if f.get("resolved") or f.get("status") in ("resolved", "fixed", "closed"):
            return False
        return str(f.get("severity", "")).lower() in _BLOCKING_SEV
    return False


def _norm_criteria(items: Any) -> list[dict]:
    out = []
    for i, c in enumerate(items if isinstance(items, list) else []):
        if isinstance(c, dict):
            out.append(
                {
                    "id": str(c.get("id", f"c{i + 1}")),
                    "text": str(c.get("text", "")),
                    "verified": c.get("verified") is True,  # strict: only literal true
                    "evidence": c.get("evidence", ""),
                }
            )
        elif isinstance(c, str):
            out.append({"id": f"c{i + 1}", "text": c, "verified": False, "evidence": ""})
    return out


def _apply_pinned(pinned: list[dict], reported: Any) -> list[dict]:
    """Project a model's reported criteria onto the orchestrator-pinned contract.
    Ids/text come only from ``pinned``; the model may only supply ``verified`` +
    ``evidence`` for a pinned id. Added, renamed, reworded or dropped criteria
    are ignored (a dropped one simply stays unverified)."""
    got = {c["id"]: c for c in _norm_criteria(reported)}
    out = []
    for p in pinned:
        r = got.get(p["id"])
        out.append(
            {
                "id": p["id"],
                "text": p["text"],
                "verified": bool(r and r["verified"]),
                "evidence": r["evidence"] if r else "",
            }
        )
    return out


def _extract_json(text: str) -> dict | None:
    """Lenient: whole string, ```json fence, or first balanced {...} span."""
    text = (text or "").strip()
    cands = [text]
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        cands.append(m.group(1))
    s, e = text.find("{"), text.rfind("}")
    if 0 <= s < e:
        cands.append(text[s : e + 1])
    for c in cands:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            continue
    return None


def parse_handoff(
    text: str,
    *,
    mission_id: str,
    iteration: int,
    stage: str,
    model: str,
    role: str,
    objective: str,
    pinned: list[dict] | None = None,
) -> Handoff:
    """Parse model output into a Handoff. Identity fields are forced to the
    orchestrator's values (a model cannot spoof mission/stage/model). Unparseable
    output yields a blocked handoff carrying the raw text as evidence. When
    ``pinned`` is given, completion_criteria is forced to the pinned contract."""
    obj = _extract_json(text)
    h = Handoff(mission_id=mission_id, iteration=iteration, stage=stage, model=model, role=role, objective=objective)
    if pinned is not None:
        h.completion_criteria = _apply_pinned(pinned, [])
    if obj is None:
        h.completion_status = "blocked"
        h.evidence = [f"unparseable_output: {(text or '')[:800]}"]
        h.open_questions = ["stage output was not valid JSON handoff"]
        return h
    for k in HANDOFF_FIELDS:
        if k in ("mission_id", "iteration", "stage", "model", "role", "objective"):
            continue
        v = obj.get(k)
        if v is None:
            continue
        if k in _LIST_FIELDS:
            v = v if isinstance(v, list) else [v]
        setattr(h, k, v)
    h.completion_criteria = (
        _apply_pinned(pinned, obj.get("completion_criteria"))
        if pinned is not None
        else _norm_criteria(h.completion_criteria)
    )
    if h.completion_status not in STATUSES:
        h.completion_status = "in_progress"
    try:
        h.confidence = max(0.0, min(1.0, float(h.confidence)))
    except (TypeError, ValueError):
        h.confidence = 0.0
    h.recommended_next_stage = str(h.recommended_next_stage or "")
    return h


# ── judge contract ───────────────────────────────────────────────────────
def enforce_judge(
    verdict: str, state: Handoff, judge: Handoff, pinned: list[dict] | None = None
) -> tuple[str, list[str]]:
    """Return (final_verdict, reasons). COMPLETE only if every gate passes.
    With ``pinned``, the judge is evaluated strictly against the original
    criteria: only the judge's verification of those ids counts."""
    verdict = (verdict or "").strip().upper()
    if verdict not in ("COMPLETE", "CONTINUE"):
        return "CONTINUE", [f"invalid_verdict:{verdict or 'missing'}"]
    if verdict == "CONTINUE":
        return "CONTINUE", []
    reasons = []
    if judge.completion_status != "review_ready":
        reasons.append(f"judge_status={judge.completion_status}")
    if state.completion_status != "review_ready":
        reasons.append(f"executor_status={state.completion_status}")
    if pinned is not None:
        crit = _apply_pinned(pinned, judge.completion_criteria)
    else:
        crit = judge.completion_criteria or state.completion_criteria
    if not crit:
        reasons.append("no_acceptance_criteria")
    unv = [c for c in crit if not c.get("verified")]
    if unv:
        reasons.append(f"unverified_criteria={[c['id'] for c in unv]}")
    if judge.blocking_findings() or state.blocking_findings():
        reasons.append("open_high_severity_findings")
    if judge.confidence < _float("PAL_DEBATE_MIN_CONFIDENCE", 0.0):
        reasons.append(f"confidence={judge.confidence:.2f}<floor")
    return ("CONTINUE", reasons) if reasons else ("COMPLETE", [])


# ── anti-loop ────────────────────────────────────────────────────────────
def fingerprint(state: Handoff, reviews: list[Handoff]) -> str:
    """Stable digest of *substantive* state. Free-text prose is excluded so
    rephrasing alone doesn't count as progress."""

    def _s(x):
        return json.dumps(x, sort_keys=True, default=str)

    payload = {
        "verified": sorted(c["id"] for c in state.completion_criteria if c.get("verified")),
        "files": sorted(map(_s, state.files_changed)),
        "tests": sorted(map(_s, state.tests_executed)),
        "findings": sorted(_s(f) for r in reviews for f in r.findings),
        "status": state.completion_status,
    }
    return hashlib.sha256(_s(payload).encode()).hexdigest()[:16]


# ── compression ──────────────────────────────────────────────────────────
_BULK = ("actions_taken", "evidence", "commands_executed", "tests_executed")


def _compress_prior(d: dict) -> dict:
    """Headroom-compress bulk text in an *old* handoff; structured decision
    fields (criteria, findings, status) stay verbatim."""
    from providers.router import headroom_adapter as ha

    out = dict(d)
    for k in _BULK:
        v = out.get(k)
        if v:
            out[k] = [ha.compress_tool_result(x, tool_name="debate_handoff") if isinstance(x, str) else x for x in v]
    return out


def render_context(history: list[dict], latest: dict | None) -> str:
    compress = _flag("PAL_DEBATE_COMPRESS", "1")
    parts = []
    for h in history:
        parts.append(json.dumps(_compress_prior(h) if compress else h, default=str))
    ctx = "PRIOR_HANDOFFS (compressed, oldest first):\n" + "\n".join(parts) if parts else "PRIOR_HANDOFFS: none"
    if latest is not None:
        ctx += "\n\nLATEST_HANDOFF (canonical):\n" + json.dumps(latest, default=str)
    return ctx


# ── prompts ──────────────────────────────────────────────────────────────
_SCHEMA = (
    "Reply with ONE JSON object only, keys: " + ", ".join(HANDOFF_FIELDS) + ". "
    "completion_criteria = [{id,text,verified(bool),evidence}]; findings = "
    "[{id,severity(low|medium|high|critical),text,resolved(bool)}]; "
    "completion_status in in_progress|review_ready|blocked; confidence 0..1. "
    "Mark verified=true ONLY with concrete evidence (command output, test result)."
)
_ROLE_PROMPT = {
    "executor": "You are the EXECUTOR. Do or revise the work toward the objective, apply prior corrections, "
    "report exactly what you did and verified. Set review_ready only when you believe all criteria are met. ",
    "reviewer": "You are a skeptical REVIEWER. Verify the latest handoff's claims, list defects as findings, "
    "give concrete corrections, and flip verified->false on criteria lacking evidence. ",
    "judge": 'You are the JUDGE. Add a top-level key "verdict": "COMPLETE" or "CONTINUE". COMPLETE only if '
    "completion_status=review_ready and every criterion is verified with evidence and no high/critical "
    "finding is open. Otherwise CONTINUE with recommended_next_stage. ",
}


def _prompt(role: str, objective: str, ctx: str, pinned: list[dict] | None = None) -> str:
    pin = ""
    if pinned is not None:
        pin = (
            "PINNED_CRITERIA (authoritative, immutable; reuse these exact ids, report only verified+evidence; "
            "any added/changed/removed criteria are ignored): " + json.dumps(pinned, default=str) + "\n\n"
        )
    return f"{_ROLE_PROMPT[role]}{_SCHEMA}\n\n{pin}OBJECTIVE: {objective}\n\n{ctx}"


# ── model selection ──────────────────────────────────────────────────────
def _resolve_models() -> tuple[str, list[str], str]:
    from providers.router import chat_repl, chat_router

    ex = os.getenv("PAL_DEBATE_EXECUTOR") or chat_router.route("code", chat_repl._is_available).get("smart")
    if not ex:
        raise RuntimeError("debate: no executor model available")
    revs = _csv("PAL_DEBATE_REVIEWERS")
    if not revs:
        cand = [
            chat_router.route("review", chat_repl._is_available).get("smart"),
            chat_router.route("hi", chat_repl._is_available).get("cheap"),
        ]
        revs = [m for m in dict.fromkeys(cand) if m]
    judge = os.getenv("PAL_DEBATE_JUDGE") or (revs[0] if revs else ex)
    return ex, revs, judge


def _default_call(model: str, prompt: str, system: str) -> str:
    from providers.router import dispatch

    resp = dispatch.generate(
        model, prompt, system, temperature=_float("PAL_DEBATE_TEMPERATURE", 0.2), category="debate", tool="debate"
    )
    return getattr(resp, "content", "") or ""


# ── pipeline ─────────────────────────────────────────────────────────────
def _persist(mission_id: str, h: Handoff) -> None:
    d = os.getenv("PAL_DEBATE_STATE_DIR")
    if not d:
        return
    try:
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{mission_id}.jsonl"), "a", encoding="utf-8") as fp:
            fp.write(json.dumps(h.to_dict(), default=str) + "\n")
    except OSError as exc:
        log.warning("debate: persist failed: %s", exc)


def run_debate(
    objective: str,
    criteria: list | None = None,
    *,
    call: Callable[[str, str, str], str] | None = None,
    models: tuple[str, list[str], str] | None = None,
    mission_id: str | None = None,
) -> dict:
    """Run the pipeline. ``call(model, prompt, system) -> text`` is injectable
    for tests; default routes through ``dispatch.generate`` (the PAL path).

    Returns {mission_id, outcome, iterations, halt_reason, verdict_reasons,
    final (Handoff dict), history (list of handoff dicts)}.
    outcome in COMPLETE | MAX_ITER | NO_PROGRESS | BLOCKED | DISABLED | ERROR.
    """
    mission_id = mission_id or uuid.uuid4().hex[:12]
    if not is_enabled():
        return {
            "mission_id": mission_id,
            "outcome": "DISABLED",
            "iterations": 0,
            "halt_reason": "PAL_DEBATE=0",
            "history": [],
            "final": None,
        }
    call = call or _default_call
    ex, revs, judge_m = models or _resolve_models()
    cap = max_iterations()
    stall_n = _no_progress_n()

    history: list[dict] = []  # every handoff, in order
    pinned = _norm_criteria(criteria or [])  # original contract; never mutated by any stage
    state = Handoff(
        mission_id=mission_id, objective=objective, stage="executor", completion_criteria=_apply_pinned(pinned, [])
    )
    latest: dict = state.to_dict()
    seen_fp: list[str] = []
    reasons: list[str] = []
    outcome, halt = "MAX_ITER", f"reached max iterations ({cap})"
    it = 0

    verdicts: list[str] = []

    def stage(role: str, model: str, iteration: int) -> Handoff:
        ctx = render_context([x for x in history if x["iteration"] < iteration], latest)
        raw = call(model, _prompt(role, objective, ctx, pinned), f"PAL debate {role}. Output JSON only.")
        h = parse_handoff(
            raw,
            mission_id=mission_id,
            iteration=iteration,
            stage=role,
            model=model,
            role=role,
            objective=objective,
            pinned=pinned,
        )
        if role == "judge":
            verdicts.append(str((_extract_json(raw) or {}).get("verdict", "")))
        history.append(h.to_dict())
        _persist(mission_id, h)
        return h

    try:
        for it in range(1, cap + 1):
            state = stage("executor", ex, it)
            latest = state.to_dict()
            reviews: list[Handoff] = []
            for rm in revs:
                r = stage("reviewer", rm, it)
                reviews.append(r)
                latest = r.to_dict()  # next reviewer sees the previous review, compressed history behind it
            # judge sees executor state + all reviews (reviews are in history)
            latest = {"executor": state.to_dict(), "reviews": [r.to_dict() for r in reviews]}
            j = stage("judge", judge_m, it)
            verdict, reasons = enforce_judge(verdicts[-1], state, j, pinned)

            # carry judge's verification result forward as the authoritative criteria state
            state.completion_criteria = _apply_pinned(pinned, j.completion_criteria)
            latest = state.to_dict()
            latest["corrections"] = (
                list(state.corrections) + [c for r in reviews for c in r.corrections] + list(j.corrections)
            )
            latest["findings"] = [f for r in reviews for f in r.findings] + list(j.findings)

            if verdict == "COMPLETE":
                outcome, halt = "COMPLETE", "judge COMPLETE, contract satisfied"
                break
            if all(x.completion_status == "blocked" for x in [state, j]) and j.recommended_next_stage == "":
                outcome, halt = "BLOCKED", "executor and judge both blocked"
                break

            fp = fingerprint(state, reviews + [j])
            seen_fp.append(fp)
            if len(seen_fp) >= stall_n + 1 and len(set(seen_fp[-(stall_n + 1) :])) == 1:
                outcome, halt = "NO_PROGRESS", f"state fingerprint unchanged for {stall_n} iterations"
                break
    except Exception as exc:  # total fallback exhaustion etc.
        log.warning("debate: aborted: %s", exc)
        outcome, halt = "ERROR", f"{exc.__class__.__name__}: {exc}"

    return {
        "mission_id": mission_id,
        "outcome": outcome,
        "iterations": it,
        "halt_reason": halt,
        "verdict_reasons": reasons,
        "final": latest,
        "history": history,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="pal debate", description="executor -> reviewers -> judge pipeline")
    ap.add_argument("objective")
    ap.add_argument("--criterion", action="append", default=[], help="acceptance criterion (repeatable)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from providers.router import headless

    headless._setup()
    out = run_debate(a.objective, a.criterion)
    if a.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(f"{out['outcome']} after {out['iterations']} iter — {out['halt_reason']}")
        if out["verdict_reasons"]:
            print("downgrade reasons:", "; ".join(out["verdict_reasons"]))
    return 0 if out["outcome"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
