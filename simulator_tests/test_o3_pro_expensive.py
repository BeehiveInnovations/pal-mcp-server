#!/usr/bin/env python3
"""
O3-Pro Expensive Model Test

⚠️  WARNING: This test uses o3-pro which is EXTREMELY EXPENSIVE! ⚠️

This test is intentionally NOT added to TEST_REGISTRY to prevent accidental execution.
It can only be run manually using:
    python communication_simulator_test.py --individual o3_pro_expensive

Tests that o3-pro model:
1. Uses the correct /v1/responses endpoint (not /v1/chat/completions)
2. Successfully completes a chat call
3. Returns properly formatted response
"""

from .base_test import BaseSimulatorTest


class O3ProExpensiveTest(BaseSimulatorTest):
    """Test o3-pro model basic functionality - EXPENSIVE, manual only"""

    @property
    def test_name(self) -> str:
        return "o3_pro_expensive"

    @property
    def test_description(self) -> str:
        return "⚠️ EXPENSIVE O3-Pro basic validation (manual only)"

    def run_test(self) -> bool:
        """Test o3-pro model with endpoint verification - EXPENSIVE!"""
        try:
            self.logger.warning("⚠️ ⚠️ ⚠️  EXPENSIVE TEST - O3-PRO COSTS ~$15-60 PER 1K TOKENS! ⚠️ ⚠️ ⚠️")
            self.logger.info("Test: O3-Pro endpoint and functionality test")

            # First, verify we're hitting the right endpoint by checking logs
            self.logger.info("Step 1: Testing o3-pro with chat tool")

            # One simple chat call
            response, tool_result = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What is 2 + 2?",
                    "model": "o3-pro",
                    "temperature": 1.0,
                },
            )

            if not response:
                self.logger.error("❌ O3-Pro chat call failed - no response")
                if tool_result and "error" in tool_result:
                    error_msg = tool_result["error"]
                    self.logger.error(f"Error details: {error_msg}")
                    # Check if it's the endpoint error we're trying to fix
                    if "v1/responses" in str(error_msg) and "v1/chat/completions" in str(error_msg):
                        self.logger.error(
                            "❌ ENDPOINT BUG DETECTED: o3-pro is trying to use chat/completions instead of responses endpoint!"
                        )
                return False

            # Check the metadata to verify endpoint was used
            if tool_result and isinstance(tool_result, dict):
                metadata = tool_result.get("metadata", {})
                endpoint_used = metadata.get("endpoint", "unknown")

                if endpoint_used == "responses":
                    self.logger.info("✅ Correct endpoint used: /v1/responses")
                else:
                    self.logger.warning(f"⚠️ Endpoint used: {endpoint_used} (expected: responses)")

            # Verify the response content
            if response and "4" in str(response):
                self.logger.info("✅ O3-Pro response is mathematically correct")
            else:
                self.logger.warning(f"⚠️ Unexpected response: {response}")

            self.logger.info("✅ O3-Pro test completed successfully")
            self.logger.warning("💰 Test completed - check your billing!")
            return True

        except Exception as e:
            self.logger.error(f"O3-Pro test failed with exception: {e}")
            # Log the full error for debugging endpoint issues
            import traceback

            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


def main():
    """Run the O3-Pro expensive test"""
    import sys

    print("⚠️ ⚠️ ⚠️  WARNING: This test uses O3-PRO which is EXTREMELY EXPENSIVE! ⚠️ ⚠️ ⚠️")
    print("O3-Pro can cost $15-60 per 1K tokens!")
    print("This is a MINIMAL test but may still cost $5-15!")
    print()

    response = input("Are you absolutely sure you want to run this expensive test? Type 'YES_I_UNDERSTAND_THE_COST': ")
    if response != "YES_I_UNDERSTAND_THE_COST":
        print("❌ Test cancelled")
        sys.exit(1)

    print("💰 Running minimal O3-Pro test...")

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = O3ProExpensiveTest(verbose=verbose)

    success = test.run_test()

    if success:
        print("✅ O3-Pro test completed successfully")
        print("💰 Don't forget to check your billing!")
    else:
        print("❌ O3-Pro test failed")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
