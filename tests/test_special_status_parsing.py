"""
Tests for special status parsing in the base tool
"""

from pydantic import BaseModel

from tools.base import BaseTool


class MockRequest(BaseModel):
    """Mock request for testing"""

    test_field: str = "test"


class TestTool(BaseTool):
    """Minimal test tool implementation"""

    def get_name(self) -> str:
        return "test_tool"

    def get_description(self) -> str:
        return "Test tool for special status parsing"

    def get_input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def get_system_prompt(self) -> str:
        return "Test prompt"

    def get_request_model(self):
        return MockRequest

    async def prepare_prompt(self, request) -> str:
        return "test prompt"


class TestSpecialStatusParsing:
    """Test special status parsing functionality"""

    def setup_method(self):
        """Setup test tool and request"""
        self.tool = TestTool()
        self.request = MockRequest()

    def test_full_codereview_required_parsing(self):
        """Test parsing of full_codereview_required status"""
        response_json = '{"status": "full_codereview_required", "reason": "Codebase too large for quick review"}'

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "full_codereview_required"
        assert result.content_type == "json"
        assert "reason" in result.content

    def test_full_codereview_required_without_reason(self):
        """Test parsing of full_codereview_required without optional reason"""
        response_json = '{"status": "full_codereview_required"}'

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "full_codereview_required"
        assert result.content_type == "json"

    def test_test_sample_needed_parsing(self):
        """Test parsing of test_sample_needed status"""
        response_json = '{"status": "test_sample_needed", "reason": "Cannot determine test framework"}'

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "test_sample_needed"
        assert result.content_type == "json"
        assert "reason" in result.content

    def test_more_tests_required_parsing(self):
        """Test parsing of more_tests_required status"""
        response_json = (
            '{"status": "more_tests_required", "pending_tests": "test_auth (test_auth.py), test_login (test_user.py)"}'
        )

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "more_tests_required"
        assert result.content_type == "json"
        assert "pending_tests" in result.content

    def test_files_required_to_continue_still_works(self):
        """Test that existing files_required_to_continue still works"""
        response_json = '{"status": "files_required_to_continue", "mandatory_instructions": "What files need review?", "files_needed": ["src/"]}'

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "files_required_to_continue"
        assert result.content_type == "json"
        assert "mandatory_instructions" in result.content

    def test_invalid_status_payload(self):
        """Test that invalid payloads for known statuses are handled gracefully"""
        # Missing required field 'reason' for test_sample_needed
        response_json = '{"status": "test_sample_needed"}'

        result = self.tool._parse_response(response_json, self.request)

        # Should fall back to normal processing since validation failed
        assert result.status in ["success", "continuation_available"]

    def test_unknown_status_ignored(self):
        """Test that unknown status types are ignored and treated as normal responses"""
        response_json = '{"status": "unknown_status", "data": "some data"}'

        result = self.tool._parse_response(response_json, self.request)

        # Should be treated as normal response
        assert result.status in ["success", "continuation_available"]

    def test_normal_response_unchanged(self):
        """Test that normal text responses are handled normally"""
        response_text = "This is a normal response with some analysis."

        result = self.tool._parse_response(response_text, self.request)

        # Should be processed as normal response
        assert result.status in ["success", "continuation_available"]
        assert response_text in result.content

    def test_malformed_json_handled(self):
        """Test that malformed JSON is handled gracefully"""
        response_text = '{"status": "files_required_to_continue", "question": "incomplete json'

        result = self.tool._parse_response(response_text, self.request)

        # Should fall back to normal processing
        assert result.status in ["success", "continuation_available"]

    def test_metadata_preserved(self):
        """Test that model metadata is preserved in special status responses"""
        response_json = '{"status": "full_codereview_required", "reason": "Too complex"}'
        model_info = {"model_name": "test-model", "provider": "test-provider"}

        result = self.tool._parse_response(response_json, self.request, model_info)

        assert result.status == "full_codereview_required"
        assert result.metadata["model_used"] == "test-model"
        assert "original_request" in result.metadata

    def test_more_tests_required_detailed(self):
        """Test more_tests_required with detailed pending_tests parameter"""
        # Test the exact format expected by testgen prompt
        pending_tests = "test_authentication_edge_cases (test_auth.py), test_password_validation_complex (test_auth.py), test_user_registration_flow (test_user.py)"
        response_json = f'{{"status": "more_tests_required", "pending_tests": "{pending_tests}"}}'

        result = self.tool._parse_response(response_json, self.request)

        assert result.status == "more_tests_required"
        assert result.content_type == "json"

        # Verify the content contains the validated, parsed data
        import json

        parsed_content = json.loads(result.content)
        assert parsed_content["status"] == "more_tests_required"
        assert parsed_content["pending_tests"] == pending_tests

        # Verify Claude would receive the pending_tests parameter correctly
        assert "test_authentication_edge_cases (test_auth.py)" in parsed_content["pending_tests"]
        assert "test_password_validation_complex (test_auth.py)" in parsed_content["pending_tests"]
        assert "test_user_registration_flow (test_user.py)" in parsed_content["pending_tests"]

    def test_more_tests_required_missing_pending_tests(self):
        """Test that more_tests_required without required pending_tests field fails validation"""
        response_json = '{"status": "more_tests_required"}'

        result = self.tool._parse_response(response_json, self.request)

        # Should fall back to normal processing since validation failed (missing required field)
        assert result.status in ["success", "continuation_available"]
        assert result.content_type != "json"

    def test_test_sample_needed_missing_reason(self):
        """Test that test_sample_needed without required reason field fails validation"""
        response_json = '{"status": "test_sample_needed"}'

        result = self.tool._parse_response(response_json, self.request)

        # Should fall back to normal processing since validation failed (missing required field)
        assert result.status in ["success", "continuation_available"]
        assert result.content_type != "json"

    def test_special_status_json_format_preserved(self):
        """Test that special status responses preserve exact JSON format for Claude"""
        test_cases = [
            {
                "input": '{"status": "files_required_to_continue", "mandatory_instructions": "What framework to use?", "files_needed": ["tests/"]}',
                "expected_fields": ["status", "mandatory_instructions", "files_needed"],
            },
            {
                "input": '{"status": "full_codereview_required", "reason": "Codebase too large"}',
                "expected_fields": ["status", "reason"],
            },
            {
                "input": '{"status": "test_sample_needed", "reason": "Cannot determine test framework"}',
                "expected_fields": ["status", "reason"],
            },
            {
                "input": '{"status": "more_tests_required", "pending_tests": "test_auth (test_auth.py), test_login (test_user.py)"}',
                "expected_fields": ["status", "pending_tests"],
            },
        ]

        for test_case in test_cases:
            result = self.tool._parse_response(test_case["input"], self.request)

            # Verify status is correctly detected
            import json

            input_data = json.loads(test_case["input"])
            assert result.status == input_data["status"]
            assert result.content_type == "json"

            # Verify all expected fields are preserved in the response
            parsed_content = json.loads(result.content)
            for field in test_case["expected_fields"]:
                assert field in parsed_content, f"Field {field} missing from {input_data['status']} response"

                # Special handling for mandatory_instructions which gets enhanced
                if field == "mandatory_instructions" and input_data["status"] == "files_required_to_continue":
                    # Check that enhanced instructions contain the original message
                    assert parsed_content[field].startswith(
                        input_data[field]
                    ), f"Enhanced {field} should start with original value in {input_data['status']} response"
                    assert (
                        "IMPORTANT GUIDANCE:" in parsed_content[field]
                    ), f"Enhanced {field} should contain guidance in {input_data['status']} response"
                else:
                    assert (
                        parsed_content[field] == input_data[field]
                    ), f"Field {field} value mismatch in {input_data['status']} response"

    def test_focused_review_required_parsing(self):
        """Test that focused_review_required status is parsed correctly"""
        import json

        json_response = {
            "status": "focused_review_required",
            "reason": "Codebase too large for single review",
            "suggestion": "Review authentication module (auth.py, login.py)",
        }

        result = self.tool._parse_response(json.dumps(json_response), self.request)

        assert result.status == "focused_review_required"
        assert result.content_type == "json"
        parsed_content = json.loads(result.content)
        assert parsed_content["status"] == "focused_review_required"
        assert parsed_content["reason"] == "Codebase too large for single review"
        assert parsed_content["suggestion"] == "Review authentication module (auth.py, login.py)"

    def test_focused_review_required_missing_suggestion(self):
        """Test that focused_review_required fails validation without suggestion"""
        import json

        json_response = {
            "status": "focused_review_required",
            "reason": "Codebase too large",
            # Missing required suggestion field
        }

        result = self.tool._parse_response(json.dumps(json_response), self.request)

        # Should fall back to normal response since validation failed
        assert result.status == "success"
        assert result.content_type == "text"

    def test_refactor_analysis_complete_parsing(self):
        """Test that RefactorAnalysisComplete status is properly parsed"""
        import json

        json_response = {
            "status": "refactor_analysis_complete",
            "refactor_opportunities": [
                {
                    "id": "refactor-001",
                    "type": "decompose",
                    "severity": "critical",
                    "file": "/test.py",
                    "start_line": 1,
                    "end_line": 5,
                    "context_start_text": "def test():",
                    "context_end_text": "    pass",
                    "issue": "Large function needs decomposition",
                    "suggestion": "Extract helper methods",
                    "rationale": "Improves readability",
                    "code_to_replace": "old code",
                    "replacement_code_snippet": "new code",
                }
            ],
            "priority_sequence": ["refactor-001"],
            "next_actions_for_claude": [
                {
                    "action_type": "EXTRACT_METHOD",
                    "target_file": "/test.py",
                    "source_lines": "1-5",
                    "description": "Extract helper method",
                }
            ],
        }

        result = self.tool._parse_response(json.dumps(json_response), self.request)

        assert result.status == "refactor_analysis_complete"
        assert result.content_type == "json"
        parsed_content = json.loads(result.content)
        assert "refactor_opportunities" in parsed_content
        assert len(parsed_content["refactor_opportunities"]) == 1
        assert parsed_content["refactor_opportunities"][0]["id"] == "refactor-001"

    def test_refactor_analysis_complete_validation_error(self):
        """Test that RefactorAnalysisComplete validation catches missing required fields"""
        import json

        json_response = {
            "status": "refactor_analysis_complete",
            "refactor_opportunities": [
                {
                    "id": "refactor-001",
                    # Missing required fields like type, severity, etc.
                }
            ],
            "priority_sequence": ["refactor-001"],
            "next_actions_for_claude": [],
        }

        result = self.tool._parse_response(json.dumps(json_response), self.request)

        # Should fall back to normal response since validation failed
        assert result.status == "success"
        assert result.content_type == "text"
