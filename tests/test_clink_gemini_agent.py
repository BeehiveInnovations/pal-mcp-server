import asyncio
import shutil
from pathlib import Path

import pytest

from clink.agents.base import CLIAgentError
from clink.agents.gemini import GeminiAgent
from clink.models import ResolvedCLIClient, ResolvedCLIRole


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, _input):
        return self._stdout, self._stderr


@pytest.fixture()
def gemini_agent():
    prompt_path = Path("systemprompts/clink/gemini_default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="gemini",
        executable=["gemini"],
        internal_args=[],
        config_args=[],
        env={},
        timeout_seconds=30,
        parser="gemini_json",
        roles={"default": role},
        output_to_file=None,
        working_dir=None,
    )
    return GeminiAgent(client), role


async def _run_agent_with_process(monkeypatch, agent, role, process):
    async def fake_create_subprocess_exec(*_args, **_kwargs):
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    return await agent.run(role=role, prompt="do something", files=[], images=[])


@pytest.mark.asyncio
async def test_gemini_agent_recovers_tool_error(monkeypatch, gemini_agent):
    agent, role = gemini_agent
    error_json = """{
  "error": {
    "type": "FatalToolExecutionError",
    "message": "Error executing tool replace: Failed to edit",
    "code": "edit_expected_occurrence_mismatch"
  }
}"""
    stderr = ("Error: Failed to edit, expected 1 occurrence but found 2.\n" + error_json).encode()
    process = DummyProcess(stderr=stderr, returncode=54)

    result = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 54
    assert result.parsed.metadata["cli_error_recovered"] is True
    assert result.parsed.metadata["cli_error_code"] == "edit_expected_occurrence_mismatch"
    assert "Gemini CLI reported a tool failure" in result.parsed.content


@pytest.mark.asyncio
async def test_gemini_agent_propagates_unrecoverable_error(monkeypatch, gemini_agent):
    agent, role = gemini_agent
    stderr = b"Plain failure without structured payload"
    process = DummyProcess(stderr=stderr, returncode=54)

    with pytest.raises(CLIAgentError):
        await _run_agent_with_process(monkeypatch, agent, role, process)
