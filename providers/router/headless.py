"""Headless one-shot runner: `pal run`.

Turns PAL into something callable like a function — hand it a task (or a plan
file) and it executes autonomously and prints ONLY the result, no REPL. Built
on the same _tools_loop / _ask_agent the interactive chat uses.

    pal run "count the lines in *.py"            # tools (full) -> result
    pal run --ro "list the open ports"            # read-only tools
    pal run --agent "add a docstring to main"     # full Claude Code agent
    pal run --model qwen3 "..."                    # pick the executor model
    pal run --plan steps.md                        # run every step, print each
    pal run --json "..."                           # structured output to parse
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re


def _setup() -> None:
    os.environ["LOG_LEVEL"] = os.getenv("PAL_CHAT_LOGLEVEL", "ERROR")
    logging.disable(logging.WARNING)
    from server import configure_providers

    configure_providers()


def _pick_tools_model(task: str, model: str | None) -> str | None:
    from providers.router import chat_repl, chat_router

    if model:
        return model
    env = os.getenv("PAL_CHAT_TOOLS_MODEL")
    if env:
        return env
    if chat_repl._is_available("qwen3"):
        return "qwen3"
    return chat_router.route(task, chat_repl._is_available)["model"]


async def run_task(
    task: str, *, mode: str = "tools", model: str | None = None, full: bool = True,
    max_steps: int | None = None, agent_role: str | None = None,
) -> dict:
    """Run one task; return {task, mode, model, tools_used?, result}."""
    from providers.router import chat_repl

    cwd = os.getcwd()
    if mode == "agent":
        from server import handle_call_tool

        role = agent_role or ("edit" if full else "default")
        ans = await chat_repl._ask_agent(handle_call_tool, task, cwd, role)
        return {"task": task, "mode": "agent", "role": role, "result": ans}

    m = _pick_tools_model(task, model)
    if not m:
        return {"task": task, "mode": "tools", "result": "__ERROR__no model available"}
    steps = max_steps if max_steps else (8 if full else 5)

    # A2: size guard — if the task is too large for this model's input cap,
    # reroute to a bigger-context same-category (or global-fallback) model.
    from providers.router import size_guard

    ok, hint = size_guard.check_or_reroute(m, task)
    if not ok and hint and hint.startswith("route:"):
        alt = hint.split(":", 1)[1]
        if alt and alt not in ("none", "None"):
            m = alt

    # A1: failover across the model's same-category chain. dispatch.generate
    # already does per-call fallback, but _tools_loop CATCHES a provider error
    # and RETURNS ("__ERROR__…", transcript) instead of raising — so if a whole
    # loop dies on an exhausted provider we retry the next model here. Errors
    # that are not provider/rate issues (no tools, no provider) are not retried.
    from providers.router import fallback_chain

    candidates = [m]
    if fallback_chain.is_enabled():
        candidates += fallback_chain.chain_for(m)
    _nonretry = ("no local tools enabled", "no provider for", "no model available")
    ans = transcript = None
    for cand in candidates:
        ans, transcript = await chat_repl._tools_loop(task, cand, cwd, max_steps=steps, full=full)
        m = cand
        if isinstance(ans, str) and ans.startswith("__ERROR__") and not any(k in ans for k in _nonretry):
            continue
        break
    return {
        "task": task,
        "mode": "tools",
        "model": m,
        "full": full,
        "tools_used": [{"tool": n, "args": a} for n, a, _ in transcript],
        "result": ans,
    }


def _read_plan(path: str) -> list[str]:
    steps: list[str] = []
    with open(path, encoding="utf-8") as fp:
        for raw in fp:
            ln = raw.strip()
            if not ln or ln.startswith("#"):
                continue
            ln = re.sub(r"^([-*+]|\d+[.)])\s+", "", ln)  # strip md bullets / numbering
            if ln:
                steps.append(ln)
    return steps


async def run_plan(path: str, **kw) -> dict:
    steps = _read_plan(path)
    results = []
    for i, step in enumerate(steps, 1):
        res = await run_task(step, **kw)
        results.append({
            "step": i,
            "task": step,
            "result": res.get("result", ""),
            "tools_used": res.get("tools_used", []),
        })
    return {"plan": path, "steps_run": len(results), "steps": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pal run", description="Headless: run a task or plan, print the result.")
    ap.add_argument("task", nargs="?", help="the task to run (omit when using --plan)")
    ap.add_argument("--agent", action="store_true", help="run via the full Claude Code agent (real tools)")
    ap.add_argument("--ro", action="store_true", help="read-only tools (no arbitrary commands / edits)")
    ap.add_argument("--model", help="override the executor model")
    ap.add_argument("--plan", help="path to a plan file (one step per line, md bullets ok)")
    ap.add_argument("--task-file", help="read the WHOLE file as ONE task (prose plan; unlike --plan which splits by line)")
    ap.add_argument("--max-steps", type=int, default=None, help="tool-call budget per task/step (default 8 full, 5 ro)")
    ap.add_argument("--agent-role", default=None, help="clink role for --agent (e.g. autonomous, edit, plan, review)")
    ap.add_argument("--json", action="store_true", help="emit structured JSON")
    args = ap.parse_args(argv)

    _setup()
    mode = "agent" if args.agent else "tools"
    full = not args.ro

    if args.plan:
        out = asyncio.run(run_plan(args.plan, mode=mode, model=args.model, full=full, max_steps=args.max_steps, agent_role=args.agent_role))
        if args.json:
            print(json.dumps(out, indent=2, default=str))
        else:
            for s in out["steps"]:
                print(f"### step {s['step']}: {s['task']}\n{s['result']}\n")
        return 0

    task_text = args.task
    if args.task_file:
        with open(args.task_file, encoding="utf-8") as fp:
            task_text = fp.read().strip()
    if not task_text:
        ap.error("provide a task, or use --task-file <file> / --plan <file>")
    out = asyncio.run(run_task(task_text, mode=mode, model=args.model, full=full, max_steps=args.max_steps, agent_role=args.agent_role))
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(out["result"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
