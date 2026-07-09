"""OpenCode-specific CLI agent hooks."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from pathlib import Path

from clink.models import ResolvedCLIRole
from clink.parsers.base import ParserError

from .base import AgentOutput, BaseCLIAgent

# Keep well under common ARG_MAX limits while still allowing modest prompts inline.
_MAX_INLINE_PROMPT_CHARS = 100_000


class OpenCodeAgent(BaseCLIAgent):
    """OpenCode CLI agent.

    OpenCode accepts the user message as a positional argument to ``opencode run``.
    Large prompts are written to a temporary file and attached via ``--file`` to
    avoid command-line length limits.
    """

    def __init__(self, client):
        super().__init__(client)
        self._pending_message: str | None = None
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
        prompt_path: Path | None = None
        self._pending_message = None
        self._pending_prompt_file = None

        try:
            if len(prompt) <= _MAX_INLINE_PROMPT_CHARS:
                self._pending_message = prompt
            else:
                fd, tmp_path = tempfile.mkstemp(prefix="clink-opencode-", suffix=".md")
                os.close(fd)
                prompt_path = Path(tmp_path)
                prompt_path.write_text(prompt, encoding="utf-8")
                self._pending_prompt_file = str(prompt_path)
                self._pending_message = (
                    "Read and fully follow the instructions in the attached file. "
                    "Return only your final answer to those instructions."
                )

            # Message is supplied as a CLI argument; stdin is unused.
            return await super().run(
                role=role,
                prompt="",
                system_prompt=system_prompt,
                files=files,
                images=images,
            )
        finally:
            self._pending_message = None
            self._pending_prompt_file = None
            if prompt_path is not None:
                try:
                    prompt_path.unlink(missing_ok=True)
                except OSError:  # pragma: no cover - best effort cleanup
                    pass

    def _build_command(self, *, role: ResolvedCLIRole, system_prompt: str | None) -> list[str]:
        command = list(self.client.executable)
        command.extend(self.client.internal_args)
        command.extend(self.client.config_args)

        if self._pending_prompt_file:
            command.extend(["--file", self._pending_prompt_file])

        command.extend(role.role_args)

        if self._pending_message is not None:
            command.append(self._pending_message)

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
