"""Gemini-specific CLI agent hooks."""

from __future__ import annotations

from clink.models import ResolvedCLIClient

from .base import BaseCLIAgent


class GeminiAgent(BaseCLIAgent):
    """Placeholder for Gemini-specific behaviour."""

    def __init__(self, client: ResolvedCLIClient):
        super().__init__(client)
