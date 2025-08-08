"""
Consensus tool - Step-by-step multi-model consensus with expert analysis

This tool provides a structured workflow for gathering consensus from multiple models.
It guides the CLI agent through systematic steps where the CLI agent first provides its own analysis,
then consults each requested model one by one, and finally synthesizes all perspectives.

Key features:
- Step-by-step consensus workflow with progress tracking
- The CLI agent's initial neutral analysis followed by model-specific consultations
- Context-aware file embedding
- Support for stance-based analysis (for/against/neutral)
- Final synthesis combining all perspectives
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import Field, model_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from mcp.types import TextContent

from config import TEMPERATURE_ANALYTICAL
from systemprompts import CONSENSUS_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for consensus workflow
CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS = {
    "step": (
        "Describe your current consensus analysis step. In step 1, provide your own neutral, balanced analysis "
        "of the proposal/idea/plan after thinking carefully about all aspects. Consider technical feasibility, "
        "user value, implementation complexity, and alternatives. In subsequent steps (2+), you will receive "
        "individual model responses to synthesize. CRITICAL: Be thorough and balanced in your initial assessment, "
        "considering both benefits and risks, opportunities and challenges."
    ),
    "step_number": (
        "The index of the current step in the consensus workflow, beginning at 1. Step 1 is your analysis, "
        "steps 2+ are for processing individual model responses."
    ),
    "total_steps": (
        "Total number of steps needed. This equals the number of models to consult. "
        "Step 1 includes your analysis + first model consultation on return of the call. Final step includes "
        "last model consultation + synthesis."
    ),
    "next_step_required": ("Set to true if more models need to be consulted. False when ready for final synthesis."),
    "findings": (
        "In step 1, provide your comprehensive analysis of the proposal. In steps 2+, summarize the key points "
        "from the model response received, noting agreements and disagreements with previous analyses."
    ),
    "relevant_files": (
        "Files that are relevant to the consensus analysis. Include files that help understand the proposal, "
        "provide context, or contain implementation details."
    ),
    "models": (
        "List of model configurations to consult. Each can have a model name, stance (for/against/neutral), "
        "and optional custom stance prompt. The same model can be used multiple times with different stances, "
        "but each model + stance combination must be unique. "
        "Example: [{'model': 'o3', 'stance': 'for'}, {'model': 'o3', 'stance': 'against'}, "
        "{'model': 'flash', 'stance': 'neutral'}]"
    ),
    "current_model_index": (
        "Internal tracking of which model is being consulted (0-based index). Used to determine which model "
        "to call next."
    ),
    "model_responses": ("Accumulated responses from models consulted so far. Internal field for tracking progress."),
    "images": (
        "Optional list of image paths or base64 data URLs for visual context. Useful for UI/UX discussions, "
        "architecture diagrams, mockups, or any visual references that help inform the consensus analysis."
    ),
}


class ConsensusRequest(WorkflowRequest):
    """Request model for consensus workflow steps"""

    # Required fields for each step
    step: str = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["findings"])
    confidence: str = Field(default="exploring", exclude=True, description="Not used")

    # Consensus-specific fields (only needed in step 1)
    models: list[dict] | None = Field(None, description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["models"])
    relevant_files: list[str] | None = Field(
        default_factory=list,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
    )

    # Internal tracking fields
    current_model_index: int | None = Field(
        0,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["current_model_index"],
    )
    model_responses: list[dict] | None = Field(
        default_factory=list,
        description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["model_responses"],
    )

    # Optional images for visual debugging
    images: list[str] | None = Field(default=None, description=CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["images"])

    # Override inherited fields to exclude them from schema
    temperature: float | None = Field(default=None, exclude=True)
    thinking_mode: str | None = Field(default=None, exclude=True)
    use_websearch: bool | None = Field(default=None, exclude=True)

    # Not used in consensus workflow
    files_checked: list[str] | None = Field(default_factory=list, exclude=True)
    relevant_context: list[str] | None = Field(default_factory=list, exclude=True)
    issues_found: list[dict] | None = Field(default_factory=list, exclude=True)
    hypothesis: str | None = Field(None, exclude=True)
    backtrack_from_step: int | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def validate_step_one_requirements(self):
        """Ensure step 1 has required models field and unique model+stance combinations."""
        if self.step_number == 1:
            if not self.models:
                raise ValueError("Step 1 requires 'models' field to specify which models to consult")

            # Check for unique model + stance combinations
            seen_combinations = set()
            for model_config in self.models:
                model_name = model_config.get("model", "")
                stance = model_config.get("stance", "neutral")
                combination = f"{model_name}:{stance}"

                if combination in seen_combinations:
                    raise ValueError(
                        f"Duplicate model + stance combination found: {model_name} with stance '{stance}'. "
                        f"Each model + stance combination must be unique."
                    )
                seen_combinations.add(combination)

        return self


class ConsensusTool(WorkflowTool):
    """
    Consensus workflow tool for step-by-step multi-model consensus gathering.

    This tool implements a structured consensus workflow where the CLI agent first provides
    its own neutral analysis, then consults each specified model individually,
    and finally synthesizes all perspectives into a unified recommendation.
    """

    def __init__(self):
        super().__init__()
        self.initial_prompt: str | None = None
        self.models_to_consult: list[dict] = []
        self.accumulated_responses: list[dict] = []
        self._current_arguments: dict[str, Any] = {}

    def get_name(self) -> str:
        return "consensus"

    def get_description(self) -> str:
        return (
            "COMPREHENSIVE CONSENSUS WORKFLOW - Step-by-step multi-model consensus with structured analysis. "
            "This tool guides you through a systematic process where you:\n\n"
            "1. Start with step 1: provide your own neutral analysis of the proposal\n"
            "2. The tool will then consult each specified model one by one\n"
            "3. You'll receive each model's response in subsequent steps\n"
            "4. Track and synthesize perspectives as they accumulate\n"
            "5. Final step: present comprehensive consensus and recommendations\n\n"
            "IMPORTANT: This workflow enforces sequential model consultation:\n"
            "- Step 1 is always your independent analysis\n"
            "- Each subsequent step processes one model response\n"
            "- Total steps = number of models (each step includes consultation + response)\n"
            "- Models can have stances (for/against/neutral) for structured debate\n"
            "- Same model can be used multiple times with different stances\n"
            "- Each model + stance combination must be unique\n\n"
            "Perfect for: complex decisions, architectural choices, feature proposals, "
            "technology evaluations, strategic planning."
        )

    def get_system_prompt(self) -> str:
        # For the CLI agent's initial analysis, use a neutral version of the consensus prompt
        return CONSENSUS_PROMPT.replace(
            "{stance_prompt}",
            """BALANCED PERSPECTIVE

