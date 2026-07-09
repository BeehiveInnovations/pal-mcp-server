"""Grok Build-specific CLI agent hooks."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from clink.models import ResolvedCLIRole
from clink.parsers.base import ParserError

from .base import AgentOutput, BaseCLIAgent


class GrokAgent(BaseCLIAgent):
    """Grok Build CLI agent.

    Grok headless mode does not read the prompt from stdin. The agent writes the
    prepared prompt to a temporary file and invokes ``--prompt-file``.
    """

    def __init__(self, client):
        super().__init__(client)
        self._pending_prompt_file: str | None = None

    async def run(
        self,
        *,
        role: ResolvedCLIRole,
        prompt: str,
        system_prompt: str | None = None,
        files: Sequence[str],
        images: Sequence[str],
    ) -> AgentOutput:
        fd, tmp_path = tempfile.mkstemp(prefix="clink-grok-", suffix=".txt")
        os.close(fd)
        prompt_path = Path(tmp_path)
        self._pending_prompt_file = str(prompt_path)
        try:
            prompt_path.write_text(prompt, encoding="utf-8")
            # Stdin is unused by Grok headless mode; pass empty payload.
            return await super().run(
                role=role,
                prompt="",
                system_prompt=system_prompt,
                files=files,
                images=images,
            )
        finally:
            self._pending_prompt_file = None
            try:
                prompt_path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - best effort cleanup
                pass

    def _build_command(self, *, role: ResolvedCLIRole, system_prompt: str | None) -> list[str]:
        command = list(self.client.executable)
        command.extend(self.client.internal_args)
        command.extend(self.client.config_args)

        if self._pending_prompt_file:
            command.extend(["--prompt-file", self._pending_prompt_file])

        command.extend(role.role_args)
        return command

    def _recover_from_error(
        self,
        *,
        returncode: int,
        stdout: str,
        stderr: str,
        sanitized_command: list[str],
        duration_seconds: float,
        output_file_content: str | None,
    ) -> AgentOutput | None:
        try:
            parsed = self._parser.parse(stdout, stderr)
        except ParserError:
            return None

        return AgentOutput(
            parsed=parsed,
            sanitized_command=sanitized_command,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration_seconds,
            parser_name=self._parser.name,
            output_file_content=output_file_content,
        )
