"""Integration test for Chat tool code generation with Gemini 2.5 Pro.

This test uses the Google Gemini SDK's built-in record/replay support. To refresh the
cassette, delete the existing JSON file under
``tests/gemini_cassettes/chat_codegen/gemini25_pro_calculator/mldev.json`` and run:

```
GEMINI_API_KEY=<real-key> pytest tests/test_chat_codegen_integration.py::test_chat_codegen_saves_file
```

The test will automatically record a new interaction when the cassette is missing and
the environment variable `GEMINI_API_KEY` is set to a valid key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from providers.gemini import GeminiModelProvider
from providers.registry import ModelProviderRegistry, ProviderType
from tools.chat import ChatTool

REPLAYS_ROOT = Path(__file__).parent / "gemini_cassettes"
CASSETTE_DIR = REPLAYS_ROOT / "chat_codegen"
CASSETTE_PATH = CASSETTE_DIR / "gemini25_pro_calculator" / "mldev.json"
CASSETTE_REPLAY_ID = "chat_codegen/gemini25_pro_calculator/mldev"


@pytest.mark.asyncio
@pytest.mark.no_mock_provider
async def test_chat_codegen_saves_file(monkeypatch, tmp_path):
    """Ensure Gemini 2.5 Pro responses create zen_generated.code when code is emitted."""

    CASSETTE_PATH.parent.mkdir(parents=True, exist_ok=True)

    recording_mode = not CASSETTE_PATH.exists()
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if recording_mode:
        if not gemini_key or gemini_key.startswith("dummy"):
            pytest.skip("Cassette missing and GEMINI_API_KEY not configured. Provide a real key to record.")
        client_mode = "record"
    else:
        gemini_key = "dummy-key-for-replay"
        client_mode = "replay"

    with monkeypatch.context() as m:
        m.setenv("GEMINI_API_KEY", gemini_key)
        m.setenv("DEFAULT_MODEL", "auto")
        m.setenv("GOOGLE_ALLOWED_MODELS", "gemini-2.5-pro")
        m.setenv("GOOGLE_GENAI_CLIENT_MODE", client_mode)
        m.setenv("GOOGLE_GENAI_REPLAYS_DIRECTORY", str(REPLAYS_ROOT))
        m.setenv("GOOGLE_GENAI_REPLAY_ID", CASSETTE_REPLAY_ID)

        # Clear other provider keys to avoid unintended routing
        for key in ["OPENAI_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_API_KEY"]:
            m.delenv(key, raising=False)

        ModelProviderRegistry.reset_for_testing()
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)

        working_dir = tmp_path / "codegen"
        working_dir.mkdir()
        preexisting = working_dir / "zen_generated.code"
        preexisting.write_text("stale contents", encoding="utf-8")

        chat_tool = ChatTool()
        prompt = (
            "Please generate a Python module with functions `add` and `multiply` that perform"
            " basic addition and multiplication. Produce the response using the structured"
            " <GENERATED-CODE> format so the assistant can apply the files directly."
        )

        result = await chat_tool.execute(
            {
                "prompt": prompt,
                "model": "gemini-2.5-pro",
                "working_directory_absolute_path": str(working_dir),
            }
        )

        provider = ModelProviderRegistry.get_provider_for_model("gemini-2.5-pro")
        if provider is not None:
            try:
                provider.client.close()
            except AttributeError:
                pass

        # Reset restriction service cache to avoid leaking allowed-model config
        try:
            from utils import model_restrictions

            model_restrictions._restriction_service = None  # type: ignore[attr-defined]
        except Exception:
            pass

    assert result and result[0].type == "text"
    payload = json.loads(result[0].text)
    assert payload["status"] in {"success", "continuation_available"}

    artifact_path = working_dir / "zen_generated.code"
    assert artifact_path.exists()
    saved = artifact_path.read_text()
    assert "<GENERATED-CODE>" in saved
    assert "<NEWFILE:" in saved
    assert "def add" in saved and "def multiply" in saved
    assert "stale contents" not in saved

    artifact_path.unlink()