Provide objective analysis considering both positive and negative aspects. However, if there is overwhelming evidence
that the proposal clearly leans toward being exceptionally good or particularly problematic, you MUST accurately
reflect this reality. Being "balanced" means being truthful about the weight of evidence, not artificially creating
50/50 splits when the reality is 90/10.

Your analysis should:
- Present all significant pros and cons discovered
- Weight them according to actual impact and likelihood
- If evidence strongly favors one conclusion, clearly state this
- Provide proportional coverage based on the strength of arguments
- Help the questioner see the true balance of considerations

Remember: Artificial balance that misrepresents reality is not helpful. True balance means accurate representation
of the evidence, even when it strongly points in one direction.""",
        )

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> ToolModelCategory:
        """Consensus workflow requires extended reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the consensus workflow-specific request model."""
        return ConsensusRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema for consensus workflow."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Consensus tool-specific field definitions
        consensus_field_overrides = {
            # Override standard workflow fields that need consensus-specific descriptions
            "step": {
                "type": "string",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["findings"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
            },
            # consensus-specific fields (not in base workflow)
            "models": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "model": {"type": "string"},
                        "stance": {"type": "string", "enum": ["for", "against", "neutral"], "default": "neutral"},
                        "stance_prompt": {"type": "string"},
                    },
                    "required": ["model"],
                },
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["models"],
            },
            "current_model_index": {
                "type": "integer",
                "minimum": 0,
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["current_model_index"],
            },
            "model_responses": {
                "type": "array",
                "items": {"type": "object"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["model_responses"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": CONSENSUS_WORKFLOW_FIELD_DESCRIPTIONS["images"],
            },
        }

        # Define excluded fields for consensus workflow
        excluded_workflow_fields = [
            "files_checked",  # Not used in consensus workflow
            "relevant_context",  # Not used in consensus workflow
            "issues_found",  # Not used in consensus workflow
            "hypothesis",  # Not used in consensus workflow
            "backtrack_from_step",  # Not used in consensus workflow
            "confidence",  # Not used in consensus workflow
        ]

        excluded_common_fields = [
            "model",  # Consensus uses 'models' field instead
            "temperature",  # Not used in consensus workflow
            "thinking_mode",  # Not used in consensus workflow
            "use_websearch",  # Not used in consensus workflow
        ]

        # Build schema with proper field exclusion
        # Include model field for compatibility but don't require it
        schema = WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=consensus_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=False,  # Consensus doesn't require model at MCP boundary
            tool_name=self.get_name(),
            excluded_workflow_fields=excluded_workflow_fields,
            excluded_common_fields=excluded_common_fields,
        )
        return schema

    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int
    ) -> list[str]:  # noqa: ARG002
        """Define required actions for each consensus phase.

        Note: confidence parameter is kept for compatibility with base class but not used.
        """
        if step_number == 1:
            # CLI Agent's initial analysis
            return [
                "You've provided your initial analysis. The tool will now consult other models.",
                "Wait for the next step to receive the first model's response.",
            ]
        elif step_number < total_steps - 1:
            # Processing individual model responses
            return [
                "Review the model response provided in this step",
                "Note key agreements and disagreements with previous analyses",
                "Wait for the next model's response",
            ]
        else:
            # Ready for final synthesis
            return [
                "All models have been consulted",
                "Synthesize all perspectives into a comprehensive recommendation",
                "Identify key points of agreement and disagreement",
                "Provide clear, actionable guidance based on the consensus",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """Consensus workflow doesn't use traditional expert analysis - it consults models step by step."""
        return False

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Not used in consensus workflow."""
        return ""

    def requires_expert_analysis(self) -> bool:
        """Consensus workflow handles its own model consultations."""
        return False

    def requires_model(self) -> bool:
        """
        Consensus tool doesn't require model resolution at the MCP boundary.

        Uses it's own set of models

        Returns:
            bool: False
        """
        return False

    # Hook method overrides for consensus-specific behavior

    def prepare_step_data(self, request) -> dict:
        """Prepare consensus-specific step data."""
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": [],  # Not used
            "relevant_files": request.relevant_files or [],
            "relevant_context": [],  # Not used
            "issues_found": [],  # Not used
            "confidence": "exploring",  # Not used, kept for compatibility
            "hypothesis": None,  # Not used
            "images": request.images or [],  # Now used for visual context
        }
        return step_data

    async def handle_work_completion(self, response_data: dict, request, arguments: dict) -> dict:  # noqa: ARG002
        """Handle consensus workflow completion - no expert analysis, just final synthesis."""
        response_data["consensus_complete"] = True
        response_data["status"] = "consensus_workflow_complete"

        # Prepare final synthesis data
        response_data["complete_consensus"] = {
            "initial_prompt": self.initial_prompt,
            "models_consulted": [m["model"] + ":" + m.get("stance", "neutral") for m in self.accumulated_responses],
            "total_responses": len(self.accumulated_responses),
            "consensus_confidence": "high",  # Consensus complete
        }

        response_data["next_steps"] = (
            "CONSENSUS GATHERING IS COMPLETE. You MUST now synthesize all perspectives and present:\n"
            "1. Key points of AGREEMENT across models\n"
            "2. Key points of DISAGREEMENT and why they differ\n"
            "3. Your final consolidated recommendation\n"
            "4. Specific, actionable next steps for implementation\n"
            "5. Critical risks or concerns that must be addressed"
        )

        return response_data

    def handle_work_continuation(self, response_data: dict, request) -> dict:
        """Handle continuation between consensus steps."""
        current_idx = request.current_model_index or 0

        if request.step_number == 1:
            # After CLI Agent's initial analysis, prepare to consult first model
            response_data["status"] = "consulting_models"
            response_data["next_model"] = self.models_to_consult[0] if self.models_to_consult else None
            response_data["next_steps"] = (
                "Your initial analysis is complete. The tool will now consult the specified models."
            )
        elif current_idx < len(self.models_to_consult):
            next_model = self.models_to_consult[current_idx]
            response_data["status"] = "consulting_next_model"
            response_data["next_model"] = next_model
            response_data["models_remaining"] = len(self.models_to_consult) - current_idx
            response_data["next_steps"] = f"Model consultation in progress. Next: {next_model['model']}"
        else:
            response_data["status"] = "ready_for_synthesis"
            response_data["next_steps"] = "All models consulted. Ready for final synthesis."

        return response_data

    async def execute_workflow(self, arguments: dict[str, Any]) -> list:
        """Override execute_workflow to handle model consultations between steps."""

        # Store arguments
        self._current_arguments = arguments

        # Validate request
        request = self.get_workflow_request_model()(**arguments)

        # On first step, store the models to consult
        if request.step_number == 1:
            self.initial_prompt = request.step
            self.models_to_consult = request.models or []
            self.accumulated_responses = []
            # Set total steps: len(models) (each step includes consultation + response)
            request.total_steps = len(self.models_to_consult)

        # For all steps (1 through total_steps), consult the corresponding model
        if request.step_number <= request.total_steps:
            # Calculate which model to consult for this step
            model_idx = request.step_number - 1  # 0-based index

            if model_idx < len(self.models_to_consult):
                # Consult the model for this step
                model_response = await self._consult_model(self.models_to_consult[model_idx], request)

                # Add to accumulated responses
                self.accumulated_responses.append(model_response)

                # Include the model response in the step data
                response_data = {
                    "status": "model_consulted",
                    "step_number": request.step_number,
                    "total_steps": request.total_steps,
                    "model_consulted": model_response["model"],
                    "model_stance": model_response.get("stance", "neutral"),
                    "model_response": model_response,
                    "current_model_index": model_idx + 1,
                    "next_step_required": request.step_number < request.total_steps,
                }

                # Add CLAI Agent's analysis to step 1
                if request.step_number == 1:
                    response_data["agent_analysis"] = {
                        "initial_analysis": request.step,
                        "findings": request.findings,
                    }
                    response_data["status"] = "analysis_and_first_model_consulted"

                # Check if this is the final step
                if request.step_number == request.total_steps:
                    response_data["status"] = "consensus_workflow_complete"
                    response_data["consensus_complete"] = True
                    response_data["complete_consensus"] = {
                        "initial_prompt": self.initial_prompt,
                        "models_consulted": [
                            f"{m['model']}:{m.get('stance', 'neutral')}" for m in self.accumulated_responses
                        ],
                        "total_responses": len(self.accumulated_responses),
                        "consensus_confidence": "high",
                    }
                    response_data["next_steps"] = (
                        "CONSENSUS GATHERING IS COMPLETE. Synthesize all perspectives and present:\n"
                        "1. Key points of AGREEMENT across models\n"
                        "2. Key points of DISAGREEMENT and why they differ\n"
                        "3. Your final consolidated recommendation\n"
                        "4. Specific, actionable next steps for implementation\n"
                        "5. Critical risks or concerns that must be addressed"
                    )
                else:
                    response_data["next_steps"] = (
                        f"Model {model_response['model']} has provided its {model_response.get('stance', 'neutral')} "
                        f"perspective. Please analyze this response and call {self.get_name()} again with:\n"
                        f"- step_number: {request.step_number + 1}\n"
                        f"- findings: Summarize key points from this model's response"
                    )

                # Add accumulated responses for tracking
                response_data["accumulated_responses"] = self.accumulated_responses

                # Add metadata (since we're bypassing the base class metadata addition)
                model_name = self.get_request_model_name(request)
                provider = self.get_model_provider(model_name)
                response_data["metadata"] = {
                    "tool_name": self.get_name(),
                    "model_name": model_name,
                    "model_used": model_name,
                    "provider_used": provider.get_provider_type().value,
                }

                return [TextContent(type="text", text=json.dumps(response_data, indent=2, ensure_ascii=False))]

        # Otherwise, use standard workflow execution
        return await super().execute_workflow(arguments)

    async def _consult_model(self, model_config: dict, request) -> dict:
        """Consult a single model and return its response."""
        try:
            # Get the provider for this model
            model_name = model_config["model"]
            provider = self.get_model_provider(model_name)

            # Prepare the prompt with any relevant files
            # Use continuation_id=None for blinded consensus - each model should only see
            # original prompt + files, not conversation history or other model responses
            prompt = self.initial_prompt
            if request.relevant_files:
                file_content, _ = self._prepare_file_content_for_prompt(
                    request.relevant_files,
                    None,  # Use None instead of request.continuation_id for blinded consensus
                    "Context files",
                )
                if file_content:
                    prompt = f"{prompt}\n\n=== CONTEXT FILES ===\n{file_content}\n=== END CONTEXT ==="

            # Get stance-specific system prompt
            stance = model_config.get("stance", "neutral")
            stance_prompt = model_config.get("stance_prompt")
            system_prompt = self._get_stance_enhanced_prompt(stance, stance_prompt)

            # Call the model
            response = provider.generate_content(
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=0.2,  # Low temperature for consistency
                thinking_mode="medium",
                images=request.images if request.images else None,
            )

            return {
                "model": model_name,
                "stance": stance,
                "status": "success",
                "verdict": response.content,
                "metadata": {
                    "provider": provider.get_provider_type().value,
                    "model_name": model_name,
                },
            }

        except Exception as e:
            logger.exception("Error consulting model %s", model_config)
            return {
                "model": model_config.get("model", "unknown"),
                "stance": model_config.get("stance", "neutral"),
                "status": "error",
                "error": str(e),
            }

    def _get_stance_enhanced_prompt(self, stance: str, custom_stance_prompt: str | None = None) -> str:
        """Get the system prompt with stance injection."""
        base_prompt = CONSENSUS_PROMPT

        if custom_stance_prompt:
            return base_prompt.replace("{stance_prompt}", custom_stance_prompt)

        stance_prompts = {
            "for": """SUPPORTIVE PERSPECTIVE WITH INTEGRITY

