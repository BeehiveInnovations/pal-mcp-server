"""Agent factory for clink CLI integrations."""

from __future__ import annotations

from clink.models import ResolvedCLIClient

from .base import AgentOutput, BaseCLIAgent, CLIAgentError
from .claude import ClaudeAgent
from .codex import CodexAgent
from .gemini import GeminiAgent

_AGENTS: dict[str, type[BaseCLIAgent]] = {
    "gemini": GeminiAgent,
    "codex": CodexAgent,
    "claude": ClaudeAgent,
}


def available_runners() -> list[str]:
    """Return the sorted names of every registered agent runner."""

    return sorted(_AGENTS)


def create_agent(client: ResolvedCLIClient) -> BaseCLIAgent:
    agent_key = (client.runner or client.name).lower()
    agent_cls = _AGENTS.get(agent_key, BaseCLIAgent)
    return agent_cls(client)


__all__ = [
    "AgentOutput",
    "available_runners",
    "BaseCLIAgent",
    "CLIAgentError",
    "create_agent",
]
