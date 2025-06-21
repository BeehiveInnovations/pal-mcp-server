"""
Interactive Sequential Planner - Break down complex tasks through step-by-step planning

This tool enables structured planning through an interactive, step-by-step process that builds
plans incrementally with the ability to revise, branch, and adapt as understanding deepens.

The planner guides users through sequential thinking with forced pauses between steps to ensure
thorough consideration of alternatives, dependencies, and strategic decisions before moving to
tactical implementation details.

Key features:
- Sequential planning with full context awareness
- Forced deep reflection for complex plans (≥5 steps) in early stages
- Branching capabilities for exploring alternative approaches
- Revision capabilities to update earlier decisions
- Dynamic step count adjustment as plans evolve
- Self-contained completion without external expert analysis

Perfect for: complex project planning, system design with unknowns, migration strategies,
architectural decisions, and breaking down large problems into manageable steps.
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, field_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_BALANCED
from systemprompts import PLANNER_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions matching original planner tool
PLANNER_FIELD_DESCRIPTIONS = {
    "step": (
        "Your current planning step. For the first step, describe the task/problem to plan and be extremely expressive "
        "so that subsequent steps can break this down into simpler steps. "
        "For subsequent steps, provide the actual planning step content. Can include: regular planning steps, "
        "revisions of previous steps, questions about previous decisions, realizations about needing more analysis, "
        "changes in approach, etc."
    ),
    "step_number": "Current step number in the planning sequence (starts at 1)",
    "total_steps": "Current estimate of total steps needed (can be adjusted up/down as planning progresses)",
    "next_step_required": "Whether another planning step is required after this one",
    "is_step_revision": "True if this step revises/replaces a previous step",
    "revises_step_number": "If is_step_revision is true, which step number is being revised",
    "is_branch_point": "True if this step branches from a previous step to explore alternatives",
    "branch_from_step": "If is_branch_point is true, which step number is the branching point",
    "branch_id": "Identifier for the current branch (e.g., 'approach-A', 'microservices-path')",
    "more_steps_needed": "True if more steps are needed beyond the initial estimate",
}


class PlannerRequest(WorkflowRequest):
    """Request model for planner workflow tool matching original planner exactly"""

    # Required fields for each planning step
    step: str = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["next_step_required"])

    # Optional revision/branching fields (planning-specific)
    is_step_revision: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["is_step_revision"])
    revises_step_number: Optional[int] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["revises_step_number"])
    is_branch_point: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["is_branch_point"])
    branch_from_step: Optional[int] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["branch_from_step"])
    branch_id: Optional[str] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["branch_id"])
    more_steps_needed: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["more_steps_needed"])

    # Exclude all investigation/analysis fields that aren't relevant to planning
    findings: str = Field(
        default="", exclude=True, description="Not used for planning - step content serves as findings"
    )
    files_checked: list[str] = Field(default_factory=list, exclude=True, description="Planning doesn't examine files")
    relevant_files: list[str] = Field(default_factory=list, exclude=True, description="Planning doesn't use files")
    relevant_context: list[str] = Field(
        default_factory=list, exclude=True, description="Planning doesn't track code context"
    )
    issues_found: list[dict] = Field(default_factory=list, exclude=True, description="Planning doesn't find issues")
    confidence: str = Field(default="planning", exclude=True, description="Planning uses different confidence model")
    hypothesis: Optional[str] = Field(default=None, exclude=True, description="Planning doesn't use hypothesis")
    backtrack_from_step: Optional[int] = Field(default=None, exclude=True, description="Planning uses revision instead")

    # Exclude other non-planning fields
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)
    use_assistant_model: Optional[bool] = Field(default=False, exclude=True, description="Planning is self-contained")
    images: Optional[list] = Field(default=None, exclude=True, description="Planning doesn't use images")

    @field_validator("step_number")
    @classmethod
    def validate_step_number(cls, v):
        if v < 1:
            raise ValueError("step_number must be at least 1")
        return v

    @field_validator("total_steps")
    @classmethod
    def validate_total_steps(cls, v):
        if v < 1:
            raise ValueError("total_steps must be at least 1")
        return v


class PlannerTool(WorkflowTool):
    """
    Planner workflow tool for step-by-step planning using the workflow architecture.

    This tool provides the same planning capabilities as the original planner tool
    but uses the new workflow architecture for consistency with other workflow tools.
    It maintains all the original functionality including:
    - Sequential step-by-step planning
    - Branching and revision capabilities
    - Deep thinking pauses for complex plans
    - Conversation memory integration
    - Self-contained operation (no expert analysis)
    """

    def __init__(self):
        super().__init__()
        self.branches = {}

    def get_name(self) -> str:
        return "planner"

    def get_description(self) -> str:
        return (
            "INTERACTIVE SEQUENTIAL PLANNER - Break down complex tasks through step-by-step planning. "
            "This tool enables you to think sequentially, building plans incrementally with the ability "
            "to revise, branch, and adapt as understanding deepens.\n\n"
            "How it works:\n"
            "- Start with step 1: describe the task/problem to plan\n"
            "- Continue with subsequent steps, building the plan piece by piece\n"
            "- Adjust total_steps estimate as you progress\n"
            "- Revise previous steps when new insights emerge\n"
            "- Branch into alternative approaches when needed\n"
            "- Add more steps even after reaching the initial estimate\n\n"
            "Key features:\n"
            "- Sequential thinking with full context awareness\n"
            "- Forced deep reflection for complex plans (≥5 steps) in early stages\n"
            "- Branching for exploring alternative strategies\n"
            "- Revision capabilities to update earlier decisions\n"
            "- Dynamic step count adjustment\n\n"
            "ENHANCED: For complex plans (≥5 steps), the first 3 steps enforce deep thinking pauses\n"
            "to prevent surface-level planning and ensure thorough consideration of alternatives,\n"
            "dependencies, and strategic decisions before moving to tactical details.\n\n"
            "Perfect for: complex project planning, system design with unknowns, "
            "migration strategies, architectural decisions, problem decomposition."
        )

    def get_system_prompt(self) -> str:
        return PLANNER_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_BALANCED

    def get_model_category(self) -> "ToolModelCategory":
        """Planner requires deep analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def requires_model(self) -> bool:
        """
        Planner tool doesn't require model resolution at the MCP boundary.

        The planner is a pure data processing tool that organizes planning steps
        and provides structured guidance without calling external AI models.

        Returns:
            bool: False - planner doesn't need AI model access
        """
        return False

    def get_workflow_request_model(self):
        """Return the planner-specific request model."""
        return PlannerRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Return planning-specific field definitions beyond the standard workflow fields."""
        return {
            # Planning-specific optional fields
            "is_step_revision": {
                "type": "boolean",
                "description": PLANNER_FIELD_DESCRIPTIONS["is_step_revision"],
            },
            "revises_step_number": {
                "type": "integer",
                "minimum": 1,
                "description": PLANNER_FIELD_DESCRIPTIONS["revises_step_number"],
            },
            "is_branch_point": {
                "type": "boolean",
                "description": PLANNER_FIELD_DESCRIPTIONS["is_branch_point"],
            },
            "branch_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": PLANNER_FIELD_DESCRIPTIONS["branch_from_step"],
            },
            "branch_id": {
                "type": "string",
                "description": PLANNER_FIELD_DESCRIPTIONS["branch_id"],
            },
            "more_steps_needed": {
                "type": "boolean",
                "description": PLANNER_FIELD_DESCRIPTIONS["more_steps_needed"],
            },
        }

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with field exclusion."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Exclude investigation-specific fields that planning doesn't need
        excluded_workflow_fields = [
            "findings",  # Planning uses step content instead
            "files_checked",  # Planning doesn't examine files
            "relevant_files",  # Planning doesn't use files
            "relevant_context",  # Planning doesn't track code context
            "issues_found",  # Planning doesn't find issues
            "confidence",  # Planning uses different confidence model
            "hypothesis",  # Planning doesn't use hypothesis
            "backtrack_from_step",  # Planning uses revision instead
        ]

        # Exclude common fields that planning doesn't need
        excluded_common_fields = [
            "temperature",  # Planning doesn't need temperature control
            "thinking_mode",  # Planning doesn't need thinking mode
            "use_websearch",  # Planning doesn't need web search
            "images",  # Planning doesn't use images
            "files",  # Planning doesn't use files
        ]

        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=self.get_tool_fields(),
            required_fields=[],  # No additional required fields beyond workflow defaults
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
            excluded_workflow_fields=excluded_workflow_fields,
            excluded_common_fields=excluded_common_fields,
        )

    # ================================================================================
    # Abstract Methods - Required Implementation from BaseWorkflowMixin
    # ================================================================================

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for each planning phase."""
        if step_number == 1:
            # Initial planning tasks
            return [
                "Think deeply about the complete scope and complexity of what needs to be planned",
                "Consider multiple approaches and their trade-offs",
                "Identify key constraints, dependencies, and potential challenges",
                "Think about stakeholders, success criteria, and critical requirements",
            ]
        elif step_number <= 3 and total_steps >= 5:
            # Complex plan early stages - force deep thinking
            if step_number == 2:
                return [
                    "Evaluate the approach from step 1 - are there better alternatives?",
                    "Break down the major phases and identify critical decision points",
                    "Consider resource requirements and potential bottlenecks",
                    "Think about how different parts interconnect and affect each other",
                ]
            else:  # step_number == 3
                return [
                    "Validate that the emerging plan addresses the original requirements",
                    "Identify any gaps or assumptions that need clarification",
                    "Consider how to validate progress and adjust course if needed",
                    "Think about what the first concrete steps should be",
                ]
        else:
            # Later steps or simple plans
            return [
                "Continue developing the plan with concrete, actionable steps",
                "Consider implementation details and practical considerations",
                "Think about how to sequence and coordinate different activities",
                "Prepare for execution planning and resource allocation",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """Planner is self-contained and doesn't need expert analysis."""
        return False

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Planner doesn't use expert analysis."""
        return ""

    def requires_expert_analysis(self) -> bool:
        """Planner is self-contained like the original planner tool."""
        return False

    # ================================================================================
    # Workflow Customization - Match Original Planner Behavior
    # ================================================================================

    def prepare_step_data(self, request) -> dict:
        """
        Prepare step data from request with planner-specific fields.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": f"Planning step {request.step_number}: {request.step}",  # Use step content as findings
            "files_checked": [],  # Planner doesn't check files
            "relevant_files": [],  # Planner doesn't use files
            "relevant_context": [],  # Planner doesn't track context like debug
            "issues_found": [],  # Planner doesn't track issues
            "confidence": "planning",  # Planning confidence is different from investigation
            "hypothesis": None,  # Planner doesn't use hypothesis
            "images": [],  # Planner doesn't use images
            # Planner-specific fields
            "is_step_revision": request.is_step_revision or False,
            "revises_step_number": request.revises_step_number,
            "is_branch_point": request.is_branch_point or False,
            "branch_from_step": request.branch_from_step,
            "branch_id": request.branch_id,
            "more_steps_needed": request.more_steps_needed or False,
        }
        return step_data

    def build_base_response(self, request, continuation_id: str = None) -> dict:
        """
        Build the base response structure with planner-specific fields.
        """
        # Use work_history from workflow mixin for consistent step tracking
        # Add 1 to account for current step being processed
        current_step_count = len(self.work_history) + 1

        response_data = {
            "status": f"{self.get_name()}_in_progress",
            "step_number": request.step_number,
            "total_steps": request.total_steps,
            "next_step_required": request.next_step_required,
            "step_content": request.step,
            f"{self.get_name()}_status": {
                "files_checked": len(self.consolidated_findings.files_checked),
                "relevant_files": len(self.consolidated_findings.relevant_files),
                "relevant_context": len(self.consolidated_findings.relevant_context),
                "issues_found": len(self.consolidated_findings.issues_found),
                "images_collected": len(self.consolidated_findings.images),
                "current_confidence": self.get_request_confidence(request),
                "step_history_length": current_step_count,  # Use work_history + current step
            },
            "metadata": {
                "branches": list(self.branches.keys()),
                "step_history_length": current_step_count,  # Use work_history + current step
                "is_step_revision": request.is_step_revision or False,
                "revises_step_number": request.revises_step_number,
                "is_branch_point": request.is_branch_point or False,
                "branch_from_step": request.branch_from_step,
                "branch_id": request.branch_id,
                "more_steps_needed": request.more_steps_needed or False,
            },
        }

        if continuation_id:
            response_data["continuation_id"] = continuation_id

        return response_data

    def handle_work_continuation(self, response_data: dict, request) -> dict:
        """
        Handle work continuation with planner-specific deep thinking pauses.
        """
        response_data["status"] = f"pause_for_{self.get_name()}"
        response_data[f"{self.get_name()}_required"] = True

        # Get planner-specific required actions
        required_actions = self.get_required_actions(request.step_number, "planning", request.step, request.total_steps)
        response_data["required_actions"] = required_actions

        # Enhanced deep thinking pauses for complex plans
        if request.total_steps >= 5 and request.step_number <= 3:
            response_data["status"] = "pause_for_deep_thinking"
            response_data["thinking_required"] = True
            response_data["required_thinking"] = required_actions

            if request.step_number == 1:
                response_data["next_steps"] = (
                    f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. This is a complex plan ({request.total_steps} steps) "
                    f"that requires deep thinking. You MUST first spend time reflecting on the planning challenge:\n\n"
                    f"REQUIRED DEEP THINKING before calling {self.get_name()} step {request.step_number + 1}:\n"
                    f"1. Analyze the FULL SCOPE: What exactly needs to be accomplished?\n"
                    f"2. Consider MULTIPLE APPROACHES: What are 2-3 different ways to tackle this?\n"
                    f"3. Identify CONSTRAINTS & DEPENDENCIES: What limits our options?\n"
                    f"4. Think about SUCCESS CRITERIA: How will we know we've succeeded?\n"
                    f"5. Consider RISKS & MITIGATION: What could go wrong early vs late?\n\n"
                    f"Only call {self.get_name()} again with step_number: {request.step_number + 1} AFTER this deep analysis."
                )
            elif request.step_number == 2:
                response_data["next_steps"] = (
                    f"STOP! Complex planning requires reflection between steps. DO NOT call {self.get_name()} immediately.\n\n"
                    f"MANDATORY REFLECTION before {self.get_name()} step {request.step_number + 1}:\n"
                    f"1. EVALUATE YOUR APPROACH: Is the direction from step 1 still the best?\n"
                    f"2. IDENTIFY MAJOR PHASES: What are the 3-5 main chunks of work?\n"
                    f"3. SPOT DEPENDENCIES: What must happen before what?\n"
                    f"4. CONSIDER RESOURCES: What skills, tools, or access do we need?\n"
                    f"5. FIND CRITICAL PATHS: Where could delays hurt the most?\n\n"
                    f"Think deeply about these aspects, then call {self.get_name()} with step_number: {request.step_number + 1}."
                )
            elif request.step_number == 3:
                response_data["next_steps"] = (
                    f"PAUSE for final strategic reflection. DO NOT call {self.get_name()} yet.\n\n"
                    f"FINAL DEEP THINKING before {self.get_name()} step {request.step_number + 1}:\n"
                    f"1. VALIDATE COMPLETENESS: Does this plan address all original requirements?\n"
                    f"2. CHECK FOR GAPS: What assumptions need validation? What's unclear?\n"
                    f"3. PLAN FOR ADAPTATION: How will we know if we need to change course?\n"
                    f"4. DEFINE FIRST STEPS: What are the first 2-3 concrete actions?\n"
                    f"5. TRANSITION MINDSET: Ready to shift from strategic to tactical planning?\n\n"
                    f"After this reflection, call {self.get_name()} with step_number: {request.step_number + 1} to continue with tactical details."
                )
        else:
            # Normal flow for simple plans or later steps
            remaining_steps = request.total_steps - request.step_number
            response_data["next_steps"] = (
                f"Continue with step {request.step_number + 1}. Approximately {remaining_steps} steps remaining."
            )

        return response_data

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match original planner tool format.
        """
        # No need to append to step_history since workflow mixin already manages work_history
        # and we calculate step counts from work_history

        # Handle branching like original planner
        if request.is_branch_point and request.branch_from_step and request.branch_id:
            if request.branch_id not in self.branches:
                self.branches[request.branch_id] = []
            step_data = self.prepare_step_data(request)
            self.branches[request.branch_id].append(step_data)

        # Ensure metadata exists and preserve existing metadata from build_base_response
        if "metadata" not in response_data:
            response_data["metadata"] = {}

        # Store planner-specific metadata that should persist through workflow metadata addition
        planner_metadata = {
            "branches": list(self.branches.keys()),
            "is_step_revision": request.is_step_revision or False,
            "revises_step_number": request.revises_step_number,
            "is_branch_point": request.is_branch_point or False,
            "branch_from_step": request.branch_from_step,
            "branch_id": request.branch_id,
            "more_steps_needed": request.more_steps_needed or False,
        }

        # Update metadata while preserving existing values
        response_data["metadata"].update(planner_metadata)

        # Add planner-specific output instructions for final steps
        if not request.next_step_required:
            response_data["planning_complete"] = True
            response_data["plan_summary"] = (
                f"COMPLETE PLAN: {request.step} (Total {request.total_steps} steps completed)"
            )
            response_data["output"] = {
                "instructions": "This is a structured planning response. Present the step_content as the main planning analysis. If next_step_required is true, continue with the next step. If planning_complete is true, present the complete plan in a well-structured format with clear sections, headings, numbered steps, and visual elements like ASCII charts for phases/dependencies. Use bullet points, sub-steps, sequences, and visual organization to make complex plans easy to understand and follow. IMPORTANT: Do NOT use emojis - use clear text formatting and ASCII characters only. Do NOT mention time estimates or costs unless explicitly requested.",
                "format": "step_by_step_planning",
                "presentation_guidelines": {
                    "completed_plans": "Use clear headings, numbered phases, ASCII diagrams for workflows/dependencies, bullet points for sub-tasks, and visual sequences where helpful. No emojis. No time/cost estimates unless requested.",
                    "step_content": "Present as main analysis with clear structure and actionable insights. No emojis. No time/cost estimates unless requested.",
                    "continuation": "Use continuation_id for related planning sessions or implementation planning",
                },
            }
            response_data["next_steps"] = (
                "Planning complete. Present the complete plan to the user in a well-structured format with clear sections, "
                "numbered steps, visual elements (ASCII charts/diagrams where helpful), sub-step breakdowns, and implementation guidance. "
                "Use headings, bullet points, and visual organization to make the plan easy to follow. "
                "If there are phases, dependencies, or parallel tracks, show these relationships visually. "
                "IMPORTANT: Do NOT use emojis - use clear text formatting and ASCII characters only. "
                "Do NOT mention time estimates or costs unless explicitly requested. "
                "After presenting the plan, offer to either help implement specific parts or use the continuation_id to start related planning sessions."
            )

        # Convert generic status names to planner-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "planning_success",
            f"pause_for_{tool_name}": f"pause_for_{tool_name}",  # Keep the full tool name for workflow consistency
            f"{tool_name}_required": f"{tool_name}_required",  # Keep the full tool name for workflow consistency
            f"{tool_name}_complete": f"{tool_name}_complete",  # Keep the full tool name for workflow consistency
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        return response_data

    # ================================================================================
    # Hook Method Overrides for Planner-Specific Behavior
    # ================================================================================

    def get_completion_status(self) -> str:
        """Planner uses planning-specific status."""
        return "planning_complete"

    def get_completion_data_key(self) -> str:
        """Planner uses 'complete_planning' key."""
        return "complete_planning"

    def get_completion_message(self) -> str:
        """Planner-specific completion message."""
        return (
            "Planning complete. Present the complete plan to the user in a well-structured format "
            "and offer to help implement specific parts or start related planning sessions."
        )

    def get_skip_reason(self) -> str:
        """Planner-specific skip reason."""
        return "Planner is self-contained and completes planning without external analysis"

    def get_skip_expert_analysis_status(self) -> str:
        """Planner-specific expert analysis skip status."""
        return "skipped_by_tool_design"

    def store_initial_issue(self, step_description: str):
        """Store initial planning description."""
        self.initial_planning_description = step_description

    def get_initial_request(self, fallback_step: str) -> str:
        """Get initial planning description."""
        try:
            return self.initial_planning_description
        except AttributeError:
            return fallback_step

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the planner-specific request model."""
        return PlannerRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