You are tasked with advocating FOR this proposal, but with CRITICAL GUARDRAILS:

MANDATORY ETHICAL CONSTRAINTS:
- This is NOT a debate for entertainment. You MUST act in good faith and in the best interest of the questioner
- You MUST think deeply about whether supporting this idea is safe, sound, and passes essential requirements
- You MUST be direct and unequivocal in saying "this is a bad idea" when it truly is
- There must be at least ONE COMPELLING reason to be optimistic, otherwise DO NOT support it

WHEN TO REFUSE SUPPORT (MUST OVERRIDE STANCE):
- If the idea is fundamentally harmful to users, project, or stakeholders
- If implementation would violate security, privacy, or ethical standards
- If the proposal is technically infeasible within realistic constraints
- If costs/risks dramatically outweigh any potential benefits

YOUR SUPPORTIVE ANALYSIS SHOULD:
- Identify genuine strengths and opportunities
- Propose solutions to overcome legitimate challenges
- Highlight synergies with existing systems
- Suggest optimizations that enhance value
- Present realistic implementation pathways

Remember: Being "for" means finding the BEST possible version of the idea IF it has merit, not blindly supporting bad ideas.""",
            "against": """CRITICAL PERSPECTIVE WITH RESPONSIBILITY

You are tasked with critiquing this proposal, but with ESSENTIAL BOUNDARIES:

