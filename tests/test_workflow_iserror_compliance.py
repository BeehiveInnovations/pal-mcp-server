"""
Regression tests for isError-compliance in pal-mcp-server workflow mixin.

The `_call_expert_analysis` method in `tools/workflow/workflow_mixin.py`
caught `except Exception as e:` and returned `{"error": str(e), "status":
"analysis_error"}` as a dict. FastMCP wraps that as success content
with `isError=false`, so MCP clients treat the failure as data and the
LLM often proceeds as if the call had succeeded.

The fix replaces the swallowed-error return with
`raise ToolExecutionError(...)` so FastMCP sets `isError=true` on the
wire while preserving the formatted message in content for the LLM.

Reference: https://composio.dev/blog/mcp-security-vulnerabilities (Dayna
Blackwell MCP security audit, June 2026).
"""

import json

import pytest

from tools.shared.exceptions import ToolExecutionError


class TestWorkflowIsErrorCompliance:
    """Workflow expert-analysis failure must surface as ToolExecutionError."""

    def setup_method(self):
        """Set up clean state before each test."""
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.registry import ModelProviderRegistry

        registry = ModelProviderRegistry()
        registry._providers.clear()
        registry._initialized_providers.clear()

    def teardown_method(self):
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        from providers.registry import ModelProviderRegistry

        registry = ModelProviderRegistry()
        registry._providers.clear()
        registry._initialized_providers.clear()

    def test_expert_analysis_failure_raises_tool_execution_error(self):
        """A failing expert-analysis call inside the workflow mixin must
        raise ToolExecutionError (which maps to isError=true on the MCP
        wire) instead of returning a {'error': ...} dict that FastMCP
        would treat as success content."""
        from tools.workflow.workflow_mixin import BaseWorkflowMixin

        mixin = BaseWorkflowMixin.__new__(BaseWorkflowMixin)

        # Force the model call to raise
        async def _boom(*args, **kwargs):
            raise RuntimeError("upstream model timeout")

        # Inject the failing provider into the mixin's model_context
        class _FakeModelContext:
            def __init__(self):
                self.provider = type(
                    "_P", (), {"generate_content": _boom}
                )()

        mixin._model_context = _FakeModelContext()

        async def _call_it():
            return await mixin._call_expert_analysis({}, request=None)

        import asyncio

        with pytest.raises(ToolExecutionError) as exc_info:
            asyncio.run(_call_it())

        # The ToolExecutionError payload should be JSON-encoded
        # containing the original error message
        payload = exc_info.value.payload
        if isinstance(payload, str):
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {"error": payload}
        else:
            data = payload

        assert "upstream model timeout" in str(data.get("error", ""))
        assert data.get("status") == "analysis_error"
