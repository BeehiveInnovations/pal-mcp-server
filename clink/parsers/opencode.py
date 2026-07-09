"""Parser for OpenCode CLI JSONL output."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


class OpenCodeJSONLParser(BaseParser):
    """Parse stdout emitted by `opencode run --format json`."""

    name = "opencode_jsonl"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        lines = [line.strip() for line in (stdout or "").splitlines() if line.strip()]
        events: list[dict[str, Any]] = []
        text_parts: list[str] = []
        errors: list[str] = []
        session_id: str | None = None
        usage: dict[str, Any] | None = None
        cost: float | None = None

        for line in lines:
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            events.append(event)
            event_type = event.get("type")
            event_session = event.get("sessionID")
            if isinstance(event_session, str) and event_session:
                session_id = event_session

            if event_type == "text":
                part = event.get("part") or {}
                text = part.get("text") if isinstance(part, dict) else None
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
            elif event_type == "error":
                error_block = event.get("error")
                message: str | None = None
                if isinstance(error_block, dict):
                    data = error_block.get("data")
                    if isinstance(data, dict):
                        data_message = data.get("message")
                        if isinstance(data_message, str) and data_message.strip():
                            message = data_message.strip()
                    if message is None:
                        name = error_block.get("name")
                        if isinstance(name, str) and name.strip():
                            message = name.strip()
                if message is None:
                    fallback = event.get("message")
                    if isinstance(fallback, str) and fallback.strip():
                        message = fallback.strip()
                if message:
                    errors.append(message)
            elif event_type == "step_finish":
                part = event.get("part") if isinstance(event.get("part"), dict) else {}
                reason = part.get("reason")
                # Prefer final-step token/cost metadata when available.
                if reason in (None, "stop"):
                    tokens = part.get("tokens")
                    if isinstance(tokens, dict):
                        usage = tokens
                    part_cost = part.get("cost")
                    if isinstance(part_cost, (int, float)):
                        cost = float(part_cost)

        if not text_parts and errors:
            text_parts.extend(errors)

        if not text_parts:
            raise ParserError("OpenCode CLI JSONL output did not include a text event")

        content = "\n\n".join(text_parts).strip()
        metadata: dict[str, Any] = {"events": events}
        if errors:
            metadata["errors"] = errors
        if session_id:
            metadata["session_id"] = session_id
            metadata["sessionID"] = session_id
        if usage:
            metadata["usage"] = usage
            metadata["token_usage"] = usage
        if cost is not None:
            metadata["cost"] = cost
        if stderr and stderr.strip():
            metadata["stderr"] = stderr.strip()

        return ParsedCLIResponse(content=content, metadata=metadata)
