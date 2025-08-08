#!/usr/bin/env python3
"""
OpenRouter Fallback Test

Tests that verify the system correctly falls back to OpenRouter when:
- Only OPENROUTER_API_KEY is configured
- Native models (flash, pro) are requested but map to OpenRouter equivalents
- Auto mode correctly selects OpenRouter models
"""


from .base_test import BaseSimulatorTest


class OpenRouterFallbackTest(BaseSimulatorTest):
    """Test OpenRouter fallback behavior when it's the only provider"""

    @property
    def test_name(self) -> str:
        return "openrouter_fallback"

    @property
    def test_description(self) -> str:
        return "OpenRouter fallback behavior when only provider"

    def run_test(self) -> bool:
        """Test OpenRouter fallback behavior"""
        try:
            self.logger.info("Test: OpenRouter fallback behavior when only provider available")

            # Check if ONLY OpenRouter API key is configured (this is a fallback test)
            import os

            has_openrouter = bool(os.environ.get("OPENROUTER_API_KEY"))
            has_gemini = bool(os.environ.get("GEMINI_API_KEY"))
            has_openai = bool(os.environ.get("OPENAI_API_KEY"))

            if not has_openrouter:
                self.logger.info("  ⚠️  OpenRouter API key not configured - skipping test")
                self.logger.info("  ℹ️  This test requires OPENROUTER_API_KEY to be set in .env")
                return True  # Return True to indicate test is skipped, not failed

            if has_gemini or has_openai:
                self.logger.info("  ⚠️  Other API keys configured - this is not a fallback scenario")
                self.logger.info("  ℹ️  This test requires ONLY OpenRouter to be configured (no Gemini/OpenAI keys)")
                self.logger.info("  ℹ️  Current setup has multiple providers, so fallback behavior doesn't apply")
                return True  # Return True to indicate test is skipped, not failed

            # Setup test files
            self.setup_test_files()

            # Test 1: Auto mode should work with OpenRouter
            self.logger.info("  1: Testing auto mode with OpenRouter as only provider")

            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What is 2 + 2? Give a brief answer.",
                    # No model specified - should use auto mode
                    "temperature": 0.1,
                },
            )

            if not response1:
                self.logger.error("  ❌ Auto mode with OpenRouter failed")
                return False

            self.logger.info("  ✅ Auto mode call completed with OpenRouter")

            # Test 2: Flash model should map to OpenRouter equivalent
            self.logger.info("  2: Testing flash model mapping to OpenRouter")

            # Use codereview tool to test a different tool type
            test_code = """def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total"""

            test_file = self.create_additional_test_file("sum_function.py", test_code)

            response2, _ = self.call_mcp_tool(
                "codereview",
                {
                    "step": "Quick review of this sum function for quality and potential issues",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Starting code review of sum function",
                    "relevant_files": [test_file],
                    "model": "flash",
                    "temperature": 0.1,
                },
            )

            if not response2:
                self.logger.error("  ❌ Flash model mapping to OpenRouter failed")
                return False

            self.logger.info("  ✅ Flash model successfully mapped to OpenRouter")

            # Test 3: Pro model should map to OpenRouter equivalent
            self.logger.info("  3: Testing pro model mapping to OpenRouter")

            response3, _ = self.call_mcp_tool(
                "analyze",
                {
                    "step": "Analyze the structure of this Python code",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Starting code structure analysis",
                    "relevant_files": [self.test_files["python"]],
                    "model": "pro",
                    "temperature": 0.1,
                },
            )

            if not response3:
                self.logger.error("  ❌ Pro model mapping to OpenRouter failed")
                return False

            self.logger.info("  ✅ Pro model successfully mapped to OpenRouter")

            # Test 4: Debug tool with OpenRouter
            self.logger.info("  4: Testing debug tool with OpenRouter")

            response4, _ = self.call_mcp_tool(
                "debug",
                {
                    "step": "Why might a function return None instead of a value?",
                    "step_number": 1,
                    "total_steps": 1,
                    "next_step_required": False,
                    "findings": "Starting debug investigation of None return values",
                    "model": "flash",  # Should map to OpenRouter
                    "temperature": 0.1,
                },
            )

            if not response4:
                self.logger.error("  ❌ Debug tool with OpenRouter failed")
                return False

            self.logger.info("  ✅ Debug tool working with OpenRouter")

            # Test 5: Validate logs show OpenRouter is being used
            self.logger.info("  5: Validating OpenRouter is the active provider")
            logs = self.get_recent_server_logs()

            # Check for provider fallback logs
            fallback_logs = [
                line
                for line in logs.split("\n")
                if "No Gemini API key found" in line
                or "No OpenAI API key found" in line
                or "Only OpenRouter available" in line
                or "Using OpenRouter" in line
            ]

            # Check for OpenRouter provider initialization
            provider_logs = [
                line
                for line in logs.split("\n")
                if "OpenRouter provider" in line or "OpenRouterProvider" in line or "openrouter.ai/api/v1" in line
            ]

            # Check for model resolution through OpenRouter
            model_resolution_logs = [
                line
                for line in logs.split("\n")
                if ("Resolved model" in line and "via OpenRouter" in line)
                or ("Model alias" in line and "resolved to" in line)
                or ("flash" in line and "gemini-flash" in line)
                or ("pro" in line and "gemini-pro" in line)
            ]

            # Log findings
            self.logger.info(f"   Fallback indication logs: {len(fallback_logs)}")
            self.logger.info(f"   OpenRouter provider logs: {len(provider_logs)}")
            self.logger.info(f"   Model resolution logs: {len(model_resolution_logs)}")

            # Sample logs for debugging
            if self.verbose:
                if fallback_logs:
                    self.logger.debug("  📋 Sample fallback logs:")
                    for log in fallback_logs[:3]:
                        self.logger.debug(f"    {log}")

                if provider_logs:
                    self.logger.debug("  📋 Sample provider logs:")
                    for log in provider_logs[:3]:
                        self.logger.debug(f"    {log}")

            # Success criteria
            openrouter_active = len(provider_logs) > 0
            models_resolved = len(model_resolution_logs) > 0
            all_tools_worked = True  # We checked this above

            success_criteria = [
                ("OpenRouter provider active", openrouter_active),
                ("Models resolved through OpenRouter", models_resolved),
                ("All tools worked with OpenRouter", all_tools_worked),
            ]

            passed_criteria = sum(1 for _, passed in success_criteria if passed)
            self.logger.info(f"   Success criteria met: {passed_criteria}/{len(success_criteria)}")

            for criterion, passed in success_criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            if passed_criteria >= 2:  # At least 2 out of 3 criteria
                self.logger.info("  ✅ OpenRouter fallback test passed")
                return True
            else:
                self.logger.error("  ❌ OpenRouter fallback test failed")
                return False

        except Exception as e:
            self.logger.error(f"OpenRouter fallback test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()


def main():
    """Run the OpenRouter fallback tests"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = OpenRouterFallbackTest(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
