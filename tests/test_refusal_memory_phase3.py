"""Phase 3: breaker half-open probes + optional persistence."""

from __future__ import annotations

import json

import pytest

from providers.router import refusal_memory as rm


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.setenv("PAL_REFUSAL_MEMORY", "1")
    monkeypatch.setenv("PAL_RESILIENCE_PATH", str(tmp_path / "res.json"))
    monkeypatch.delenv("PAL_RESILIENCE_PERSIST", raising=False)
    monkeypatch.delenv("PAL_BREAKER_HALFOPEN", raising=False)
    rm.clear()
    yield
    rm.clear()


def _trip():
    for _ in range(rm.AVAIL_MIN):
        rm.record("m", "c", "status:503")
    assert rm.is_blacklisted("m", "c") is True


def test_half_open_admits_single_probe_per_interval():
    _trip()
    rm._MEM[("m", "c")].ts -= rm.HALFOPEN_INTERVAL + 1
    assert rm.is_blacklisted("m", "c") is False  # the probe
    assert rm.is_blacklisted("m", "c") is True  # others still blocked


def test_probe_success_closes():
    _trip()
    rm.record_success("m", "c")
    assert rm.is_blacklisted("m", "c") is False
    assert ("m", "c") not in rm._MEM


def test_probe_failure_reopens():
    _trip()
    rm._MEM[("m", "c")].ts -= rm.HALFOPEN_INTERVAL + 1
    assert rm.is_blacklisted("m", "c") is False
    rm.record("m", "c", "status:503")
    assert rm.is_blacklisted("m", "c") is True


def test_halfopen_disabled(monkeypatch):
    monkeypatch.setenv("PAL_BREAKER_HALFOPEN", "0")
    _trip()
    rm._MEM[("m", "c")].ts -= rm.HALFOPEN_INTERVAL + 1
    assert rm.is_blacklisted("m", "c") is True


def test_policy_never_probed_nor_closed_by_success():
    rm.record("m", "c", "status:403")
    rm._MEM[("m", "c")].ts -= rm.HALFOPEN_INTERVAL + 1
    assert rm.is_blacklisted("m", "c") is True
    rm.record_success("m", "c")
    assert rm.is_blacklisted("m", "c") is True


def test_single_transient_still_never_blacklists():
    rm.record("m", "c", "status:502")
    assert rm.is_blacklisted("m", "c") is False


def test_persist_off_writes_nothing(tmp_path):
    _trip()
    assert not (tmp_path / "res.json").exists()


def test_persist_roundtrip_and_ttl(monkeypatch, tmp_path):
    monkeypatch.setenv("PAL_RESILIENCE_PERSIST", "1")
    rm.record("m", "c", "status:403")
    rm.record("old", "c", "status:403")
    rm._MEM[("old", "c")].ts -= rm.PERSIST_TTL + 5
    rm._save_locked()
    rm._MEM.clear()
    rm.hydrate(force=True)
    assert rm.is_blacklisted("m", "c") is True
    assert rm.is_blacklisted("old", "c") is False
    assert json.loads((tmp_path / "res.json").read_text())["v"] == 1


def test_disabled_ignores_existing_file(monkeypatch, tmp_path):
    monkeypatch.setenv("PAL_RESILIENCE_PERSIST", "1")
    rm.record("m", "c", "status:403")
    rm._MEM.clear()
    monkeypatch.setenv("PAL_RESILIENCE_PERSIST", "0")
    assert rm.hydrate(force=True) == 0
    assert rm.is_blacklisted("m", "c") is False
