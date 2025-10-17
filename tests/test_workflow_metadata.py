"""
Tests for workflow tool metadata functionality.

This test ensures that workflow tools include metadata (provider_used and model_used)
in their responses, similar to regular tools, for consistent tracking across all tool types.
"""

import json
import os

import pytest

from providers.registry import ModelProviderRegistry
from providers.shared import ProviderType
from tools.debug import DebugIssueTool
from tools.shared.exceptions import ToolExecutionError


class TestWorkflowMetadata:
    """Test cases for workflow tool metadata functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

        # Clear provider registry
        registry = ModelProviderRegistry()
        registry._providers.clear()
        registry._initialized_providers.clear()

    def teardown_method(self):
        """Clean up after each test."""
        # Clear restriction service cache
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @pytest.mark.no_mock_provider
    def test_workflow_metadata_in_response(self):
        """
        Test that workflow tools include metadata in their responses.

        This test verifies that workflow tools (like debug) include provider_used
        and model_used metadata in their responses, ensuring consistency with
        regular tools for tracking purposes.
        """
        # Save original environment
        original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENROUTER_ALLOWED_MODELS",
        ]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up test environment with OpenRouter API key
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("OPENROUTER_ALLOWED_MODELS", None)  # Clear any restrictions
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

            # Register OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Create debug tool
            debug_tool = DebugIssueTool()

            # Create mock model context like server.py does
            from utils.model_context import ModelContext

            model_name = "flash"
            model_context = ModelContext(model_name)

            # Create arguments with model context (like server.py provides)
            arguments = {
                "step": "Investigating the test issue to check metadata functionality",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": False,  # Final step to trigger completion
                "findings": "Initial findings for test",
                "model": model_name,
                "confidence": "high",
                "_model_context": model_context,
                "_resolved_model_name": model_name,
            }

            # Execute the workflow tool
            import asyncio

            result = asyncio.run(debug_tool.execute_workflow(arguments))

            # Parse the JSON response
            assert len(result) == 1
            response_text = result[0].text
            response_data = json.loads(response_text)

            # Verify metadata is present
            assert "metadata" in response_data, "Workflow response should include metadata"
            metadata = response_data["metadata"]

            # Verify required metadata fields
            assert "tool_name" in metadata, "Metadata should include tool_name"
            assert "model_used" in metadata, "Metadata should include model_used"
            assert "provider_used" in metadata, "Metadata should include provider_used"

            # Verify metadata values
            assert metadata["tool_name"] == "debug", "tool_name should be 'debug'"
            assert metadata["model_used"] == model_name, f"model_used should be '{model_name}'"
            assert metadata["provider_used"] == "openrouter", "provider_used should be 'openrouter'"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_workflow_metadata_in_error_response(self):
        """
        Test that workflow tools include metadata even in error responses.
        """
        # Save original environment
        original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENROUTER_ALLOWED_MODELS",
        ]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up test environment with OpenRouter API key
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("OPENROUTER_ALLOWED_MODELS", None)  # Clear any restrictions
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

            # Register OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Create debug tool
            debug_tool = DebugIssueTool()

            # Create arguments with invalid data to trigger error
            model_name = "flash"
            arguments = {
                "step": "Test step",
                "step_number": "invalid",  # This should cause an error during validation
                "_resolved_model_name": model_name,
            }

            # Execute the workflow tool - should fail gracefully
            import asyncio

            with pytest.raises(ToolExecutionError) as exc_info:
                asyncio.run(debug_tool.execute(arguments))

            response_data = json.loads(exc_info.value.payload)

            # Verify it's an error response with metadata
            assert "status" in response_data
            assert "error" in response_data or "content" in response_data
            assert "metadata" in response_data, "Error responses should include metadata"

            metadata = response_data["metadata"]
            assert "tool_name" in metadata, "Error metadata should include tool_name"
            assert metadata["tool_name"] == "debug", "tool_name should be 'debug'"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_workflow_metadata_fallback_handling(self):
        """
        Test that workflow tools handle metadata gracefully when model context is missing.
        """
        # Save original environment
        original_env = {}
        for key in ["OPENROUTER_ALLOWED_MODELS"]:
            original_env[key] = os.environ.get(key)

        try:
            # Clear any restrictions
            os.environ.pop("OPENROUTER_ALLOWED_MODELS", None)

            # Create debug tool
            debug_tool = DebugIssueTool()

            # Create arguments without model context (fallback scenario)
            arguments = {
                "step": "Test step without model context",
                "step_number": 1,
                "total_steps": 1,
                "next_step_required": False,
                "findings": "Test findings",
                "model": "flash",
                "confidence": "low",
                # No _model_context or _resolved_model_name
            }

            # Execute the workflow tool
            import asyncio

            result = asyncio.run(debug_tool.execute_workflow(arguments))

            # Parse the JSON response
            assert len(result) == 1
            response_text = result[0].text
            response_data = json.loads(response_text)

            # Verify metadata is still present with fallback values
            assert "metadata" in response_data, "Workflow response should include metadata even in fallback"
            metadata = response_data["metadata"]

            # Verify fallback metadata
            assert "tool_name" in metadata, "Fallback metadata should include tool_name"
            assert "model_used" in metadata, "Fallback metadata should include model_used"
            assert "provider_used" in metadata, "Fallback metadata should include provider_used"

            assert metadata["tool_name"] == "debug", "tool_name should be 'debug'"
            assert metadata["model_used"] == "flash", "model_used should be from request"
            assert metadata["provider_used"] == "unknown", "provider_used should be 'unknown' in fallback"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    @pytest.mark.no_mock_provider
    def test_workflow_metadata_preserves_existing_response_fields(self):
        """
        Test that adding metadata doesn't interfere with existing workflow response fields.
        """
        # Save original environment
        original_env = {}
        for key in [
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "XAI_API_KEY",
            "OPENROUTER_API_KEY",
            "OPENROUTER_ALLOWED_MODELS",
        ]:
            original_env[key] = os.environ.get(key)

        try:
            # Set up test environment
            os.environ.pop("GEMINI_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("XAI_API_KEY", None)
            os.environ.pop("OPENROUTER_ALLOWED_MODELS", None)  # Clear any restrictions
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"

            # Register OpenRouter provider
            from providers.openrouter import OpenRouterProvider

            ModelProviderRegistry.register_provider(ProviderType.OPENROUTER, OpenRouterProvider)

            # Create debug tool
            debug_tool = DebugIssueTool()

            # Create mock model context
            from utils.model_context import ModelContext

            model_name = "flash"
            model_context = ModelContext(model_name)

            # Create arguments for intermediate step
            arguments = {
                "step": "Testing intermediate step for metadata preservation",
                "step_number": 1,
                "total_steps": 3,
                "next_step_required": True,  # Intermediate step
                "findings": "Intermediate findings",
                "model": model_name,
                "confidence": "medium",
                "_model_context": model_context,
                "_resolved_model_name": model_name,
            }

            # Execute the workflow tool
            import asyncio

            result = asyncio.run(debug_tool.execute_workflow(arguments))

            # Parse the JSON response
            assert len(result) == 1
            response_text = result[0].text
            response_data = json.loads(response_text)

            # Verify standard workflow fields are preserved
            assert "status" in response_data, "Standard workflow status should be preserved"
            assert "step_number" in response_data, "Standard workflow step_number should be preserved"
            assert "total_steps" in response_data, "Standard workflow total_steps should be preserved"
            assert "next_step_required" in response_data, "Standard workflow next_step_required should be preserved"

            # Verify metadata was added without breaking existing fields
            assert "metadata" in response_data, "Metadata should be added"
            metadata = response_data["metadata"]
            assert metadata["tool_name"] == "debug"
            assert metadata["model_used"] == model_name
            assert metadata["provider_used"] == "openrouter"

            # Verify specific intermediate step fields
            assert response_data["next_step_required"] is True, "next_step_required should be preserved"
            assert response_data["step_number"] == 1, "step_number should be preserved"

        finally:
            # Restore original environment
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
