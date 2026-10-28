"""Unit tests for the self_heal migration probation guard."""

from __future__ import annotations

import pytest

from providers.router import self_heal as sh


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_SELF_HEAL", "1")
    monkeypatch.setattr(sh, "DRIFT_LOG", tmp_path / "drift.log")
    sh._ALIAS_MAP.clear()
    sh._PROVISIONAL.clear()
    yield
    sh._ALIAS_MAP.clear()
    sh._PROVISIONAL.clear()


def test_single_hint_stays_on_probation(monkeypatch):
    monkeypatch.setattr(sh, "MIN_HINTS", 2)
    committed = sh.record_migration("old", "new", provider="google")
    assert committed is False
    # not aliased yet, and nothing written to the drift log
    assert sh.resolve("old") == "old"
    assert not sh.DRIFT_LOG.exists()


def test_repeated_hint_commits(monkeypatch):
    monkeypatch.setattr(sh, "MIN_HINTS", 2)
    assert sh.record_migration("old", "new", provider="google") is False
    assert sh.record_migration("old", "new", provider="google") is True
    assert sh.resolve("old") == "new"
    assert sh.DRIFT_LOG.exists()
    assert "old" in sh.DRIFT_LOG.read_text()


def test_min_hints_one_restores_immediate(monkeypatch):
    monkeypatch.setattr(sh, "MIN_HINTS", 1)
    assert sh.record_migration("old", "new") is True
    assert sh.resolve("old") == "new"


def test_apply_after_retry_still_recovers_current_call(monkeypatch):
    """Even while an alias is on probation, the one-shot retry with the new id
    must succeed so the current request is not lost."""
    monkeypatch.setattr(sh, "MIN_HINTS", 2)
    calls = []

    def flaky(model_id):
        calls.append(model_id)
        if model_id == "dead-model":
            raise RuntimeError(
                "This model models/dead-model is no longer available. "
                "Please update your code to use models/live-model instead."
            )
        return f"ok:{model_id}"

    out = sh.apply_after_retry(flaky, "dead-model", "google")
    assert out == "ok:live-model"
    assert calls == ["dead-model", "live-model"]
    # but the alias is NOT yet permanent (only one hint seen)
    assert sh.resolve("dead-model") == "dead-model"
