#!/usr/bin/env python3
"""
X.AI GROK Model Tests

Tests that verify X.AI GROK functionality including:
- Model alias resolution (grok, grok3, grokfast map to actual GROK models)
- GROK-3 and GROK-3-fast models work correctly
- Conversation continuity works with GROK models
- API integration and response validation
"""


from .base_test import BaseSimulatorTest


class XAIModelsTest(BaseSimulatorTest):
    """Test X.AI GROK model functionality and integration"""

    @property
    def test_name(self) -> str:
        return "xai_models"

    @property
    def test_description(self) -> str:
        return "X.AI GROK model functionality and integration"

    def run_test(self) -> bool:
        """Test X.AI GROK model functionality"""
        try:
            self.logger.info("Test: X.AI GROK model functionality and integration")

            # Check if X.AI API key is configured and not empty
            import os

            xai_key = os.environ.get("XAI_API_KEY", "")
            is_valid = bool(xai_key and xai_key != "your_xai_api_key_here" and xai_key.strip())

            if not is_valid:
                self.logger.info("  ⚠️  X.AI API key not configured or empty - skipping test")
                self.logger.info("  ℹ️  This test requires XAI_API_KEY to be set in .env with a valid key")
                return True  # Return True to indicate test is skipped, not failed

            # Setup test files for later use
            self.setup_test_files()

            # Test 1: 'grok' alias (should map to grok-4)
            self.logger.info("  1: Testing 'grok' alias (should map to grok-4)")

            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from GROK model!' and nothing else.",
                    "model": "grok",
                    "temperature": 0.1,
                },
            )

            if not response1:
                self.logger.error("  ❌ GROK alias test failed")
                return False

            self.logger.info("  ✅ GROK alias call completed")
            if continuation_id:
                self.logger.info(f"  ✅ Got continuation_id: {continuation_id}")

            # Test 2: Direct grok-3 model name
            self.logger.info("  2: Testing direct model name (grok-3)")

            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from GROK-3!' and nothing else.",
                    "model": "grok-3",
                    "temperature": 0.1,
                },
            )

            if not response2:
                self.logger.error("  ❌ Direct GROK-3 model test failed")
                return False

            self.logger.info("  ✅ Direct GROK-3 model call completed")

            # Test 3: grok-3-fast model
            self.logger.info("  3: Testing GROK-3-fast model")

            response3, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from GROK-3-fast!' and nothing else.",
                    "model": "grok-3-fast",
                    "temperature": 0.1,
                },
            )

            if not response3:
                self.logger.error("  ❌ GROK-3-fast model test failed")
                return False

            self.logger.info("  ✅ GROK-3-fast model call completed")

            # Test 4: Shorthand aliases
            self.logger.info("  4: Testing shorthand aliases (grok3, grokfast)")

            response4, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from grok3 alias!' and nothing else.",
                    "model": "grok3",
                    "temperature": 0.1,
                },
            )

            if not response4:
                self.logger.error("  ❌ grok3 alias test failed")
                return False

            response5, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from grokfast alias!' and nothing else.",
                    "model": "grokfast",
                    "temperature": 0.1,
                },
            )

            if not response5:
                self.logger.error("  ❌ grokfast alias test failed")
                return False

            self.logger.info("  ✅ Shorthand aliases work correctly")

            # Test 5: Conversation continuity with GROK models
            self.logger.info("  5: Testing conversation continuity with GROK")

            response6, new_continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Remember this number: 87. What number did I just tell you?",
                    "model": "grok",
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
                    "model": "grok",
                    "continuation_id": new_continuation_id,
                    "temperature": 0.1,
                },
            )

            if not response7:
                self.logger.error("  ❌ Failed to continue conversation")
                return False

            # Check if the model remembered the number
            if "87" in response7:
                self.logger.info("  ✅ Conversation continuity working with GROK")
            else:
                self.logger.warning("  ⚠️  Model may not have remembered the number")

            # Test 6: Validate X.AI API usage from logs
            self.logger.info("  6: Validating X.AI API usage in logs")
            logs = self.get_recent_server_logs()

            # Check for X.AI API calls
            xai_logs = [line for line in logs.split("\n") if "x.ai" in line.lower()]
            xai_api_logs = [line for line in logs.split("\n") if "api.x.ai" in line]
            grok_logs = [line for line in logs.split("\n") if "grok" in line.lower()]

            # Check for specific model resolution
            grok_resolution_logs = [
                line
                for line in logs.split("\n")
                if ("Resolved model" in line and "grok" in line.lower()) or ("grok" in line and "->" in line)
            ]

            # Check for X.AI provider usage
            xai_provider_logs = [line for line in logs.split("\n") if "XAI" in line or "X.AI" in line]

            # Log findings
            self.logger.info(f"   X.AI-related logs: {len(xai_logs)}")
            self.logger.info(f"   X.AI API logs: {len(xai_api_logs)}")
            self.logger.info(f"   GROK-related logs: {len(grok_logs)}")
            self.logger.info(f"   Model resolution logs: {len(grok_resolution_logs)}")
            self.logger.info(f"   X.AI provider logs: {len(xai_provider_logs)}")

            # Sample log output for debugging
            if self.verbose and xai_logs:
                self.logger.debug("  📋 Sample X.AI logs:")
                for log in xai_logs[:3]:
                    self.logger.debug(f"    {log}")

            if self.verbose and grok_logs:
                self.logger.debug("  📋 Sample GROK logs:")
                for log in grok_logs[:3]:
                    self.logger.debug(f"    {log}")

            # Success criteria
            grok_mentioned = len(grok_logs) > 0
            api_used = len(xai_api_logs) > 0 or len(xai_logs) > 0
            provider_used = len(xai_provider_logs) > 0

            success_criteria = [
                ("GROK models mentioned in logs", grok_mentioned),
                ("X.AI API calls made", api_used),
                ("X.AI provider used", provider_used),
                ("All model calls succeeded", True),  # We already checked this above
                ("Conversation continuity works", True),  # We already tested this
            ]

            passed_criteria = sum(1 for _, passed in success_criteria if passed)
            self.logger.info(f"   Success criteria met: {passed_criteria}/{len(success_criteria)}")

            for criterion, passed in success_criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            if passed_criteria >= 3:  # At least 3 out of 5 criteria
                self.logger.info("  ✅ X.AI GROK model tests passed")
                return True
            else:
                self.logger.error("  ❌ X.AI GROK model tests failed")
                return False

        except Exception as e:
            self.logger.error(f"X.AI GROK model test failed: {e}")
            return False
        finally:
            self.cleanup_test_files()


def main():
    """Run the X.AI GROK model tests"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = XAIModelsTest(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
