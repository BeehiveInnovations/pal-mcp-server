import asyncio
import json
import shutil
from pathlib import Path

import pytest

from clink.agents.base import CLIAgentError
from clink.agents.grok import GrokAgent
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
def grok_agent():
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="grok",
        executable=["grok"],
        internal_args=[],
        config_args=["--output-format", "json", "--always-approve"],
        env={},
        timeout_seconds=30,
        parser="grok_json",
        runner="grok",
        roles={"default": role},
        output_to_file=None,
        working_dir=None,
    )
    return GrokAgent(client), role


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
async def test_grok_agent_uses_prompt_file(monkeypatch, grok_agent):
    agent, role = grok_agent
    stdout_payload = json.dumps(
        {
            "text": "42",
            "stopReason": "EndTurn",
            "sessionId": "sess-123",
            "requestId": "req-456",
        }
    ).encode()
    process = DummyProcess(stdout=stdout_payload)

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt="Respond with 42")

    assert result.parsed.content == "42"
    assert result.parsed.metadata["sessionId"] == "sess-123"
    assert "--prompt-file" in captured["command"]
    prompt_file_idx = captured["command"].index("--prompt-file")
    prompt_file = Path(captured["command"][prompt_file_idx + 1])
    # Temp file is cleaned up after the run.
    assert not prompt_file.exists()
    assert process.stdin_data == b""


@pytest.mark.asyncio
async def test_grok_agent_recovers_error_payload(monkeypatch, grok_agent):
    agent, role = grok_agent
    stdout_payload = json.dumps({"type": "error", "message": "Couldn't start session"}).encode()
    process = DummyProcess(stdout=stdout_payload, returncode=1)

    result, _ = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 1
    assert "Couldn't start session" in result.parsed.content
    assert result.parsed.metadata["is_error"] is True


@pytest.mark.asyncio
async def test_grok_agent_propagates_unparseable_output(monkeypatch, grok_agent):
    agent, role = grok_agent
    process = DummyProcess(stdout=b"", returncode=1)

    with pytest.raises(CLIAgentError):
        await _run_agent_with_process(monkeypatch, agent, role, process)
