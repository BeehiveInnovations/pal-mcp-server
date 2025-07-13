"""
Tests for o3-pro output_text parsing fix using HTTP transport recording.

This test validates the fix that uses `response.output_text` convenience field
instead of manually parsing `response.output.content[].text`.

Uses HTTP transport recorder to record real o3-pro API responses at the HTTP level while allowing
the OpenAI SDK to create real response objects that we can test.

RECORDING: To record new responses, delete the cassette file and run with real API keys.
"""

import json
import os
import unittest
from pathlib import Path

import pytest
from dotenv import load_dotenv

from providers import ModelProviderRegistry
from providers.base import ProviderType
from providers.openai_provider import OpenAIModelProvider
from tests.http_transport_recorder import TransportFactory
from tools.chat import ChatTool

# Load environment variables from .env file
load_dotenv()

# Use absolute path for cassette directory
cassette_dir = Path(__file__).parent / "openai_cassettes"
cassette_dir.mkdir(exist_ok=True)


@pytest.fixture
def allow_all_models(monkeypatch):
    """Allow all models by resetting the restriction service singleton."""
    # Import here to avoid circular imports
    from utils.model_restrictions import _restriction_service
    
    # Store original state
    original_service = _restriction_service
    original_allowed_models = os.getenv("ALLOWED_MODELS")
    original_openai_key = os.getenv("OPENAI_API_KEY")
    
    # Reset the singleton so it will re-read env vars inside this fixture
    monkeypatch.setattr("utils.model_restrictions._restriction_service", None)
    monkeypatch.setenv("ALLOWED_MODELS", "")  # empty string = no restrictions
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")  # transport layer expects a key
    
    # Also clear the provider registry cache to ensure clean state
    from providers.registry import ModelProviderRegistry
    ModelProviderRegistry.clear_cache()
    
    yield
    
    # Clean up: reset singleton again so other tests don't see the unrestricted version
    monkeypatch.setattr("utils.model_restrictions._restriction_service", None)
    # Clear registry cache again for other tests
    ModelProviderRegistry.clear_cache()


@pytest.mark.no_mock_provider  # Disable provider mocking for this test
class TestO3ProOutputTextFix(unittest.IsolatedAsyncioTestCase):
    """Test o3-pro response parsing fix using respx for HTTP recording/replay."""

    def setUp(self):
        """Set up the test by ensuring OpenAI provider is registered."""
        # Clear any cached providers to ensure clean state
        ModelProviderRegistry.clear_cache()
        # Manually register the OpenAI provider to ensure it's available
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

    @pytest.mark.usefixtures("allow_all_models")
    async def test_o3_pro_uses_output_text_field(self):
        """Test that o3-pro parsing uses the output_text convenience field via ChatTool."""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"

        # Skip if no API key available and cassette doesn't exist
        if not cassette_path.exists() and not os.getenv("OPENAI_API_KEY"):
            pytest.skip("Set real OPENAI_API_KEY to record cassettes")

        # Create transport (automatically selects record vs replay mode)
        transport = TransportFactory.create_transport(str(cassette_path))

        # Get provider and inject custom transport
        provider = ModelProviderRegistry.get_provider_for_model("o3-pro")
        if not provider:
            self.fail("OpenAI provider not available for o3-pro model")

        # Inject transport for this test
        original_transport = getattr(provider, "_test_transport", None)
        provider._test_transport = transport

        try:
            # Execute ChatTool test with custom transport
            result = await self._execute_chat_tool_test()

            # Verify the response works correctly
            self._verify_chat_tool_response(result)

            # Verify cassette was created/used
            if not cassette_path.exists():
                self.fail(f"Cassette should exist at {cassette_path}")

            print(
                f"✅ HTTP transport {'recorded' if isinstance(transport, type(transport).__bases__[0]) else 'replayed'} o3-pro interaction"
            )

        finally:
            # Restore original transport (if any)
            if original_transport:
                provider._test_transport = original_transport
            elif hasattr(provider, "_test_transport"):
                delattr(provider, "_test_transport")

    async def _execute_chat_tool_test(self):
        """Execute the ChatTool with o3-pro and return the result."""
        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        return await chat_tool.execute(arguments)

    def _verify_chat_tool_response(self, result):
        """Verify the ChatTool response contains expected data."""
        # Verify we got a valid response
        self.assertIsNotNone(result, "Should get response from ChatTool")

        # Parse the result content (ChatTool returns MCP TextContent format)
        self.assertIsInstance(result, list, "ChatTool should return list of content")
        self.assertTrue(len(result) > 0, "Should have at least one content item")

        # Get the text content (result is a list of TextContent objects)
        content_item = result[0]
        self.assertEqual(content_item.type, "text", "First item should be text content")

        text_content = content_item.text
        self.assertTrue(len(text_content) > 0, "Should have text content")

        # Parse the JSON response from chat tool
        try:
            response_data = json.loads(text_content)
        except json.JSONDecodeError:
            self.fail(f"Could not parse chat tool response as JSON: {text_content}")

        # Verify the response makes sense for the math question
        actual_content = response_data.get("content", "")
        self.assertIn("4", actual_content, "Should contain the answer '4'")

        # Verify metadata shows o3-pro was used
        metadata = response_data.get("metadata", {})
        self.assertEqual(metadata.get("model_used"), "o3-pro", "Should use o3-pro model")
        self.assertEqual(metadata.get("provider_used"), "openai", "Should use OpenAI provider")

        # Additional verification that the fix is working
        self.assertTrue(actual_content.strip(), "Content should not be empty")
        self.assertIsInstance(actual_content, str, "Content should be string")

        # Verify successful status
        self.assertEqual(response_data.get("status"), "continuation_available", "Should have successful status")


if __name__ == "__main__":
    print("🎥 OpenAI Response Recording Tests for O3-Pro Output Text Fix")
    print("=" * 50)
    print("RECORD MODE: Requires OPENAI_API_KEY - makes real API calls through ChatTool")
    print("REPLAY MODE: Uses recorded HTTP responses - free and fast")
    print("RECORDING: Delete .json files in tests/openai_cassettes/ to re-record")
    print()

    unittest.main()
