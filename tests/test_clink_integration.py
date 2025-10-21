import json
import os
import shutil

import pytest

from tools.clink import CLinkTool


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clink_gemini_single_digit_sum():
    if shutil.which("gemini") is None:
        pytest.skip("gemini CLI is not installed or on PATH")

    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        pytest.skip("Gemini API key is not configured")

    tool = CLinkTool()
    prompt = "Respond with a single digit equal to the sum of 2 + 2. Output only that digit."

    results = await tool.execute(
        {
            "prompt": prompt,
            "cli_name": "gemini",
            "role": "default",
            "absolute_file_paths": [],
            "images": [],
        }
    )

    assert results, "clink tool returned no outputs"
    payload = json.loads(results[0].text)
    status = payload["status"]
    assert status in {"success", "continuation_available"}

    content = payload.get("content", "").strip()
    assert content == "4"

    if status == "continuation_available":
        offer = payload.get("continuation_offer") or {}
        assert offer.get("continuation_id"), "Expected continuation metadata when status indicates availability"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clink_claude_single_digit_sum():
    if shutil.which("claude") is None:
        pytest.skip("claude CLI is not installed or on PATH")

    tool = CLinkTool()
    prompt = "Respond with a single digit equal to the sum of 2 + 2. Output only that digit."

    results = await tool.execute(
        {
            "prompt": prompt,
            "cli_name": "claude",
            "role": "default",
            "absolute_file_paths": [],
            "images": [],
        }
    )

    assert results, "clink tool returned no outputs"
    payload = json.loads(results[0].text)
    status = payload["status"]

    if status == "error":
        metadata = payload.get("metadata") or {}
        reason = payload.get("content") or metadata.get("message") or "Claude CLI reported an error"
        pytest.skip(f"Skipping Claude integration test: {reason}")

    assert status in {"success", "continuation_available"}

    content = payload.get("content", "").strip()
    assert content == "4"

    if status == "continuation_available":
        offer = payload.get("continuation_offer") or {}
        assert offer.get("continuation_id"), "Expected continuation metadata when status indicates availability"
