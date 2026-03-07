"""Parser for GitHub Copilot CLI JSONL output."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


class CopilotJSONLParser(BaseParser):
    """Parse JSONL stdout emitted by `copilot -p ... --output-format json`."""

    name = "copilot_jsonl"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
        events: list[dict[str, Any]] = []
        assistant_messages: list[str] = []
        result_event: dict[str, Any] | None = None

        for line in lines:
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            events.append(event)
            event_type = event.get("type")

            if event_type == "assistant.message":
                data = event.get("data") or {}
                content = data.get("content")
                if isinstance(content, str) and content.strip():
                    assistant_messages.append(content.strip())

            elif event_type == "result":
                result_event = event

        if not assistant_messages:
            raise ParserError("Copilot CLI JSONL output did not include an assistant.message event")

        content = "\n\n".join(assistant_messages).strip()
        metadata: dict[str, Any] = {"events": events}

        if result_event:
            metadata["result"] = result_event
            session_id = result_event.get("sessionId")
            if isinstance(session_id, str):
                metadata["session_id"] = session_id
            usage = result_event.get("usage")
            if isinstance(usage, dict):
                metadata["usage"] = usage

        if stderr and stderr.strip():
            metadata["stderr"] = stderr.strip()

        return ParsedCLIResponse(content=content, metadata=metadata)
