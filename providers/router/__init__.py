"""PAL smart-router primitives.

Phase 1: self_heal, health_probe, rate_limit, response_cache.
Phase 2: refusal_memory, classifier.
Phase 3: hybrid (speculative-draft + confidence envelope).
Phase 4: tooling/ (MCP-in-MCP proxy) + clink client coverage.
"""

from providers.router import (  # noqa: F401
    bandit,
    classifier,
    dispatch,
    episode_store,
    fallback_chain,
    guardrail,
    health_probe,
    lesson_store,
    quota_probe,
    rate_limit,
    refusal_memory,
    response_cache,
    self_heal,
    size_guard,
)

# NOTE: `distill` is an offline CLI (python -m providers.router.distill); it is
# intentionally NOT eagerly imported here so `-m` execution has clean semantics.

__all__ = [
    "bandit",
    "classifier",
    "dispatch",
    "episode_store",
    "fallback_chain",
    "health_probe",
    "lesson_store",
    "quota_probe",
    "rate_limit",
    "refusal_memory",
    "response_cache",
    "self_heal",
    "size_guard",
]
