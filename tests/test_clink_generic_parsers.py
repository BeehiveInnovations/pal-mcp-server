"""Tests for the configuration-driven clink parsers."""

import json

import pytest

from clink.parsers import ParserError, available_parsers, get_parser
from clink.parsers.agy import AgyJSONParser
from clink.parsers.generic import GenericJSONLParser, GenericJSONParser, GenericTextParser, _lookup


class TestDottedLookup:
    def test_resolves_nested_dicts(self):
        assert _lookup({"a": {"b": {"c": 1}}}, "a.b.c") == 1

    def test_indexes_into_lists(self):
        assert _lookup({"items": [{"text": "first"}, {"text": "second"}]}, "items.1.text") == "second"

    def test_missing_segment_returns_none(self):
        assert _lookup({"a": {"b": 1}}, "a.missing.c") is None

    def test_out_of_range_index_returns_none(self):
        assert _lookup({"items": []}, "items.0") is None

    def test_non_numeric_index_on_list_returns_none(self):
        assert _lookup({"items": [1, 2]}, "items.name") is None


class TestGenericJSONParser:
    def test_extracts_default_content_path(self):
        parser = GenericJSONParser()
        result = parser.parse(json.dumps({"response": "hello"}), "")
        assert result.content == "hello"

    def test_honours_configured_content_path(self):
        parser = GenericJSONParser({"content_path": "data.message"})
        result = parser.parse(json.dumps({"data": {"message": "deep"}}), "")
        assert result.content == "deep"

    def test_collects_metadata_paths(self):
        parser = GenericJSONParser({"metadata_paths": {"turns": "num_turns", "tokens": "usage.total"}})
        result = parser.parse(json.dumps({"response": "hi", "num_turns": 2, "usage": {"total": 40}}), "")
        assert result.metadata == {"turns": 2, "tokens": 40}

    def test_skips_leading_progress_output(self):
        parser = GenericJSONParser()
        result = parser.parse('Loading...\n{"response": "done"}', "")
        assert result.content == "done"

    def test_empty_stdout_raises(self):
        with pytest.raises(ParserError, match="empty stdout"):
            GenericJSONParser().parse("   ", "")

    def test_missing_json_object_raises(self):
        with pytest.raises(ParserError, match="no JSON object"):
            GenericJSONParser().parse("not json at all", "")

    def test_malformed_json_raises(self):
        with pytest.raises(ParserError, match="Failed to decode"):
            GenericJSONParser().parse('{"response": ', "")

    def test_missing_content_path_raises(self):
        with pytest.raises(ParserError, match="did not contain text at 'response'"):
            GenericJSONParser().parse(json.dumps({"other": "value"}), "")

    def test_status_mismatch_raises_with_detail(self):
        parser = GenericJSONParser(
            {"status_path": "status", "success_values": ["SUCCESS"], "error_path": "error.message"}
        )
        payload = json.dumps({"status": "FAILED", "error": {"message": "quota exceeded"}, "response": "x"})
        with pytest.raises(ParserError, match="quota exceeded"):
            parser.parse(payload, "")

    def test_status_match_passes(self):
        parser = GenericJSONParser({"status_path": "status", "success_values": ["SUCCESS"]})
        result = parser.parse(json.dumps({"status": "SUCCESS", "response": "ok"}), "")
        assert result.content == "ok"

    def test_brace_in_progress_line_does_not_break_decoding(self):
        parser = GenericJSONParser()
        result = parser.parse('Loading {profile}...\n{"response": "done"}', "")
        assert result.content == "done"

    def test_trailing_output_after_document_is_ignored(self):
        parser = GenericJSONParser()
        result = parser.parse('{"response": "done"}\nShutting down.', "")
        assert result.content == "done"

    def test_success_values_given_as_a_bare_string(self):
        parser = GenericJSONParser({"status_path": "status", "success_values": "SUCCESS"})
        result = parser.parse(json.dumps({"status": "SUCCESS", "response": "ok"}), "")
        assert result.content == "ok"

    def test_success_values_as_string_still_rejects_other_statuses(self):
        parser = GenericJSONParser({"status_path": "status", "success_values": "SUCCESS"})
        with pytest.raises(ParserError, match="status 'FAILED'"):
            parser.parse(json.dumps({"status": "FAILED", "response": "x"}), "")

    def test_last_document_wins_over_leading_progress_json(self):
        """Progress records are JSON too, so first-wins returned the wrong one."""

        stdout = '{"event": "progress"}\n{"response": "final answer"}'
        assert GenericJSONParser().parse(stdout, "").content == "final answer"

    def test_bracketed_log_prefix_is_not_fatal(self):
        """Regression: `[INFO] ...` looks like the start of a JSON array.

        Treating an undecodable line-initial bracket as fatal aborted the parse
        before the real payload on a later line was ever reached.
        """

        stdout = '[INFO] contacting model...\n{"response": "x"}'
        assert GenericJSONParser().parse(stdout, "").content == "x"

    def test_trailing_bracketed_log_after_payload_is_not_fatal(self):
        """Regression: a pending error was checked before a successful decode."""

        stdout = '{"response": "x"}\n[INFO] done'
        assert GenericJSONParser().parse(stdout, "").content == "x"

    def test_leading_bracketed_log_does_not_block_an_indented_payload(self):
        """Regression: the failed log line was treated as a parent to nest under."""

        stdout = '[INFO] starting\n  {"response": "x"}'
        assert GenericJSONParser().parse(stdout, "").content == "x"

    @pytest.mark.parametrize(
        "log_line",
        [
            "[INFO] done",
            "[2026-09-17 10:00:00] done",
            "[1/3] uploading",
            "[ WARNING ] slow",
            "[warn] retrying",
        ],
    )
    def test_common_log_prefix_shapes_are_not_fatal(self, log_line):
        """Timestamps, step counters, and spaced levels all open with a bracket."""

        assert GenericJSONParser().parse(f'{{"response": "x"}}\n{log_line}', "").content == "x"

    def test_truncated_object_after_a_valid_record_is_an_error(self):
        with pytest.raises(ParserError, match="Failed to decode"):
            GenericJSONParser().parse('{"event": "progress"}\n{', "")

    def test_malformed_object_after_a_valid_record_is_an_error(self):
        """An unquoted key must not silently yield the earlier progress record."""

        with pytest.raises(ParserError, match="Failed to decode"):
            GenericJSONParser().parse('{"event": "progress"}\n{response: "x"}', "")

    def test_array_payload_still_decodes(self):
        stdout = 'Loading...\n[\n  {"response": "first"}\n]'
        assert GenericJSONParser({"content_path": "0.response"}).parse(stdout, "").content == "first"

    def test_several_bracketed_log_lines_are_skipped(self):
        stdout = '[INFO] start\n[warn] retry\n{"response": "ok"}'
        assert GenericJSONParser().parse(stdout, "").content == "ok"

    def test_truncated_payload_after_a_valid_record_is_an_error(self):
        """A failure with no later success must not fall back to the earlier document."""

        stdout = '{"event": "progress"}\n{"response": '
        with pytest.raises(ParserError, match="Failed to decode"):
            GenericJSONParser().parse(stdout, "")

    def test_indented_top_level_document_is_accepted(self):
        stdout = 'Loading...\n  {"response": "x"}'
        assert GenericJSONParser().parse(stdout, "").content == "x"

    def test_json_not_at_a_line_start_explains_the_requirement(self):
        with pytest.raises(ParserError, match="beginning of a line"):
            GenericJSONParser().parse('Result: {"response": "x"}', "")

    def test_pretty_printed_payload_after_progress_returns_the_top_level(self):
        """Regression: an indented child outranked the document containing it.

        The whole-text fast path hides this, so it only appears when non-JSON
        progress output precedes a pretty-printed payload.
        """

        stdout = 'Loading...\n{\n  "response": "top",\n  "inner":\n  {"response": "nested"}\n}'
        assert GenericJSONParser().parse(stdout, "").content == "top"

    def test_pretty_printed_array_after_progress_returns_the_array(self):
        stdout = 'Loading...\n[\n  {"response": "first"},\n  {"response": "second"}\n]'
        parser = GenericJSONParser({"content_path": "0.response"})
        assert parser.parse(stdout, "").content == "first"

    def test_status_demanded_but_absent_fails_closed(self):
        parser = GenericJSONParser({"status_path": "status", "success_values": ["SUCCESS"]})
        with pytest.raises(ParserError, match="did not contain a status"):
            parser.parse(json.dumps({"response": "looks fine"}), "")

    def test_status_path_without_success_values_stays_optional(self):
        parser = GenericJSONParser({"status_path": "status"})
        assert parser.parse(json.dumps({"response": "ok"}), "").content == "ok"

    def test_truncated_outer_object_does_not_decode_to_a_nested_child(self):
        """Regression: brace scanning returned the nested object as success.

        A truncated error payload would surface its partial nested text as a
        successful response, dropping the error status entirely.
        """

        truncated = '{"status": "ERROR", "nested": {"response": "partial"}'
        with pytest.raises(ParserError, match="Failed to decode"):
            GenericJSONParser().parse(truncated, "")

    def test_non_text_content_path_raises(self):
        parser = GenericJSONParser({"content_path": "items"})
        payload = json.dumps({"items": [{"text": "hi"}]})
        with pytest.raises(ParserError, match="not text"):
            parser.parse(payload, "")

    def test_numeric_content_is_accepted(self):
        parser = GenericJSONParser({"content_path": "answer"})
        assert parser.parse(json.dumps({"answer": 4}), "").content == "4"

    def test_missing_metadata_paths_are_omitted(self):
        parser = GenericJSONParser({"metadata_paths": {"tokens": "usage.total"}})
        result = parser.parse(json.dumps({"response": "hi"}), "")
        assert "tokens" not in result.metadata

    def test_invalid_metadata_paths_option_raises(self):
        parser = GenericJSONParser({"metadata_paths": ["not", "a", "dict"]})
        with pytest.raises(ParserError, match="metadata_paths must be an object"):
            parser.parse(json.dumps({"response": "hi"}), "")


