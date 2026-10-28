"""Unit tests for providers/router/bandit.py (Phase-1 seeding)."""

from __future__ import annotations

import pytest

from providers.router import bandit
from providers.router import episode_store as es


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setattr(es, "EPISODE_PATH", tmp_path / "episodes.jsonl")
    monkeypatch.setenv("PAL_EPISODE_STORE", "1")
    monkeypatch.setenv("PAL_BANDIT", "1")
    monkeypatch.setattr(bandit, "MIN_SAMPLES", 5)
    monkeypatch.setattr(bandit, "EXPLORE_C", 0.7)
    es.clear()
    yield
    es.clear()


def _seed(model, category, n_success, n_fail):
    for _ in range(n_success):
        es.record(model, category, "success")
    for _ in range(n_fail):
        es.record(model, category, "error", err_class="availability")


def test_no_data_preserves_prior_order():
    cands = ["a", "b", "c"]
    assert bandit.reorder("cat", cands) == cands


def test_disabled_is_identity(monkeypatch):
    monkeypatch.setenv("PAL_BANDIT", "0")
    cands = ["a", "b", "c"]
    _seed("c", "cat", 20, 0)  # would normally promote c
    assert bandit.reorder("cat", cands) == cands


def test_single_candidate_untouched():
    assert bandit.reorder("cat", ["solo"]) == ["solo"]


def test_strong_model_gets_promoted():
    # prior order puts 'weak' first, but 'strong' has a great record
    cands = ["weak", "strong"]
    _seed("weak", "cat", 1, 15)  # mostly failing
    _seed("strong", "cat", 18, 1)  # mostly succeeding
    assert bandit.reorder("cat", cands)[0] == "strong"


def test_low_sample_model_not_demoted_below_prior():
    # 'top' is prior #1 with no data; 'mid' has only 2 samples (< MIN_SAMPLES)
    cands = ["top", "mid", "bottom"]
    _seed("mid", "cat", 0, 2)  # 2 failures, but below MIN_SAMPLES -> ignored
    out = bandit.reorder("cat", cands)
    # 'top' keeps the lead because low-sample evidence doesn't override prior
    assert out[0] == "top"


def test_never_drops_a_candidate():
    cands = ["a", "b", "c", "d"]
    _seed("a", "cat", 0, 30)  # a is terrible
    out = bandit.reorder("cat", cands)
    assert sorted(out) == sorted(cands)  # same set, just reordered
    assert "a" in out  # exploration floor: never removed


def test_explain_is_sorted_and_shaped():
    # both models have ample data so quality dominates the exploration bonus;
    # y (all success) must outrank x (all failure).
    cands = ["x", "y"]
    _seed("x", "cat", 0, 12)
    _seed("y", "cat", 12, 0)
    rows = bandit.explain("cat", cands)
    assert [r["model"] for r in rows][0] == "y"
    assert set(rows[0]) == {"model", "prior_index", "n", "success_rate", "score"}


def test_unseen_candidate_is_explored_first():
    # optimism-under-uncertainty: an unsampled candidate outranks a well-sampled
    # perfect one so new/rare models keep getting tried (the exploration floor).
    cands = ["seen", "unseen"]
    _seed("seen", "cat", 20, 0)
    assert bandit.reorder("cat", cands)[0] == "unseen"
