import asyncio
import shutil
from pathlib import Path

import pytest

from clink.agents.base import CLIAgentError
from clink.agents.copilot import CopilotAgent
from clink.models import ResolvedCLIClient, ResolvedCLIRole


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


@pytest.fixture()
def copilot_agent():
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="copilot",
        executable=["copilot"],
        internal_args=[],
        config_args=["--allow-all-tools", "--output-format", "json"],
        env={},
        timeout_seconds=30,
        parser="copilot_jsonl",
        roles={"default": role},
        output_to_file=None,
        working_dir=None,
    )
    return CopilotAgent(client), role


async def _run_agent_with_process(monkeypatch, agent, role, process):
    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    return await agent.run(role=role, prompt="do something", files=[], images=[])


@pytest.mark.asyncio
async def test_copilot_agent_success(monkeypatch, copilot_agent):
    agent, role = copilot_agent
    stdout = (
        b'{"type":"assistant.message","data":{"content":"Hello from Copilot"}}\n'
        b'{"type":"result","sessionId":"sess-1","usage":{"input_tokens":10,"output_tokens":5}}\n'
    )
    process = DummyProcess(stdout=stdout, returncode=0)
    result = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 0
    assert "Hello from Copilot" in result.parsed.content
    assert result.parsed.metadata["usage"]["output_tokens"] == 5
    # Prompt must be redacted in sanitized_command (metadata/logs)
    assert "do something" not in result.sanitized_command
    p_idx = result.sanitized_command.index("-p")
    assert result.sanitized_command[p_idx + 1] == "[REDACTED]"


@pytest.mark.asyncio
async def test_copilot_agent_passes_prompt_via_p_flag(monkeypatch, copilot_agent):
    agent, role = copilot_agent
    stdout = b'{"type":"assistant.message","data":{"content":"OK"}}\n'
    process = DummyProcess(stdout=stdout, returncode=0)

    captured_args = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_args["command"] = list(args)
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    await agent.run(role=role, prompt="test prompt", files=[], images=[])

    cmd = captured_args["command"]
    assert "-p" in cmd
    idx = cmd.index("-p")
    assert cmd[idx + 1] == "test prompt"


@pytest.mark.asyncio
async def test_copilot_agent_uses_devnull_stdin(monkeypatch, copilot_agent):
    agent, role = copilot_agent
    stdout = b'{"type":"assistant.message","data":{"content":"OK"}}\n'
    process = DummyProcess(stdout=stdout, returncode=0)

    captured_kwargs = {}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured_kwargs.update(kwargs)
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    await agent.run(role=role, prompt="test", files=[], images=[])

    assert captured_kwargs["stdin"] == asyncio.subprocess.DEVNULL


@pytest.mark.asyncio
async def test_copilot_agent_recovers_from_error(monkeypatch, copilot_agent):
    agent, role = copilot_agent
    stdout = b'{"type":"assistant.message","data":{"content":"Partial output"}}\n'
    process = DummyProcess(stdout=stdout, returncode=1)
    result = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 1
    assert "Partial output" in result.parsed.content


@pytest.mark.asyncio
async def test_copilot_agent_propagates_unparseable_error(monkeypatch, copilot_agent):
    agent, role = copilot_agent
    process = DummyProcess(stdout=b"not json at all", returncode=1)

    with pytest.raises(CLIAgentError):
        await _run_agent_with_process(monkeypatch, agent, role, process)


@pytest.mark.asyncio
async def test_copilot_agent_executable_not_found(monkeypatch, copilot_agent):
    agent, role = copilot_agent

    def fake_which(_name):
        return None

    monkeypatch.setattr(shutil, "which", fake_which)

    with pytest.raises(CLIAgentError, match="not found in PATH"):
        await agent.run(role=role, prompt="test", files=[], images=[])