class TestGenericJSONLParser:
    def test_selects_last_matching_record(self):
        parser = GenericJSONLParser({"match": {"type": "message"}, "content_path": "text"})
        stdout = "\n".join(
            [
                json.dumps({"type": "start"}),
                json.dumps({"type": "message", "text": "first"}),
                json.dumps({"type": "message", "text": "last"}),
            ]
        )
        assert parser.parse(stdout, "").content == "last"

    def test_ignores_unparseable_lines(self):
        parser = GenericJSONLParser({"match": {"type": "message"}, "content_path": "text"})
        stdout = "garbage\n" + json.dumps({"type": "message", "text": "ok"})
        assert parser.parse(stdout, "").content == "ok"

    def test_supports_nested_match_paths(self):
        parser = GenericJSONLParser({"match": {"item.type": "answer"}, "content_path": "item.text"})
        stdout = json.dumps({"item": {"type": "answer", "text": "nested"}})
        assert parser.parse(stdout, "").content == "nested"

    def test_include_events_option(self):
        parser = GenericJSONLParser({"match": {"type": "m"}, "content_path": "text", "include_events": True})
        stdout = json.dumps({"type": "m", "text": "hi"})
        assert parser.parse(stdout, "").metadata["events"] == [{"type": "m", "text": "hi"}]

    def test_missing_path_does_not_match_literal_none(self):
        parser = GenericJSONLParser({"match": {"type": "None"}, "content_path": "text"})
        with pytest.raises(ParserError, match="no record matching"):
            parser.parse(json.dumps({"other": "value", "text": "hi"}), "")

    def test_boolean_written_as_a_string_in_config_matches(self):
        parser = GenericJSONLParser({"match": {"is_final": "true"}, "content_path": "text"})
        stdout = json.dumps({"is_final": True, "text": "done"})
        assert parser.parse(stdout, "").content == "done"

    def test_retained_events_keep_the_tail_and_report_truncation(self):
        from clink.parsers.generic import MAX_RETAINED_EVENTS

        parser = GenericJSONLParser({"match": {"type": "m"}, "content_path": "text", "include_events": True})
        total = MAX_RETAINED_EVENTS + 50
        stdout = "\n".join(json.dumps({"type": "m", "text": str(i)}) for i in range(total))
        result = parser.parse(stdout, "")

        assert len(result.metadata["events"]) == MAX_RETAINED_EVENTS
        assert result.metadata["events_truncated"] == 50
        assert result.metadata["events"][-1]["text"] == str(total - 1)

    def test_empty_match_is_rejected(self):
        parser = GenericJSONLParser({"match": {}, "content_path": "text"})
        with pytest.raises(ParserError, match="at least one field"):
            parser.parse(json.dumps({"text": "hi"}), "")

    def test_events_are_not_retained_unless_requested(self):
        parser = GenericJSONLParser({"match": {"type": "m"}, "content_path": "text"})
        result = parser.parse(json.dumps({"type": "m", "text": "hi"}), "")
        assert "events" not in result.metadata

    def test_status_is_checked_on_the_selected_record(self):
        parser = GenericJSONLParser(
            {
                "match": {"type": "result"},
                "content_path": "text",
                "status_path": "status",
                "success_values": ["ok"],
            }
        )
        stdout = json.dumps({"type": "result", "status": "failed", "text": "partial"})
        with pytest.raises(ParserError, match="status 'failed'"):
            parser.parse(stdout, "")

    def test_no_match_raises(self):
        parser = GenericJSONLParser({"match": {"type": "message"}})
        with pytest.raises(ParserError, match="no record matching"):
            parser.parse(json.dumps({"type": "other"}), "")

    def test_empty_stdout_raises(self):
        with pytest.raises(ParserError, match="empty stdout"):
            GenericJSONLParser({"match": {"type": "m"}}).parse("", "")

    def test_invalid_match_option_raises(self):
        with pytest.raises(ParserError, match="match must be an object"):
            GenericJSONLParser({"match": "nope"}).parse(json.dumps({"a": 1}), "")


