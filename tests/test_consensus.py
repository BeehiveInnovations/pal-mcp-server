"""
Tests for the Consensus tool
"""

import json
import unittest
from unittest.mock import Mock, patch

from tools.consensus import ConsensusTool, ModelConfig


class TestConsensusTool(unittest.TestCase):
    """Test cases for the Consensus tool"""

    def setUp(self):
        """Set up test fixtures"""
        self.tool = ConsensusTool()

    def test_tool_metadata(self):
        """Test tool metadata is correct"""
        self.assertEqual(self.tool.get_name(), "consensus")
        self.assertTrue("MULTI-MODEL CONSENSUS" in self.tool.get_description())
        self.assertEqual(self.tool.get_default_temperature(), 0.2)

    def test_input_schema(self):
        """Test input schema is properly defined"""
        schema = self.tool.get_input_schema()
        self.assertEqual(schema["type"], "object")
        self.assertIn("prompt", schema["properties"])
        self.assertIn("models", schema["properties"])
        self.assertEqual(schema["required"], ["prompt", "models"])

        # Check that schema includes model configuration information
        models_desc = schema["properties"]["models"]["description"]
        # Check description includes object format
        self.assertIn("model configurations", models_desc)
        self.assertIn("specific stance and custom instructions", models_desc)
        # Check example shows new format
        self.assertIn("'model': 'o3'", models_desc)
        self.assertIn("'stance': 'for'", models_desc)
        self.assertIn("'stance_prompt'", models_desc)

    def test_normalize_stance_basic(self):
        """Test basic stance normalization"""
        # Test basic stances
        self.assertEqual(self.tool._normalize_stance("for"), "for")
        self.assertEqual(self.tool._normalize_stance("against"), "against")
        self.assertEqual(self.tool._normalize_stance("neutral"), "neutral")
        self.assertEqual(self.tool._normalize_stance(None), "neutral")

    def test_normalize_stance_synonyms(self):
        """Test stance synonym normalization"""
        # Supportive synonyms
        self.assertEqual(self.tool._normalize_stance("support"), "for")
        self.assertEqual(self.tool._normalize_stance("favor"), "for")

        # Critical synonyms
        self.assertEqual(self.tool._normalize_stance("critical"), "against")
        self.assertEqual(self.tool._normalize_stance("oppose"), "against")

        # Case insensitive
        self.assertEqual(self.tool._normalize_stance("FOR"), "for")
        self.assertEqual(self.tool._normalize_stance("Support"), "for")
        self.assertEqual(self.tool._normalize_stance("AGAINST"), "against")
        self.assertEqual(self.tool._normalize_stance("Critical"), "against")

        # Test unknown stances default to neutral
        self.assertEqual(self.tool._normalize_stance("supportive"), "neutral")
        self.assertEqual(self.tool._normalize_stance("maybe"), "neutral")
        self.assertEqual(self.tool._normalize_stance("contra"), "neutral")
        self.assertEqual(self.tool._normalize_stance("random"), "neutral")

    def test_model_config_validation(self):
        """Test ModelConfig validation"""
        # Valid config
        config = ModelConfig(model="o3", stance="for", stance_prompt="Custom prompt")
        self.assertEqual(config.model, "o3")
        self.assertEqual(config.stance, "for")
        self.assertEqual(config.stance_prompt, "Custom prompt")

        # Default stance
        config = ModelConfig(model="flash")
        self.assertEqual(config.stance, "neutral")
        self.assertIsNone(config.stance_prompt)

        # Test that empty model is handled by validation elsewhere
        # Pydantic allows empty strings by default, but the tool validates it
        config = ModelConfig(model="")
        self.assertEqual(config.model, "")

    def test_validate_model_combinations(self):
        """Test model combination validation with ModelConfig objects"""
        # Valid combinations
        configs = [
            ModelConfig(model="o3", stance="for"),
            ModelConfig(model="pro", stance="against"),
            ModelConfig(model="grok"),  # neutral default
            ModelConfig(model="o3", stance="against"),
        ]
        valid, skipped = self.tool._validate_model_combinations(configs)
        self.assertEqual(len(valid), 4)
        self.assertEqual(len(skipped), 0)

        # Test max instances per combination (2)
        configs = [
            ModelConfig(model="o3", stance="for"),
            ModelConfig(model="o3", stance="for"),
            ModelConfig(model="o3", stance="for"),  # This should be skipped
            ModelConfig(model="pro", stance="against"),
        ]
        valid, skipped = self.tool._validate_model_combinations(configs)
        self.assertEqual(len(valid), 3)
        self.assertEqual(len(skipped), 1)
        self.assertIn("max 2 instances", skipped[0])

        # Test unknown stances get normalized to neutral
        configs = [
            ModelConfig(model="o3", stance="maybe"),  # Unknown stance -> neutral
            ModelConfig(model="pro", stance="kinda"),  # Unknown stance -> neutral
            ModelConfig(model="grok"),  # Already neutral
        ]
        valid, skipped = self.tool._validate_model_combinations(configs)
        self.assertEqual(len(valid), 3)  # All are valid (normalized to neutral)
        self.assertEqual(len(skipped), 0)  # None skipped

        # Verify normalization worked
        self.assertEqual(valid[0].stance, "neutral")  # maybe -> neutral
        self.assertEqual(valid[1].stance, "neutral")  # kinda -> neutral
        self.assertEqual(valid[2].stance, "neutral")  # already neutral

    def test_get_stance_enhanced_prompt(self):
        """Test stance-enhanced prompt generation"""
        # Test that stance prompts are injected correctly
        for_prompt = self.tool._get_stance_enhanced_prompt("for")
        self.assertIn("SUPPORTIVE PERSPECTIVE", for_prompt)

        against_prompt = self.tool._get_stance_enhanced_prompt("against")
        self.assertIn("CRITICAL PERSPECTIVE", against_prompt)

        neutral_prompt = self.tool._get_stance_enhanced_prompt("neutral")
        self.assertIn("BALANCED PERSPECTIVE", neutral_prompt)

        # Test custom stance prompt
        custom_prompt = "Focus on user experience and business value"
        enhanced = self.tool._get_stance_enhanced_prompt("for", custom_prompt)
        self.assertIn(custom_prompt, enhanced)
        self.assertNotIn("SUPPORTIVE PERSPECTIVE", enhanced)  # Should use custom instead

    def test_format_consensus_output(self):
        """Test consensus output formatting"""
        responses = [
            {"model": "o3", "stance": "for", "status": "success", "verdict": "Good idea"},
            {"model": "pro", "stance": "against", "status": "success", "verdict": "Bad idea"},
            {"model": "grok", "stance": "neutral", "status": "error", "error": "Timeout"},
        ]
        skipped = ["flash:maybe (invalid stance)"]

        output = self.tool._format_consensus_output(responses, skipped)
        output_data = json.loads(output)

        self.assertEqual(output_data["status"], "consensus_success")
        self.assertEqual(output_data["models_used"], ["o3:for", "pro:against"])
        self.assertEqual(output_data["models_skipped"], skipped)
        self.assertEqual(output_data["models_errored"], ["grok"])
        self.assertIn("next_steps", output_data)

    @patch("tools.consensus.ConsensusTool.get_model_provider")
    async def test_execute_with_model_configs(self, mock_get_provider):
        """Test execute with ModelConfig objects"""
        # Mock provider
        mock_provider = Mock()
        mock_response = Mock()
        mock_response.content = "Test response"
        mock_provider.generate_content.return_value = mock_response
        mock_get_provider.return_value = mock_provider

        # Test with ModelConfig objects including custom stance prompts
        models = [
            {"model": "o3", "stance": "support", "stance_prompt": "Focus on user benefits"},  # Test synonym
            {"model": "pro", "stance": "critical", "stance_prompt": "Focus on technical risks"},  # Test synonym
            {"model": "grok", "stance": "neutral"},
        ]

        result = await self.tool.execute({"prompt": "Test prompt", "models": models})

        # Verify all models were called
        self.assertEqual(mock_get_provider.call_count, 3)

        # Check that response contains expected format
        response_text = result[0].text
        response_data = json.loads(response_text)
        self.assertEqual(response_data["status"], "consensus_success")
        self.assertEqual(len(response_data["models_used"]), 3)

        # Verify stance normalization worked
        models_used = response_data["models_used"]
        self.assertIn("o3:for", models_used)  # support -> for
        self.assertIn("pro:against", models_used)  # critical -> against
        self.assertIn("grok", models_used)  # neutral (no suffix)


if __name__ == "__main__":
    unittest.main()
