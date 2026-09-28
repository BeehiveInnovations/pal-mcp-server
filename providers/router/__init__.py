"""PAL smart-router primitives.

Phase 1: self_heal, health_probe, rate_limit, response_cache.
Phase 2: refusal_memory, classifier.
Phase 3: hybrid (speculative-draft + confidence envelope).
Phase 4: tooling/ (MCP-in-MCP proxy) + clink client coverage.
"""
from providers.router import (  # noqa: F401
    classifier,
    health_probe,
    rate_limit,
    refusal_memory,
    response_cache,
    self_heal,
)

__all__ = [
    "classifier", "health_probe", "rate_limit", "refusal_memory",
    "response_cache", "self_heal",
]
