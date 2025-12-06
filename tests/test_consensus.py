"""
Tests for the Consensus tool using WorkflowTool architecture.
"""

from unittest.mock import Mock

import pytest

from tools.consensus import ConsensusRequest, ConsensusTool
from tools.models import ToolModelCategory


class TestConsensusTool:
    """Test suite for ConsensusTool using WorkflowTool architecture."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = ConsensusTool()

        assert tool.get_name() == "consensus"
        assert "consensus" in tool.get_description()
        assert tool.get_default_temperature() == 1.0  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is False  # Consensus manages its own models

    def test_request_validation_step1(self):
        """Test Pydantic request model validation for step 1."""
        # Valid step 1 request with models
        step1_request = ConsensusRequest(
            step="Analyzing the real-time collaboration proposal",
            step_number=1,
            total_steps=4,  # 1 (Claude) + 2 models + 1 (synthesis)
            next_step_required=True,
            findings="Initial assessment shows strong value but technical complexity",
            confidence="medium",
            models=[{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
            relevant_files=["/proposal.md"],
        )

        assert step1_request.step_number == 1
        assert step1_request.confidence == "medium"
        assert len(step1_request.models) == 2
        assert step1_request.models[0]["model"] == "flash"

    def test_request_validation_missing_models_step1(self):
        """Test that step 1 requires models field."""
        with pytest.raises(ValueError, match="Step 1 requires 'models' field"):
            ConsensusRequest(
                step="Test step",
                step_number=1,
                total_steps=3,
                next_step_required=True,
                findings="Test findings",
                # Missing models field
            )

    def test_request_validation_later_steps(self):
        """Test request validation for steps 2+."""
        # Step 2+ doesn't require models field
        step2_request = ConsensusRequest(
            step="Processing first model response",
            step_number=2,
            total_steps=4,
            next_step_required=True,
            findings="Model provided supportive perspective",
            confidence="medium",
            continuation_id="test-id",
            current_model_index=1,
        )

        assert step2_request.step_number == 2
        assert step2_request.models is None  # Not required after step 1

    def test_request_validation_duplicate_model_stance(self):
        """Test that duplicate model+stance combinations are rejected."""
        # Valid: same model with different stances
        valid_request = ConsensusRequest(
            step="Analyze this proposal",
            step_number=1,
            total_steps=1,
            next_step_required=True,
            findings="Initial analysis",
            models=[
                {"model": "o3", "stance": "for"},
                {"model": "o3", "stance": "against"},
                {"model": "flash", "stance": "neutral"},
            ],
            continuation_id="test-id",
        )
        assert len(valid_request.models) == 3

        # Invalid: duplicate model+stance combination
        with pytest.raises(ValueError, match="Duplicate model \\+ stance combination"):
            ConsensusRequest(
                step="Analyze this proposal",
                step_number=1,
                total_steps=1,
                next_step_required=True,
                findings="Initial analysis",
                models=[
                    {"model": "o3", "stance": "for"},
                    {"model": "flash", "stance": "neutral"},
                    {"model": "o3", "stance": "for"},  # Duplicate!
                ],
                continuation_id="test-id",
            )

    def test_input_schema_generation(self):
        """Test that input schema is generated correctly."""
        tool = ConsensusTool()
        schema = tool.get_input_schema()

        # Verify consensus workflow fields are present
        assert "step" in schema["properties"]
        assert "step_number" in schema["properties"]
        assert "total_steps" in schema["properties"]
        assert "next_step_required" in schema["properties"]
        assert "findings" in schema["properties"]
        # confidence field should be excluded
        assert "confidence" not in schema["properties"]
        assert "models" in schema["properties"]
        # relevant_files should be present as it's used by consensus
        assert "relevant_files" in schema["properties"]

        # model field should NOT be present as consensus uses 'models' field instead
        assert "model" not in schema["properties"]

        # Verify workflow fields that should NOT be present
        assert "files_checked" not in schema["properties"]
        assert "hypothesis" not in schema["properties"]
        assert "issues_found" not in schema["properties"]
        assert "temperature" not in schema["properties"]
        assert "thinking_mode" not in schema["properties"]

        # Images should be present now
        assert "images" in schema["properties"]
        assert schema["properties"]["images"]["type"] == "array"
        assert schema["properties"]["images"]["items"]["type"] == "string"

        # Verify field types
        assert schema["properties"]["step"]["type"] == "string"
        assert schema["properties"]["step_number"]["type"] == "integer"
        assert schema["properties"]["models"]["type"] == "array"

        # Verify models array structure
        models_items = schema["properties"]["models"]["items"]
        assert models_items["type"] == "object"
        assert "model" in models_items["properties"]
        assert "stance" in models_items["properties"]
        assert "stance_prompt" in models_items["properties"]

    def test_get_required_actions(self):
        """Test required actions for different consensus phases."""
        tool = ConsensusTool()

        # Step 1: Claude's initial analysis
        actions = tool.get_required_actions(1, "exploring", "Initial findings", 4)
        assert any("initial analysis" in action for action in actions)
        assert any("consult other models" in action for action in actions)

        # Step 2-3: Model consultations
        actions = tool.get_required_actions(2, "medium", "Model findings", 4)
        assert any("Review the model response" in action for action in actions)

        # Final step: Synthesis
        actions = tool.get_required_actions(4, "high", "All findings", 4)
        assert any("All models have been consulted" in action for action in actions)
        assert any("Synthesize all perspectives" in action for action in actions)

    def test_prepare_step_data(self):
        """Test step data preparation for consensus workflow."""
        tool = ConsensusTool()
        request = ConsensusRequest(
            step="Test step",
            step_number=1,
            total_steps=3,
            next_step_required=True,
            findings="Test findings",
            confidence="medium",
            models=[{"model": "test"}],
            relevant_files=["/test.py"],
        )

        step_data = tool.prepare_step_data(request)

        # Verify consensus-specific fields
        assert step_data["step"] == "Test step"
        assert step_data["findings"] == "Test findings"
        assert step_data["relevant_files"] == ["/test.py"]

        # Verify unused workflow fields are empty
        assert step_data["files_checked"] == []
        assert step_data["relevant_context"] == []
        assert step_data["issues_found"] == []
        assert step_data["hypothesis"] is None

    def test_stance_enhanced_prompt_generation(self):
        """Test stance-enhanced prompt generation."""
        tool = ConsensusTool()

        # Test different stances
        for_prompt = tool._get_stance_enhanced_prompt("for")
        assert "SUPPORTIVE PERSPECTIVE" in for_prompt

        against_prompt = tool._get_stance_enhanced_prompt("against")
        assert "CRITICAL PERSPECTIVE" in against_prompt

        neutral_prompt = tool._get_stance_enhanced_prompt("neutral")
        assert "BALANCED PERSPECTIVE" in neutral_prompt

        # Test custom stance prompt
        custom = "Focus on specific aspects"
        custom_prompt = tool._get_stance_enhanced_prompt("for", custom)
        assert custom in custom_prompt
        assert "SUPPORTIVE PERSPECTIVE" not in custom_prompt

    def test_should_call_expert_analysis(self):
        """Test that consensus workflow doesn't use expert analysis."""
        tool = ConsensusTool()
        assert tool.should_call_expert_analysis({}) is False
        assert tool.requires_expert_analysis() is False

    def test_execute_workflow_step1_basic(self):
        """Test basic workflow validation for step 1."""
        tool = ConsensusTool()

        # Test that step 1 sets up the workflow correctly
        arguments = {
            "step": "Initial analysis of proposal",
            "step_number": 1,
            "total_steps": 2,
            "next_step_required": True,
            "findings": "Found pros and cons",
            "models": [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
        }

        # Verify models_to_consult is set correctly from step 1
        request = tool.get_workflow_request_model()(**arguments)
        assert len(request.models) == 2
        assert request.models[0]["model"] == "flash"
        assert request.models[1]["model"] == "o3-mini"

    def test_execute_workflow_total_steps_calculation(self):
        """Test that total_steps is calculated correctly from models."""
        tool = ConsensusTool()

        # Test with 2 models
        arguments = {
            "step": "Initial analysis",
            "step_number": 1,
            "total_steps": 4,  # This should be corrected to 2
            "next_step_required": True,
            "findings": "Analysis complete",
            "models": [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
        }

        request = tool.get_workflow_request_model()(**arguments)
        # The tool should set total_steps = len(models) = 2
        assert len(request.models) == 2

    def test_consult_model_basic_structure(self):
        """Test basic model consultation structure."""
        tool = ConsensusTool()

        # Test that _get_stance_enhanced_prompt works
        for_prompt = tool._get_stance_enhanced_prompt("for")
        against_prompt = tool._get_stance_enhanced_prompt("against")
        neutral_prompt = tool._get_stance_enhanced_prompt("neutral")

        assert "SUPPORTIVE PERSPECTIVE" in for_prompt
        assert "CRITICAL PERSPECTIVE" in against_prompt
        assert "BALANCED PERSPECTIVE" in neutral_prompt

    def test_model_configuration_validation(self):
        """Test model configuration validation."""
        tool = ConsensusTool()

        # Test single model config
        models = [{"model": "flash", "stance": "neutral"}]
        arguments = {
            "step": "Test",
            "step_number": 1,
            "total_steps": 1,
            "next_step_required": False,
            "findings": "Test findings",
            "models": models,
        }

        request = tool.get_workflow_request_model()(**arguments)
        assert len(request.models) == 1
        assert request.models[0]["model"] == "flash"
        assert request.models[0]["stance"] == "neutral"

    def test_handle_work_continuation(self):
        """Test work continuation handling - legacy method for compatibility."""
        tool = ConsensusTool()
        tool.models_to_consult = [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}]

        # Note: In the new workflow, model consultation happens DURING steps in execute_workflow
        # This method is kept for compatibility but not actively used in the step-by-step flow

        # Test after step 1
        request = Mock(step_number=1, current_model_index=0)
        response_data = {}

        result = tool.handle_work_continuation(response_data, request)
        # The method still exists but returns legacy status for compatibility
        assert "status" in result

        # Test between model consultations
        request = Mock(step_number=2, current_model_index=1)
        response_data = {}

        result = tool.handle_work_continuation(response_data, request)
        assert "status" in result

    def test_customize_workflow_response(self):
        """Test response customization for consensus workflow."""
        tool = ConsensusTool()
        tool.accumulated_responses = [{"model": "test", "response": "data"}]

        # Test different step numbers (new workflow: 2 models = 2 steps)
        request = Mock(step_number=1, total_steps=2)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "initial_analysis_complete"

        request = Mock(step_number=2, total_steps=2)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "ready_for_synthesis"

    @pytest.mark.asyncio
    async def test_consensus_with_relevant_files_model_context_fix(self):
        """Test that consensus tool properly handles relevant_files without RuntimeError.

        This is a regression test for the bug where _prepare_file_content_for_prompt
        was called without model_context parameter, causing RuntimeError:
        'Model context not provided for file preparation'

        Bug details:
        - Occurred when consensus tool processed requests with relevant_files
        - _consult_model method called _prepare_file_content_for_prompt without model_context
        - Method expected model_context parameter but got None (default value)
        - Runtime validation in base_tool.py threw RuntimeError
        """
        from unittest.mock import AsyncMock, Mock, patch

        from utils.model_context import ModelContext

        tool = ConsensusTool()

        # Create a mock request with relevant_files (the trigger condition)
        mock_request = Mock()
        mock_request.relevant_files = ["/test/file1.py", "/test/file2.js"]
        mock_request.continuation_id = None

        # Mock model configuration
        model_config = {"model": "flash", "stance": "neutral"}

        # Mock the provider and model name resolution
        with (
            patch.object(tool, "get_model_provider") as mock_get_provider,
            patch.object(tool, "_prepare_file_content_for_prompt") as mock_prepare_files,
            patch.object(tool, "_get_stance_enhanced_prompt") as mock_get_prompt,
            patch.object(tool, "get_name", return_value="consensus"),
        ):

            # Setup mocks
            mock_provider = Mock()
            mock_provider.generate_content = AsyncMock(return_value={"response": "test response"})
            mock_get_provider.return_value = mock_provider
            mock_prepare_files.return_value = ("file content", [])
            mock_get_prompt.return_value = "system prompt"

            # Set up the tool's attributes that would be set during normal execution
            tool.original_proposal = "Test proposal"

            try:
                # This should not raise RuntimeError after the fix
                # The method should create ModelContext and pass it to _prepare_file_content_for_prompt
                await tool._consult_model(model_config, mock_request)

                # Verify that _prepare_file_content_for_prompt was called with model_context
                mock_prepare_files.assert_called_once()
                call_args = mock_prepare_files.call_args

                # Check that model_context was passed as keyword argument
                assert "model_context" in call_args.kwargs, "model_context should be passed as keyword argument"

                # Verify the model_context is a proper ModelContext instance
                model_context = call_args.kwargs["model_context"]
                assert isinstance(model_context, ModelContext), "model_context should be ModelContext instance"

                # Verify model_context properties are correct
                assert model_context.model_name == "flash"
                # Note: provider is accessed lazily, conversation_history and tool_name
                # are not part of ModelContext constructor in current implementation

            except RuntimeError as e:
                if "Model context not provided" in str(e):
                    pytest.fail("The model_context fix is not working. RuntimeError still occurs: " + str(e))
                else:
                    # Re-raise if it's a different RuntimeError
                    raise


if __name__ == "__main__":
    import unittest

    unittest.main()
