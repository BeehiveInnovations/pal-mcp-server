"""Agent factory for clink CLI integrations."""

from __future__ import annotations

from clink.models import ResolvedCLIClient

from .base import AgentOutput, BaseCLIAgent, CLIAgentError
from .claude import ClaudeAgent
from .codex import CodexAgent
from .gemini import GeminiAgent
from .qwen import QwenAgent

_AGENTS: dict[str, type[BaseCLIAgent]] = {
    "gemini": GeminiAgent,
    "codex": CodexAgent,
    "claude": ClaudeAgent,
    "qwen": QwenAgent,
}


def create_agent(client: ResolvedCLIClient) -> BaseCLIAgent:
    agent_key = (client.runner or client.name).lower()
    agent_cls = _AGENTS.get(agent_key, BaseCLIAgent)
    return agent_cls(client)


__all__ = [
    "AgentOutput",
    "BaseCLIAgent",
    "CLIAgentError",
    "create_agent",
]
