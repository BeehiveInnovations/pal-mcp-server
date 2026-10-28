"""Unit tests for providers.router.debate (Phase 7)."""

from __future__ import annotations

import json

from providers.router import debate

MODELS = ("ex", ["rv1", "rv2"], "jg")


def _crit(v):
    return [{"id": "c1", "text": "t", "verified": v, "evidence": "out" if v else ""}]


def _script(judge_seq, exec_verified=True):
    calls = []

    def call(model, prompt, system):
        calls.append(model)
        if model == "ex":
            return json.dumps(
                {
                    "completion_status": "review_ready",
                    "completion_criteria": _crit(exec_verified),
                    "files_changed": ["a.py"],
                    "confidence": 0.9,
                }
            )
        if model.startswith("rv"):
            return json.dumps({"findings": [], "completion_criteria": _crit(exec_verified)})
        v = judge_seq.pop(0) if len(judge_seq) > 1 else judge_seq[0]
        return json.dumps(
            {
                "verdict": v[0],
                "completion_status": "review_ready",
                "completion_criteria": _crit(v[1]),
                "confidence": 0.9,
                "recommended_next_stage": "executor",
            }
        )

    return call, calls


def test_complete_and_order():
    call, calls = _script([("COMPLETE", True)])
    out = debate.run_debate("obj", [{"id": "c1", "text": "t"}], call=call, models=MODELS)
    assert out["outcome"] == "COMPLETE" and out["iterations"] == 1
    assert calls == ["ex", "rv1", "rv2", "jg"]


def test_complete_downgraded_on_unverified():
    call, _ = _script([("COMPLETE", False)], exec_verified=False)
    out = debate.run_debate("obj", [{"id": "c1", "text": "t"}], call=call, models=MODELS)
    assert out["outcome"] != "COMPLETE"
    assert any("unverified" in r for r in out["verdict_reasons"])


def test_max_iter_hard_cap(monkeypatch):
    monkeypatch.setenv("PAL_DEBATE_MAX_ITER", "999")
    assert debate.max_iterations() == 10
    monkeypatch.setenv("PAL_DEBATE_MAX_ITER", "2")
    monkeypatch.setenv("PAL_DEBATE_NO_PROGRESS_N", "9")
    n = {"i": 0}

    def call(model, prompt, system):  # always progresses (new file each round)
        n["i"] += 1
        return json.dumps({"verdict": "CONTINUE", "completion_status": "in_progress", "files_changed": [f"f{n['i']}"]})

    out = debate.run_debate("o", call=call, models=MODELS)
    assert out["outcome"] == "MAX_ITER" and out["iterations"] == 2


def test_no_progress_halts(monkeypatch):
    monkeypatch.setenv("PAL_DEBATE_MAX_ITER", "8")
    monkeypatch.setenv("PAL_DEBATE_NO_PROGRESS_N", "2")
    call = lambda m, p, s: json.dumps({"verdict": "CONTINUE", "completion_status": "in_progress"})  # noqa: E731
    out = debate.run_debate("o", call=call, models=MODELS)
    assert out["outcome"] == "NO_PROGRESS" and out["iterations"] < 8


def test_unparseable_is_blocked_and_identity_forced():
    h = debate.parse_handoff(
        "garbage", mission_id="m", iteration=1, stage="executor", model="x", role="executor", objective="o"
    )
    assert h.completion_status == "blocked" and h.mission_id == "m"
    h2 = debate.parse_handoff(
        '{"mission_id":"evil","model":"evil"}',
        mission_id="m",
        iteration=1,
        stage="executor",
        model="x",
        role="executor",
        objective="o",
    )
    assert h2.mission_id == "m" and h2.model == "x"


def test_disabled(monkeypatch):
    monkeypatch.setenv("PAL_DEBATE", "0")
    assert debate.run_debate("o")["outcome"] == "DISABLED"


def test_stage_cannot_shrink_or_replace_pinned_criteria():
    pinned = [{"id": "c1", "text": "real one"}, {"id": "c2", "text": "real two"}]
    seen = {}

    def call(model, prompt, system):
        if model == "jg":
            seen["jprompt"] = prompt
        # every stage claims a single trivially-verified replacement contract
        fake = [{"id": "c1", "text": "shrunk", "verified": True, "evidence": "x"}]
        out = {"completion_status": "review_ready", "completion_criteria": fake, "confidence": 0.9}
        if model == "jg":
            out["verdict"] = "COMPLETE"
        return json.dumps(out)

    out = debate.run_debate("obj", pinned, call=call, models=MODELS)
    assert out["outcome"] != "COMPLETE"
    assert "unverified_criteria=['c2']" in out["verdict_reasons"]
    assert "PINNED_CRITERIA" in seen["jprompt"] and "real two" in seen["jprompt"]
    for h in out["history"]:
        assert [(c["id"], c["text"]) for c in h["completion_criteria"]] == [("c1", "real one"), ("c2", "real two")]
    assert out["final"]["completion_criteria"][0]["text"] == "real one"


def test_judge_without_criteria_or_extra_ids_cannot_complete():
    pinned = debate._norm_criteria([{"id": "c1", "text": "t"}])
    st = debate.Handoff(completion_status="review_ready", completion_criteria=_crit(True))
    jg = debate.parse_handoff(
        '{"completion_status":"review_ready","completion_criteria":[{"id":"zz","verified":true}]}',
        mission_id="m",
        iteration=1,
        stage="judge",
        model="jg",
        role="judge",
        objective="o",
        pinned=pinned,
    )
    v, r = debate.enforce_judge("COMPLETE", st, jg, pinned)
    assert v == "CONTINUE" and any("unverified" in x for x in r)
