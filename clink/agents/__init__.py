"""Agent factory for clink CLI integrations."""

from __future__ import annotations

from clink.models import ResolvedCLIClient

from .base import AgentOutput, BaseCLIAgent, CLIAgentError
from .gemini import GeminiAgent

_AGENTS: dict[str, type[BaseCLIAgent]] = {
    "gemini": GeminiAgent,
}


def create_agent(client: ResolvedCLIClient) -> BaseCLIAgent:
    agent_key = client.name.lower()
    agent_cls = _AGENTS.get(agent_key, BaseCLIAgent)
    return agent_cls(client)


__all__ = [
    "AgentOutput",
    "BaseCLIAgent",
    "CLIAgentError",
    "create_agent",
]
