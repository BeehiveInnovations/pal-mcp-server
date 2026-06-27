"""Integration tests for codex agent PATH resolution."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path

import pytest

from clink.agents.codex import CodexAgent
from clink.models import ResolvedCLIClient, ResolvedCLIRole


class DummyProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, _input):
        return self._stdout, self._stderr


@pytest.fixture()
def codex_agent():
    prompt_path = Path("systemprompts/clink/default.txt").resolve()
    role = ResolvedCLIRole(name="default", prompt_path=prompt_path, role_args=[])
    client = ResolvedCLIClient(
        name="codex",
        executable=["codex"],
        internal_args=["exec"],
        config_args=["--json", "--dangerously-bypass-approvals-and-sandbox"],
        env={},
        timeout_seconds=30,
        parser="codex_jsonl",
        roles={"default": role},
        output_to_file=None,
        working_dir=None,
    )
    return CodexAgent(client), role


@pytest.mark.asyncio
async def test_codex_agent_resolves_nvm_installed_binary(monkeypatch, codex_agent, tmp_path):
    agent, role = codex_agent
    nvm_bin = tmp_path / ".nvm" / "versions" / "node" / "v22.0.0" / "bin"
    nvm_bin.mkdir(parents=True)
    codex_path = nvm_bin / "codex"
    codex_path.write_text("#!/bin/sh\necho codex\n")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("NVM_DIR", str(tmp_path / ".nvm"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", str(tmp_path))

    captured: dict[str, object] = {}

    async def fake_create_subprocess_exec(*args, **_kwargs):
        captured["args"] = args
        captured["env"] = _kwargs.get("env")
        return DummyProcess(
            stdout=b'{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}', returncode=0
        )

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    await agent.run(role=role, prompt="ping", files=[], images=[])

    assert captured["args"][0] == str(codex_path)
    env = captured["env"]
    assert env is not None
    assert str(nvm_bin) in env["PATH"].split(os.pathsep)
