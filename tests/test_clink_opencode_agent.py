import asyncio
import shutil
from pathlib import Path

import pytest

from clink.agents.base import CLIAgentError
from clink.agents.opencode import _MAX_INLINE_PROMPT_CHARS, OpenCodeAgent
from clink.models import ResolvedCLIClient, ResolvedCLIRole


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.stdin_data: bytes | None = None

    async def communicate(self, input_data):
        self.stdin_data = input_data
        return self._stdout, self._stderr


@pytest.fixture()
def opencode_agent():
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="opencode",
        executable=["opencode"],
        internal_args=["run"],
        config_args=["--format", "json", "--auto"],
        env={},
        timeout_seconds=30,
        parser="opencode_jsonl",
        runner="opencode",
        roles={"default": role},
        output_to_file=None,
        working_dir=None,
    )
    return OpenCodeAgent(client), role


async def _run_agent_with_process(monkeypatch, agent, role, process, *, prompt="Respond with 42"):
    captured: dict = {}

    async def fake_create_subprocess_exec(*args, **_kwargs):
        captured["command"] = list(args)
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)

    result = await agent.run(
        role=role,
        prompt=prompt,
        system_prompt=None,
        files=[],
        images=[],
    )
    return result, captured


@pytest.mark.asyncio
async def test_opencode_agent_passes_inline_message(monkeypatch, opencode_agent):
    agent, role = opencode_agent
    stdout = b"""
{"type":"text","sessionID":"ses_abc","part":{"type":"text","text":"Hello from OpenCode"}}
{"type":"step_finish","sessionID":"ses_abc","part":{"type":"step-finish","reason":"stop","cost":0.001,"tokens":{"input":10,"output":5}}}
"""
    process = DummyProcess(stdout=stdout)

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt="Respond with 42")

    assert "Hello from OpenCode" in result.parsed.content
    assert captured["command"][-1] == "Respond with 42"
    assert "--file" not in captured["command"]
    assert process.stdin_data == b""


@pytest.mark.asyncio
async def test_opencode_agent_uses_file_for_large_prompt(monkeypatch, opencode_agent):
    agent, role = opencode_agent
    stdout = b'{"type":"text","part":{"type":"text","text":"ok"}}'
    process = DummyProcess(stdout=stdout)
    large_prompt = "X" * (_MAX_INLINE_PROMPT_CHARS + 10)

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt=large_prompt)

    assert result.parsed.content == "ok"
    assert "--file" in captured["command"]
    file_idx = captured["command"].index("--file")
    prompt_file = Path(captured["command"][file_idx + 1])
    assert not prompt_file.exists()
    assert "attached file" in captured["command"][-1].lower()


@pytest.mark.asyncio
async def test_opencode_agent_recovers_jsonl(monkeypatch, opencode_agent):
    agent, role = opencode_agent
    stdout = b'{"type":"text","part":{"type":"text","text":"Recovered"}}'
    process = DummyProcess(stdout=stdout, returncode=2)

    result, _ = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 2
    assert result.parsed.content == "Recovered"


@pytest.mark.asyncio
async def test_opencode_agent_propagates_invalid_json(monkeypatch, opencode_agent):
    agent, role = opencode_agent
    process = DummyProcess(stdout=b"not json", returncode=1)

    with pytest.raises(CLIAgentError):
        await _run_agent_with_process(monkeypatch, agent, role, process)
