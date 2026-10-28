"""Phase-1 bandit seeding: reorder routing candidates by observed success.

This is the *reversible, in-session* half of PAL's learning loop -- the only
autonomy the multi-model debate agreed to ship. It does NOT mutate any file,
prompt, or the ``CATEGORY_PREFERENCES`` table. Given the router's existing
ordered candidate list for a category, it returns a *reordered* list biased
toward models that have actually been succeeding, while a UCB-style
exploration bonus guarantees every candidate keeps getting sampled.

Why this is safe (the "exploration floor"):
  * reorder() never DROPS a candidate -- it only permutes. server.py still
    tries the whole list, and refusal_memory still filters availability the
    class-aware way. So a bad streak can demote a model but never starve it.
  * A candidate with little/no data keeps its PRIOR rank (optimistic) plus a
    large exploration bonus, so new/rare models are tried, not buried.
  * All state is the in-memory episode ring; a restart reverts to pure prior
    order. Nothing here persists. Persisting a learned order is Phase-2 and is
    human-gated (see distill.py) -- never auto-applied.

Scoring for a candidate at prior index ``i`` in a list of length ``L``::

    prior(i) = 1 - i / L                      # 1.0 for the top prior, down
    base     = empirical_success_rate  if n >= MIN_SAMPLES else prior(i)
    bonus    = EXPLORE_C * sqrt(ln(N_total + 1) / (n + 1))
    score    = base + bonus                    # sort desc, prior breaks ties

Env:
    PAL_BANDIT=0            disable; reorder() returns the input unchanged
    PAL_BANDIT_MIN_SAMPLES  min episodes before empirical rate is trusted (5)
    PAL_BANDIT_EXPLORE_C    exploration weight (0.7); 0 = pure exploit
    PAL_BANDIT_WINDOW       recent-episode window read per candidate (200)
"""

from __future__ import annotations

import math
import os

from providers.router import episode_store

MIN_SAMPLES = int(os.getenv("PAL_BANDIT_MIN_SAMPLES", "5"))
EXPLORE_C = float(os.getenv("PAL_BANDIT_EXPLORE_C", "0.7"))
WINDOW = int(os.getenv("PAL_BANDIT_WINDOW", "200"))


def is_enabled() -> bool:
    return os.getenv("PAL_BANDIT", "1") not in ("0", "false", "no")


def _prior(i: int, length: int) -> float:
    if length <= 1:
        return 1.0
    return 1.0 - i / length


def score(model: str, category: str, prior_index: int, length: int, total_n: int) -> float:
    """UCB-style score for one candidate. Exposed for tests/observability."""
    n, good = episode_store.observed(model, category, window=WINDOW)
    if n >= MIN_SAMPLES:
        base = good / n
    else:
        # not enough evidence -> trust the hand-tuned prior order
        base = _prior(prior_index, length)
    bonus = EXPLORE_C * math.sqrt(math.log(total_n + 1) / (n + 1))
    return base + bonus


def reorder(category: str, candidates: list[str]) -> list[str]:
    """Return candidates reordered by score (desc), prior order breaking ties.

    Pure function of the episode ring + input; never drops a candidate.
    """
    if not is_enabled() or not category or len(candidates) < 2:
        return list(candidates)

    length = len(candidates)
    total_n = sum(episode_store.observed(c, category, window=WINDOW)[0] for c in candidates)

    scored = []
    for i, c in enumerate(candidates):
        s = score(c, category, i, length, total_n)
        # sort key: higher score first; on tie keep original (prior) order
        scored.append((-s, i, c))
    scored.sort()
    return [c for _, _, c in scored]


def explain(category: str, candidates: list[str]) -> list[dict]:
    """Per-candidate score breakdown for `pal --diag` style introspection."""
    length = len(candidates)
    total_n = sum(episode_store.observed(c, category, window=WINDOW)[0] for c in candidates)
    rows = []
    for i, c in enumerate(candidates):
        n, good = episode_store.observed(c, category, window=WINDOW)
        rows.append(
            {
                "model": c,
                "prior_index": i,
                "n": n,
                "success_rate": (good / n) if n else None,
                "score": round(score(c, category, i, length, total_n), 4),
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
