"""Parser for Gemini CLI JSON output."""

from __future__ import annotations

import json
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


class GeminiJSONParser(BaseParser):
    """Parse stdout produced by `gemini -o json`."""

    name = "gemini_json"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        if not stdout.strip():
            raise ParserError("Gemini CLI returned empty stdout while JSON output was expected")

        try:
            payload: dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive logging
            raise ParserError(f"Failed to decode Gemini CLI JSON output: {exc}") from exc

        response = payload.get("response")
        if not isinstance(response, str) or not response.strip():
            raise ParserError("Gemini CLI response is missing a textual 'response' field")

        metadata: dict[str, Any] = {"raw": payload}

        stats = payload.get("stats")
        if isinstance(stats, dict):
            metadata["stats"] = stats
            models = stats.get("models")
            if isinstance(models, dict) and models:
                model_name = next(iter(models.keys()))
                metadata["model_used"] = model_name
                model_stats = models.get(model_name) or {}
                tokens = model_stats.get("tokens")
                if isinstance(tokens, dict):
                    metadata["token_usage"] = tokens
                api_stats = model_stats.get("api")
                if isinstance(api_stats, dict):
                    metadata["latency_ms"] = api_stats.get("totalLatencyMs")

        if stderr and stderr.strip():
            metadata["stderr"] = stderr.strip()

        return ParsedCLIResponse(content=response.strip(), metadata=metadata)
