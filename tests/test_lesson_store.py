"""Unit tests for providers/router/lesson_store.py (teacher-sourced logic).

Emphasis on the origin-channel injection defense: a lesson can only be created
through emit_lesson with an authenticated teacher and provenance -- there is no
path from task text to a stored rule.
"""

from __future__ import annotations

import json

import pytest

from providers.router import lesson_store as ls


@pytest.fixture(autouse=True)
def _tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "LESSON_PATH", tmp_path / "lessons.jsonl")
    monkeypatch.setenv("PAL_LESSON_STORE", "1")
    ls.clear()
    yield tmp_path / "lessons.jsonl"
    ls.clear()


def _routing(**kw):
    base = {
        "teacher_id": "orchestrator",
        "scope": "routing",
        "rationale": "grok refuses security tasks; or-free completes them",
        "category": "security_permissive",
        "target_model": "or-free",
        "action": "prefer",
        "confidence": 0.9,
        "provenance": ["task:abc123", "2026-09-28T00:00:00Z"],
    }
    base.update(kw)
    return ls.emit_lesson(
        base.pop("teacher_id"), base.pop("scope"), base.pop("rationale"), **base
    )


# ----- origin-channel authentication -----------------------------------------
def test_unknown_teacher_rejected(monkeypatch):
    monkeypatch.setenv("PAL_LEARN_AUTO", "0")  # strict teacher gate only when auto-learn is off
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("attacker", "routing", "x", category="c", target_model="m",
                       provenance=["p"])


def test_missing_provenance_rejected():
    # this is the anti-injection cut: no provenance => cannot enter
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("orchestrator", "routing", "x", category="c", target_model="m",
                       provenance=[])


def test_routing_requires_category_and_model():
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("orchestrator", "routing", "x", provenance=["p"])


def test_bad_confidence_rejected():
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("orchestrator", "prompt", "x", confidence=2.0, provenance=["p"])


def test_no_text_scraping_entry_point():
    # There must be no public function that builds a Lesson from free text.
    # emit_lesson is the only constructor path; assert nothing else is exported
    # that takes raw text and returns a Lesson.
    suspects = [n for n in dir(ls) if n.startswith(("parse", "scrape", "ingest", "from_text"))]
    assert suspects == []


# ----- persistence + trust ----------------------------------------------------
def test_emit_persists_and_weights():
    les = _routing()
    assert les.trust_weight() == pytest.approx(1.0 * 0.9)  # orchestrator * conf
    line = json.loads(open(ls.LESSON_PATH).read().splitlines()[0])
    assert line["teacher_id"] == "orchestrator"
    assert line["target_model"] == "or-free"
    assert line["status"] == "proposal"


def test_self_grade_is_low_trust():
    les = _routing(teacher_id="self", confidence=1.0)
    assert les.trust_weight() == pytest.approx(0.3)


# ----- scope gating -----------------------------------------------------------
def test_non_routing_scope_is_human_review_only():
    les = ls.emit_lesson(
        "orchestrator", "classifier", "add regex for 'threat model'",
        confidence=0.9, provenance=["p"],
    )
    assert les.status == "human_review_only"
    # classifier/prompt/tool lessons never surface as routing feed
    assert ls.routing_lessons("security_permissive") == []
    assert any(x.lesson_id == les.lesson_id for x in ls.pending_review())


def test_routing_lessons_read_back_from_disk():
    _routing()
    got = ls.routing_lessons("security_permissive")
    assert len(got) == 1
    assert got[0].target_model == "or-free"


def test_last_write_wins_per_model_action():
    _routing(confidence=0.5)
    _routing(confidence=0.95)  # supersedes
    got = ls.routing_lessons("security_permissive")
    assert len(got) == 1
    assert got[0].confidence == 0.95


# ----- rollback ---------------------------------------------------------------
def test_deactivate_survives_disk_reload():
    les = _routing()
    assert ls.deactivate(les.lesson_id) is True
    # a fresh disk read (tombstone applied) no longer returns it
    assert ls.routing_lessons("security_permissive") == []
