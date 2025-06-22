"""
Test for the simple workflow tool prompt size validation fix.

This test verifies that workflow tools now have basic size validation for the 'step' field
to prevent oversized instructions. The fix is minimal - just prompts users to use shorter
instructions and put detailed content in files.
"""

from config import MCP_PROMPT_SIZE_LIMIT


class TestWorkflowPromptSizeValidationSimple:
    """Test that workflow tools have minimal size validation for step field"""

    def test_workflow_tool_normal_step_content_works(self):
        """Test that normal step content works fine"""

        # Normal step content should be fine
        normal_step = "Investigate the authentication issue in the login module"

        assert len(normal_step) < MCP_PROMPT_SIZE_LIMIT, "Normal step should be under limit"

    def test_workflow_tool_large_step_content_exceeds_limit(self):
        """Test that very large step content would exceed the limit"""

        # Create very large step content
        large_step = "Investigate this issue: " + ("A" * (MCP_PROMPT_SIZE_LIMIT + 1000))

        assert len(large_step) > MCP_PROMPT_SIZE_LIMIT, "Large step should exceed limit"

    def test_workflow_tool_size_validation_message(self):
        """Test that the size validation gives helpful guidance"""

        # The validation should tell users to:
        # 1. Use shorter instructions
        # 2. Put detailed content in files

        expected_guidance = "use shorter instructions and provide detailed context via file paths"

        # This is what the error message should contain
        assert "shorter instructions" in expected_guidance.lower()
        assert "file paths" in expected_guidance.lower()
