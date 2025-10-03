"""Integration test for ConsensusTool using OpenAI and Gemini recordings."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from tests.transport_helpers import inject_transport
from tools.consensus import ConsensusTool

# Directories for recorded HTTP interactions
CASSETTE_DIR = Path(__file__).parent / "openai_cassettes"
CASSETTE_DIR.mkdir(exist_ok=True)
CONSENSUS_CASSETTE_PATH = CASSETTE_DIR / "consensus_step1_gpt5_for.json"

GEMINI_REPLAY_DIR = Path(__file__).parent / "gemini_cassettes"
GEMINI_REPLAY_DIR.mkdir(exist_ok=True)
GEMINI_REPLAY_ID = "consensus/step2_gemini25_flash_against/mldev"
GEMINI_REPLAY_PATH = GEMINI_REPLAY_DIR / "consensus" / "step2_gemini25_flash_against" / "mldev.json"


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_consensus_multi_model_consultations(monkeypatch):
    """Exercise ConsensusTool against gpt-5 (supporting) and gemini-2.0-flash (critical)."""

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
    ]

    recording_mode = not CONSENSUS_CASSETTE_PATH.exists() or not GEMINI_REPLAY_PATH.exists()
    if recording_mode:
        openai_key = env_updates["OPENAI_API_KEY"].strip()
        gemini_key = env_updates["GEMINI_API_KEY"].strip()
        if (not openai_key or openai_key.startswith("dummy")) or (not gemini_key or gemini_key.startswith("dummy")):
            pytest.skip(
                "Consensus cassette missing and OPENAI_API_KEY/GEMINI_API_KEY not configured. Provide real keys to record."
            )

    GEMINI_REPLAY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with monkeypatch.context() as m:
        m.setenv("DEFAULT_MODEL", env_updates["DEFAULT_MODEL"])

        if recording_mode:
            m.setenv("OPENAI_API_KEY", env_updates["OPENAI_API_KEY"])
            m.setenv("GEMINI_API_KEY", env_updates["GEMINI_API_KEY"])
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "record")
        else:
            m.setenv("OPENAI_API_KEY", "dummy-key-for-replay")
            m.setenv("GEMINI_API_KEY", "dummy-key-for-replay")
            m.setenv("GOOGLE_GENAI_CLIENT_MODE", "replay")

        m.setenv("GOOGLE_GENAI_REPLAYS_DIRECTORY", str(GEMINI_REPLAY_DIR))
        m.setenv("GOOGLE_GENAI_REPLAY_ID", GEMINI_REPLAY_ID)

        for key in keys_to_clear:
            m.delenv(key, raising=False)

        # Reset providers and register only OpenAI & Gemini for deterministic behavior
        ModelProviderRegistry.reset_for_testing()
        from providers.gemini import GeminiModelProvider
        from providers.openai_provider import OpenAIModelProvider

        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        # Inject HTTP transport for OpenAI interactions
        inject_transport(monkeypatch, CONSENSUS_CASSETTE_PATH)

        tool = ConsensusTool()

        models_to_consult = [
            {"model": "gpt-5", "stance": "for"},
            {"model": "gemini-2.5-flash", "stance": "against"},
        ]

        # Step 1: CLI agent analysis followed by first model consultation
        step1_arguments = {
            "step": "Evaluate SwiftUI vs UIKit adoption and recommend ONE word (SwiftUI or UIKit).",
            "step_number": 1,
            "total_steps": len(models_to_consult),
            "next_step_required": True,
            "findings": "SwiftUI momentum is strong but UIKit remains battle-tested.",
            "models": models_to_consult,
        }

        step1_response = await tool.execute(step1_arguments)
        assert step1_response and step1_response[0].type == "text"
        step1_data = json.loads(step1_response[0].text)

        assert step1_data["status"] == "analysis_and_first_model_consulted"
        assert step1_data["model_consulted"] == "gpt-5"
        assert step1_data["model_response"]["status"] == "success"
        assert step1_data["model_response"]["metadata"]["provider"] == "openai"
        assert step1_data["model_response"]["verdict"]

        continuation_offer = step1_data.get("continuation_offer")
        assert continuation_offer is not None
        continuation_id = continuation_offer["continuation_id"]

        # Prepare step 2 inputs using the first model's response summary
        summary_for_step2 = step1_data["model_response"]["verdict"][:200]

        step2_arguments = {
            "step": f"Incorporated gpt-5 perspective: {summary_for_step2}",
            "step_number": 2,
            "total_steps": len(models_to_consult),
            "next_step_required": False,
            "findings": "Ready to gather opposing stance before synthesis.",
            "continuation_id": continuation_id,
            "current_model_index": step1_data.get("current_model_index", 1),
            "model_responses": step1_data.get("model_responses", []),
        }

        step2_response = await tool.execute(step2_arguments)

    assert step2_response and step2_response[0].type == "text"
    step2_data = json.loads(step2_response[0].text)

    assert step2_data["status"] == "consensus_workflow_complete"
    assert step2_data["model_consulted"] == "gemini-2.5-flash"
    assert step2_data["model_response"]["metadata"]["provider"] == "google"
    assert step2_data["model_response"]["verdict"]
    assert step2_data["complete_consensus"]["models_consulted"] == [
        "gpt-5:for",
        "gemini-2.5-flash:against",
    ]
    assert step2_data["consensus_complete"] is True

    continuation_offer_final = step2_data.get("continuation_offer")
    assert continuation_offer_final is not None
    assert continuation_offer_final["continuation_id"] == continuation_id

    # Ensure Gemini replay session is flushed to disk before verification
    gemini_provider = ModelProviderRegistry.get_provider_for_model("gemini-2.5-flash")
    if gemini_provider is not None:
        try:
            client = gemini_provider.client
            if hasattr(client, "close"):
                client.close()
        finally:
            if hasattr(gemini_provider, "_client"):
                gemini_provider._client = None

    # Ensure cassettes exist for future replays
    assert CONSENSUS_CASSETTE_PATH.exists()
    assert GEMINI_REPLAY_PATH.exists()

    # Clean up provider registry state after test
    ModelProviderRegistry.reset_for_testing()