MANDATORY FAIRNESS CONSTRAINTS:
- You MUST NOT oppose genuinely excellent, common-sense ideas just to be contrarian
- You MUST acknowledge when a proposal is fundamentally sound and well-conceived
- You CANNOT give harmful advice or recommend against beneficial changes
- If the idea is outstanding, say so clearly while offering constructive refinements

WHEN TO MODERATE CRITICISM (MUST OVERRIDE STANCE):
- If the proposal addresses critical user needs effectively
- If it follows established best practices with good reason
- If benefits clearly and substantially outweigh risks
- If it's the obvious right solution to the problem

YOUR CRITICAL ANALYSIS SHOULD:
- Identify legitimate risks and failure modes
- Point out overlooked complexities
- Suggest more efficient alternatives
- Highlight potential negative consequences
- Question assumptions that may be flawed

Remember: Being "against" means rigorous scrutiny to ensure quality, not undermining good ideas that deserve support.""",
            "neutral": """BALANCED PERSPECTIVE

Provide objective analysis considering both positive and negative aspects. However, if there is overwhelming evidence
that the proposal clearly leans toward being exceptionally good or particularly problematic, you MUST accurately
reflect this reality. Being "balanced" means being truthful about the weight of evidence, not artificially creating
50/50 splits when the reality is 90/10.

