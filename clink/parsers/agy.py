"""Parser for Antigravity CLI (`agy`) JSON output."""

from __future__ import annotations

from typing import Any

from .generic import GenericJSONParser

# `agy --output-format json` emits a single flat object:
#   {"conversation_id": ..., "status": "SUCCESS", "response": "...",
#    "duration_seconds": 1.2, "num_turns": 1, "usage": {...}}
AGY_PARSER_DEFAULTS: dict[str, Any] = {
    "content_path": "response",
    "status_path": "status",
    "success_values": ["SUCCESS"],
    "error_path": "error",
    "metadata_paths": {
        "conversation_id": "conversation_id",
        "status": "status",
        "num_turns": "num_turns",
        "duration_seconds": "duration_seconds",
        "total_tokens": "usage.total_tokens",
        "input_tokens": "usage.input_tokens",
        "output_tokens": "usage.output_tokens",
    },
}


class AgyJSONParser(GenericJSONParser):
    """Parse stdout produced by `agy --output-format json`.

    This is the generic JSON parser with the Antigravity response shape applied
    as defaults, so callers get useful errors without repeating the paths in
    every configuration file.
    """

    name = "agy_json"

    def __init__(self, options: dict[str, Any] | None = None):
        merged = dict(AGY_PARSER_DEFAULTS)
        overrides = dict(options or {})
        # metadata_paths merges key by key: supplying one extra field should add
        # to the defaults rather than silently replacing all of them.
        extra_metadata = overrides.pop("metadata_paths", None)
        if extra_metadata:
            merged["metadata_paths"] = {**AGY_PARSER_DEFAULTS["metadata_paths"], **extra_metadata}
        merged.update(overrides)
        super().__init__(merged)
