"""
Unit tests to validate UTF-8 localization and encoding
of French characters.

These tests check:
1. Language instruction generation according to LOCALE
2. UTF-8 encoding with json.dumps(ensure_ascii=False)
3. French characters and emojis are displayed correctly
4. MCP tools return localized content
"""

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import Mock

from tools.shared.base_tool import BaseTool


class MockTestTool(BaseTool):
    """Concrete implementation of BaseTool for testing."""

    def __init__(self):
        super().__init__()

    def get_name(self) -> str:
        return "test_tool"

    def get_description(self) -> str:
        return "A test tool for localization testing"

    def get_input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def get_system_prompt(self) -> str:
        return "You are a test assistant."

    def get_request_model(self):
        from tools.shared.base_models import ToolRequest

        return ToolRequest

    async def prepare_prompt(self, request) -> str:
        return "Test prompt"

    async def execute(self, arguments: dict) -> list:
        return [Mock(text="test response")]


class TestUTF8Localization(unittest.TestCase):
    """Tests for UTF-8 localization and French character encoding."""

    def setUp(self):
        """Test setup."""
        self.original_locale = os.getenv("LOCALE")

    def tearDown(self):
        """Cleanup after tests."""
        if self.original_locale is not None:
            os.environ["LOCALE"] = self.original_locale
        else:
            os.environ.pop("LOCALE", None)

    def test_language_instruction_generation_french(self):
        """Test language instruction generation for French."""
        # Set LOCALE to French
        os.environ["LOCALE"] = "fr-FR"

        # Test get_language_instruction method
        tool = MockTestTool()
        instruction = tool.get_language_instruction()  # Checks
        self.assertIsInstance(instruction, str)
        self.assertIn("fr-FR", instruction)
        self.assertTrue(instruction.endswith("\n\n"))

    def test_language_instruction_generation_english(self):
        """Test language instruction generation for English."""
        # Set LOCALE to English
        os.environ["LOCALE"] = "en-US"

        tool = MockTestTool()
        instruction = tool.get_language_instruction()  # Checks
        self.assertIsInstance(instruction, str)
        self.assertIn("en-US", instruction)
        self.assertTrue(instruction.endswith("\n\n"))

    def test_language_instruction_empty_locale(self):
        """Test with empty LOCALE."""
        # Set LOCALE to empty
        os.environ["LOCALE"] = ""

        tool = MockTestTool()
        instruction = tool.get_language_instruction()

        # Should return empty string
        self.assertEqual(instruction, "")

    def test_language_instruction_no_locale(self):
        """Test with no LOCALE variable set."""
        # Remove LOCALE
        os.environ.pop("LOCALE", None)

        tool = MockTestTool()
        instruction = tool.get_language_instruction()

        # Should return empty string
        self.assertEqual(instruction, "")

    def test_json_dumps_utf8_encoding(self):
        """Test that json.dumps uses ensure_ascii=False for UTF-8."""
        # Test data with French characters and emojis
        test_data = {
            "status": "succès",
            "message": "Tâche terminée avec succès",
            "details": {
                "créé": "2024-01-01",
                "développeur": "Jean Dupont",
                "préférences": ["français", "développement"],
                "emojis": "🔴 🟠 🟡 🟢 ✅ ❌",
            },
        }

        # Test with ensure_ascii=False (correct)
        json_correct = json.dumps(test_data, ensure_ascii=False, indent=2)

        # Check that UTF-8 characters are preserved
        self.assertIn("succès", json_correct)
        self.assertIn("terminée", json_correct)
        self.assertIn("créé", json_correct)
        self.assertIn("développeur", json_correct)
        self.assertIn("préférences", json_correct)
        self.assertIn("français", json_correct)
        self.assertIn("développement", json_correct)
        self.assertIn("🔴", json_correct)
        self.assertIn("🟢", json_correct)
        self.assertIn("✅", json_correct)

        # Check that characters are NOT escaped
        self.assertNotIn("\\u", json_correct)
        self.assertNotIn("\\ud83d", json_correct)

    def test_json_dumps_ascii_encoding_comparison(self):
        """Test comparison between ensure_ascii=True and False."""
        test_data = {"message": "Développement réussi! 🎉"}

        # With ensure_ascii=True (old, incorrect behavior)
        json_escaped = json.dumps(test_data, ensure_ascii=True)

        # With ensure_ascii=False (new, correct behavior)
        json_utf8 = json.dumps(test_data, ensure_ascii=False)  # Checks
        self.assertIn("\\u", json_escaped)  # Characters are escaped
        self.assertNotIn("é", json_escaped)  # UTF-8 characters are escaped

        self.assertNotIn("\\u", json_utf8)  # No escaped characters
        self.assertIn("é", json_utf8)  # UTF-8 characters preserved
        self.assertIn("🎉", json_utf8)  # Emojis preserved

    def test_french_characters_in_file_content(self):
        """Test reading and writing files with French characters."""
        # Test content with French characters
        test_content = """
# System configuration
# Created by: Lead Developer
# Creation date: December 15, 2024

def process_data(preferences, parameters):
    ""\"
    Processes data according to user preferences.

    Args:
        preferences: User preferences dictionary
        parameters: Configuration parameters

    Returns:
        Processing result
    ""\"
    return "Processing completed successfully! ✅"

# Helper functions
def generate_report():
    ""\"Generates a summary report.""\"
    return {
        "status": "success",
        "data": "Report generated",
        "emojis": "📊 📈 📉"
    }
"""

        # Test writing and reading
        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False) as f:
            f.write(test_content)
            temp_file = f.name

        try:
            # Read file
            with open(temp_file, encoding="utf-8") as f:
                read_content = f.read()

            # Checks
            self.assertEqual(read_content, test_content)
            self.assertIn("Lead Developer", read_content)
            self.assertIn("Creation", read_content)
            self.assertIn("preferences", read_content)
            self.assertIn("parameters", read_content)
            self.assertIn("completed", read_content)
            self.assertIn("successfully", read_content)
            self.assertIn("✅", read_content)
            self.assertIn("success", read_content)
            self.assertIn("generated", read_content)
            self.assertIn("📊", read_content)

        finally:
            # Cleanup
            os.unlink(temp_file)

    def test_unicode_normalization(self):
        """Test Unicode normalization for accented characters."""
        # Test with different Unicode encodings
        test_cases = [
            "café",  # e + acute accent combined
            "café",  # e with precomposed acute accent
            "naïf",  # i + diaeresis
            "coeur",  # oe ligature
            "été",  # e + acute accent
        ]

        for text in test_cases:
            # Test that json.dumps preserves characters
            json_output = json.dumps({"text": text}, ensure_ascii=False)
            self.assertIn(text, json_output)

            # Parse and check
            parsed = json.loads(json_output)
            self.assertEqual(parsed["text"], text)

    def test_emoji_preservation(self):
        """Test emoji preservation in JSON encoding."""
        # Emojis used in Zen MCP tools
        emojis = [
            "🔴",  # Critical
            "🟠",  # High
            "🟡",  # Medium
            "🟢",  # Low
            "✅",  # Success
            "❌",  # Error
            "⚠️",  # Warning
            "📊",  # Charts
            "🎉",  # Celebration
            "🚀",  # Rocket
            "🇫🇷",  # French flag
        ]

        test_data = {"emojis": emojis, "message": " ".join(emojis)}

        # Test with ensure_ascii=False
        json_output = json.dumps(test_data, ensure_ascii=False)

        # Checks
        for emoji in emojis:
            self.assertIn(emoji, json_output)  # No escaped characters
        self.assertNotIn("\\u", json_output)

        # Test parsing
        parsed = json.loads(json_output)
        self.assertEqual(parsed["emojis"], emojis)
        self.assertEqual(parsed["message"], " ".join(emojis))