Your analysis should:
- Present all significant pros and cons discovered
- Weight them according to actual impact and likelihood
- If evidence strongly favors one conclusion, clearly state this
- Provide proportional coverage based on the strength of arguments
- Help the questioner see the true balance of considerations

Remember: Artificial balance that misrepresents reality is not helpful. True balance means accurate representation
of the evidence, even when it strongly points in one direction.""",
        }

        stance_prompt = stance_prompts.get(stance, stance_prompts["neutral"])
        return base_prompt.replace("{stance_prompt}", stance_prompt)

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """Customize response for consensus workflow."""
        # Store model responses in the response for tracking
        if self.accumulated_responses:
            response_data["accumulated_responses"] = self.accumulated_responses

        # Add consensus-specific fields
        if request.step_number == 1:
            response_data["consensus_workflow_status"] = "initial_analysis_complete"
        elif request.step_number < request.total_steps - 1:
            response_data["consensus_workflow_status"] = "consulting_models"
        else:
            response_data["consensus_workflow_status"] = "ready_for_synthesis"

        # Customize metadata for consensus workflow
        self._customize_consensus_metadata(response_data, request)

        return response_data

    def _customize_consensus_metadata(self, response_data: dict, request) -> None:
        """
        Customize metadata for consensus workflow to accurately reflect multi-model nature.

        The default workflow metadata shows the model running Agent's analysis steps,
        but consensus is a multi-model tool that consults different models. We need
        to provide accurate metadata that reflects this.
        """
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        metadata = response_data["metadata"]

        # Always preserve tool_name
        metadata["tool_name"] = self.get_name()

        if request.step_number == request.total_steps:
            # Final step - show comprehensive consensus metadata
            models_consulted = []
            if self.models_to_consult:
                models_consulted = [f"{m['model']}:{m.get('stance', 'neutral')}" for m in self.models_to_consult]

            metadata.update(
                {
                    "workflow_type": "multi_model_consensus",
                    "models_consulted": models_consulted,
                    "consensus_complete": True,
                    "total_models": len(self.models_to_consult) if self.models_to_consult else 0,
                }
            )

            # Remove the misleading single model metadata
            metadata.pop("model_used", None)
            metadata.pop("provider_used", None)

        else:
            # Intermediate steps - show consensus workflow in progress
            models_to_consult = []
            if self.models_to_consult:
                models_to_consult = [f"{m['model']}:{m.get('stance', 'neutral')}" for m in self.models_to_consult]

            metadata.update(
                {
                    "workflow_type": "multi_model_consensus",
                    "models_to_consult": models_to_consult,
                    "consultation_step": request.step_number,
                    "total_consultation_steps": request.total_steps,
                }
            )

            # Remove the misleading single model metadata that shows Agent's execution model
            # instead of the models being consulted
            metadata.pop("model_used", None)
            metadata.pop("provider_used", None)

    def _add_workflow_metadata(self, response_data: dict, arguments: dict[str, Any]) -> None:
        """
        Override workflow metadata addition for consensus tool.

        The consensus tool doesn't use single model metadata because it's a multi-model
        workflow. Instead, we provide consensus-specific metadata that accurately
        reflects the models being consulted.
        """
        # Initialize metadata if not present
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        # Add basic tool metadata
        response_data["metadata"]["tool_name"] = self.get_name()

        # The consensus-specific metadata is already added by _customize_consensus_metadata
        # which is called from customize_workflow_response. We don't add the standard
        # single-model metadata (model_used, provider_used) because it's misleading
        # for a multi-model consensus workflow.

        logger.debug(
            f"[CONSENSUS_METADATA] {self.get_name()}: Using consensus-specific metadata instead of single-model metadata"
        )

    def store_initial_issue(self, step_description: str):
        """Store initial prompt for model consultations."""
        self.initial_prompt = step_description

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the consensus workflow-specific request model."""
        return ConsensusRequest

    async def prepare_prompt(self, request) -> str:  # noqa: ARG002
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
