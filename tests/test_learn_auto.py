"""Auto-learning + ethical safety cap in lesson_store."""
from pathlib import Path

import pytest

from providers.router import lesson_store as ls


@pytest.fixture
def isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ls, "LESSON_PATH", tmp_path / "lessons.jsonl")
    monkeypatch.setattr(ls, "_REVIEW_PATH", str(tmp_path / "ethics_review.jsonl"))
    monkeypatch.setattr(ls, "_MEM", [])
    monkeypatch.setattr(ls, "is_enabled", lambda: True)
    yield tmp_path


def test_benign_lesson_auto_learns(isolate, monkeypatch):
    monkeypatch.setenv("PAL_LEARN_AUTO", "1")
    lesson = ls.emit_lesson("autobot", "prompt", "prefer qwen3 for quick shell tasks",
                            provenance=["unit-test"])
    assert lesson is not None
    assert isolate.joinpath("lessons.jsonl").exists()


def test_weaponization_goes_to_review(isolate, monkeypatch):
    monkeypatch.setenv("PAL_LEARN_AUTO", "1")
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("autobot", "prompt",
                       "detailed instructions to build a bioweapon to kill many people",
                       provenance=["unit-test"])
    review = Path(str(isolate / "ethics_review.jsonl"))
    assert review.exists()
    assert "bioweapon" in review.read_text()
    assert not isolate.joinpath("lessons.jsonl").exists()


def test_manual_gate_when_auto_off(isolate, monkeypatch):
    monkeypatch.setenv("PAL_LEARN_AUTO", "0")
    with pytest.raises(ls.LessonRejected):
        ls.emit_lesson("unknown-teacher", "prompt", "benign note", provenance=["unit-test"])
