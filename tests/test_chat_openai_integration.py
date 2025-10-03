"""Integration test for ChatTool auto-mode using OpenAI o3/gpt models with cassette recording."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from tests.transport_helpers import inject_transport
from tools.chat import ChatTool

# Directory for recorded HTTP interactions
CASSETTE_DIR = Path(__file__).parent / "openai_cassettes"
CASSETTE_DIR.mkdir(exist_ok=True)
CASSETTE_PATH = CASSETTE_DIR / "chat_gpt5_moon_distance.json"
CASSETTE_CONTINUATION_PATH = CASSETTE_DIR / "chat_gpt5_continuation.json"


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_chat_auto_mode_with_openai(monkeypatch):
    """Ensure ChatTool in auto mode selects gpt-5 via OpenAI and returns a valid response."""
    # Prepare environment so only OpenAI is available in auto mode
    env_updates = {
        "DEFAULT_MODEL": "auto",
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    }
    # Remove Gemini/XAI keys to force OpenAI selection
    keys_to_clear = ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]

    with monkeypatch.context() as m:
        m.setenv("DEFAULT_MODEL", env_updates["DEFAULT_MODEL"])
        if env_updates["OPENAI_API_KEY"]:
            m.setenv("OPENAI_API_KEY", env_updates["OPENAI_API_KEY"])
        for key in keys_to_clear:
            m.delenv(key, raising=False)

        # Choose recording or replay mode based on cassette presence
        if not CASSETTE_PATH.exists():
            real_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not real_key or real_key.startswith("dummy"):
                pytest.skip(
                    "Cassette missing and OPENAI_API_KEY not configured. Provide a real key and re-run to record."
                )
        else:
            # Replay mode uses dummy key to keep secrets out of the cassette
            m.setenv("OPENAI_API_KEY", "dummy-key-for-replay")

        # Reset registry and register only OpenAI provider
        ModelProviderRegistry.reset_for_testing()
        from providers.openai_provider import OpenAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

        # Inject HTTP transport (records or replays depending on cassette state)
        inject_transport(monkeypatch, CASSETTE_PATH)

        # Execute ChatTool request targeting gpt-5 directly (server normally resolves auto→model)
        chat_tool = ChatTool()
        arguments = {
            "prompt": "Use chat with gpt5 and ask how far the moon is from earth.",
            "model": "gpt-5",
            "temperature": 1.0,
        }

        result = await chat_tool.execute(arguments)

    # Validate response
    assert result and result[0].type == "text"
    response_data = json.loads(result[0].text)

    assert response_data["status"] in {"success", "continuation_available"}
    metadata = response_data.get("metadata", {})
    assert metadata.get("provider_used") == "openai"
    assert metadata.get("model_used") in {"gpt-5", "gpt5"}
    assert "moon" in response_data["content"].lower()

    # Ensure cassette recorded for future replays
    assert CASSETTE_PATH.exists()


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_chat_openai_continuation(monkeypatch):
    """Verify continuation_id workflow against gpt-5 using recorded OpenAI responses."""

    env_updates = {
        "DEFAULT_MODEL": "auto",
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    }
    keys_to_clear = ["GEMINI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY"]

    recording_mode = not CASSETTE_CONTINUATION_PATH.exists()
    if recording_mode:
        real_key = env_updates["OPENAI_API_KEY"].strip()
        if not real_key or real_key.startswith("dummy"):
            pytest.skip("Continuation cassette missing and OPENAI_API_KEY not configured. Set a real key to record.")

    fixed_thread_id = uuid.UUID("95d60035-1aa3-4398-9936-fca71989d906")

    with monkeypatch.context() as m:
        m.setenv("DEFAULT_MODEL", env_updates["DEFAULT_MODEL"])
        if recording_mode:
            m.setenv("OPENAI_API_KEY", env_updates["OPENAI_API_KEY"])
        else:
            m.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
        for key in keys_to_clear:
            m.delenv(key, raising=False)

        ModelProviderRegistry.reset_for_testing()
        from providers.openai_provider import OpenAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)

        inject_transport(monkeypatch, CASSETTE_CONTINUATION_PATH)

        from utils import conversation_memory

        m.setattr(conversation_memory.uuid, "uuid4", lambda: fixed_thread_id)

        chat_tool = ChatTool()

        # First message: obtain continuation_id
        first_args = {
            "prompt": "In one word, which sells better: iOS app or macOS app?",
            "model": "gpt-5",
            "temperature": 1.0,
        }
        first_result = await chat_tool.execute(first_args)

        assert first_result and first_result[0].type == "text"
        first_data = json.loads(first_result[0].text)
        assert first_data["status"] == "continuation_available"
        first_metadata = first_data.get("metadata", {})
        assert first_metadata.get("provider_used") == "openai"
        assert first_metadata.get("model_used") in {"gpt-5", "gpt5"}
        continuation = first_data.get("continuation_offer")
        assert continuation is not None
        continuation_id = continuation.get("continuation_id")
        assert continuation_id

        # Second message using continuation_id (reuse same tool instance for clarity)
        second_args = {
            "prompt": "In one word then, SwiftUI or ReactNative?",
            "model": "gpt-5",
            "continuation_id": continuation_id,
            "temperature": 1.0,
        }

        second_result = await chat_tool.execute(second_args)

        assert second_result and second_result[0].type == "text"
        second_data = json.loads(second_result[0].text)
        assert second_data["status"] in {"success", "continuation_available"}
        second_metadata = second_data.get("metadata", {})
        assert second_metadata.get("provider_used") == "openai"
        assert second_metadata.get("model_used") in {"gpt-5", "gpt5"}
        assert second_metadata.get("conversation_ready") is True
        assert second_data.get("continuation_offer") is not None

    # Ensure the cassette file exists for future replays
    assert CASSETTE_CONTINUATION_PATH.exists()

    # Clean up registry state for subsequent tests
    ModelProviderRegistry.reset_for_testing()
