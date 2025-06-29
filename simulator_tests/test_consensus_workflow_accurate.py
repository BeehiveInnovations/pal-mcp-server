"""
Accurate Consensus Workflow Test

This test validates the complete consensus workflow step-by-step to ensure:
1. Step 1: Claude provides its own analysis
2. Step 2: Tool consults first model and returns response to Claude
3. Step 3: Tool consults second model and returns response to Claude
4. Step 4: Claude synthesizes all perspectives

This replaces the old faulty test that used non-workflow parameters.
"""

import json

from .conversation_base_test import ConversationBaseTest


class TestConsensusWorkflowAccurate(ConversationBaseTest):
    """Test complete consensus workflow with accurate step-by-step behavior"""

    @property
    def test_name(self) -> str:
        return "consensus_workflow_accurate"

    @property
    def test_description(self) -> str:
        return "Test NEW efficient consensus workflow: 2 models = 2 steps (Claude+model1, model2+synthesis)"

    def run_test(self) -> bool:
        """Run complete consensus workflow test"""
        # Set up the test environment
        self.setUp()

        try:
            self.logger.info("Testing complete consensus workflow step-by-step")
            self.logger.info("Expected NEW flow: Step1(Claude+Model1) -> Step2(Model2+Synthesis)")

            # ============================================================================
            # STEP 1: Claude analysis + first model consultation
            # ============================================================================
            self.logger.info("=== STEP 1: Claude analysis + flash:for consultation ===")

            step1_response, continuation_id = self.call_mcp_tool_direct(
                "consensus",
                {
                    "step": "Should we add a new AI-powered search feature to our application? Please analyze the technical feasibility, user value, and implementation complexity.",
                    "step_number": 1,
                    "total_steps": 2,  # 2 models (each step includes consultation + analysis)
                    "next_step_required": True,
                    "findings": "Initial assessment of AI search feature proposal considering user needs, technical constraints, and business value.",
                    "models": [
                        {
                            "model": "flash",
                            "stance": "for",
                            "stance_prompt": "Focus on innovation benefits and competitive advantages.",
                        },
                        {
                            "model": "flash",
                            "stance": "against",
                            "stance_prompt": "Focus on implementation complexity and resource requirements.",
                        },
                    ],
                    "model": "flash",  # Claude's execution model
                },
            )

            if not step1_response:
                self.logger.error("Step 1 failed - no response")
                return False

            step1_data = json.loads(step1_response)
            self.logger.info(f"Step 1 status: {step1_data.get('status')}")

            # Validate step 1 response (should include Claude's analysis + first model consultation)
            if step1_data.get("status") != "analysis_and_first_model_consulted":
                self.logger.error(
                    f"Expected status 'analysis_and_first_model_consulted', got: {step1_data.get('status')}"
                )
                return False

            if step1_data.get("step_number") != 1:
                self.logger.error(f"Expected step_number 1, got: {step1_data.get('step_number')}")
                return False

            if not step1_data.get("next_step_required"):
                self.logger.error("Expected next_step_required=True for step 1")
                return False

            # Verify Claude's analysis is included
            if "agent_analysis" not in step1_data:
                self.logger.error("Expected agent_analysis in step 1 response")
                return False

            # Verify first model response is included
            if "model_response" not in step1_data:
                self.logger.error("Expected model_response in step 1 response")
                return False

            model1_response = step1_data["model_response"]
            if model1_response.get("model") != "flash" or model1_response.get("stance") != "for":
                self.logger.error(
                    f"Expected flash:for model response in step 1, got: {model1_response.get('model')}:{model1_response.get('stance')}"
                )
                return False

            self.logger.info("✓ Step 1 completed - Claude analysis + first model (flash:for) consulted")

            # ============================================================================
            # STEP 2: Final step - second model consultation + synthesis
            # ============================================================================
            self.logger.info("=== STEP 2: Final step - second model (flash:against) + synthesis ===")

            step2_response, _ = self.call_mcp_tool_direct(
                "consensus",
                {
                    "step": "I need to review the second model's perspective and provide final synthesis.",
                    "step_number": 2,
                    "total_steps": 2,
                    "next_step_required": False,  # Final step
                    "findings": "Analyzed first model's 'for' perspective. Now ready for second model's 'against' stance and final synthesis.",
                    "continuation_id": continuation_id,
                    "model": "flash",
                },
            )

            if not step2_response:
                self.logger.error("Step 2 failed - no response")
                return False

            self.logger.info(f"Step 2 raw response: {step2_response[:500]}...")
            step2_data = json.loads(step2_response)
            self.logger.info(f"Step 2 status: {step2_data.get('status')}")

            # Validate step 2 - should show consensus completion
            if step2_data.get("status") != "consensus_workflow_complete":
                self.logger.error(f"Expected status 'consensus_workflow_complete', got: {step2_data.get('status')}")
                return False

            if step2_data.get("model_consulted") != "flash":
                self.logger.error(f"Expected model_consulted 'flash', got: {step2_data.get('model_consulted')}")
                return False

            if step2_data.get("model_stance") != "against":
                self.logger.error(f"Expected model_stance 'against', got: {step2_data.get('model_stance')}")
                return False

            # Verify model response is included
            if "model_response" not in step2_data:
                self.logger.error("Expected model_response in step 2")
                return False

            model2_response = step2_data["model_response"]
            if model2_response.get("model") != "flash":
                self.logger.error(f"Expected model_response.model 'flash', got: {model2_response.get('model')}")
                return False

            # Verify consensus completion data
            if not step2_data.get("consensus_complete"):
                self.logger.error("Expected consensus_complete=True in final step")
                return False

            if "complete_consensus" not in step2_data:
                self.logger.error("Expected complete_consensus data in final step")
                return False

            self.logger.info("✓ Step 2 completed - Second model (flash:against) consulted and consensus complete")
            self.logger.info(f"Model 2 verdict preview: {model2_response.get('verdict', 'No verdict')[:100]}...")

            # Validate final consensus completion data
            complete_consensus = step2_data["complete_consensus"]
            if complete_consensus.get("total_responses") != 2:
                self.logger.error(f"Expected 2 model responses, got: {complete_consensus.get('total_responses')}")
                return False

            models_consulted = complete_consensus.get("models_consulted", [])
            expected_models = ["flash:for", "flash:against"]
            if models_consulted != expected_models:
                self.logger.error(f"Expected models {expected_models}, got: {models_consulted}")
                return False

            # ============================================================================
            # VALIDATION: Check accumulated responses are available
            # ============================================================================
            self.logger.info("=== VALIDATION: Checking accumulated responses ===")

            if "accumulated_responses" not in step2_data:
                self.logger.error("Expected accumulated_responses in final step")
                return False

            accumulated = step2_data["accumulated_responses"]
            if len(accumulated) != 2:
                self.logger.error(f"Expected 2 accumulated responses, got: {len(accumulated)}")
                return False

            # Verify first response (flash:for)
            response1 = accumulated[0]
            if response1.get("model") != "flash" or response1.get("stance") != "for":
                self.logger.error(f"First response incorrect: {response1}")
                return False

            # Verify second response (flash:against)
            response2 = accumulated[1]
            if response2.get("model") != "flash" or response2.get("stance") != "against":
                self.logger.error(f"Second response incorrect: {response2}")
                return False

            self.logger.info("✓ All accumulated responses validated")

            # ============================================================================
            # SUCCESS
            # ============================================================================
            self.logger.info("🎉 CONSENSUS WORKFLOW TEST PASSED")
            self.logger.info("✓ Step 1: Claude analysis + first model (flash:for) consulted")
            self.logger.info("✓ Step 2: Second model (flash:against) consulted + synthesis completed")
            self.logger.info("✓ All model responses accumulated correctly")
            self.logger.info("✓ New efficient workflow: 2 models = 2 steps (not 4)")
            self.logger.info("✓ Workflow progression validated at each step")

            return True

        except Exception as e:
            self.logger.error(f"Consensus workflow test failed with exception: {str(e)}")
            import traceback

            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
