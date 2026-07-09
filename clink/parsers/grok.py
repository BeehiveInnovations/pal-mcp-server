"""Parser for Grok Build CLI JSON output."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


class GrokJSONParser(BaseParser):
    """Parse stdout produced by `grok -p ... --output-format json`."""

    name = "grok_json"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        if not stdout.strip():
            raise ParserError("Grok CLI returned empty stdout while JSON output was expected")

        try:
            payload: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ParserError(f"Failed to decode Grok CLI JSON output: {exc}") from exc

        if not isinstance(payload, dict):
            raise ParserError("Grok CLI returned unexpected JSON payload")

        metadata: dict[str, Any] = {"raw": payload}

        if payload.get("type") == "error":
            message = payload.get("message")
            content = message.strip() if isinstance(message, str) and message.strip() else "Grok CLI reported an error"
            metadata["is_error"] = True
            if stderr and stderr.strip():
                metadata["stderr"] = stderr.strip()
            return ParsedCLIResponse(content=content, metadata=metadata)

        text = payload.get("text")
        content = text.strip() if isinstance(text, str) else ""

        for key in ("sessionId", "requestId", "stopReason", "thought"):
            value = payload.get(key)
            if value is not None:
                metadata[key] = value
        if isinstance(payload.get("sessionId"), str) and payload["sessionId"]:
            metadata["session_id"] = payload["sessionId"]

        if content:
            if stderr and stderr.strip():
                metadata["stderr"] = stderr.strip()
            return ParsedCLIResponse(content=content, metadata=metadata)

        stderr_text = stderr.strip() if stderr else ""
        if stderr_text:
            metadata["stderr"] = stderr_text
            return ParsedCLIResponse(
                content="Grok CLI returned no textual result. Raw stderr was preserved for troubleshooting.",
                metadata=metadata,
            )

        raise ParserError("Grok CLI response did not contain a textual 'text' field")
