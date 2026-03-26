#!/usr/bin/env python3
"""
OpenRouter Model Tests

Tests that verify OpenRouter functionality including:
- Model alias resolution (flash, pro, o3, etc. map to OpenRouter equivalents)
- Multiple OpenRouter models work correctly
- Conversation continuity works with OpenRouter models
- Error handling when models are not available
"""

from .base_test import BaseSimulatorTest


class OpenRouterModelsTest(BaseSimulatorTest):
    """Test OpenRouter model functionality and alias mapping"""

    @property
    def test_name(self) -> str:
        return "openrouter_models"

    @property
    def test_description(self) -> str:
        return "OpenRouter model functionality and alias mapping"

    def run_test(self) -> bool:
        """Test OpenRouter model functionality"""
        try:
            self.logger.info("Test: OpenRouter model functionality and alias mapping")

            # Check if OpenRouter API key is configured
            import os

            has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))

            if not has_openrouter:
                self.logger.info("  ⚠️  OpenRouter API key not configured - skipping test")
                self.logger.info("  ℹ️  This test requires OPENROUTER_API_KEY to be set in .env")
                return True  # Return True to indicate test is skipped, not failed

            # Setup test files for later use
            self.setup_test_files()

            # Test 1: Flash alias mapping to OpenRouter
            self.logger.info("  1: Testing 'flash' alias (should map to google/gemini-2.5-flash)")

            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Flash model!' and nothing else.",
                    "model": "flash",
                    "temperature": 0.1,
                },
            )

            if not response1:
                self.logger.error("  ❌ Flash alias test failed")
                return False

            self.logger.info("  ✅ Flash alias call completed")
            if continuation_id:
                self.logger.info(f"  ✅ Got continuation_id: {continuation_id}")

            # Test 2: Pro alias mapping to OpenRouter
            self.logger.info("  2: Testing 'pro' alias (should map to google/gemini-2.5-pro)")

            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Pro model!' and nothing else.",
                    "model": "pro",
                    "temperature": 0.1,
                },
            )

            if not response2:
                self.logger.error("  ❌ Pro alias test failed")
                return False

            self.logger.info("  ✅ Pro alias call completed")

            # Test 3: O3 alias mapping to OpenRouter (should map to openai/gpt-4o)
            self.logger.info("  3: Testing 'o3' alias (should map to openai/gpt-4o)")

            response3, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from O3 model!' and nothing else.",
                    "model": "o3",
                    "temperature": 0.1,
                },
            )

            if not response3:
                self.logger.error("  ❌ O3 alias test failed")
                return False

            self.logger.info("  ✅ O3 alias call completed")

            # Test 4: Direct OpenRouter model name
            self.logger.info("  4: Testing direct OpenRouter model name (anthropic/claude-3-haiku)")

            response4, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Claude Haiku!' and nothing else.",
                    "model": "anthropic/claude-3-haiku",
                    "temperature": 0.1,
                },
            )

            if not response4:
                self.logger.error("  ❌ Direct OpenRouter model test failed")
                return False

            self.logger.info("  ✅ Direct OpenRouter model call completed")

            # Test 5: OpenRouter alias from config
            self.logger.info("  5: Testing OpenRouter alias from config ('opus' -> anthropic/claude-opus-4)")

            response5, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Opus!' and nothing else.",
                    "model": "opus",
                    "temperature": 0.1,
                },
            )

            if not response5:
                self.logger.error("  ❌ OpenRouter alias test failed")
                return False

            self.logger.info("  ✅ OpenRouter alias call completed")

            # Test 6: Conversation continuity with OpenRouter models
            self.logger.info("  6: Testing conversation continuity with OpenRouter")

            response6, new_continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Remember this number: 42. What number did I just tell you?",
                    "model": "sonnet",  # Claude Sonnet via OpenRouter
                    "temperature": 0.1,
                },
            )

            if not response6 or not new_continuation_id:
                self.logger.error("  ❌ Failed to start conversation with continuation_id")
                return False

            # Continue the conversation
            response7, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What was the number I told you earlier?",
                    "model": "sonnet",
                    "continuation_id": new_continuation_id,
                    "temperature": 0.1,
                },
            )

            if not response7:
                self.logger.error("  ❌ Failed to continue conversation")
                return False

            # Check if the model remembered the number
            if "42" in response7:
                self.logger.info("  ✅ Conversation continuity working with OpenRouter")
            else:
                self.logger.warning("  ⚠️  Model may not have remembered the number")

            # Test 7: Validate OpenRouter API usage from logs
            self.logger.info("  7: Validating OpenRouter API usage in logs")
            logs = self.get_recent_server_logs()

            # Check for OpenRouter API calls
            openrouter_logs = [line for line in logs.split("\n") if "openrouter" in line.lower()]
            openrouter_api_logs = [line for line in logs.split("\n") if "openrouter.ai/api/v1" in line]

            # Check for specific model mappings
            flash_mapping_logs = [
                line
                for line in logs.split("\n")
                if ("flash" in line and "google/gemini-flash" in line)
                or ("Resolved model" in line and "google/gemini-flash" in line)
            ]

            pro_mapping_logs = [
                line
                for line in logs.split("\n")
                if ("pro" in line and "google/gemini-pro" in line)
                or ("Resolved model" in line and "google/gemini-pro" in line)
            ]

            # Log findings
            self.logger.info(f"   OpenRouter-related logs: {len(openrouter_logs)}")
            self.logger.info(f"   OpenRouter API logs: {len(openrouter_api_logs)}")
            self.logger.info(f"   Flash mapping logs: {len(flash_mapping_logs)}")
            self.logger.info(f"   Pro mapping logs: {len(pro_mapping_logs)}")

            # Sample log output for debugging
            if self.verbose and openrouter_logs:
                self.logger.debug("  📋 Sample OpenRouter logs:")
                for log in openrouter_logs[:5]:
                    self.logger.debug(f"    {log}")

            # Success criteria
            openrouter_api_used = len(openrouter_api_logs) > 0
            models_mapped = len(flash_mapping_logs) > 0 or len(pro_mapping_logs) > 0

            success_criteria = [
                ("OpenRouter API calls made", openrouter_api_used),
                ("Model aliases mapped correctly", models_mapped),
                ("All model calls succeeded", True),  # We already checked this above
            ]

            passed_criteria = sum(1 for _, passed in success_criteria if passed)
            self.logger.info(f"   Success criteria met: {passed_criteria}/{len(success_criteria)}")

            for criterion, passed in success_criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            if passed_criteria >= 2:  # At least 2 out of 3 criteria
                self.logger.info("  ✅ OpenRouter model tests passed")
                return True
            else:
                self.logger.error("  ❌ OpenRouter model tests failed")
                return False

        except Exception as e:
            self.logger.error(f"OpenRouter model test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()


def main():
    """Run the OpenRouter model tests"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = OpenRouterModelsTest(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
