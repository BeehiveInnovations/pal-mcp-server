"""Adaptive Writer -> Executor -> (Reviewers) -> Judge mission pipeline.

PAL sizes the team to the mission. It first assesses the mission's TYPE
(code / recon / fileops / analysis / general) and COMPLEXITY (1-5), then:

  - complexity 1 (easy):     ONE model does the whole thing directly.
  - complexity 2-3 (moderate): WRITER -> EXECUTOR -> JUDGE.
  - complexity 4-5 (complex):  + 1-2 REVIEWER sub-agents before the judge.

Models are chosen by capability and mission type; roles get DIFFERENT models so
work is genuinely divided across accounts. Every call goes through
``dispatch.generate`` (key_pool rotation + guardrails + Headroom). Anthropic/
Claude is never selected. No database; a hard iteration cap prevents loops.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

log = logging.getLogger(__name__)

_TYPES = ("code", "recon", "fileops", "analysis", "general")

_WRITER_SYS = (
    "You are the WRITER sub-agent of a mission. Do NOT run tools. You are shown "
    "the current content of relevant repo files under REPO CONTEXT. Given the "
    "mission, acceptance criteria and feedback, output ONLY one JSON object:\n"
    '{"files":[{"path":"...","content":"..."}],'
    '"edits":[{"path":"...","old":"exact snippet from the file","new":"replacement"}],'
    '"commands":["..."],"rationale":"...","done_hint":false}\n'
    "Use edits to MODIFY existing files: old must match the current file text "
    "exactly and be small+unique; use files only for NEW files; commands run bash "
    "on Kali. Preserve all unrelated code."
)
_REVIEWER_SYS = (
    "You are a REVIEWER sub-agent. Given the mission, the writer's plan and the "
    "executor's results, output ONLY one JSON object:\n"
    '{"issues":["..."],"corrections":"...","looks_done":false}\n'
    "List concrete defects and how to fix them; be terse."
)
_JUDGE_SYS = (
    "You are the JUDGE sub-agent. Given the mission, acceptance criteria, the "
    "executor's results and any reviewer notes, output ONLY one JSON object:\n"
    '{"decision":"COMPLETE","reason":"...","feedback":"..."}\n'
    'decision is "COMPLETE" or "CONTINUE". Say COMPLETE only when every '
    "acceptance criterion is verified; otherwise CONTINUE with concrete feedback."
)


def _no_claude(models: list[str]) -> list[str]:
    return [m for m in models if "claude" not in m.lower() and "anthropic" not in m.lower()]


def _env_models(var: str, default: list[str]) -> list[str]:
    got = [m.strip() for m in (os.getenv(var, "") or "").split(",") if m.strip()]
    return _no_claude(got or default)


def _pick(models: list[str]) -> str | None:
    from providers.router import chat_repl

    for m in models:
        try:
            if chat_repl._is_available(m):
                return m
        except Exception:
            pass
    return models[0] if models else None


def _pick_distinct(models: list[str], used: set[str]) -> str | None:
    from providers.router import chat_repl

    for m in models:
        if m in used:
            continue
        try:
            if chat_repl._is_available(m):
                return m
        except Exception:
            pass
    return _pick([m for m in models if m not in used]) or _pick(models)


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


# --- adaptive assessment ----------------------------------------------------

def _heuristic_assess(goal: str) -> dict:
    g = goal.lower()
    # Only classify as recon when it is a GENUINE security action (verb+target),
    # not when a security word is merely the object of a file/git op (e.g.
    # "create a directory called enumeration").
    try:
        from providers.router import intent as _intent

        _is_sec = _intent.classify_intent(goal).is_security
    except Exception:
        _is_sec = any(w in g for w in ("nmap", "scan", "recon", "enumerate", "subdomain", "port", "exploit", "payload", "nuclei"))
    if _is_sec:
        typ = "recon"
    elif any(w in g for w in ("code", "function", "class", "refactor", "implement", "module", "script", "api", "bug", "test")):
        typ = "code"
    elif any(w in g for w in ("analyze", "summarize", "explain", "compare", "review", "assess", "report on")):
        typ = "analysis"
    elif any(w in g for w in ("file", "create", "write", "move", "rename", "directory", ".txt", ".json", "folder")):
        typ = "fileops"
    else:
        typ = "general"
    steps = g.count(" and ") + g.count(",") + g.count(" then ") + g.count(";") + g.count(" after ")
    n = len(goal)
    if n > 300 or steps >= 5:
        complexity = 5
    elif n > 200 or steps >= 3:
        complexity = 4
    elif n > 110 or steps >= 2:
        complexity = 3
    elif n > 70 or steps >= 1:
        complexity = 2
    else:
        complexity = 1
    return {"type": typ, "complexity": complexity}


def assess_mission(goal: str, model: str | None = None) -> dict:
    """Classify mission type + complexity (1-5): a cheap model, heuristic fallback."""
    base = _heuristic_assess(goal)
    if os.getenv("PAL_MISSION_AUTO", "1").lower() in ("0", "false", "no"):
        return base
    from providers.router import dispatch

    m = model or _pick(_env_models("PAL_MISSION_ASSESS_MODELS", ["gemini-3.5-flash-lite", "qwen3"]))
    if not m:
        return base
    try:
        r = dispatch.generate(
            m,
            'Classify this mission. Output ONLY JSON {"type":"code|recon|fileops|analysis|general",'
            f'"complexity":1-5}}.\nMISSION: {goal}',
            "You are a concise mission classifier.",
            temperature=0.0, category="mission", tool="mission", max_output_tokens=80,
        )
        j = _extract_json(getattr(r, "content", "") or "")
        if j and j.get("type") in _TYPES and str(j.get("complexity", "")).strip().isdigit():
            return {"type": j["type"], "complexity": max(1, min(5, int(j["complexity"])))}
    except Exception:
        pass
    return base


def _team_for(complexity: int) -> dict:
    c = max(1, min(5, int(complexity)))
    return {"single": c <= 1, "reviewers": max(0, c - 3)}  # c4 -> 1 reviewer, c5 -> 2


def _writer_pool(mtype: str) -> list[str]:
    default = ["gemini-3.5-flash-lite", "openai/gpt-oss-120b", "qwen3"]
    # code/analysis favour a stronger reasoning model as writer
    if mtype in ("code", "analysis"):
        default = ["openai/gpt-oss-120b", "gemini-3.5-flash-lite", "qwen3"]
    return _env_models("PAL_MISSION_WRITER_MODELS", default)


def _executor_pool(mtype: str) -> list[str]:
    default = ["qwen3", "openai/gpt-oss-120b", "gemini-3.5-flash-lite"]
    return _env_models("PAL_MISSION_EXECUTOR_MODELS", default)


def _repo_context(goal: str, max_bytes: int = 18000) -> str:
    """Current content of repo files relevant to the goal (headroom-compressed),
    so the writer modifies real code instead of guessing."""
    import subprocess

    files: list[str] = []
    for p in re.findall(r"(/[\w./\-]+\.(?:py|json|md|txt|toml|cfg))", goal):
        if os.path.isfile(p) and p not in files:
            files.append(p)
    root = None
    rm = re.search(r"(/[\w./\-]+?pal-mcp-server)\b", goal)
    if rm and os.path.isdir(rm.group(1)):
        root = rm.group(1)
    if root:
        symbols = set(re.findall(r"\b([a-z]+_[a-z_]+|[A-Za-z]+[A-Z][A-Za-z]+)\b", goal))
        for sym in list(symbols)[:8]:
            try:
                targets = [os.path.join(root, "providers"), os.path.join(root, "conf"),
                           os.path.join(root, "server.py"), os.path.join(root, "cli.py")]
                targets = [t for t in targets if os.path.exists(t)]
                out = subprocess.run(
                    ["grep", "-rlw", "--include=*.py", "--exclude-dir=.pal_venv",
                     "--exclude-dir=zen-mcp-server", "--exclude-dir=__pycache__",
                     "--exclude-dir=node_modules", "--exclude-dir=tests", sym, *targets],
                    capture_output=True, text=True, timeout=8).stdout
                for hit in out.split()[:2]:
                    if hit not in files:
                        files.append(hit)
            except Exception:
                pass
            if len(files) >= 6:
                break
    # RAW content (never compressed): the writer emits exact old->new edit
    # snippets that must match the file byte-for-byte, so compression would
    # break edit matching. Cap total size to stay within budget.
    parts, total = [], 0
    for fp in files[:6]:
        try:
            c = open(fp).read()
            if len(c) > max_bytes:
                c = c[:max_bytes] + "\n...[truncated]..."
            parts.append(f"--- FILE {fp} ---\n{c}")
            total += len(c)
            if total >= max_bytes:
                break
        except Exception:
            pass
    return "\n\n".join(parts)


def _is_protected(path: str) -> bool:
    """Never let a mission write/overwrite credentials or config."""
    if os.getenv("PAL_MISSION_ALLOW_SENSITIVE", "0") in ("1", "true", "yes"):
        return False
    p = os.path.abspath(os.path.expanduser(path or ""))
    base = os.path.basename(p)
    if base == ".env" or base.startswith(".env.") or base == "keys.json":
        return True
    if os.path.join(os.path.expanduser("~"), ".pal") in p and base.endswith(".json"):
        return True
    # Unify with the executor's credential guard: *.pem/*.key/id_rsa/credentials*/
    # secret*/engagement*/pentest-report* etc. are protected at the writer stage too.
    try:
        from providers.tooling import authz as _authz

        if _authz.scan_name(path or ""):
            return True
    except Exception:
        pass
    return False


async def _panel_models(mtype: str, cap: int) -> list[str]:
    from providers.router import chat_repl

    candidates = _writer_pool(mtype) + _executor_pool(mtype) + [
        "command-r-08-2024",
        "meta-llama/Llama-3.1-8B-Instruct",
        "Qwen/Qwen3.8-27B",
        "deepseek-ai/DeepSeek-V4.1-Flash",
        "zai-org/GLM-5.3-Flash",
        "openai/gpt-oss-20b",
        "gemini-flash-latest",
    ]
    picked: list[str] = []
    for m in candidates:
        if m in picked or "claude" in m.lower() or "anthropic" in m.lower():
            continue
        try:
            if chat_repl._is_available(m):
                picked.append(m)
        except Exception:
            pass
        if len(picked) >= cap:
            break
    return picked


async def run_panel(goal, models, judge, full):
    """Fan a mission out across MANY models in parallel (8-10): decompose into
    independent subtasks, run each on a distinct model concurrently, then judge."""
    from providers.router import dispatch

    criteria = f"The mission is accomplished and verified on disk: {goal}"
    dec = await asyncio.to_thread(
        dispatch.generate, models[0],
        f'Split this mission into up to {len(models)} INDEPENDENT subtasks. '
        f'Output ONLY JSON {{"subtasks":["...","..."]}}.\nMISSION: {goal}',
        "You are a terse mission decomposer.", temperature=0.2,
        category="mission", tool="mission", max_output_tokens=500,
    )
    subs = (_extract_json(getattr(dec, "content", "") or "") or {}).get("subtasks") or [goal]
    subs = subs[: len(models)]
    repo_ctx = _repo_context(goal)

    async def _do(i, sub):
        m = models[i % len(models)]
        try:
            wr = await asyncio.to_thread(
                dispatch.generate, m,
                f"REPO CONTEXT:\n{repo_ctx}\n\nSUBTASK: {sub}\nMISSION: {goal}",
                _WRITER_SYS, temperature=0.2, category="mission", tool="mission",
                max_output_tokens=int(os.getenv("PAL_TOOLS_MAX_TOKENS", "8192")),
            )
            plan = _extract_json(getattr(wr, "content", "") or "") or {}
            rep = await _execute_plan(plan, m, full, goal=goal)
            return {"subtask": sub, "model": m, "exec": rep}
        except Exception as exc:
            return {"subtask": sub, "model": m, "error": str(exc)[:120]}

    results = await asyncio.gather(*[_do(i, s) for i, s in enumerate(subs)])
    jr = await asyncio.to_thread(
        dispatch.generate, judge,
        f"MISSION: {goal}\nACCEPTANCE: {criteria}\nPANEL_RESULTS: {json.dumps(results)[:4000]}",
        _JUDGE_SYS, temperature=0.1, category="mission", tool="mission",
    )
    verdict = _extract_json(getattr(jr, "content", "") or "") or {"decision": "CONTINUE"}
    return {
        "status": "COMPLETE" if str(verdict.get("decision", "")).upper() == "COMPLETE" else "INCOMPLETE",
        "mode": "panel", "team_size": len(models), "models": models,
        "subtasks": subs, "results": results, "judge": judge, "verdict": verdict,
    }


async def _execute_plan(plan: dict, executor: str, full: bool, goal: str = "") -> dict:
    from providers.router import chat_repl

    # Pin the mission GOAL's authorization boundary for the whole plan so a
    # writer-emitted command ("git add . && git push") inherits the goal's
    # explicit file scope and cannot widen it (push_scope narrows-only).
    _gtok = None
    try:
        from providers.router import intent as _intent
        from providers.tooling import authz as _authz

        if goal:
            _gtok = _authz.push_scope(_intent.scope_for_request(goal, os.getcwd()))
    except Exception:
        _gtok = None

    report: dict = {"files_written": [], "edits_applied": [], "edits_failed": [], "results": []}
    for e in plan.get("edits", []) or []:
        path, old, new = e.get("path"), e.get("old"), e.get("new")
        if path and _is_protected(path):
            report["edits_failed"].append({"path": path, "reason": "protected path (config/creds)"})
            continue
        if path and old is not None and os.path.isfile(path):
            try:
                cur = open(path).read()
                if old in cur:
                    with open(path, "w") as fh:
                        fh.write(cur.replace(old, new or "", 1))
                    report["edits_applied"].append(path)
                else:
                    report["edits_failed"].append({"path": path, "reason": "old snippet not found"})
            except Exception as exc:
                report["edits_failed"].append({"path": path, "reason": str(exc)[:80]})
    for entry in plan.get("files", []) or []:
        path, content = entry.get("path"), entry.get("content", "")
        if path and _is_protected(path):
            report["edits_failed"].append({"path": path, "reason": "protected path (config/creds)"})
            continue
        if path:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w") as fh:
                fh.write(content)
            report["files_written"].append(path)
    for cmd in plan.get("commands", []) or []:
        answer, _tr = await chat_repl._tools_loop(
            f"Run this exact bash command and report its output: {cmd}",
            executor, os.getcwd(), max_steps=3, full=full,
        )
        report["results"].append({"cmd": cmd, "answer": (answer or "")[:600]})
    if _gtok is not None:
        try:
            from providers.tooling import authz as _authz

            _authz.pop_scope(_gtok)
        except Exception:
            pass
    return report


def _goal_artifacts(goal: str) -> list[str]:
    """Absolute-ish file paths the goal asks to produce, for on-disk verification."""
    return re.findall(r"(/[\w./\-]+\.[A-Za-z0-9]{1,6})", goal or "")


async def run_mission(
    goal: str,
    *,
    writer: str | None = None,
    executor: str | None = None,
    judge: str | None = None,
    max_iters: int | None = None,
    full: bool = True,
    auto: bool = True,
) -> dict:
    """Adaptive mission run. Returns a result dict with the chosen team + transcript."""
    from providers.router import chat_repl, dispatch

    assessment = assess_mission(goal) if auto else {"type": "general", "complexity": 3}
    team = _team_for(assessment["complexity"])
    mtype = assessment["type"]
    max_iters = int(max_iters or os.getenv("PAL_MISSION_MAX_ITERS", "4"))

    # PANEL: many models in parallel for complex missions (or PAL_MISSION_PANEL=1).
    _panel = os.getenv("PAL_MISSION_PANEL", "auto").lower()
    if auto and (_panel in ("1", "true", "yes") or (_panel == "auto" and assessment["complexity"] >= 4)):
        cap = int(os.getenv("PAL_MISSION_PANEL_MAX", "10"))
        pmodels = await _panel_models(mtype, cap)
        if len(pmodels) >= 3:
            pjudge = judge or _pick(_env_models("PAL_MISSION_REVIEWER_MODELS", ["gemini-3.5-flash-lite"]))
            res = await run_panel(goal, pmodels, pjudge, full)
            res["assessment"] = assessment
            return res

    used: set[str] = set()
    writer = writer or _pick(_writer_pool(mtype))
    if writer:
        used.add(writer)
    executor = executor or _pick_distinct(_executor_pool(mtype), used)
    if executor:
        used.add(executor)

    # EASY: one capable model does the whole thing directly via the tool loop.
    if team["single"] and auto:
        solo = executor or writer
        answer, _tr = await chat_repl._tools_loop(goal, solo, os.getcwd(), max_steps=6, full=full)
        artifacts = _goal_artifacts(goal)
        if artifacts:
            # completion is decided by the artifacts existing on disk, not by
            # whether the tool loop emitted a clean final answer.
            missing = [p for p in artifacts if not os.path.exists(p)]
            ok = not missing
        else:
            ok = "__ERROR__" not in (answer or "")
            missing = []
        return {"status": "COMPLETE" if ok else "INCOMPLETE", "mode": "single", "model": solo,
                "assessment": assessment, "team_size": 1, "artifacts": artifacts,
                "missing": missing, "answer": (answer or "")[:600]}

    judge = judge or _pick_distinct(_env_models("PAL_MISSION_REVIEWER_MODELS", [writer or "qwen3"]), used) or writer
    used.add(judge)
    reviewer_models: list[str] = []
    for _ in range(team["reviewers"]):
        rm = _pick_distinct(_executor_pool(mtype) + _writer_pool(mtype), used)
        if rm:
            reviewer_models.append(rm)
            used.add(rm)

    criteria = f"The mission is accomplished and verified on disk: {goal}"
    transcript: list[dict] = []
    feedback = ""
    repo_ctx = _repo_context(goal)
    for iteration in range(1, max_iters + 1):
        wr = await asyncio.to_thread(
            dispatch.generate, writer,
            f"REPO CONTEXT:\n{repo_ctx}\n\nMISSION: {goal}\nACCEPTANCE: {criteria}\nFEEDBACK: {feedback or '(none)'}",
            _WRITER_SYS, temperature=0.2, category="mission", tool="mission",
            max_output_tokens=int(os.getenv("PAL_TOOLS_MAX_TOKENS", "8192")),
        )
        plan = _extract_json(getattr(wr, "content", "") or "") or {}
        report = await _execute_plan(plan, executor, full, goal=goal)

        review_notes = []
        for rm in reviewer_models:
            rr = await asyncio.to_thread(
                dispatch.generate, rm,
                f"MISSION: {goal}\nPLAN: {json.dumps(plan)[:2000]}\nRESULTS: {json.dumps(report)[:2000]}",
                _REVIEWER_SYS, temperature=0.2, category="mission", tool="mission", max_output_tokens=300,
            )
            review_notes.append({"model": rm, "note": _extract_json(getattr(rr, "content", "") or "") or {}})

        jr = await asyncio.to_thread(
            dispatch.generate, judge,
            f"MISSION: {goal}\nACCEPTANCE: {criteria}\nRESULTS: {json.dumps(report)[:3000]}\n"
            f"REVIEWS: {json.dumps(review_notes)[:1500]}",
            _JUDGE_SYS, temperature=0.1, category="mission", tool="mission",
        )
        verdict = _extract_json(getattr(jr, "content", "") or "") or {"decision": "CONTINUE", "feedback": "no verdict"}
        transcript.append({"iteration": iteration, "writer": writer, "executor": executor,
                           "reviewers": reviewer_models, "judge": judge, "plan": plan,
                           "exec": report, "reviews": review_notes, "verdict": verdict})
        if str(verdict.get("decision", "")).upper() == "COMPLETE":
            return {"status": "COMPLETE", "mode": "team", "iterations": iteration,
                    "assessment": assessment, "team_size": 3 + len(reviewer_models),
                    "writer": writer, "executor": executor, "reviewers": reviewer_models,
                    "judge": judge, "transcript": transcript}
        feedback = verdict.get("feedback", "")

    return {"status": "INCOMPLETE", "mode": "team", "iterations": max_iters,
            "assessment": assessment, "team_size": 3 + len(reviewer_models),
            "writer": writer, "executor": executor, "reviewers": reviewer_models,
            "judge": judge, "transcript": transcript}


def run_mission_sync(goal: str, **kwargs) -> dict:
    return asyncio.run(run_mission(goal, **kwargs))


def main(argv: list[str]) -> int:
    """CLI: pal mission "<goal>" [--writer M] [--executor M] [--judge M] [--max-iters N] [--no-auto] [--json]"""
    import argparse

    ap = argparse.ArgumentParser(prog="pal mission", description="adaptive writer->executor->judge mission")
    ap.add_argument("goal")
    ap.add_argument("--writer")
    ap.add_argument("--executor")
    ap.add_argument("--judge")
    ap.add_argument("--max-iters", type=int)
    ap.add_argument("--no-auto", action="store_true", help="disable auto team-sizing")
    ap.add_argument("--ro", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    os.environ.setdefault("PAL_TOOLBELT", "1")
    from server import configure_providers

    configure_providers()
    res = run_mission_sync(
        a.goal, writer=a.writer, executor=a.executor, judge=a.judge,
        max_iters=a.max_iters, full=not a.ro, auto=not a.no_auto,
    )
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        asmt = res.get("assessment", {})
        print(f"status: {res['status']}  mode: {res.get('mode')}  team_size: {res.get('team_size')}")
        print(f"assessed: type={asmt.get('type')} complexity={asmt.get('complexity')}")
        if res.get("mode") == "single":
            print(f"model: {res.get('model')}")
        else:
            print(f"writer={res.get('writer')} executor={res.get('executor')} "
                  f"reviewers={res.get('reviewers')} judge={res.get('judge')}")
    return 0 if res["status"] == "COMPLETE" else 1