class TestGenericTextParser:
    def test_returns_stdout_verbatim(self):
        assert GenericTextParser().parse("  plain answer  ", "").content == "plain answer"

    def test_empty_stdout_raises(self):
        with pytest.raises(ParserError, match="empty stdout"):
            GenericTextParser().parse("", "")


class TestAgyParser:
    def test_parses_agy_payload(self):
        payload = json.dumps(
            {
                "conversation_id": "abc-123",
                "status": "SUCCESS",
                "response": "PONG\n",
                "duration_seconds": 3.5,
                "num_turns": 1,
                "usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
            }
        )
        result = AgyJSONParser().parse(payload, "")
        assert result.content == "PONG"
        assert result.metadata["conversation_id"] == "abc-123"
        assert result.metadata["total_tokens"] == 12
        assert result.metadata["num_turns"] == 1

    def test_non_success_status_raises(self):
        payload = json.dumps({"status": "ERROR", "response": "partial"})
        with pytest.raises(ParserError, match="status 'ERROR'"):
            AgyJSONParser().parse(payload, "")

    def test_metadata_paths_merge_rather_than_replace(self):
        """Adding one field must not discard the bundled Antigravity paths."""

        parser = AgyJSONParser({"metadata_paths": {"extra": "usage.input_tokens"}})
        payload = json.dumps(
            {"status": "SUCCESS", "response": "hi", "conversation_id": "c1", "usage": {"input_tokens": 5}}
        )
        metadata = parser.parse(payload, "").metadata
        assert metadata["extra"] == 5
        assert metadata["conversation_id"] == "c1"

    def test_error_detail_is_surfaced(self):
        payload = json.dumps({"status": "ERROR", "error": "quota exhausted", "response": "x"})
        with pytest.raises(ParserError, match="quota exhausted"):
            AgyJSONParser().parse(payload, "")

    def test_options_override_defaults(self):
        parser = AgyJSONParser({"content_path": "custom"})
        result = parser.parse(json.dumps({"status": "SUCCESS", "custom": "overridden"}), "")
        assert result.content == "overridden"


class TestParserRegistry:
    def test_generic_parsers_are_registered(self):
        names = available_parsers()
        for expected in ("json", "jsonl", "text", "agy_json"):
            assert expected in names

    def test_get_parser_passes_options_to_configurable_parsers(self):
        parser = get_parser("json", {"content_path": "a.b"})
        assert parser.parse(json.dumps({"a": {"b": "value"}}), "").content == "value"

    def test_get_parser_ignores_options_for_fixed_parsers(self):
        parser = get_parser("claude_json", {"content_path": "ignored"})
        assert parser.name == "claude_json"

    def test_unknown_parser_lists_available_names(self):
        with pytest.raises(ParserError, match="Available parsers"):
            get_parser("does_not_exist")
