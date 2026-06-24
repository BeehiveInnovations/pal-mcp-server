"""
Tests for Challenge tool - validating real Gemma adversarial red-team call behavior

This module contains unit tests to ensure that the Challenge tool
correctly calls Gemma via the inherited SimpleTool.execute() and returns
the verbatim model response (TASK-20260624-560).
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from tools.challenge import CHALLENGE_SYSTEM_PROMPT, ChallengeRequest, ChallengeTool
from tools.shared.exceptions import ToolExecutionError


class TestChallengeTool:
    """Test suite for Challenge tool"""

    def setup_method(self):
        """Set up test fixtures"""
        self.tool = ChallengeTool()

    def test_tool_metadata(self):
        """Test that tool metadata matches requirements"""
        assert self.tool.get_name() == "challenge"
        assert "reflexive agreement" in self.tool.get_description()
        assert "critical thinking" in self.tool.get_description()
        assert "reasoned analysis" in self.tool.get_description()
        assert self.tool.get_default_temperature() == 1.0  # TEMPERATURE_ANALYTICAL

    def test_requires_model(self):
        """Test that challenge tool requires a model (makes real Gemma call)"""
        assert self.tool.requires_model() is True

    def test_schema_structure(self):
        """Test that schema has correct structure and includes optional model field"""
        schema = self.tool.get_input_schema()

        # Basic schema structure
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema

        # Required fields
        assert "prompt" in schema["required"]
        assert len(schema["required"]) == 1  # Only prompt is required

        # Properties
        properties = schema["properties"]
        assert "prompt" in properties

        # model field is now present (optional) since challenge calls Gemma (TASK-560)
        assert "model" in properties

    def test_request_model_validation(self):
        """Test that the request model validates correctly"""
        # Test valid request
        request = ChallengeRequest(prompt="The sky is green")
        assert request.prompt == "The sky is green"

        # Test with longer prompt
        long_prompt = (
            "Machine learning models always produce accurate results and should be trusted without verification"
        )
        request = ChallengeRequest(prompt=long_prompt)
        assert request.prompt == long_prompt

    def test_required_fields(self):
        """Test that required fields are enforced"""
        from pydantic import ValidationError

        # Missing prompt should raise validation error
        with pytest.raises(ValidationError):
            ChallengeRequest()

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful execution of challenge tool with mocked Gemma call"""
        fake_gemma_response = (
            "The claim that all software bugs are caused by syntax errors is clearly wrong.\n"
            "Logic errors, race conditions, and off-by-one errors are common non-syntax bugs.\n"
            "VERDICT: fail"
        )

        mock_provider = MagicMock()
        mock_provider.get_provider_type.return_value = MagicMock(value="google")
        mock_provider.generate_content.return_value = MagicMock(
            content=fake_gemma_response,
            usage={"input_tokens": 10, "output_tokens": 20},
            model_name="gemma-4-26b-a4b-it",
            metadata={"finish_reason": "STOP"},
        )

        mock_model_context = MagicMock()
        mock_model_context.model_name = "gemma-4-26b-a4b-it"
        mock_model_context.provider = mock_provider
        mock_model_context.capabilities = MagicMock(supports_extended_thinking=False)

        arguments = {
            "prompt": "All software bugs are caused by syntax errors",
            "_model_context": mock_model_context,
        }

        with patch("server.get_follow_up_instructions", return_value=""):
            result = await self.tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        assert result[0].type == "text"

        # Parse the JSON response — format_response returns Gemma text verbatim
        response_data = json.loads(result[0].text)
        assert response_data["status"] in ("success", "continuation_available")
        assert response_data["content"] == fake_gemma_response
        assert "VERDICT: fail" in response_data["content"]

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        """Test error handling in execute method"""
        with patch.object(self.tool, "get_request_model", side_effect=Exception("Test error")):
            with pytest.raises(ToolExecutionError) as exc_info:
                await self.tool.execute({"prompt": "test"})

        response_data = json.loads(exc_info.value.payload)
        assert response_data["status"] == "error"
        # SimpleTool.execute() puts the error message in "content", not "error"
        assert "Test error" in response_data["content"]

    def test_wrap_prompt_for_challenge(self):
        """Test the prompt wrapping functionality"""
        original_prompt = "Python is the best programming language"
        wrapped = self.tool._wrap_prompt_for_challenge(original_prompt)

        # Check structure
        assert "CRITICAL REASSESSMENT – Do not automatically agree" in wrapped
        assert "Carefully evaluate the statement above" in wrapped
        assert f'"{original_prompt}"' in wrapped
        assert "flaws, gaps, or misleading points" in wrapped
        assert "thoughtful analysis" in wrapped

    def test_multiple_prompts(self):
        """Test that tool handles various types of prompts correctly"""
        test_prompts = [
            "All code should be written in assembly for maximum performance",
            "Comments are unnecessary if code is self-documenting",
            "Testing is a waste of time for experienced developers",
            "Global variables make code easier to understand",
            "The more design patterns used, the better the code",
        ]

        for prompt in test_prompts:
            request = ChallengeRequest(prompt=prompt)
            wrapped = self.tool._wrap_prompt_for_challenge(request.prompt)

            # Each wrapped prompt should contain the original
            assert prompt in wrapped
            assert "CRITICAL REASSESSMENT" in wrapped

    def test_tool_fields(self):
        """Test tool-specific field definitions"""
        fields = self.tool.get_tool_fields()

        assert "prompt" in fields
        assert fields["prompt"]["type"] == "string"
        assert "Statement to scrutinize" in fields["prompt"]["description"]
        assert "strip the word 'challenge'" in fields["prompt"]["description"]

    def test_required_fields_list(self):
        """Test required fields list"""
        required = self.tool.get_required_fields()
        assert required == ["prompt"]

    @pytest.mark.asyncio
    async def test_not_used_methods(self):
        """Test prepare_prompt and format_response behave correctly"""
        request = ChallengeRequest(prompt="test")

        # prepare_prompt builds the full adversarial prompt (TASK-560: no longer empty)
        # We need a minimal _model_context stub because build_standard_prompt reads it
        self.tool._model_context = MagicMock()
        self.tool._model_context.model_name = "gemma-4-26b-a4b-it"
        self.tool._current_arguments = {}
        prompt = await self.tool.prepare_prompt(request)
        # prompt must be non-empty — it contains the CHALLENGE_SYSTEM_PROMPT + wrapped text
        assert CHALLENGE_SYSTEM_PROMPT in prompt
        assert "test" in prompt

        # format_response passes through verbatim; format_response still works as before
        response = self.tool.format_response("test response", request)
        assert response == "test response"

    def test_special_characters_in_prompt(self):
        """Test handling of special characters in prompts"""
        special_prompt = 'The "best" way to handle errors is to use try/except: pass'
        request = ChallengeRequest(prompt=special_prompt)
        wrapped = self.tool._wrap_prompt_for_challenge(request.prompt)

        # Should handle quotes properly
        assert special_prompt in wrapped

    @pytest.mark.asyncio
    async def test_unicode_support(self):
        """Test that tool handles unicode characters correctly with mocked Gemma call"""
        unicode_prompt = "软件开发中最重要的是写代码，测试不重要 🚀"
        fake_gemma_response = f"Challenging: {unicode_prompt}\nVERDICT: fail"

        mock_provider = MagicMock()
        mock_provider.get_provider_type.return_value = MagicMock(value="google")
        mock_provider.generate_content.return_value = MagicMock(
            content=fake_gemma_response,
            usage={"input_tokens": 5, "output_tokens": 15},
            model_name="gemma-4-26b-a4b-it",
            metadata={"finish_reason": "STOP"},
        )

        mock_model_context = MagicMock()
        mock_model_context.model_name = "gemma-4-26b-a4b-it"
        mock_model_context.provider = mock_provider
        mock_model_context.capabilities = MagicMock(supports_extended_thinking=False)

        arguments = {
            "prompt": unicode_prompt,
            "_model_context": mock_model_context,
        }

        with patch("server.get_follow_up_instructions", return_value=""):
            result = await self.tool.execute(arguments)

        response_data = json.loads(result[0].text)
        assert response_data["status"] in ("success", "continuation_available")
        # format_response returns verbatim — mock response includes the unicode prompt
        assert unicode_prompt in response_data["content"]


if __name__ == "__main__":
    pytest.main([__file__])
