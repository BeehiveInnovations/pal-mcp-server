"""Parser for grok CLI JSON output."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


class GrokJSONParser(BaseParser):
    """Parse stdout produced by `grok --output-format json`.

    grok emits a single JSON object on stdout::

        {"text":"...","stopReason":"EndTurn","sessionId":"...","requestId":"..."}

    Log or MCP noise may appear on stderr — it is ignored.  If leading junk
    appears before the opening brace on stdout (e.g. progress lines) we slice
    from the first ``{``.
    """

    name = "grok_json"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        if not stdout.strip():
            raise ParserError("grok CLI returned empty stdout while JSON output was expected")

        # Find the first decodable JSON object on stdout. We try every "{" rather than
        # only the first, because a leading log/progress line may itself contain "{"
        # (e.g. "Connecting to {endpoint}"); raw_decode also ignores any output that
        # trails the object.
        decoder = json.JSONDecoder()
        payload: dict[str, Any] | None = None
        last_error: json.JSONDecodeError | None = None
        index = stdout.find("{")
        while index != -1:
            try:
                candidate, _ = decoder.raw_decode(stdout[index:])
            except json.JSONDecodeError as exc:
                last_error = exc
            else:
                if isinstance(candidate, dict):
                    payload = candidate
                    break
            index = stdout.find("{", index + 1)

        if payload is None:
            if last_error is not None:
                raise ParserError(f"Failed to decode grok CLI JSON output: {last_error}") from last_error
            raise ParserError(f"grok CLI stdout contains no JSON object: {stdout[:200]!r}")

        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ParserError("grok CLI JSON response is missing a non-empty 'text' field")

        metadata: dict[str, Any] = {"raw": payload}
        if payload.get("stopReason"):
            metadata["stop_reason"] = payload["stopReason"]
        if payload.get("sessionId"):
            metadata["session_id"] = payload["sessionId"]
        if payload.get("requestId"):
            metadata["request_id"] = payload["requestId"]
        if stderr and stderr.strip():
            metadata["stderr"] = stderr.strip()

        return ParsedCLIResponse(content=text.strip(), metadata=metadata)