class TestLocalizationIntegration(unittest.TestCase):
    """Integration tests for localization with real tools."""

    def setUp(self):
        """Integration test setup."""
        self.original_locale = os.getenv("LOCALE")

    def tearDown(self):
        """Cleanup after integration tests."""
        if self.original_locale is not None:
            os.environ["LOCALE"] = self.original_locale
        else:
            os.environ.pop("LOCALE", None)

    def test_codereview_tool_french_locale_simple(self):
        """Test that the codereview tool correctly handles French locale configuration."""
        # Set to French
        original_locale = os.environ.get("LOCALE")
        os.environ["LOCALE"] = "fr-FR"

        try:
            # Test language instruction generation
            from tools.codereview import CodeReviewTool

            codereview_tool = CodeReviewTool()

            # Test that the tool correctly gets language instruction for French
            language_instruction = codereview_tool.get_language_instruction()

            # Should contain French locale
            self.assertIn("fr-FR", language_instruction)

            # Should contain language instruction format
            self.assertIn("respond in", language_instruction.lower())

        finally:
            # Restore original locale
            if original_locale is not None:
                os.environ["LOCALE"] = original_locale
            else:
                os.environ.pop("LOCALE", None)

    def test_multiple_locales_switching(self):
        """Test switching locales during execution."""
        tool = MockTestTool()

        # French
        os.environ["LOCALE"] = "fr-FR"
        instruction_fr = tool.get_language_instruction()
        self.assertIn("fr-FR", instruction_fr)

        # English
        os.environ["LOCALE"] = "en-US"
        instruction_en = tool.get_language_instruction()
        self.assertIn("en-US", instruction_en)

        # Spanish
        os.environ["LOCALE"] = "es-ES"
        instruction_es = tool.get_language_instruction()
        self.assertIn("es-ES", instruction_es)

        # Chinese
        os.environ["LOCALE"] = "zh-CN"
        instruction_zh = tool.get_language_instruction()
        self.assertIn("zh-CN", instruction_zh)

        # Check that all instructions are different
        instructions = [
            instruction_fr,
            instruction_en,
            instruction_es,
            instruction_zh,
        ]
        for i, inst1 in enumerate(instructions):
            for j, inst2 in enumerate(instructions):
                if i != j:
                    self.assertNotEqual(inst1, inst2)


# Helper function to run async tests
def run_async_test(test_func):
    """Helper to run async test functions."""
    return asyncio.run(test_func())


if __name__ == "__main__":
    unittest.main(verbosity=2)
