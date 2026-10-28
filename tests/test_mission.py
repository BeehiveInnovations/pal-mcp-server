"""Tests for the writer->executor->judge mission pipeline."""

import asyncio
import json
from types import SimpleNamespace

from providers.router import mission


def _resp(content: str):
    return SimpleNamespace(content=content, metadata={})


def test_complete_cycle(monkeypatch, tmp_path):
    """Writer authors a file, executor writes it, judge marks COMPLETE."""
    target = tmp_path / "out.txt"
    writer_json = json.dumps({"files": [{"path": str(target), "content": "HELLO"}], "commands": []})

    calls = {"n": 0}

    def fake_generate(model, prompt, system, **kw):
        calls["n"] += 1
        if "WRITER" in system:
            return _resp(writer_json)
        return _resp(json.dumps({"decision": "COMPLETE", "reason": "verified"}))

    async def fake_loop(task, model, cwd, max_steps=3, full=True):
        return ("ran", [])

    monkeypatch.setattr("providers.router.dispatch.generate", fake_generate)
    monkeypatch.setattr("providers.router.chat_repl._tools_loop", fake_loop)
    monkeypatch.setattr(mission, "_pick", lambda models: models[0])

    res = asyncio.run(mission.run_mission("make out.txt", writer="w", executor="e", judge="j", max_iters=3, auto=False))
    assert res["status"] == "COMPLETE"
    assert res["iterations"] == 1
    assert target.read_text() == "HELLO"
    assert str(target) in res["transcript"][0]["exec"]["files_written"]


def test_iteration_cap(monkeypatch):
    """Judge never says COMPLETE -> stops at the cap, status INCOMPLETE."""
    def fake_generate(model, prompt, system, **kw):
        if "WRITER" in system:
            return _resp(json.dumps({"files": [], "commands": []}))
        return _resp(json.dumps({"decision": "CONTINUE", "feedback": "not done"}))

    async def fake_loop(task, model, cwd, max_steps=3, full=True):
        return ("", [])

    monkeypatch.setattr("providers.router.dispatch.generate", fake_generate)
    monkeypatch.setattr("providers.router.chat_repl._tools_loop", fake_loop)
    monkeypatch.setattr(mission, "_pick", lambda models: models[0])

    res = asyncio.run(mission.run_mission("goal", writer="w", executor="e", judge="j", max_iters=2, auto=False))
    assert res["status"] == "INCOMPLETE"
    assert res["iterations"] == 2
    assert len(res["transcript"]) == 2


def test_claude_excluded():
    assert mission._no_claude(["qwen3", "anthropic/claude-opus-4.5", "gemini-x"]) == ["qwen3", "gemini-x"]


def test_extract_json_tolerates_prose():
    assert mission._extract_json('sure! {"decision":"COMPLETE"} done') == {"decision": "COMPLETE"}
    assert mission._extract_json("no json here") is None


def test_heuristic_complexity_scales():
    easy = mission._heuristic_assess("write ok to /tmp/x.txt")
    hard = mission._heuristic_assess(
        "enumerate the subdomains, then scan each with nmap, and analyze the results, "
        "and write a report, and verify it, and summarize the findings"
    )
    assert easy["complexity"] <= 2
    assert hard["complexity"] >= 4


def test_team_for_scales():
    assert mission._team_for(1)["single"] is True
    assert mission._team_for(3) == {"single": False, "reviewers": 0}
    assert mission._team_for(5)["reviewers"] == 2


def test_heuristic_type_detection():
    assert mission._heuristic_assess("nmap scan of the target")["type"] == "recon"
    assert mission._heuristic_assess("implement a python function")["type"] == "code"


def test_goal_artifacts_parsed():
    a = mission._goal_artifacts("create /tmp/mission_demo/report.txt and also /tmp/x.json please")
    assert "/tmp/mission_demo/report.txt" in a and "/tmp/x.json" in a


def test_single_mode_completes_when_artifact_exists(monkeypatch, tmp_path):
    target = tmp_path / "made.txt"
    target.write_text("done")

    async def fake_loop(task, model, cwd, max_steps=6, full=True):
        return ("[reached max tool steps]", [])  # no clean final answer

    monkeypatch.setattr("providers.router.chat_repl._tools_loop", fake_loop)
    monkeypatch.setattr(mission, "assess_mission", lambda g: {"type": "fileops", "complexity": 1})
    monkeypatch.setattr(mission, "_pick", lambda models: "solo-model")
    res = asyncio.run(mission.run_mission(f"write ok to {target}", auto=True))
    assert res["mode"] == "single"
    assert res["status"] == "COMPLETE"  # artifact exists despite max-steps


def test_execute_plan_applies_edits(tmp_path):
    import asyncio as _a
    f = tmp_path / "mod.py"
    f.write_text("x = 1\ny = 2\n")
    plan = {"edits": [{"path": str(f), "old": "x = 1", "new": "x = 42"}], "files": [], "commands": []}
    rep = _a.run(mission._execute_plan(plan, "e", False))
    assert str(f) in rep["edits_applied"]
    assert f.read_text() == "x = 42\ny = 2\n"


def test_execute_plan_edit_miss_recorded(tmp_path):
    import asyncio as _a
    f = tmp_path / "mod.py"
    f.write_text("a = 1\n")
    plan = {"edits": [{"path": str(f), "old": "NOTHERE", "new": "z"}], "files": [], "commands": []}
    rep = _a.run(mission._execute_plan(plan, "e", False))
    assert rep["edits_failed"] and f.read_text() == "a = 1\n"


def test_protected_paths_blocked(tmp_path, monkeypatch):
    import asyncio as _a
    env = tmp_path / ".env"
    env.write_text("SECRET=1")
    monkeypatch.delenv("PAL_MISSION_ALLOW_SENSITIVE", raising=False)
    plan = {"files": [{"path": str(env), "content": "WIPED"}],
            "edits": [{"path": str(env), "old": "SECRET=1", "new": "X"}], "commands": []}
    rep = _a.run(mission._execute_plan(plan, "e", False))
    assert env.read_text() == "SECRET=1"  # untouched
    assert any("protected" in str(x) for x in rep["edits_failed"])


def test_is_protected():
    assert mission._is_protected("/home/kali/tools/pal-mcp-server/.env")
    assert mission._is_protected("/home/kali/.pal/keys.json")
    assert not mission._is_protected("/tmp/whatever.py")
