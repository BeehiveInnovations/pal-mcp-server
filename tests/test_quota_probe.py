"""Unit tests for providers/router/quota_probe.py."""

from __future__ import annotations

import json

import pytest

from providers.router import quota_probe as qp


@pytest.fixture(autouse=True)
def _tmp_stats(tmp_path, monkeypatch):
    p = tmp_path / "provider_stats.jsonl"
    monkeypatch.setattr(qp, "STATS_PATH", p)
    yield p


class _FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code


def _stub(status_code=None, exc=None):
    def requester(url, timeout):
        if exc is not None:
            raise exc
        return _FakeResp(status_code)

    return requester


# ----- probe_one --------------------------------------------------------------
def test_probe_one_200_available():
    rec = qp.probe_one("groq", "https://example.test", requester=_stub(status_code=200))
    assert rec["available"] is True
    assert rec["status_code"] == 200
    assert rec["error"] is None
    assert rec["latency_ms"] >= 0


def test_probe_one_401_still_available_service_up():
    rec = qp.probe_one("openai", "https://example.test", requester=_stub(status_code=401))
    assert rec["available"] is True
    assert rec["status_code"] == 401


def test_probe_one_429_unavailable():
    rec = qp.probe_one("groq", "https://example.test", requester=_stub(status_code=429))
    assert rec["available"] is False
    assert "429" in (rec["error"] or "")


def test_probe_one_503_unavailable():
    rec = qp.probe_one("gemini", "https://example.test", requester=_stub(status_code=503))
    assert rec["available"] is False


def test_probe_one_timeout_unavailable():
    rec = qp.probe_one("openrouter", "https://example.test", requester=_stub(exc=RuntimeError("timeout")))
    assert rec["available"] is False
    assert "timeout" in (rec["error"] or "").lower()


# ----- probe_all --------------------------------------------------------------
def test_probe_all_writes_jsonl_per_provider(_tmp_stats):
    results = qp.probe_all({"a": "https://a.test", "b": "https://b.test"}, requester=_stub(status_code=200))
    assert set(results.keys()) == {"a", "b"}
    assert all(r["available"] for r in results.values())
    lines = _tmp_stats.read_text().splitlines()
    assert len(lines) == 2
    for ln in lines:
        rec = json.loads(ln)
        assert rec["provider"] in {"a", "b"}


def test_probe_all_appends_not_overwrites(_tmp_stats):
    qp.probe_all({"a": "https://a.test"}, requester=_stub(status_code=200))
    qp.probe_all({"a": "https://a.test"}, requester=_stub(status_code=429))
    lines = _tmp_stats.read_text().splitlines()
    assert len(lines) == 2


# ----- is_available -----------------------------------------------------------
def test_is_available_true_when_no_records():
    assert qp.is_available("nobody") is True  # optimistic default


def test_is_available_reads_last_record(_tmp_stats):
    qp.probe_all({"g": "https://x.test"}, requester=_stub(status_code=200))
    assert qp.is_available("g") is True

    qp.probe_all({"g": "https://x.test"}, requester=_stub(status_code=429))
    assert qp.is_available("g") is False


def test_is_available_stale_record_is_optimistic(_tmp_stats, monkeypatch):
    # Write a very-old unavailable record
    old_rec = {
        "provider": "g",
        "url": "https://x",
        "checked_at": "2020-01-01T00:00:00Z",
        "available": False,
        "latency_ms": 0,
        "status_code": 429,
        "error": "status=429",
    }
    _tmp_stats.write_text(json.dumps(old_rec) + "\n")
    assert qp.is_available("g", max_age_s=60) is True


def test_is_available_ignores_other_providers(_tmp_stats):
    qp.probe_all({"a": "https://a.test"}, requester=_stub(status_code=429))
    assert qp.is_available("a") is False
    assert qp.is_available("b") is True  # no record → optimistic


def test_is_available_skips_malformed_lines(_tmp_stats):
    _tmp_stats.write_text('{"provider":"g","checked_at":"bad","available":false}\ngarbage\n')
    # bad timestamp → optimistic True
    assert qp.is_available("g") is True
