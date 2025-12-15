"""Cross-provider continuation tests for ChatTool."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from tests.transport_helpers import inject_transport
from tools.chat import ChatTool

CASSETTE_DIR = Path(__file__).parent / "openai_cassettes"
CASSETTE_DIR.mkdir(exist_ok=True)


def get_cassette_for_model(base_name: str, model_name: str) -> Path:
    """Dynamically select cassette based on model's API routing configuration."""
    from providers.openai import OpenAIModelProvider

    provider = OpenAIModelProvider(api_key="dummy-key-for-check")
    capabilities = provider.get_capabilities(model_name)

    if capabilities.use_openai_response_api:
        return CASSETTE_DIR / f"{base_name}_responses.json"
    else:
        return CASSETTE_DIR / f"{base_name}.json"


GEMINI_CASSETTE_DIR = Path(__file__).parent / "gemini_cassettes"
GEMINI_CASSETTE_DIR.mkdir(exist_ok=True)
GEMINI_REPLAY_ID = "chat_cross/step1_gemini25_flash_number/mldev"
GEMINI_REPLAY_PATH = GEMINI_CASSETTE_DIR / "chat_cross" / "step1_gemini25_flash_number" / "mldev.json"

FIXED_THREAD_ID = uuid.UUID("dbadc23e-c0f4-4853-982f-6c5bc722b5de")


WORD_TO_NUMBER = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _extract_number(text: str) -> str:
    digit_match = re.search(r"\b(\d{1,2})\b", text)
    if digit_match:
        return digit_match.group(1)

    lower_text = text.lower()
    for word, value in WORD_TO_NUMBER.items():
        if re.search(rf"\b{word}\b", lower_text):
            return str(value)
    return ""


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_chat_cross_model_continuation(monkeypatch, tmp_path):
    """Verify continuation across Gemini then OpenAI using recorded interactions."""

    env_updates = {
        "DEFAULT_MODEL": "auto",
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    }
    keys_to_clear = [
        "XAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "MISTRAL_API_KEY",
        "CUSTOM_API_KEY",
        "CUSTOM_API_URL",
        "GEMINI_BASE_URL",  # Ensure standard Gemini API is used for cassettes
        "OPENAI_BASE_URL",  # Ensure standard OpenAI API is used for cassettes
        "LOCALE",  # Ensure English prompts match cassette recordings
    ]

    # Check if cassettes exist (dynamically determine OpenAI cassette path)
    openai_cassette_path = get_cassette_for_model("chat_cross_step2_gpt5_reminder", "gpt-5")
    recording_mode = not openai_cassette_path.exists() or not GEMINI_REPLAY_PATH.exists()
    if recording_mode:
        openai_key = env_updates["OPENAI_API_KEY"].strip()
        gemini_key = env_updates["GEMINI_API_KEY"].strip()
        if (not openai_key or openai_key.startswith("dummy")) or (not gemini_key or gemini_key.startswith("dummy")):
            pytest.skip(
                "Cross-provider cassette missing and OPENAI_API_KEY/GEMINI_API_KEY not configured. Provide real keys to record."
            )

    GEMINI_REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Step 1 – Gemini picks a number
    with monkeypatch.context() as m:
        m.setenv("DEFAULT_MODEL", env_updates["DEFAULT_MODEL"])
        m.setenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-flash")
        m.setenv("OPENAI_ALLOWED_MODELS", "gpt-5")
        if recording_mode:
            m.setenv("OPENAI_API_KEY", env_updates["OPENAI_API_KEY"])
            m.setenv("GEMINI_API_KEY", env_updates["GEMINI_API_KEY"])
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "record")
        else:
            m.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
            m.setenv("GEMINI_API_KEY", "dummy-key-for-replay")
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "replay")

        m.setenv("GOOGLE_GENAI_REPLAYS_DIRECTORY", str(GEMINI_CASSETTE_DIR))
        m.setenv("GOOGLE_GENAI_REPLAY_ID", GEMINI_REPLAY_ID)

        for key in keys_to_clear:
            m.delenv(key, raising=False)

        ModelProviderRegistry.reset_for_testing()
        from providers.gemini import GeminiModelProvider
        from providers.openai import OpenAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        from utils import conversation_memory

        m.setattr(conversation_memory.uuid, "uuid4", lambda: FIXED_THREAD_ID)

        chat_tool = ChatTool()
        working_directory = str(tmp_path)

        step1_args = {
            "prompt": "Pick a number between 1 and 10 and respond with JUST that number.",
            "model": "gemini-2.5-flash",
            "temperature": 0.2,
            "working_directory_absolute_path": working_directory,
        }

        step1_result = await chat_tool.execute(step1_args)
        assert step1_result and step1_result[0].type == "text"

        step1_data = json.loads(step1_result[0].text)
        assert step1_data["status"] in {"success", "continuation_available"}
        assert step1_data.get("metadata", {}).get("provider_used") == "google"
        continuation_offer = step1_data.get("continuation_offer")
        assert continuation_offer is not None
        continuation_id = continuation_offer["continuation_id"]
        assert continuation_id

        chosen_number = _extract_number(step1_data["content"])
        assert chosen_number.isdigit()
        assert 1 <= int(chosen_number) <= 10

        # Ensure replay is flushed for Gemini recordings
        gemini_provider = ModelProviderRegistry.get_provider_for_model("gemini-2.5-flash")
        if gemini_provider is not None:
            try:
                client = gemini_provider.client
                if hasattr(client, "close"):
                    client.close()
            finally:
                if hasattr(gemini_provider, "_client"):
                    gemini_provider._client = None

    assert GEMINI_REPLAY_PATH.exists()

    # Step 2 – gpt-5 recalls the number via continuation
    with monkeypatch.context() as m:
        if recording_mode:
            m.setenv("OPENAI_API_KEY", env_updates["OPENAI_API_KEY"])
            m.setenv("GEMINI_API_KEY", env_updates["GEMINI_API_KEY"])
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "record")
        else:
            m.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
            m.setenv("GEMINI_API_KEY", "dummy-key-for-replay")
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "replay")

        m.setenv("DEFAULT_MODEL", env_updates["DEFAULT_MODEL"])
        m.setenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-flash")
        m.setenv("OPENAI_ALLOWED_MODELS", "gpt-5")
        m.setenv("GOOGLE_GENAI_REPLAYS_DIRECTORY", str(GEMINI_CASSETTE_DIR))
        m.setenv("GOOGLE_GENAI_REPLAY_ID", GEMINI_REPLAY_ID)
        for key in keys_to_clear:
            m.delenv(key, raising=False)

        ModelProviderRegistry.reset_for_testing()

        # Inject transport BEFORE provider registration to ensure monkeypatch is applied
        inject_transport(monkeypatch, openai_cassette_path)

        from providers.gemini import GeminiModelProvider
        from providers.openai import OpenAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        chat_tool = ChatTool()
        step2_args = {
            "prompt": "Remind me, what number did you pick, respond with JUST that number.",
            "model": "gpt-5",
            "continuation_id": continuation_id,
            "temperature": 0.2,
            "working_directory_absolute_path": working_directory,
        }

        step2_result = await chat_tool.execute(step2_args)
        assert step2_result and step2_result[0].type == "text"

        step2_data = json.loads(step2_result[0].text)
        assert step2_data["status"] in {"success", "continuation_available"}
        assert step2_data.get("metadata", {}).get("provider_used") == "openai"

        recalled_number = _extract_number(step2_data["content"])
        assert recalled_number == chosen_number

    assert openai_cassette_path.exists()

    ModelProviderRegistry.reset_for_testing()
