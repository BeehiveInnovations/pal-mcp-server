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
        response_text = response.strip() if isinstance(response, str) else ""

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

        if response_text:
            if stderr and stderr.strip():
                metadata["stderr"] = stderr.strip()
            return ParsedCLIResponse(content=response_text, metadata=metadata)

        fallback_message, extra_metadata = self._build_fallback_message(payload, stderr)
        if fallback_message:
            metadata.update(extra_metadata)
            if stderr and stderr.strip():
                metadata["stderr"] = stderr.strip()
            return ParsedCLIResponse(content=fallback_message, metadata=metadata)

        raise ParserError("Gemini CLI response is missing a textual 'response' field")

    def _build_fallback_message(self, payload: dict[str, Any], stderr: str) -> tuple[str | None, dict[str, Any]]:
        """Derive a human friendly message when Gemini returns empty content."""

        stderr_text = stderr.strip() if stderr else ""
        stderr_lower = stderr_text.lower()
        extra_metadata: dict[str, Any] = {"empty_response": True}

        if "429" in stderr_lower or "rate limit" in stderr_lower:
            extra_metadata["rate_limit_status"] = 429
            message = (
                "Gemini request returned no content because the API reported a 429 rate limit. "
                "Retry after reducing the request size or waiting for quota to replenish."
            )
            return message, extra_metadata

        stats = payload.get("stats")
        if isinstance(stats, dict):
            models = stats.get("models")
            if isinstance(models, dict) and models:
                first_model = next(iter(models.values()))
                if isinstance(first_model, dict):
                    api_stats = first_model.get("api")
                    if isinstance(api_stats, dict):
                        total_errors = api_stats.get("totalErrors")
                        total_requests = api_stats.get("totalRequests")
                        if isinstance(total_errors, int) and total_errors > 0:
                            extra_metadata["api_total_errors"] = total_errors
                            if isinstance(total_requests, int):
                                extra_metadata["api_total_requests"] = total_requests
                            message = (
                                "Gemini CLI returned no textual output. The API reported "
                                f"{total_errors} error(s); see stderr for details."
                            )
                            return message, extra_metadata

        if stderr_text:
            message = "Gemini CLI returned no textual output. Raw stderr was preserved for troubleshooting."
            return message, extra_metadata

        return None, extra_metadata
