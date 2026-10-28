"""Unit tests for providers/router/episode_store.py."""

from __future__ import annotations

import json

import pytest

from providers.router import episode_store as es


@pytest.fixture(autouse=True)
def _tmp_episodes(tmp_path, monkeypatch):
    p = tmp_path / "episodes.jsonl"
    monkeypatch.setattr(es, "EPISODE_PATH", p)
    monkeypatch.setenv("PAL_EPISODE_STORE", "1")
    es.clear()
    yield p
    es.clear()


def test_record_appends_jsonl_and_ring(_tmp_episodes):
    es.record("groq", "debug", "success", latency_ms=120, prompt="hello", tool="chat")
    assert _tmp_episodes.exists()
    lines = _tmp_episodes.read_text().strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["model"] == "groq"
    assert obj["outcome"] == "success"
    assert obj["latency_ms"] == 120
    # prompt is hashed, never stored raw
    assert obj["prompt_hash"].startswith("sha256:")
    assert "hello" not in lines[0]
    assert obj["reward"] is None  # reserved for Phase 2


def test_invalid_outcome_coerced_to_error(_tmp_episodes):
    es.record("m", "c", "banana")
    assert es.get_recent(1)[0].outcome == "error"


def test_get_recent_is_newest_first(_tmp_episodes):
    for i in range(5):
        es.record("m", "c", "success", latency_ms=i)
    recent = es.get_recent(3)
    assert [e.latency_ms for e in recent] == [4, 3, 2]


def test_success_rate(_tmp_episodes):
    for _ in range(3):
        es.record("m", "c", "success")
    es.record("m", "c", "error")
    assert es.success_rate("m", "c") == pytest.approx(0.75)
    assert es.success_rate("other", "c") is None


def test_disabled_writes_nothing(_tmp_episodes, monkeypatch):
    monkeypatch.setenv("PAL_EPISODE_STORE", "0")
    es.record("m", "c", "success")
    assert not _tmp_episodes.exists()
    assert es.get_recent(1) == []


def test_write_failure_never_raises(_tmp_episodes, monkeypatch):
    # point at an unwritable path; record must swallow the OSError
    monkeypatch.setattr(es, "EPISODE_PATH", _tmp_episodes.parent / "nope" / "x.jsonl")

    def _boom(*a, **k):
        raise OSError("read-only fs")

    monkeypatch.setattr(es.Path, "mkdir", _boom)
    es.record("m", "c", "success")  # must not raise
    # in-memory ring still updated even when disk write fails
    assert es.get_recent(1)[0].model == "m"
