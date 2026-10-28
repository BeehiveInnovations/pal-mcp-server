"""Unit tests for providers/router/distill.py (Phase-2 offline proposer)."""

from __future__ import annotations

import json

import pytest

from providers.router import distill


def _ep(model, category, outcome, err_class=None, latency_ms=100):
    return {
        "model": model,
        "category": category,
        "outcome": outcome,
        "err_class": err_class,
        "latency_ms": latency_ms,
    }


def test_aggregate_counts_by_class():
    eps = [
        _ep("m", "cat", "success"),
        _ep("m", "cat", "success"),
        _ep("m", "cat", "refusal"),
        _ep("m", "cat", "error", err_class="availability"),
        _ep("m", "cat", "error", err_class="unknown"),
    ]
    agg = distill.aggregate(eps)
    rec = agg[("cat", "m")]
    assert rec["n"] == 5
    assert rec["success"] == 2
    assert rec["policy_refusal"] == 1
    assert rec["avail_fail"] == 1
    assert rec["other_err"] == 1


def test_quality_excludes_availability():
    # 8 success, 2 policy refusals, 10 transient 5xx.
    # quality = 8/(8+2) = 0.8 ; availability must NOT drag quality down.
    eps = (
        [_ep("m", "cat", "success") for _ in range(8)]
        + [_ep("m", "cat", "refusal") for _ in range(2)]
        + [_ep("m", "cat", "error", err_class="availability") for _ in range(10)]
    )
    agg = distill.aggregate(eps)
    st = distill._stats(agg[("cat", "m")])
    assert st["quality_rate"] == pytest.approx(0.8)
    assert st["reliability"] == pytest.approx(1 - 10 / 20)


def test_recommend_reorders_on_quality():
    prefs = {"cat": ("weak", "strong")}
    eps = (
        [_ep("weak", "cat", "refusal") for _ in range(10)]
        + [_ep("strong", "cat", "success") for _ in range(10)]
    )
    prop = distill.build_proposal(eps, preferences=prefs, min_samples=5)
    info = prop["categories"]["cat"]
    assert info["changed"] is True
    assert info["recommended_order"][0] == "strong"


def test_low_sample_keeps_prior_order():
    prefs = {"cat": ("a", "b")}
    eps = [_ep("b", "cat", "success") for _ in range(3)]  # only 3 < min_samples 5
    prop = distill.build_proposal(eps, preferences=prefs, min_samples=5)
    info = prop["categories"]["cat"]
    assert info["changed"] is False
    assert info["recommended_order"] == ["a", "b"]


def test_emerging_model_surfaced():
    prefs = {"cat": ("listed",)}
    eps = [_ep("newcomer", "cat", "success") for _ in range(8)]
    prop = distill.build_proposal(eps, preferences=prefs, min_samples=5)
    emerging = prop["categories"]["cat"]["emerging"]
    assert any(e["model"] == "newcomer" for e in emerging)


def test_proposal_is_advisory_only():
    prop = distill.build_proposal([], preferences={"cat": ("a",)}, min_samples=5)
    assert "HUMAN-GATED" in prop["apply_hint"]
    assert "never auto-applied" in prop["apply_hint"]


def test_write_and_report(tmp_path):
    prefs = {"cat": ("a", "b")}
    eps = [_ep("b", "cat", "success") for _ in range(10)] + [_ep("a", "cat", "refusal") for _ in range(10)]
    prop = distill.build_proposal(eps, preferences=prefs, min_samples=5)
    path = distill.write_proposal(prop, tmp_path)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["categories"]["cat"]["recommended_order"][0] == "b"
    report = distill.render_report(prop)
    assert "CHANGE PROPOSED" in report
    assert "proposal for human review" in report


def test_main_print_only_writes_no_file(tmp_path, monkeypatch, capsys):
    # point episode store at an empty/nonexistent file
    from providers.router import episode_store as es

    monkeypatch.setattr(es, "EPISODE_PATH", tmp_path / "none.jsonl")
    monkeypatch.setattr(distill, "PROPOSAL_DIR", tmp_path / "distill")
    rc = distill.main(["--print-only"])
    assert rc == 0
    assert not (tmp_path / "distill").exists()
    out = capsys.readouterr().out
    assert "distillation" in out
