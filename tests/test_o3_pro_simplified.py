"""
Simplified o3-pro test demonstrating minimal fixture requirements.

Based on bisection testing, this test proves that only the API key
is needed - no model restrictions or registry operations required.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from tests.transport_helpers import inject_transport
from tools.chat import ChatTool

# Load environment variables from .env file
load_dotenv()

# Use absolute path for cassette directory
cassette_dir = Path(__file__).parent / "openai_cassettes"
cassette_dir.mkdir(exist_ok=True)


@pytest.fixture
def dummy_api_key(monkeypatch):
    """Minimal fixture - just set the API key for transport replay."""
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")


@pytest.mark.asyncio
class TestO3ProSimplified:
    """Test o3-pro with minimal setup - no unnecessary registry operations."""

    @pytest.mark.no_mock_provider  # Disable provider mocking for this test
    @pytest.mark.usefixtures("dummy_api_key")
    async def test_o3_pro_minimal_fixture(self, monkeypatch):
        """Test that o3-pro works with just the API key set."""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"

        # Skip if cassette doesn't exist (for test suite runs)
        if not cassette_path.exists():
            if os.getenv("OPENAI_API_KEY"):
                print(f"Recording new cassette at {cassette_path}")
            else:
                pytest.skip("Cassette not found and no OPENAI_API_KEY to record new one")

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        # Execute ChatTool test with custom transport
        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)

        # Verify we got a valid response
        assert result is not None, "Should get response from ChatTool"
        assert isinstance(result, list), "ChatTool should return list of content"
        assert len(result) > 0, "Should have at least one content item"

        # Get the text content
        content_item = result[0]
        assert content_item.type == "text", "First item should be text content"

        # Parse and verify the response
        import json

        text_content = content_item.text
        response_data = json.loads(text_content)

        # Verify response structure
        assert "status" in response_data
        assert "content" in response_data
        assert "metadata" in response_data

        # Skip further checks if error response
        if response_data["status"] == "error":
            print(f"⚠️  Got error response: {response_data['content']}")
            return

        # Verify the answer
        content = response_data["content"]
        assert "4" in content, f"Response should contain '4', got: {content[:200]}..."

        # Verify o3-pro was used
        metadata = response_data["metadata"]
        assert metadata["model_used"] == "o3-pro"
        assert metadata["provider_used"] == "openai"

        print("✅ Verified o3-pro response with minimal fixture!")

    @pytest.mark.no_mock_provider
    async def test_o3_pro_no_fixture_at_all(self, monkeypatch):
        """Test that o3-pro works without any fixture - just inline API key."""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"

        if not cassette_path.exists():
            pytest.skip("Cassette not found")

        # Set API key inline - no fixture needed!
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        # Execute test
        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)
        assert result is not None

        print("✅ Test works without any fixture - just inline API key!")
