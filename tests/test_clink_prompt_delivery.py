"""Tests for configurable prompt delivery and argument placeholders."""

import asyncio
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from clink.agents.base import PROMPT_REDACTION, BaseCLIAgent, CLIAgentError
from clink.models import OutputCaptureConfig, ResolvedCLIClient, ResolvedCLIRole


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.stdin_payload: bytes | None = None

    async def communicate(self, _input):
        self.stdin_payload = _input
        return self._stdout, self._stderr


def _make_client(**overrides) -> ResolvedCLIClient:
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    params = {
        "name": "demo",
        "executable": ["demo-cli"],
        "internal_args": [],
        "config_args": [],
        "env": {},
        "timeout_seconds": 30,
        "parser": "text",
        "roles": {"default": role},
        "output_to_file": None,
        "working_dir": None,
    }
    params.update(overrides)
    return ResolvedCLIClient(**params)


async def _run(monkeypatch, client, process, prompt="do something"):
    async def fake_create_subprocess_exec(*args, **_kwargs):
        process.command = list(args)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    agent = BaseCLIAgent(client)
    return await agent.run(role=client.get_role("default"), prompt=prompt, files=[], images=[])


class TestPromptArgRendering:
    def test_argv_without_a_placeholder_is_rejected_at_construction(self):
        with pytest.raises(ValidationError):
            _make_client(prompt_delivery="argv", prompt_args=["-p"])

    def test_stdin_is_the_default(self):
        client = _make_client()
        assert client.prompt_delivery == "stdin"
        assert client.build_prompt_args("anything") == []

    def test_argv_renders_placeholder(self):
        client = _make_client(prompt_delivery="argv", prompt_args=["-p", "{prompt}"])
        assert client.build_prompt_args("hello") == ["-p", "hello"]

    def test_argv_renders_placeholder_inside_larger_argument(self):
        client = _make_client(prompt_delivery="argv", prompt_args=["--task={prompt}"])
        assert client.build_prompt_args("hello") == ["--task=hello"]


@pytest.mark.asyncio
class TestPromptDeliveryExecution:
    async def test_stdin_delivery_pipes_prompt(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client()
        await _run(monkeypatch, client, process, prompt="piped prompt")
        assert process.stdin_payload == b"piped prompt"
        assert "piped prompt" not in " ".join(process.command)

    async def test_argv_delivery_appends_prompt_and_empties_stdin(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(prompt_delivery="argv", prompt_args=["-p", "{prompt}"])
        await _run(monkeypatch, client, process, prompt="argv prompt")
        assert process.stdin_payload == b""
        assert process.command[-2:] == ["-p", "argv prompt"]

    async def test_argv_prompt_is_redacted_from_sanitized_command(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(prompt_delivery="argv", prompt_args=["-p", "{prompt}"])
        result = await _run(monkeypatch, client, process, prompt="sensitive prompt text")
        assert "sensitive prompt text" not in " ".join(result.sanitized_command)
        assert PROMPT_REDACTION in result.sanitized_command

    async def test_output_to_file_keeps_prompt_redacted(self, monkeypatch):
        """Regression: index-based redaction stripped the output flags instead.

        With output_to_file and argv delivery combined, slicing the last N
        tokens removed the output-capture flags and left the raw prompt in the
        recorded command.
        """

        process = DummyProcess(stdout=b"done")
        client = _make_client(
            prompt_delivery="argv",
            prompt_args=["-p", "{prompt}"],
            output_to_file=OutputCaptureConfig(flag_template="--output {path}"),
        )
        result = await _run(monkeypatch, client, process, prompt="secret prompt")

        joined = " ".join(result.sanitized_command)
        assert "secret prompt" not in joined
        assert PROMPT_REDACTION in result.sanitized_command
        assert "--output" in result.sanitized_command
        # The real command still carries both the output flag and the prompt.
        assert "--output" in process.command
        assert "secret prompt" in process.command

    async def test_prompt_is_the_final_argument(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(
            prompt_delivery="argv",
            prompt_args=["-p", "{prompt}"],
            output_to_file=OutputCaptureConfig(flag_template="--output {path}"),
        )
        await _run(monkeypatch, client, process, prompt="tail prompt")
        assert process.command[-2:] == ["-p", "tail prompt"]

    async def test_stdin_delivery_leaves_command_untouched(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(internal_args=["--flag"])
        result = await _run(monkeypatch, client, process, prompt="piped")
        assert result.sanitized_command == process.command

    async def test_timeout_placeholder_is_rendered(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(internal_args=["--deadline", "{timeout_seconds}s"], timeout_seconds=45)
        await _run(monkeypatch, client, process)
        assert "--deadline" in process.command
        assert "45s" in process.command

    async def test_timeout_placeholder_is_rendered_in_prompt_args(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(
            prompt_delivery="argv",
            prompt_args=["--deadline", "{timeout_seconds}", "-p", "{prompt}"],
            timeout_seconds=90,
        )
        await _run(monkeypatch, client, process, prompt="hi")
        assert "90" in process.command

    async def test_oversized_argv_reports_a_clear_error(self, monkeypatch):
        import errno

        async def raise_e2big(*_args, **_kwargs):
            raise OSError(errno.E2BIG, "Argument list too long")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", raise_e2big)
        monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
        client = _make_client(prompt_delivery="argv", prompt_args=["-p", "{prompt}"])
        agent = BaseCLIAgent(client)

        with pytest.raises(CLIAgentError, match="too large"):
            await agent.run(role=client.get_role("default"), prompt="x" * 100, files=[], images=[])

    async def test_other_launch_errors_are_wrapped(self, monkeypatch):
        async def raise_oserror(*_args, **_kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", raise_oserror)
        monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
        client = _make_client()
        agent = BaseCLIAgent(client)

        with pytest.raises(CLIAgentError, match="Failed to launch"):
            await agent.run(role=client.get_role("default"), prompt="hi", files=[], images=[])

    async def test_arguments_without_placeholders_are_untouched(self, monkeypatch):
        process = DummyProcess(stdout=b"done")
        client = _make_client(internal_args=["--plain", "value"])
        await _run(monkeypatch, client, process)
        assert process.command[1:3] == ["--plain", "value"]
