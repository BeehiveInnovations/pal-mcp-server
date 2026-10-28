"""Unit tests for the Retry-After honor path in providers/router/rate_limit.py."""

from __future__ import annotations

import pytest

from providers.router import rate_limit


# ----- parse_retry_after ------------------------------------------------------
def test_header_integer_seconds():
    assert rate_limit.parse_retry_after({"Retry-After": "7"}, None) == 7


def test_header_float_seconds():
    assert rate_limit.parse_retry_after({"retry-after": "3.5"}, None) == 3


def test_header_zero_ok():
    assert rate_limit.parse_retry_after({"Retry-After": "0"}, None) == 0


def test_no_header_no_body_none():
    assert rate_limit.parse_retry_after({}, "") is None
    assert rate_limit.parse_retry_after(None, None) is None


def test_body_retry_in_seconds():
    assert rate_limit.parse_retry_after(None, "retry in 6.2s please") == 6


def test_body_try_again_seconds():
    assert rate_limit.parse_retry_after(None, "try again in 12 seconds") == 12


def test_body_milliseconds():
    assert rate_limit.parse_retry_after(None, "wait 4500ms then retry") == 4


def test_body_groq_phrasing():
    body = "Please retry in 6.168596011s"
    assert rate_limit.parse_retry_after(None, body) == 6


def test_header_wins_over_body():
    body = "retry in 999s"
    assert rate_limit.parse_retry_after({"Retry-After": "3"}, body) == 3


def test_invalid_header_ignored_falls_through_to_body():
    body = "retry in 5s"
    assert rate_limit.parse_retry_after({"Retry-After": "not-a-number"}, body) == 5


# ----- honor_retry_after ------------------------------------------------------
def test_honor_sleeps_expected_seconds():
    slept: list[int] = []
    got = rate_limit.honor_retry_after({"Retry-After": "4"}, None, sleep=slept.append)
    assert got == 4
    assert slept == [4]


def test_honor_caps_at_max_honor_s(monkeypatch):
    monkeypatch.setattr(rate_limit, "MAX_HONOR_S", 10)
    slept: list[int] = []
    got = rate_limit.honor_retry_after({"Retry-After": "3600"}, None, sleep=slept.append)
    assert got == 10
    assert slept == [10]


def test_honor_returns_zero_when_no_hint():
    slept: list[int] = []
    got = rate_limit.honor_retry_after({}, "no hint here", sleep=slept.append)
    assert got == 0
    assert slept == []


def test_honor_zero_hint_does_not_sleep():
    slept: list[int] = []
    got = rate_limit.honor_retry_after({"Retry-After": "0"}, None, sleep=slept.append)
    assert got == 0
    assert slept == []


@pytest.mark.parametrize(
    "body,expected",
    [
        ("retry in 7.9s", 7),
        ("Please retry in 12s", 12),
        ("try again in 3 seconds", 3),
        ("wait 2500ms", 2),
    ],
)
def test_body_variants(body, expected):
    assert rate_limit.parse_retry_after(None, body) == expected
