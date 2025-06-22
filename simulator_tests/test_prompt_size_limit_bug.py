#!/usr/bin/env python3
"""
Prompt Size Limit Bug Test

This test reproduces a critical bug where the prompt size limit check
incorrectly includes conversation history when validating incoming prompts
from Claude to MCP. The limit should ONLY apply to the actual prompt text
sent by the user, not the entire conversation context.

Bug Scenario:
- User starts a conversation with chat tool
- Continues conversation multiple times (building up history)
- On subsequent continuation, a short prompt (150 chars) triggers
  "resend_prompt" error claiming >50k characters

Expected Behavior:
- Only count the actual prompt parameter for size limit
- Conversation history should NOT count toward prompt size limit
- Only the user's actual input should be validated against 50k limit
"""

from .conversation_base_test import ConversationBaseTest


class PromptSizeLimitBugTest(ConversationBaseTest):
    """Test to reproduce and verify fix for prompt size limit bug"""

    @property
    def test_name(self) -> str:
        return "prompt_size_limit_bug"

    @property
    def test_description(self) -> str:
        return "Reproduce prompt size limit bug with conversation continuation"

    def run_test(self) -> bool:
        """Test prompt size limit bug reproduction using in-process calls"""
        try:
            self.logger.info("🐛 Test: Prompt size limit bug reproduction (in-process)")

            # Setup test environment
            self.setUp()

            # Create a test file to provide context
            test_file_content = """
# Test SwiftUI-like Framework Implementation

struct ContentView: View {
    @State private var counter = 0

    var body: some View {
        VStack {
            Text("Count: \\(counter)")
            Button("Increment") {
                counter += 1
            }
        }
    }
}

class Renderer {
    static let shared = Renderer()

    func render(view: View) {
        // Implementation details for UIKit/AppKit rendering
    }
}

protocol View {
    var body: some View { get }
}
"""
            test_file_path = self.create_additional_test_file("SwiftFramework.swift", test_file_content)

            # Step 1: Start initial conversation
            self.logger.info("  Step 1: Start conversation with initial context")

            initial_prompt = "I'm building a SwiftUI-like framework. Can you help me design the architecture?"

            response1, continuation_id = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": initial_prompt,
                    "files": [test_file_path],
                    "model": "flash",
                },
            )

            if not response1 or not continuation_id:
                self.logger.error("  ❌ Failed to start initial conversation")
                return False

            self.logger.info(f"  ✅ Initial conversation started: {continuation_id[:8]}...")

            # Step 2: Continue conversation multiple times to build substantial history
            conversation_prompts = [
                "That's helpful! Can you elaborate on the View protocol design?",
                "How should I implement the State property wrapper?",
                "What's the best approach for the VStack layout implementation?",
                "Should I use UIKit directly or create an abstraction layer?",
                "Smart approach! For the rendering layer, would you suggest UIKit/AppKit directly?",
            ]

            for i, prompt in enumerate(conversation_prompts, 2):
                self.logger.info(f"  Step {i}: Continue conversation (exchange {i})")

                response, _ = self.call_mcp_tool_direct(
                    "chat",
                    {
                        "prompt": prompt,
                        "continuation_id": continuation_id,
                        "model": "flash",
                    },
                )

                if not response:
                    self.logger.error(f"  ❌ Failed at exchange {i}")
                    return False

                self.logger.info(f"  ✅ Exchange {i} completed")

            # Step 3: Send short prompt that should NOT trigger size limit
            self.logger.info("  Step 7: Send short prompt (should NOT trigger size limit)")

            # This is a very short prompt - should not trigger the bug after fix
            short_prompt = "Thanks! This gives me a solid foundation to start prototyping."

            self.logger.info(f"     Short prompt length: {len(short_prompt)} characters")

            response_final, _ = self.call_mcp_tool_direct(
                "chat",
                {
                    "prompt": short_prompt,
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not response_final:
                self.logger.error("  ❌ Final short prompt failed")
                return False

            # Parse the response to check for the bug
            import json

            try:
                response_data = json.loads(response_final)
                status = response_data.get("status", "")

                if status == "resend_prompt":
                    # This is the bug! Short prompt incorrectly triggering size limit
                    metadata = response_data.get("metadata", {})
                    prompt_size = metadata.get("prompt_size", 0)

                    self.logger.error(
                        f"  🐛 BUG STILL EXISTS: Short prompt ({len(short_prompt)} chars) triggered resend_prompt"
                    )
                    self.logger.error(f"     Reported prompt_size: {prompt_size} (should be ~{len(short_prompt)})")
                    self.logger.error("     This indicates conversation history is still being counted")

                    return False  # Bug still exists

                elif status in ["success", "continuation_available"]:
                    self.logger.info("  ✅ Short prompt processed correctly - bug appears to be FIXED!")
                    self.logger.info(f"     Prompt length: {len(short_prompt)} chars, Status: {status}")
                    return True

                else:
                    self.logger.warning(f"  ⚠️ Unexpected status: {status}")
                    # Check if this might be a non-JSON response (successful execution)
                    if len(response_final) > 0 and not response_final.startswith('{"'):
                        self.logger.info("  ✅ Non-JSON response suggests successful tool execution")
                        return True
                    return False

            except json.JSONDecodeError:
                # Non-JSON response often means successful tool execution
                self.logger.info("  ✅ Non-JSON response suggests successful tool execution (bug likely fixed)")
                self.logger.debug(f"     Response preview: {response_final[:200]}...")
                return True

        except Exception as e:
            self.logger.error(f"Prompt size limit bug test failed: {e}")
            import traceback

            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return False


def main():
    """Run the prompt size limit bug test"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = PromptSizeLimitBugTest(verbose=verbose)

    success = test.run_test()
    if success:
        print("Bug reproduction test completed - check logs for details")
    else:
        print("Test failed to complete")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
