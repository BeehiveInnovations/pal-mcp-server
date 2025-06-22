"""
Test consensus tool with three models demonstrating sequential processing
"""

import json

from .base_test import BaseSimulatorTest


class TestConsensusThreeModels(BaseSimulatorTest):
    """Test consensus tool functionality with three models (testing sequential processing)"""

    @property
    def test_name(self) -> str:
        return "consensus_three_models"

    @property
    def test_description(self) -> str:
        return "Test consensus tool with three models using flash:against, flash:for, local-llama:neutral"

    def run_test(self) -> bool:
        """Run three-model consensus test"""
        try:
            self.logger.info("Testing consensus tool with three models: flash:against, flash:for, local-llama:neutral")

            # Send request with three ModelConfig objects using new workflow parameters
            response, continuation_id = self.call_mcp_tool(
                "consensus",
                {
                    "step": "Is a sync manager class a good idea for my CoolTodos app?",
                    "step_number": 1,
                    "total_steps": 3,  # 3 models = 3 steps
                    "next_step_required": True,
                    "findings": "Initial analysis needed on sync manager class architecture decision for CoolTodos app",
                    "models": [
                        {
                            "model": "flash",
                            "stance": "against",
                            "stance_prompt": "You are a software architecture critic. Focus on the potential downsides of adding a sync manager class: complexity overhead, maintenance burden, potential for over-engineering, and whether simpler alternatives exist. Consider if this adds unnecessary abstraction layers.",
                        },
                        {
                            "model": "flash",
                            "stance": "for",
                            "stance_prompt": "You are a software architecture advocate. Focus on the benefits of a sync manager class: separation of concerns, testability, maintainability, and how it can improve the overall architecture. Consider scalability and code organization advantages.",
                        },
                        {
                            "model": "local-llama",
                            "stance": "neutral",
                            "stance_prompt": "You are a pragmatic software engineer. Provide a balanced analysis considering both the benefits and drawbacks. Focus on the specific context of a CoolTodos app and what factors would determine if this is the right choice.",
                        },
                    ],
                    "model": "flash",  # Default model for Claude's execution
                },
            )

            # Validate response
            if not response:
                self.logger.error("Failed to get response from three-model consensus tool")
                return False

            self.logger.info(f"Three-model consensus response preview: {response[:500]}...")

            # Parse the JSON response
            try:
                consensus_data = json.loads(response)
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse three-model consensus response as JSON: {response}")
                return False

            # Validate consensus structure
            if "status" not in consensus_data:
                self.logger.error("Missing 'status' field in three-model consensus response")
                return False

            # Check for step 1 status (Claude analysis + first model consultation)
            expected_status = "analysis_and_first_model_consulted"
            if consensus_data["status"] != expected_status:
                self.logger.error(f"Three-model consensus step 1 failed with status: {consensus_data['status']}, expected: {expected_status}")

                # Log additional error details for debugging
                if "error" in consensus_data:
                    self.logger.error(f"Error message: {consensus_data['error']}")
                if "models_errored" in consensus_data:
                    self.logger.error(f"Models that errored: {consensus_data['models_errored']}")
                if "models_skipped" in consensus_data:
                    self.logger.error(f"Models skipped: {consensus_data['models_skipped']}")
                if "next_steps" in consensus_data:
                    self.logger.error(f"Suggested next steps: {consensus_data['next_steps']}")

                return False

            # Check that we have model response from step 1 
            model_response = consensus_data.get("model_response")
            if not model_response:
                self.logger.error("Three-model consensus step 1 response missing model_response")
                return False

            # Check that model response has expected structure
            if not model_response.get("model") or not model_response.get("verdict"):
                self.logger.error("Model response missing required fields (model or verdict)")
                return False

            # Check step information
            if consensus_data.get("step_number") != 1:
                self.logger.error(f"Expected step_number 1, got: {consensus_data.get('step_number')}")
                return False

            if not consensus_data.get("next_step_required"):
                self.logger.error("Expected next_step_required=True for step 1")
                return False

            self.logger.info(f"Consensus step 1 consulted model: {model_response.get('model')}")
            self.logger.info(f"Model stance: {model_response.get('stance', 'neutral')}")
            self.logger.info(f"Response status: {model_response.get('status', 'unknown')}")

            # Check metadata contains model name
            metadata = consensus_data.get("metadata", {})
            if not metadata.get("model_name"):
                self.logger.error("Missing model_name in metadata")
                return False

            self.logger.info(f"Model name in metadata: {metadata.get('model_name')}")

            # Verify we have analysis from Claude
            claude_analysis = consensus_data.get("claude_analysis")
            if not claude_analysis:
                self.logger.error("Missing Claude's analysis in step 1")
                return False

            analysis_text = claude_analysis.get("initial_analysis", "")
            self.logger.info(f"Claude analysis length: {len(analysis_text)} characters")

            self.logger.info("✓ Three-model consensus tool test completed successfully")
            self.logger.info(f"✓ Step 1 completed with model: {model_response.get('model')}")
            self.logger.info(f"✓ Analysis provided: {len(analysis_text)} characters")
            self.logger.info(f"✓ Model metadata properly included: {metadata.get('model_name')}")
            self.logger.info("✓ Ready for step 2 continuation")

            return True

        except Exception as e:
            self.logger.error(f"Three-model consensus test failed with exception: {str(e)}")
            return False
