"""Unit tests for the error-class-aware penalty logic in refusal_memory.

The critical property under test is the anti-cascade guard: a transient
availability failure (5xx/429) must NEVER permanently blacklist a provider,
while a genuine policy refusal is skipped immediately.
"""

from __future__ import annotations

import pytest

from providers.router import refusal_memory as rm


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("PAL_REFUSAL_MEMORY", "1")
    rm.clear()
    yield
    rm.clear()


# ----- classify_class ---------------------------------------------------------
@pytest.mark.parametrize(
    "reason,expected",
    [
        ("status:502", "availability"),
        ("status:429", "availability"),
        ("RESOURCE_EXHAUSTED", "availability"),
        ("status:403", "policy"),
        ("refusal:policy", "policy"),
        ("I cannot help with that", "policy"),
        ("status:401", "client"),
        ("status:400", "client"),
        ("NOT_FOUND", "client"),
        ("something weird", "unknown"),
        (None, "unknown"),
        # availability wins even when a refusal word is incidentally present
        ("status:503 service unable to respond", "availability"),
    ],
)
def test_classify_class(reason, expected):
    assert rm.classify_class(reason) == expected


# ----- policy refusals: immediate skip ---------------------------------------
def test_policy_refusal_blacklists_immediately():
    rm.record("m", "cat", "refusal:policy")
    assert rm.is_blacklisted("m", "cat") is True


def test_policy_expires_after_ttl(monkeypatch):
    monkeypatch.setattr(rm, "TTL", 100)
    rm.record("m", "cat", "status:403")
    entry = rm._MEM[("m", "cat")]
    entry.ts -= 101  # age past TTL
    assert rm.is_blacklisted("m", "cat") is False
    assert ("m", "cat") not in rm._MEM  # swept


# ----- availability: the anti-cascade guard ----------------------------------
def test_single_5xx_does_not_blacklist():
    """One transient 502 must not skip the provider (the cascade bug)."""
    rm.record("prov", "cat", "status:502")
    assert rm.is_blacklisted("prov", "cat") is False


def test_availability_needs_sustained_burst(monkeypatch):
    monkeypatch.setattr(rm, "AVAIL_MIN", 3)
    rm.record("prov", "cat", "status:503")
    rm.record("prov", "cat", "status:503")
    assert rm.is_blacklisted("prov", "cat") is False  # only 2 < AVAIL_MIN
    rm.record("prov", "cat", "status:503")
    assert rm.is_blacklisted("prov", "cat") is True  # 3 sustained -> skip


def test_availability_decays_and_reprobes(monkeypatch):
    """After the burst stops, the effective count decays and the pair
    auto-reprobes (un-blacklists) -- never permanent."""
    monkeypatch.setattr(rm, "AVAIL_MIN", 3)
    monkeypatch.setattr(rm, "AVAIL_DECAY_STEP", 300)
    monkeypatch.setattr(rm, "AVAIL_TTL", 1800)
    for _ in range(3):
        rm.record("prov", "cat", "status:502")
    assert rm.is_blacklisted("prov", "cat") is True

    # simulate 300s of silence: effective count 3 -> 2, now below AVAIL_MIN
    rm._MEM[("prov", "cat")].ts -= 300
    assert rm.is_blacklisted("prov", "cat") is False

    # far in the future the entry is forgotten entirely (full reprobe)
    rm.record("prov", "cat", "status:502")
    rm._MEM[("prov", "cat")].ts -= 2000  # past AVAIL_TTL
    assert rm.is_blacklisted("prov", "cat") is False
    assert ("prov", "cat") not in rm._MEM


def test_class_change_resets_counter(monkeypatch):
    monkeypatch.setattr(rm, "AVAIL_MIN", 3)
    for _ in range(3):
        rm.record("m", "cat", "status:500")
    assert rm.is_blacklisted("m", "cat") is True
    # a policy refusal on the same pair replaces the availability entry
    rm.record("m", "cat", "refusal:policy")
    entry = rm._MEM[("m", "cat")]
    assert entry.klass == "policy"
    assert entry.count == 1
    assert rm.is_blacklisted("m", "cat") is True  # policy -> immediate


def test_snapshot_reports_class_and_effective():
    rm.record("m", "cat", "status:502")
    snap = rm.snapshot()
    assert snap["m/cat"]["klass"] == "availability"
    assert "effective" in snap["m/cat"]
