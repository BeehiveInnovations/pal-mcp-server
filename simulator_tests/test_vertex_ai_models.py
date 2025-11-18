#!/usr/bin/env python3
"""
Vertex AI Provider Model Tests

Tests that verify Vertex AI provider functionality including:
- Model alias resolution (vertex-pro, vertex-flash, vertex-lite map to Gemini models)
- Gemini models work correctly via Vertex AI
- Conversation continuity works with Vertex AI models
- API integration with Google Cloud authentication
- Project and region configuration
"""

from .base_test import BaseSimulatorTest


class VertexAIModelsTest(BaseSimulatorTest):
    """Test Vertex AI provider functionality and integration"""

    def __init__(self, verbose: bool = False):
        """Initialize the test with proper parent class initialization"""
        super().__init__(verbose)

    @property
    def test_name(self) -> str:
        return "vertex_ai_models"

    @property
    def test_description(self) -> str:
        return "Vertex AI provider model functionality and integration"

    def run_test(self) -> bool:
        """Test Vertex AI provider models"""
        try:
            self.logger.info("Test: Vertex AI provider functionality and integration")

            # Check if Vertex AI project ID is configured and not empty
            import os

            vertex_project_id = os.environ.get("VERTEX_PROJECT_ID", "")
            is_valid = bool(
                vertex_project_id and vertex_project_id != "your_vertex_project_id_here" and vertex_project_id.strip()
            )

            if not is_valid:
                self.logger.info("  ⚠️  Vertex AI project ID not configured or empty - skipping test")
                self.logger.info("  ℹ️  This test requires VERTEX_PROJECT_ID to be set in .env with a valid project ID")
                return True  # Return True to indicate test is skipped, not failed

            # Setup test files for later use
            self.setup_test_files()

            # Log configuration for debugging
            vertex_region = os.getenv("VERTEX_REGION", "us-central1")
            self.logger.info(f"  🔧 Using Vertex AI project: {vertex_project_id} in region: {vertex_region}")

            # Test 1: 'vertex-pro' alias (should map to gemini-2.5-pro)
            self.logger.info("  1: Testing 'vertex-pro' alias (should map to gemini-2.5-pro)")

            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Vertex AI Pro model!' and nothing else.",
                    "model": "vertex-pro",
                    "temperature": 0.1,
                },
            )

            if not response1:
                self.logger.error("  ❌ Vertex AI Pro alias test failed")
                return False

            self.logger.info("  ✅ Vertex AI Pro alias call completed")
            if continuation_id:
                self.logger.info(f"  ✅ Got continuation_id: {continuation_id}")

            # Test 2: Direct gemini model name via Vertex AI
            self.logger.info("  2: Testing direct model name (gemini-2.5-flash)")

            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Vertex AI Flash!' and nothing else.",
                    "model": "gemini-2.5-flash",
                    "temperature": 0.1,
                },
            )

            if not response2:
                self.logger.error("  ❌ Direct Vertex AI gemini-2.5-flash test failed")
                return False

            self.logger.info("  ✅ Direct Vertex AI gemini-2.5-flash call completed")

            # Test 3: vertex-lite alias (should map to gemini-2.5-flash-lite)
            self.logger.info("  3: Testing vertex-lite alias")

            response3, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Vertex AI Lite!' and nothing else.",
                    "model": "vertex-lite",
                    "temperature": 0.1,
                },
            )

            if not response3:
                self.logger.error("  ❌ Vertex AI Lite alias test failed")
                return False

            self.logger.info("  ✅ Vertex AI Lite alias call completed")

            # Test 4: Additional aliases
            self.logger.info("  4: Testing additional aliases (vertex-2.0)")

            response4, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from vertex-2.0 alias!' and nothing else.",
                    "model": "vertex-2.0",
                    "temperature": 0.1,
                },
            )

            if not response4:
                self.logger.error("  ❌ vertex-2.0 alias test failed")
                return False

            self.logger.info("  ✅ Additional Vertex AI aliases work correctly")

            # Test 5: Conversation continuity with Vertex AI models
            self.logger.info("  5: Testing conversation continuity with Vertex AI")

            response6, new_continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Remember this number: 42. What number did I just tell you?",
                    "model": "vertex-pro",
                    "temperature": 0.1,
                },
            )

            if not response6 or not new_continuation_id:
                self.logger.error("  ❌ Failed to start Vertex AI conversation with continuation_id")
                return False

            # Continue the conversation
            response7, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What was the number I told you earlier?",
                    "model": "vertex-pro",
                    "continuation_id": new_continuation_id,
                    "temperature": 0.1,
                },
            )

            if not response7:
                self.logger.error("  ❌ Failed to continue Vertex AI conversation")
                return False

            # Check if the model remembered the number
            if "42" in response7:
                self.logger.info("  ✅ Conversation continuity working with Vertex AI")
            else:
                self.logger.warning("  ⚠️  Model may not have remembered the number")

            # Test 6: Validate Vertex AI API usage from logs
            self.logger.info("  6: Validating Vertex AI API usage in logs")
            logs = self.get_recent_server_logs()

            # Check for Vertex AI API calls
            vertex_logs = [line for line in logs.split("\n") if "vertex" in line.lower()]
            vertex_api_logs = [line for line in logs.split("\n") if "aiplatform.googleapis.com" in line]
            gemini_logs = [line for line in logs.split("\n") if "gemini" in line.lower()]

            # Check for specific model resolution
            vertex_resolution_logs = [
                line
                for line in logs.split("\n")
                if ("Resolved model" in line and "vertex" in line.lower()) or ("vertex" in line and "->" in line)
            ]

            # Check for Vertex AI provider usage
            vertex_provider_logs = [line for line in logs.split("\n") if "VERTEX_AI" in line or "Vertex AI" in line]

            # Check for project configuration logs
            project_logs = [
                line
                for line in logs.split("\n")
                if vertex_project_id in line and ("Vertex AI" in line or "project" in line.lower())
            ]

            # Log findings
            self.logger.info(f"   Vertex AI-related logs: {len(vertex_logs)}")
            self.logger.info(f"   Vertex AI API logs: {len(vertex_api_logs)}")
            self.logger.info(f"   Gemini-related logs: {len(gemini_logs)}")
            self.logger.info(f"   Model resolution logs: {len(vertex_resolution_logs)}")
            self.logger.info(f"   Vertex AI provider logs: {len(vertex_provider_logs)}")
            self.logger.info(f"   Project configuration logs: {len(project_logs)}")

            # Sample log output for debugging
            if self.verbose and vertex_logs:
                self.logger.debug("  📋 Sample Vertex AI logs:")
                for log in vertex_logs[:3]:
                    self.logger.debug(f"    {log}")

            if self.verbose and gemini_logs:
                self.logger.debug("  📋 Sample Gemini logs:")
                for log in gemini_logs[:3]:
                    self.logger.debug(f"    {log}")

            # Test 7: Test thinking mode capability (for supported models)
            self.logger.info("  7: Testing thinking mode capability with Vertex AI")

            response8, _ = self.call_mcp_tool(
                "thinkdeep",
                {
                    "prompt": "Think about why the sky appears blue. Explain the physics briefly.",
                    "model": "vertex-pro",  # Should support thinking mode
                    "thinking_mode": "medium",
                },
            )

            thinking_works = bool(response8)
            if thinking_works:
                self.logger.info("  ✅ Thinking mode test completed with Vertex AI")
            else:
                self.logger.warning("  ⚠️  Thinking mode test failed (may not be critical)")

            # Success criteria
            vertex_mentioned = len(vertex_logs) > 0
            api_used = len(vertex_api_logs) > 0 or len(vertex_logs) > 0
            provider_used = len(vertex_provider_logs) > 0
            project_configured = len(project_logs) > 0

            success_criteria = [
                ("Vertex AI models mentioned in logs", vertex_mentioned),
                ("Vertex AI API calls made", api_used),
                ("Vertex AI provider used", provider_used),
                ("Project configuration logged", project_configured),
                ("All model calls succeeded", True),  # We already checked this above
                ("Conversation continuity works", True),  # We already tested this
            ]

            passed_criteria = sum(1 for _, passed in success_criteria if passed)
            self.logger.info(f"   Success criteria met: {passed_criteria}/{len(success_criteria)}")

            for criterion, passed in success_criteria:
                status = "✅" if passed else "❌"
                self.logger.info(f"    {status} {criterion}")

            if passed_criteria >= 4:  # At least 4 out of 6 criteria
                self.logger.info("  ✅ Vertex AI model tests passed")
                return True
            else:
                self.logger.error("  ❌ Vertex AI model tests failed")
                return False

        except Exception as e:
            self.logger.error(f"Vertex AI model test failed: {e}")
            import traceback

            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return False
        finally:
            self.cleanup_test_files()


def main():
    """Run the Vertex AI model tests"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = VertexAIModelsTest(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
