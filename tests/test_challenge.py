"""
Tests for Challenge tool - validating critical challenge prompt wrapper

This module contains unit tests to ensure that the Challenge tool
properly wraps statements to encourage critical thinking and avoid
automatic agreement patterns.
"""

import json
from unittest.mock import patch

import pytest

from tools.challenge import ChallengeRequest, ChallengeTool
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
        """Test that challenge tool doesn't require a model"""
        assert self.tool.requires_model() is False

    def test_schema_structure(self):
        """Test that schema has correct structure and excludes model fields"""
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

        # Should NOT have model-related fields since it doesn't require a model
        assert "model" not in properties
        assert "temperature" not in properties
        assert "thinking_mode" not in properties
        assert "continuation_id" not in properties

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
        """Test successful execution of challenge tool"""
        arguments = {"prompt": "All software bugs are caused by syntax errors"}

        result = await self.tool.execute(arguments)

        # Should return a list with TextContent
        assert len(result) == 1
        assert result[0].type == "text"

        # Parse the JSON response
        response_data = json.loads(result[0].text)

        # Check response structure
        assert response_data["status"] == "challenge_accepted"
        assert response_data["original_statement"] == "All software bugs are caused by syntax errors"
        assert "challenge_prompt" in response_data
        assert "instructions" in response_data

        # Check that the challenge prompt contains critical thinking instructions
        challenge_prompt = response_data["challenge_prompt"]
        assert "CRITICAL REASSESSMENT – Do not automatically agree" in challenge_prompt
        assert "Carefully evaluate the statement above" in challenge_prompt
        assert response_data["original_statement"] in challenge_prompt
        assert "flaws, gaps, or misleading points" in challenge_prompt
        assert "thoughtful analysis" in challenge_prompt

    @pytest.mark.asyncio
    async def test_execute_error_handling(self):
        """Test error handling in execute method"""
        # Test with invalid arguments (non-dict)
        with patch.object(self.tool, "get_request_model", side_effect=Exception("Test error")):
            with pytest.raises(ToolExecutionError) as exc_info:
                await self.tool.execute({"prompt": "test"})

        response_data = json.loads(exc_info.value.payload)
        assert response_data["status"] == "error"
        assert "Test error" in response_data["error"]

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
        """Test that methods not used by challenge tool work correctly"""
        request = ChallengeRequest(prompt="test")

        # These methods aren't used since challenge doesn't call AI
        prompt = await self.tool.prepare_prompt(request)
        assert prompt == ""

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
        """Test that tool handles unicode characters correctly"""
        unicode_prompt = "软件开发中最重要的是写代码，测试不重要 🚀"
        arguments = {"prompt": unicode_prompt}

        result = await self.tool.execute(arguments)
        response_data = json.loads(result[0].text)

        assert response_data["original_statement"] == unicode_prompt
        assert unicode_prompt in response_data["challenge_prompt"]


if __name__ == "__main__":
    pytest.main([__file__])
