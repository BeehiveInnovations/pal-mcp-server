"""Integration tests for workflow step size validation.

These tests exercise the debug workflow tool end-to-end to ensure that step size
validation operates on the real execution path rather than mocked helpers.
"""

from __future__ import annotations

import json

import pytest

from config import MCP_PROMPT_SIZE_LIMIT
from tools.debug import DebugIssueTool
from tools.shared.exceptions import ToolExecutionError


def build_debug_arguments(**overrides) -> dict[str, object]:
    """Create a minimal set of workflow arguments for DebugIssueTool."""

    base_arguments: dict[str, object] = {
        "step": "Investigate the authentication issue in the login module",
        "step_number": 1,
        "total_steps": 3,
        "next_step_required": True,
        "findings": "Initial observations about the login failure",
        "files_checked": [],
        "relevant_files": [],
        "relevant_context": [],
        "issues_found": [],
        "confidence": "low",
        "use_assistant_model": False,
        # WorkflowRequest accepts optional fields; leave hypothesis/continuation unset
    }

    base_arguments.update(overrides)
    return base_arguments


@pytest.mark.asyncio
async def test_workflow_tool_accepts_normal_step_content() -> None:
    """Verify a typical step executes through the real workflow path."""

    tool = DebugIssueTool()
    arguments = build_debug_arguments()

    responses = await tool.execute(arguments)
    assert len(responses) == 1

    payload = json.loads(responses[0].text)
    assert payload["status"] == "pause_for_investigation"
    assert payload["step_number"] == 1
    assert "error" not in payload


@pytest.mark.asyncio
async def test_workflow_tool_rejects_oversized_step_with_guidance() -> None:
    """Large step content should trigger the size safeguard with helpful guidance."""

    oversized_step = "Investigate this issue: " + ("A" * (MCP_PROMPT_SIZE_LIMIT + 1000))
    tool = DebugIssueTool()
    arguments = build_debug_arguments(step=oversized_step)

    with pytest.raises(ToolExecutionError) as exc_info:
        await tool.execute(arguments)

    output_payload = json.loads(exc_info.value.payload)

    assert output_payload["status"] == "resend_prompt"
    assert output_payload["metadata"]["prompt_size"] > MCP_PROMPT_SIZE_LIMIT

    guidance = output_payload["content"].lower()
    assert "shorter instructions" in guidance
    assert "file paths" in guidance
