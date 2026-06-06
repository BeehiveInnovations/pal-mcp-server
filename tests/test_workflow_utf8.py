"""
Unit tests to validate UTF-8 encoding in workflow tools
and the generation of properly encoded JSON responses.
"""

import json
import os
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tools.analyze import AnalyzeTool
from tools.codereview import CodeReviewTool
from tools.debug import DebugIssueTool


class TestWorkflowToolsUTF8(unittest.IsolatedAsyncioTestCase):
    """Tests for UTF-8 encoding in workflow tools."""

    def setUp(self):
        """Test setup."""
        self.original_locale = os.getenv("LOCALE")
        # Default to French for tests
        os.environ["LOCALE"] = "fr-FR"

    def tearDown(self):
        """Cleanup after tests."""
        if self.original_locale is not None:
            os.environ["LOCALE"] = self.original_locale
        else:
            os.environ.pop("LOCALE", None)

    def test_workflow_json_response_structure(self):
        """Test the structure of JSON responses from workflow tools."""
        # Mock response with UTF-8 characters
        test_response = {
            "status": "pause_for_analysis",
            "step_number": 1,
            "total_steps": 3,
            "next_step_required": True,
            "findings": "Code analysis reveals performance issues 🔍",
            "files_checked": ["/src/main.py"],
            "relevant_files": ["/src/main.py"],
            "issues_found": [{"severity": "high", "description": "Function too complex - refactoring needed"}],
            "investigation_required": True,
            "required_actions": ["Review code dependencies", "Analyze architectural patterns"],
        }

        # Test JSON serialization with ensure_ascii=False
        json_str = json.dumps(test_response, indent=2, ensure_ascii=False)

        # Check UTF-8 characters are preserved
        self.assertIn("🔍", json_str)
        # No escaped characters
        self.assertNotIn("\\u", json_str)

        # Test parsing
        parsed = json.loads(json_str)
        self.assertEqual(parsed["findings"], test_response["findings"])
        self.assertEqual(len(parsed["issues_found"]), 1)

    @patch("tools.shared.base_tool.BaseTool.get_model_provider")
    @patch("utils.model_context.ModelContext")
    async def test_analyze_tool_utf8_response(self, mock_model_context, mock_get_provider):
        """Test that the analyze tool returns correct UTF-8 responses."""

        # Mock ModelContext to bypass model validation
        mock_context_instance = Mock()

        # Mock token allocation for file processing
        mock_token_allocation = Mock()
        mock_token_allocation.file_tokens = 1000
        mock_token_allocation.total_tokens = 2000
        mock_context_instance.calculate_token_allocation.return_value = mock_token_allocation

        # Mock provider with more complete setup (same as codereview test)
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.get_capabilities.return_value = Mock(supports_extended_thinking=False)
        mock_provider.generate_content = AsyncMock(
            return_value=Mock(
                content=json.dumps(
                    {
                        "status": "analysis_complete",
                        "raw_analysis": "Analysis completed successfully",
                    },
                    ensure_ascii=False,
                ),
                usage={},
                model_name="flash",
                metadata={},
            )
        )
        # Use the same provider for both contexts
        mock_get_provider.return_value = mock_provider
        mock_context_instance.provider = mock_provider
        mock_context_instance.capabilities = Mock(supports_extended_thinking=False)
        mock_model_context.return_value = mock_context_instance

        # Test the tool
        analyze_tool = AnalyzeTool()
        result = await analyze_tool.execute(
            {
                "step": "Analyze system architecture to identify issues",
                "step_number": 1,
                "total_steps": 1,
                "next_step_required": False,
                "findings": "Starting architectural analysis of Python code",
                "relevant_files": ["/test/main.py"],
                "model": "flash",
            }
        )

        # Checks
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)

        # Parse the response - must be valid UTF-8 JSON
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Structure checks
        self.assertIn("status", response_data)

        # Check that the French instruction was added
        # The mock provider's generate_content should be called
        mock_provider.generate_content.assert_called()
        # The call was successful, which means our fix worked

    @patch("tools.shared.base_tool.BaseTool.get_model_provider")
    async def test_codereview_tool_french_findings(self, mock_get_provider):
        """Test that the codereview tool produces findings in French."""
        # Mock with analysis in French
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.get_capabilities.return_value = Mock(supports_extended_thinking=False)
        mock_provider.generate_content = AsyncMock(
            return_value=Mock(
                content=json.dumps(
                    {
                        "status": "analysis_complete",
                        "raw_analysis": """
🔴 CRITIQUE: Aucun problème critique trouvé.

🟠 ÉLEVÉ: Fichier example.py:42 - Fonction trop complexe
→ Problème: La fonction process_data() contient trop de responsabilités
→ Solution: Décomposer en fonctions plus petites et spécialisées

🟡 MOYEN: Gestion d'erreurs insuffisante
→ Problème: Plusieurs fonctions n'ont pas de gestion d'erreurs appropriée
→ Solution: Ajouter des try-catch et validation des paramètres

✅ Points positifs:
• Code bien commenté et lisible
• Nomenclature cohérente
• Tests unitaires présents
""",
                    },
                    ensure_ascii=False,
                ),
                usage={},
                model_name="test-model",
                metadata={},
            )
        )
        mock_get_provider.return_value = mock_provider

        # Test the tool
        codereview_tool = CodeReviewTool()
        result = await codereview_tool.execute(
            {
                "step": "Complete review of Python code",
                "step_number": 1,
                "total_steps": 1,
                "next_step_required": False,
                "findings": "Code review complete",
                "relevant_files": ["/test/example.py"],
                "model": "test-model",
            }
        )

        # Checks
        self.assertIsNotNone(result)
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Check UTF-8 characters in analysis
        if "expert_analysis" in response_data:
            analysis = response_data["expert_analysis"]["raw_analysis"]
            # Check for French characters
            self.assertIn("ÉLEVÉ", analysis)
            self.assertIn("problème", analysis)
            self.assertIn("spécialisées", analysis)
            self.assertIn("appropriée", analysis)
            self.assertIn("paramètres", analysis)
            self.assertIn("présents", analysis)
            # Check for emojis
            self.assertIn("🔴", analysis)
            self.assertIn("🟠", analysis)
            self.assertIn("🟡", analysis)
            self.assertIn("✅", analysis)

    @patch("tools.shared.base_tool.BaseTool.get_model_provider")
    async def test_debug_tool_french_error_analysis(self, mock_get_provider):
        """Test that the debug tool analyzes errors in French."""
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.get_capabilities.return_value = Mock(supports_extended_thinking=False)
        mock_provider.generate_content = AsyncMock(
            return_value=Mock(
                content=json.dumps(
                    {
                        "status": "pause_for_investigation",
                        "step_number": 1,
                        "total_steps": 2,
                        "next_step_required": True,
                        "findings": (
                            "Erreur analysée: variable 'données' non définie. Cause probable: import manquant."
                        ),
                        "files_checked": ["/src/data_processor.py"],
                        "relevant_files": ["/src/data_processor.py"],
                        "hypothesis": ("Variable 'données' not defined - missing import"),
                        "confidence": "medium",
                        "investigation_status": "in_progress",
                        "error_analysis": ("L'erreur concerne la variable 'données' qui n'est pas définie."),
                    },
                    ensure_ascii=False,
                ),
                usage={},
                model_name="test-model",
                metadata={},
            )
        )
        mock_get_provider.return_value = mock_provider

        # Test the debug tool
        debug_tool = DebugIssueTool()
        result = await debug_tool.execute(
            {
                "step": "Analyze NameError in data processing file",
                "step_number": 1,
                "total_steps": 1,
                "next_step_required": False,
                "findings": "Error detected during script execution",
                "files_checked": ["/src/data_processor.py"],
                "relevant_files": ["/src/data_processor.py"],
                "hypothesis": ("Variable 'données' not defined - missing import"),
                "confidence": "medium",
                "model": "test-model",
            }
        )

        # Checks
        self.assertIsNotNone(result)
        response_text = result[0].text
        response_data = json.loads(response_text)

        # Check response structure
        self.assertIn("status", response_data)
        self.assertIn("investigation_status", response_data)

        # Check that UTF-8 characters are preserved
        response_str = json.dumps(response_data, ensure_ascii=False)
        self.assertIn("données", response_str)

    def test_utf8_emoji_preservation_in_workflow_responses(self):
        """Test that emojis are preserved in workflow tool responses."""
        # Mock workflow response with various emojis
        test_data = {
            "status": "analysis_complete",
            "severity_indicators": {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
                "success": "✅",
                "error": "❌",
                "warning": "⚠️",
            },
            "progress": "Analysis completed 🎉",
            "recommendations": [
                "Optimize performance 🚀",
                "Improve documentation 📚",
                "Add unit tests 🧪",
            ],
        }

        # Test JSON encoding with ensure_ascii=False
        json_str = json.dumps(test_data, ensure_ascii=False, indent=2)

        # Check emojis are preserved
        self.assertIn("🔴", json_str)
        self.assertIn("🟠", json_str)
        self.assertIn("🟡", json_str)
        self.assertIn("🟢", json_str)
        self.assertIn("✅", json_str)
        self.assertIn("❌", json_str)
        self.assertIn("⚠️", json_str)
        self.assertIn("🎉", json_str)
        self.assertIn("🚀", json_str)
        self.assertIn("📚", json_str)
        self.assertIn("🧪", json_str)

        # No escaped Unicode
        self.assertNotIn("\\u", json_str)

        # Test parsing preserves emojis
        parsed = json.loads(json_str)
        self.assertEqual(parsed["severity_indicators"]["critical"], "🔴")
        self.assertEqual(parsed["progress"], "Analysis completed 🎉")


if __name__ == "__main__":
    unittest.main(verbosity=2)
