import asyncio
import json
import shutil
from pathlib import Path

import pytest

from clink.agents.base import BaseCLIAgent
from clink.models import PromptFileConfig, ResolvedCLIClient, ResolvedCLIRole


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
        internal_args=["--output-format", "json", "--always-approve"],
        config_args=[],
        env={},
        timeout_seconds=30,
        parser="grok_json",
        runner=None,
        roles={"default": role},
        output_to_file=None,
        prompt_to_file=PromptFileConfig(flag_template="--prompt-file {path}"),
        working_dir=None,
    )
    return BaseCLIAgent(client), role


async def _run_agent_with_process(monkeypatch, agent, role, process, *, prompt="do something"):
    captured: dict = {"command": [], "prompt_file_content": None}

    async def fake_create_subprocess_exec(*args, **_kwargs):
        captured["command"].extend(args)
        # The prompt file is written before launch and only cleaned up after
        # communicate() returns, so it is readable here — capture its content to
        # prove the prompt is actually delivered via the file (not stdin).
        if "--prompt-file" in args:
            path = Path(args[args.index("--prompt-file") + 1])
            captured["prompt_file_content"] = path.read_text(encoding="utf-8")
        return process

    def fake_which(executable_name):
        return f"/usr/bin/{executable_name}"

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", fake_which)
    result = await agent.run(role=role, prompt=prompt, files=[], images=[])
    return result, captured


@pytest.mark.asyncio
async def test_prompt_to_file_writes_temp_and_uses_empty_stdin(monkeypatch, grok_agent):
    agent, role = grok_agent
    process = DummyProcess(
        stdout=json.dumps({"text": "ok", "stopReason": "EndTurn"}).encode(),
    )

    result, captured = await _run_agent_with_process(monkeypatch, agent, role, process, prompt="my prompt content")

    assert "--prompt-file" in captured["command"]
    flag_idx = captured["command"].index("--prompt-file")
    prompt_file_path = Path(captured["command"][flag_idx + 1])
    # the prompt was delivered via the file (not stdin) and the file is cleaned up
    assert captured["prompt_file_content"] == "my prompt content"
    assert process.stdin_data == b""
    assert not prompt_file_path.exists()
    assert result.parsed.content == "ok"


@pytest.mark.asyncio
async def test_prompt_to_file_respects_cleanup_false(monkeypatch, grok_agent):
    agent, role = grok_agent
    agent.client.prompt_to_file = PromptFileConfig(flag_template="--prompt-file {path}", cleanup=False)
    process = DummyProcess(stdout=json.dumps({"text": "kept"}).encode())

    _, captured = await _run_agent_with_process(monkeypatch, agent, role, process)

    prompt_file_path = Path(captured["command"][captured["command"].index("--prompt-file") + 1])
    try:
        assert prompt_file_path.exists()  # cleanup=False leaves the file in place
    finally:
        prompt_file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_prompt_to_file_path_with_spaces_stays_single_arg(monkeypatch, tmp_path, grok_agent):
    import tempfile

    agent, role = grok_agent
    spaced = tmp_path / "dir with spaces"
    spaced.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spaced))  # temp file lands in a spaced dir
    process = DummyProcess(stdout=json.dumps({"text": "ok"}).encode())

    _, captured = await _run_agent_with_process(monkeypatch, agent, role, process)

    cmd = captured["command"]
    prompt_arg = cmd[cmd.index("--prompt-file") + 1]
    # the spaced path must survive as ONE argument (not re-split by shlex)
    assert " " in prompt_arg
    assert Path(prompt_arg).parent == spaced


@pytest.mark.asyncio
async def test_grok_agent_parses_json_stdout(monkeypatch, grok_agent):
    agent, role = grok_agent
    stdout_payload = json.dumps(
        {
            "text": "Hello from grok",
            "stopReason": "EndTurn",
            "sessionId": "sess-abc",
            "requestId": "req-def",
        }
    ).encode()
    process = DummyProcess(stdout=stdout_payload)

    result, _ = await _run_agent_with_process(monkeypatch, agent, role, process)

    assert result.returncode == 0
    assert result.parsed.content == "Hello from grok"
    assert result.parsed.metadata["session_id"] == "sess-abc"
    assert result.parsed.metadata["stop_reason"] == "EndTurn"
