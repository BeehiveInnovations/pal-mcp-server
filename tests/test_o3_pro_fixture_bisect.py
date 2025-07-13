"""Bisect which operations in allow_all_models fixture are actually needed"""

from pathlib import Path

import pytest

from providers import ModelProviderRegistry
from tests.transport_helpers import inject_transport
from tools.chat import ChatTool

cassette_dir = Path(__file__).parent / "openai_cassettes"


class TestO3ProFixtureBisect:
    """Test different combinations of fixture operations"""

    @pytest.mark.asyncio
    @pytest.mark.no_mock_provider
    async def test_minimal_just_api_key(self, monkeypatch):
        """Test 1: Only set API key, no other operations"""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"
        if not cassette_path.exists():
            pytest.skip("Cassette not found")

        # Only set API key
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)
        assert result is not None
        print("Test 1 (API key only) passed!")

    @pytest.mark.asyncio
    @pytest.mark.no_mock_provider
    async def test_api_key_plus_cache_clear(self, monkeypatch):
        """Test 2: API key + cache clear only"""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"
        if not cassette_path.exists():
            pytest.skip("Cassette not found")

        # Set API key and clear cache
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
        ModelProviderRegistry.clear_cache()

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)
        assert result is not None
        print("Test 2 (API key + cache clear) passed!")

    @pytest.mark.asyncio
    @pytest.mark.no_mock_provider
    async def test_targeted_o3_pro_only(self, monkeypatch):
        """Test 3: Allow only o3-pro specifically"""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"
        if not cassette_path.exists():
            pytest.skip("Cassette not found")

        # Set API key and allow only o3-pro
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
        monkeypatch.setenv("OPENAI_ALLOWED_MODELS", "o3-pro")
        monkeypatch.setattr("utils.model_restrictions._restriction_service", None)
        ModelProviderRegistry.clear_cache()

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)
        assert result is not None
        print("Test 3 (targeted o3-pro only) passed!")

    @pytest.mark.asyncio
    @pytest.mark.no_mock_provider
    async def test_full_fixture_operations(self, monkeypatch):
        """Test 4: All fixture operations (baseline)"""
        cassette_path = cassette_dir / "o3_pro_basic_math.json"
        if not cassette_path.exists():
            pytest.skip("Cassette not found")

        # Full fixture operations
        monkeypatch.setattr("utils.model_restrictions._restriction_service", None)
        monkeypatch.setenv("ALLOWED_MODELS", "")
        monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
        ModelProviderRegistry.clear_cache()

        # Simplified transport injection - just one line!
        inject_transport(monkeypatch, cassette_path)

        chat_tool = ChatTool()
        arguments = {"prompt": "What is 2 + 2?", "model": "o3-pro", "temperature": 1.0}

        result = await chat_tool.execute(arguments)
        assert result is not None
        print("Test 4 (full fixture ops) passed!")
