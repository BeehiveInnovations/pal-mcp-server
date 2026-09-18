"""Configuration-driven parsers for CLIs that need no bespoke Python.

These parsers let a new CLI client be added with a JSON manifest alone. Point
``parser`` at one of the names below and describe the output shape through
``parser_options``:

``json``
    stdout is a single JSON object. ``content_path`` selects the response text.

``jsonl``
    stdout is newline-delimited JSON. The last record matching ``match`` wins.

``text``
    stdout is the response, with surrounding whitespace trimmed.
"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

from .base import BaseParser, ParsedCLIResponse, ParserError


def _lookup(payload: Any, path: str) -> Any:
    """Resolve a dotted path against nested dicts and lists.

    Numeric segments index into lists, so ``items.0.text`` is valid. Returns
    ``None`` when any segment is missing rather than raising, so an optional
    metadata path can simply be absent from a given response.
    """

    current = payload
    for segment in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            try:
                index = int(segment)
            except ValueError:
                return None
            if index >= len(current) or index < -len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current


MAX_RETAINED_EVENTS = 1000


def _coerce_content(value: Any, content_path: str) -> str:
    """Validate that a content path resolved to text.

    A path landing one level shallow yields a dict or list, whose ``repr``
    would otherwise be handed to the model as the CLI's answer.
    """

    if value is None:
        raise ParserError(f"CLI response did not contain text at '{content_path}'")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ParserError(
            f"CLI response at '{content_path}' is {type(value).__name__}, not text. "
            f"Check the content_path in parser_options."
        )
    text = str(value).strip()
    if not text:
        raise ParserError(f"CLI response did not contain text at '{content_path}'")
    return text


def _values_match(actual: Any, expected: Any) -> bool:
    """Compare a looked-up value with a configured one.

    A missing path yields ``None``, which must never match the literal string
    "None" coming from configuration, so absence is checked before coercion.
    """

    if actual is None:
        return expected is None
    if isinstance(actual, bool) or isinstance(expected, bool):
        return str(actual).lower() == str(expected).lower()
    return str(actual) == str(expected)


def _extract_json_document(text: str) -> Any:
    """Decode the JSON document in ``text``.

    CLIs interleave progress output with their JSON result, so the *last*
    top-level document wins: a CLI emitting {"event": "progress"} before its
    real payload would otherwise have the progress record returned as the
    answer.

    A line beginning with a bracket is only a candidate, not a promise, and the
    two brackets are treated differently because they carry different odds. A
    line opening with ``[`` is far more likely a log prefix (``[INFO] ...``,
    ``[2026-09-17 10:00:00] ...``, ``[1/3] ...``) than an array payload, so one
    that fails to decode is skipped in silence. A line opening with ``{`` is a
    claim to be the object payload every supported CLI emits, so a failure
    there is fatal unless a later candidate decodes successfully. That is how a
    truncated or malformed final payload is caught instead of silently
    returning an earlier progress record.

    Two guards keep a nested object from being mistaken for the document that
    contains it: a candidate inside an already-decoded span is skipped, and so
    is one indented more deeply than a candidate that just failed, which covers
    a truncated parent whose span never advanced.
    """

    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    except RecursionError as exc:
        raise ParserError("CLI JSON output is nested too deeply to decode") from exc

    decoder = json.JSONDecoder()
    offset = 0
    selected: Any = None
    found = False
    consumed_until = 0
    failed_indent: int | None = None
    pending_error: json.JSONDecodeError | None = None

    for line in text.splitlines(keepends=True):
        candidate = line.strip()
        indent = len(line) - len(line.lstrip())
        position = offset + indent
        offset += len(line)

        if not candidate or candidate[0] not in "{[":
            continue
        if position < consumed_until:
            continue
        if failed_indent is not None and indent > failed_indent:
            continue

        try:
            selected, consumed_until = decoder.raw_decode(text, position)
        except json.JSONDecodeError as exc:
            if candidate[0] == "[":
                # Almost certainly a log prefix rather than an array payload.
                # Not recorded as an error, and not treated as a parent whose
                # nested candidates should be skipped.
                continue
            pending_error = exc
            failed_indent = indent
            continue
        except RecursionError as exc:
            raise ParserError("CLI JSON output is nested too deeply to decode") from exc

        found = True
        pending_error = None
        failed_indent = None

    if pending_error is not None:
        raise ParserError(f"Failed to decode CLI JSON output: {pending_error}") from pending_error
    if found:
        return selected
    if "{" in text or "[" in text:
        raise ParserError(
            "CLI output contained no decodable JSON document. The json parser reads a document "
            "that starts at the beginning of a line; wrap or strip any prefix the CLI adds."
        )
    raise ParserError("CLI output contained no JSON object")


class ConfigurableParser(BaseParser):
    """Base class for parsers whose behaviour comes from parser_options."""

    def __init__(self, options: dict[str, Any] | None = None):
        self.options = dict(options or {})

    def _option(self, key: str, default: Any = None) -> Any:
        return self.options.get(key, default)

    def _build_metadata(self, payload: Any) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        metadata_paths = self._option("metadata_paths") or {}
        if not isinstance(metadata_paths, dict):
            raise ParserError("parser_options.metadata_paths must be an object mapping names to dotted paths")
        for key, path in metadata_paths.items():
            value = _lookup(payload, str(path))
            if value is not None:
                metadata[key] = value
        return metadata

    def _check_status(self, payload: Any) -> None:
        status_path = self._option("status_path")
        if not status_path:
            return
        status = _lookup(payload, str(status_path))
        success_values = self._option("success_values")
        if status is None:
            if success_values is not None:
                # Failing open here would report a truncated payload, or an
                # upstream schema change, as a successful answer.
                raise ParserError(f"CLI response did not contain a status at '{status_path}'")
            return
        if success_values is None:
            return
        if not isinstance(success_values, (list, tuple, set)):
            # A bare string would be iterated one character at a time, and a
            # number is not iterable at all.
            success_values = [success_values]
        allowed = {str(value).lower() for value in success_values}
        if str(status).lower() not in allowed:
            detail = ""
            error_path = self._option("error_path")
            if error_path:
                message = _lookup(payload, str(error_path))
                if message:
                    detail = f": {message}"
            raise ParserError(f"CLI reported status '{status}'{detail}")


class GenericJSONParser(ConfigurableParser):
    """Parse a single JSON object emitted on stdout."""

    name = "json"
    default_content_path = "response"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        text = stdout.strip()
        if not text:
            raise ParserError("CLI returned empty stdout while JSON output was expected")

        payload = _extract_json_document(text)

        self._check_status(payload)

        content_path = str(self._option("content_path", self.default_content_path))
        content = _coerce_content(_lookup(payload, content_path), content_path)

        return ParsedCLIResponse(content=content, metadata=self._build_metadata(payload))


class GenericJSONLParser(ConfigurableParser):
    """Parse newline-delimited JSON, selecting the last matching record."""

    name = "jsonl"
    default_content_path = "text"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        if not stdout.strip():
            raise ParserError("CLI returned empty stdout while JSONL output was expected")

        match = self._option("match")
        if match is None:
            match = {}
        if not isinstance(match, dict):
            raise ParserError("parser_options.match must be an object mapping dotted paths to expected values")
        if not match:
            # An empty match is vacuously true and would silently select the last
            # parseable record, which is usually a usage or completion summary.
            raise ParserError("parser_options.match must name at least one field for the jsonl parser")

        content_path = str(self._option("content_path", self.default_content_path))
        include_events = bool(self._option("include_events", False))
        events: deque[Any] = deque(maxlen=MAX_RETAINED_EVENTS)
        event_count = 0
        selected: Any = None

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if include_events:
                events.append(event)
                event_count += 1
            if all(_values_match(_lookup(event, key), value) for key, value in match.items()):
                selected = event

        if selected is None:
            raise ParserError("CLI output contained no record matching parser_options.match")

        self._check_status(selected)

        content = _coerce_content(_lookup(selected, content_path), content_path)

        metadata = self._build_metadata(selected)
        if include_events:
            # A deque bounded at collection time keeps the tail, which is what
            # matters when debugging a long run, without ever holding the whole
            # stream resident.
            if event_count > len(events):
                metadata["events_truncated"] = event_count - len(events)
            metadata["events"] = list(events)
        return ParsedCLIResponse(content=content, metadata=metadata)


class GenericTextParser(ConfigurableParser):
    """Return stdout as the response, with surrounding whitespace trimmed."""

    name = "text"

    def parse(self, stdout: str, stderr: str) -> ParsedCLIResponse:
        content = stdout.strip()
        if not content:
            raise ParserError("CLI returned empty stdout")
        return ParsedCLIResponse(content=content, metadata={})
