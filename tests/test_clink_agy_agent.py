import asyncio
import shutil
from pathlib import Path

import pytest

from clink.agents.base import BaseCLIAgent
from clink.models import PromptArgConfig, ResolvedCLIClient, ResolvedCLIRole


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
def agy_agent():
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="agy",
        executable=["agy"],
        internal_args=[],
        config_args=["--sandbox"],
        env={},
        timeout_seconds=30,
        parser="agy_text",
        runner=None,
        roles={"default": role},
        output_to_file=None,
        prompt_to_arg=PromptArgConfig(flag_template="--print {prompt}"),
        working_dir=None,
    )
    return BaseCLIAgent(client), role


async def _run_agent_with_process(monkeypatch, agent, role, process, *, prompt="do something"):
    captured: dict = {"command": [], "kwargs": {}}

    async def fake_create_subprocess_exec(*args, **kwargs):
        captured["command"].extend(args)
        captured["kwargs"] = kwargs
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    result = await agent.run(role=role, prompt=prompt, files=[], images=[])
    return result, captured


@pytest.mark.asyncio
async def test_prompt_to_arg_injects_prompt_and_uses_devnull_stdin(monkeypatch, agy_agent):
    agent, role = agy_agent
    process = DummyProcess(stdout=b"PONG")

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt="ping the model")

    # the real prompt is delivered as the --print argument value, not via stdin
    assert captured["command"][-2:] == ["--print", "ping the model"]
    # stdin must be closed (DEVNULL), not an open-but-empty pipe: an open pipe
    # with nothing written is the pre-1.1.1 Antigravity hang class described in
    # google-antigravity/antigravity-cli#76.
    assert captured["kwargs"]["stdin"] == asyncio.subprocess.DEVNULL
    assert process.stdin_data is None
    assert result.parsed.content == "PONG"


@pytest.mark.asyncio
async def test_no_prompt_to_arg_keeps_stdin_pipe(monkeypatch):
    # Regression guard: a client that does NOT set prompt_to_arg (e.g. gemini)
    # must be completely unaffected by the agy-specific DEVNULL handling.
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="gemini",
        executable=["gemini"],
        internal_args=[],
        config_args=[],
        env={},
        timeout_seconds=30,
        parser="gemini_json",
        runner=None,
        roles={"default": role},
        output_to_file=None,
        prompt_to_arg=None,
        working_dir=None,
    )
    agent = BaseCLIAgent(client)
    process = DummyProcess(stdout=b'{"response": "ok"}')

    _, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt="ping the model")

    assert captured["kwargs"]["stdin"] == asyncio.subprocess.PIPE
    assert process.stdin_data == b"ping the model"


@pytest.mark.asyncio
async def test_prompt_to_arg_redacts_prompt_in_sanitized_command(monkeypatch, agy_agent):
    agent, role = agy_agent
    process = DummyProcess(stdout=b"ok")
    sensitive_prompt = "a very long sensitive prompt with details"

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt=sensitive_prompt)

    # the real prompt reaches the subprocess argv...
    assert sensitive_prompt in captured["command"]
    # ...but the sanitized_command (surfaced in logs/metadata) redacts it instead
    # of duplicating the full prompt into every debug log line and response.
    assert sensitive_prompt not in result.sanitized_command
    assert result.sanitized_command[-2:] == ["--print", "<prompt omitted>"]


@pytest.mark.asyncio
async def test_agy_agent_parses_plain_text_stdout(monkeypatch, agy_agent):
    agent, role = agy_agent
    process = DummyProcess(stdout=b"  Hello from agy  \n")

    result, _ = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 0
    assert result.parsed.content == "Hello from agy"
    assert result.parser_name == "agy_text"
