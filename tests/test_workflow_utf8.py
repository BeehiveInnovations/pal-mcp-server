"""
Unit tests to validate UTF-8 encoding in workflow tools
and the generation of properly encoded JSON responses.
"""

import json
import os
import unittest
from unittest.mock import Mock, patch

from tools.analyze import AnalyzeTool
from tools.codereview import CodeReviewTool
from tools.debug import DebugIssueTool


class TestWorkflowToolsUTF8(unittest.TestCase):
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

        # UTF-8 checks
        self.assertIn("🔍", json_str)

        # No escaped characters
        self.assertNotIn("\\u", json_str)

        # Test parsing
        parsed = json.loads(json_str)
        self.assertEqual(parsed["findings"], test_response["findings"])
        self.assertEqual(len(parsed["issues_found"]), 1)

    @patch("tools.shared.base_tool.BaseTool.get_model_provider")
    def test_analyze_tool_utf8_response(self, mock_get_provider):
        """Test that the analyze tool returns correct UTF-8 responses."""
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.generate_content.return_value = Mock(
            content="Architectural analysis complete. Recommendations: improve modularity.",
            usage={},
            model_name="test-model",
            metadata={},
        )
        mock_get_provider.return_value = mock_provider

        # Test the tool
        analyze_tool = AnalyzeTool()
        result = analyze_tool.execute(
            {
                "step": "Analyze system architecture to identify issues",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Starting architectural analysis of Python code",
                "relevant_files": ["/test/main.py"],
                "model": "test-model",
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
        self.assertIn("step_number", response_data)

        # Check that the French instruction was added
        mock_provider.generate_content.assert_called()
        call_args = mock_provider.generate_content.call_args
        system_prompt = call_args.kwargs.get("system_prompt", "")
        self.assertIn("fr-FR", system_prompt)

    @patch("tools.shared.base_tool.BaseTool.get_model_provider")
    def test_codereview_tool_french_findings(self, mock_get_provider):
        """Test that the codereview tool produces findings in French."""
        # Mock with analysis in French
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.supports_thinking_mode.return_value = False
        mock_provider.generate_content.return_value = Mock(
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
        mock_get_provider.return_value = mock_provider

        # Test the tool
        codereview_tool = CodeReviewTool()
        result = codereview_tool.execute(
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
    def test_debug_tool_french_error_analysis(self, mock_get_provider):
        """Test that the debug tool analyzes errors in French."""
        # Mock provider
        mock_provider = Mock()
        mock_provider.get_provider_type.return_value = Mock(value="test")
        mock_provider.generate_content.return_value = Mock(
            content="Error analyzed: variable 'données' not defined. Probable cause: missing import.",
            usage={},
            model_name="test-model",
            metadata={},
        )
        mock_get_provider.return_value = mock_provider

        # Test the debug tool
        debug_tool = DebugIssueTool()
        result = debug_tool.execute(
            {
                "step": "Analyze NameError in data processing file",
                "step_number": 1,
                "total_steps": 2,
                "next_step_required": True,
                "findings": "Error detected during script execution",
                "files_checked": ["/src/data_processor.py"],
                "relevant_files": ["/src/data_processor.py"],
                "hypothesis": "Variable 'données' not defined - missing import",
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

    def test_json_utf8_serialization(self):
        """Test UTF-8 serialization with ensure_ascii=False."""
        # Test data with French characters and emojis
        test_data = {
            "analyse": {
                "statut": "terminée",
                "résultat": "Aucun problème critique détecté",
                "recommandations": [
                    "Améliorer la documentation",
                    "Optimiser les performances",
                    "Ajouter des tests unitaires",
                ],
                "métadonnées": {
                    "créé_par": "Développeur Principal",
                    "date_création": "2024-01-01",
                    "dernière_modification": "2024-01-15",
                },
                "émojis_status": {
                    "critique": "🔴",
                    "élevé": "🟠",
                    "moyen": "🟡",
                    "faible": "🟢",
                    "succès": "✅",
                    "erreur": "❌",
                },
            }
        }

        # Test with ensure_ascii=False
        json_correct = json.dumps(test_data, ensure_ascii=False, indent=2)

        # Checks
        utf8_terms = [
            "terminée",
            "résultat",
            "détecté",
            "Améliorer",
            "créé_par",
            "Développeur",
            "création",
            "métadonnées",
            "dernière",
            "émojis_status",
            "élevé",
        ]

        emojis = ["🔴", "🟠", "🟡", "🟢", "✅", "❌"]

        for term in utf8_terms:
            self.assertIn(term, json_correct)

        for emoji in emojis:
            self.assertIn(emoji, json_correct)

        # Check for escaped characters
        self.assertNotIn("\\u", json_correct)

        # Test parsing
        parsed = json.loads(json_correct)
        self.assertEqual(parsed["analyse"]["statut"], "terminée")
        self.assertEqual(parsed["analyse"]["émojis_status"]["critique"], "🔴")


if __name__ == "__main__":
    unittest.main(verbosity=2)
