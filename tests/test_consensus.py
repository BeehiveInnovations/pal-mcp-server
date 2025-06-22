"""
Tests for the Consensus tool using WorkflowTool architecture.
"""

import json
from unittest.mock import Mock, patch

import pytest

from tools.consensus import ConsensusRequest, ConsensusTool
from tools.models import ToolModelCategory


class TestConsensusTool:
    """Test suite for ConsensusTool using WorkflowTool architecture."""

    def test_tool_metadata(self):
        """Test basic tool metadata and configuration."""
        tool = ConsensusTool()

        assert tool.get_name() == "consensus"
        assert "COMPREHENSIVE CONSENSUS WORKFLOW" in tool.get_description()
        assert tool.get_default_temperature() == 0.2  # TEMPERATURE_ANALYTICAL
        assert tool.get_model_category() == ToolModelCategory.EXTENDED_REASONING
        assert tool.requires_model() is True

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
        # relevant_files should also be excluded
        assert "relevant_files" not in schema["properties"]

        # Verify workflow fields that should NOT be present
        assert "files_checked" not in schema["properties"]
        assert "hypothesis" not in schema["properties"]
        assert "issues_found" not in schema["properties"]
        assert "temperature" not in schema["properties"]
        assert "thinking_mode" not in schema["properties"]
        assert "use_websearch" not in schema["properties"]

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

    @pytest.mark.asyncio
    async def test_execute_workflow_step1(self):
        """Test workflow execution for step 1."""
        tool = ConsensusTool()

        arguments = {
            "step": "Initial analysis of proposal",
            "step_number": 1,
            "total_steps": 4,
            "next_step_required": True,
            "findings": "Found pros and cons",
            "confidence": "medium",
            "models": [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}],
            "relevant_files": ["/proposal.md"],
        }

        with patch.object(tool, "is_effective_auto_mode", return_value=False):
            with patch.object(tool, "get_model_provider", return_value=Mock()):
                result = await tool.execute_workflow(arguments)

        assert len(result) == 1
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Verify step 1 response structure
        assert response_data["status"] == "consulting_models"
        assert response_data["step_number"] == 1
        assert "continuation_id" in response_data

    @pytest.mark.asyncio
    async def test_execute_workflow_model_consultation(self):
        """Test workflow execution for model consultation steps."""
        tool = ConsensusTool()
        tool.models_to_consult = [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}]
        tool.initial_prompt = "Test prompt"

        arguments = {
            "step": "Processing model response",
            "step_number": 2,
            "total_steps": 4,
            "next_step_required": True,
            "findings": "Model provided perspective",
            "confidence": "medium",
            "continuation_id": "test-id",
            "current_model_index": 0,
        }

        # Mock the _consult_model method instead to return a proper dict
        mock_model_response = {
            "model": "flash",
            "stance": "neutral",
            "status": "success",
            "verdict": "Model analysis response",
            "metadata": {"provider": "gemini"},
        }

        with patch.object(tool, "_consult_model", return_value=mock_model_response):
            result = await tool.execute_workflow(arguments)

        assert len(result) == 1
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Verify model consultation response
        assert response_data["status"] == "model_consulted"
        assert response_data["model_consulted"] == "flash"
        assert response_data["model_stance"] == "neutral"
        assert "model_response" in response_data
        assert response_data["model_response"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_consult_model_error_handling(self):
        """Test error handling in model consultation."""
        tool = ConsensusTool()
        tool.initial_prompt = "Test prompt"

        # Mock provider to raise an error
        mock_provider = Mock()
        mock_provider.generate_content.side_effect = Exception("Model error")

        with patch.object(tool, "get_model_provider", return_value=mock_provider):
            result = await tool._consult_model(
                {"model": "test-model", "stance": "neutral"}, Mock(relevant_files=[], continuation_id=None, images=None)
            )

        assert result["status"] == "error"
        assert result["error"] == "Model error"
        assert result["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_consult_model_with_images(self):
        """Test model consultation with images."""
        tool = ConsensusTool()
        tool.initial_prompt = "Test prompt"

        # Mock provider
        mock_provider = Mock()
        mock_response = Mock(content="Model response with image analysis")
        mock_provider.generate_content.return_value = mock_response
        mock_provider.get_provider_type.return_value = Mock(value="gemini")

        test_images = ["/path/to/image1.png", "/path/to/image2.jpg"]

        with patch.object(tool, "get_model_provider", return_value=mock_provider):
            result = await tool._consult_model(
                {"model": "test-model", "stance": "neutral"},
                Mock(relevant_files=[], continuation_id=None, images=test_images),
            )

        # Verify that images were passed to generate_content
        mock_provider.generate_content.assert_called_once()
        call_args = mock_provider.generate_content.call_args
        assert call_args.kwargs.get("images") == test_images

        assert result["status"] == "success"
        assert result["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_handle_work_completion(self):
        """Test work completion handling for consensus workflow."""
        tool = ConsensusTool()
        tool.initial_prompt = "Test prompt"
        tool.accumulated_responses = [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}]

        request = Mock(confidence="high")
        response_data = {}

        result = await tool.handle_work_completion(response_data, request, {})

        assert result["consensus_complete"] is True
        assert result["status"] == "consensus_workflow_complete"
        assert "complete_consensus" in result
        assert result["complete_consensus"]["models_consulted"] == ["flash:neutral", "o3-mini:for"]
        assert result["complete_consensus"]["total_responses"] == 2

    def test_handle_work_continuation(self):
        """Test work continuation handling between steps."""
        tool = ConsensusTool()
        tool.models_to_consult = [{"model": "flash", "stance": "neutral"}, {"model": "o3-mini", "stance": "for"}]

        # Test after step 1
        request = Mock(step_number=1, current_model_index=0)
        response_data = {}

        result = tool.handle_work_continuation(response_data, request)
        assert result["status"] == "consulting_models"
        assert result["next_model"] == {"model": "flash", "stance": "neutral"}

        # Test between model consultations
        request = Mock(step_number=2, current_model_index=1)
        response_data = {}

        result = tool.handle_work_continuation(response_data, request)
        assert result["status"] == "consulting_next_model"
        assert result["next_model"] == {"model": "o3-mini", "stance": "for"}
        assert result["models_remaining"] == 1

    def test_customize_workflow_response(self):
        """Test response customization for consensus workflow."""
        tool = ConsensusTool()
        tool.accumulated_responses = [{"model": "test", "response": "data"}]

        # Test different step numbers
        request = Mock(step_number=1, total_steps=4)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "initial_analysis_complete"

        request = Mock(step_number=2, total_steps=4)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "consulting_models"

        request = Mock(step_number=4, total_steps=4)
        response_data = {}
        result = tool.customize_workflow_response(response_data, request)
        assert result["consensus_workflow_status"] == "ready_for_synthesis"


if __name__ == "__main__":
    import unittest

    unittest.main()
