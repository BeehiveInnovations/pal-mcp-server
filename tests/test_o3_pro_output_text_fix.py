"""
Tests for o3-pro output_text parsing fix using HTTP transport recording.

This test validates the fix that uses `response.output_text` convenience field
instead of manually parsing `response.output.content[].text`.

Uses HTTP transport recorder to record real o3-pro API responses at the HTTP level while allowing
the OpenAI SDK to create real response objects that we can test.

RECORDING: To record new responses, delete the cassette file and run with real API keys.
"""

import unittest
from pathlib import Path

import pytest
from dotenv import load_dotenv

from providers import ModelProviderRegistry
from tests.transport_helpers import inject_transport
from tools.chat import ChatTool

# Load environment variables from .env file
load_dotenv()

# Use absolute path for cassette directory
cassette_dir = Path(__file__).parent / "openai_cassettes"
cassette_dir.mkdir(exist_ok=True)


@pytest.mark.asyncio
class TestO3ProOutputTextFix:
    """Test o3-pro response parsing fix using respx for HTTP recording/replay."""

    def setup_method(self):
        """Set up the test by ensuring clean registry state."""
        # Use the new public API for registry cleanup
        ModelProviderRegistry.reset_for_testing()
        # Provider registration is now handled by inject_transport helper

    def teardown_method(self):
        """Clean up after test to ensure no state pollution."""
        # Use the new public API for registry cleanup
        ModelProviderRegistry.reset_for_testing()

    @pytest.mark.no_mock_provider  # Disable provider mocking for this test
    async def test_o3_pro_uses_output_text_field(self, monkeypatch):
        """Test that o3-pro parsing uses the output_text convenience field via ChatTool."""
        # Set API key inline - helper will handle provider registration
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")

        cassette_path = cassette_dir / "o3_pro_basic_math.json"

        # Require cassette for test - no cargo culting
        if not cassette_path.exists():
            pytest.skip("Cassette file required - record with real OPENAI_API_KEY")

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        # Execute ChatTool test with custom transport
        result = await self._execute_chat_tool_test()

        # Verify the response works correctly
        self._verify_chat_tool_response(result)

        # Verify cassette exists
        assert cassette_path.exists()

    async def _execute_chat_tool_test(self):
        """Execute the ChatTool with o3-pro and return the result."""
        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        return await chat_tool.execute(arguments)

    def _verify_chat_tool_response(self, result):
        """Verify the ChatTool response contains expected data."""
        # Basic response validation
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0
        assert result[0].type == "text"

        # Parse JSON response
        import json

        response_data = json.loads(result[0].text)

        # Verify response structure - no cargo culting
        assert response_data["status"] in ["success", "continuation_available"]
        assert "4" in response_data["content"]

        # Verify o3-pro was actually used
        metadata = response_data["metadata"]
        assert metadata["model_used"] == "o3-pro"
        assert metadata["provider_used"] == "openai"


if __name__ == "__main__":
    print("🎥 OpenAI Response Recording Tests for O3-Pro Output Text Fix")
    print("=" * 50)
    print("RECORD MODE: Requires OPENAI_API_KEY - makes real API calls through ChatTool")
    print("REPLAY MODE: Uses recorded HTTP responses - free and fast")
    print("RECORDING: Delete .json files in tests/openai_cassettes/ to re-record")
    print()

    unittest.main()
