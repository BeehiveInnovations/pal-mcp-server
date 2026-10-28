"""Distiller × teacher-lessons integration (opt-in, attributed, human-gated)."""

from __future__ import annotations

import pytest

from providers.router import distill
from providers.router import lesson_store as ls


@pytest.fixture(autouse=True)
def _tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "LESSON_PATH", tmp_path / "lessons.jsonl")
    monkeypatch.setenv("PAL_LESSON_STORE", "1")
    ls.clear()
    yield
    ls.clear()


def _ep(model, category, outcome):
    return {"model": model, "category": category, "outcome": outcome, "err_class": None}


def test_lessons_off_by_default():
    prefs = {"security_permissive": ("grok", "or-free")}
    ls.emit_lesson("orchestrator", "routing", "prefer or-free", category="security_permissive",
                   target_model="or-free", action="prefer", confidence=0.9, provenance=["p"])
    prop = distill.build_proposal([], preferences=prefs, min_samples=5)  # use_lessons default False
    assert prop["lessons_used"] is False
    assert prop["categories"]["security_permissive"]["lessons_applied"] == []
    # no telemetry, no lessons -> prior order preserved
    assert prop["categories"]["security_permissive"]["recommended_order"] == ["grok", "or-free"]


def test_prefer_lesson_promotes_and_is_attributed():
    prefs = {"security_permissive": ("grok", "or-free")}
    ls.emit_lesson("orchestrator", "routing", "prefer or-free", category="security_permissive",
                   target_model="or-free", action="prefer", confidence=0.9, provenance=["p"])
    prop = distill.build_proposal([], preferences=prefs, min_samples=5, use_lessons=True)
    info = prop["categories"]["security_permissive"]
    assert info["recommended_order"][0] == "or-free"  # nudged above prior #1
    assert info["lessons_applied"] and info["lessons_applied"][0]["teacher_id"] == "orchestrator"
    assert prop["lessons_used"] is True


def test_avoid_lesson_demotes():
    prefs = {"cat": ("a", "b")}
    ls.emit_lesson("orchestrator", "routing", "avoid a", category="cat",
                   target_model="a", action="avoid", confidence=1.0, provenance=["p"])
    prop = distill.build_proposal([], preferences=prefs, min_samples=5, use_lessons=True)
    assert prop["categories"]["cat"]["recommended_order"][0] == "b"


def test_lesson_cannot_introduce_unknown_model():
    prefs = {"cat": ("a", "b")}
    # a lesson pointing at a model not in the candidate list must be ignored
    ls.emit_lesson("orchestrator", "routing", "prefer ghost", category="cat",
                   target_model="ghost-model", action="prefer", confidence=1.0, provenance=["p"])
    prop = distill.build_proposal([], preferences=prefs, min_samples=5, use_lessons=True)
    info = prop["categories"]["cat"]
    assert info["recommended_order"] == ["a", "b"]  # unchanged
    assert info["lessons_applied"] == []  # ghost model filtered out


def test_strong_telemetry_survives_a_single_lesson():
    # a lesson biases but should not override overwhelming telemetry
    prefs = {"cat": ("a", "b")}
    eps = [_ep("a", "cat", "success") for _ in range(30)] + [_ep("b", "cat", "refusal") for _ in range(30)]
    # weak-ish lesson prefers b
    ls.emit_lesson("panel", "routing", "prefer b", category="cat",
                   target_model="b", action="prefer", confidence=0.5, provenance=["p"])
    prop = distill.build_proposal(eps, preferences=prefs, min_samples=5, use_lessons=True)
    # a=1.0 quality vs b=0.0 + nudge(0.5*0.5*0.5=0.125) -> a still first
    assert prop["categories"]["cat"]["recommended_order"][0] == "a"
