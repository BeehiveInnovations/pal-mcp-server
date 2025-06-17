"""
Planner tool

This tool helps you break down complex ideas, problems, or projects into multiple
manageable steps. It enables Claude to think through larger problems sequentially, creating
detailed action plans with clear dependencies and alternatives where applicable.

=== CONTINUATION FLOW LOGIC ===

The tool implements sophisticated continuation logic that enables multi-session planning:

RULE 1: No continuation_id + step_number=1
→ Creates NEW planning thread
→ NO previous context loaded
→ Returns continuation_id for future steps

RULE 2: continuation_id provided + step_number=1
→ Loads PREVIOUS COMPLETE PLAN as context
→ Starts NEW planning session with historical context
→ Claude sees summary of previous completed plan

RULE 3: continuation_id provided + step_number>1
→ NO previous context loaded (middle of current planning session)
→ Continues current planning without historical interference

RULE 4: next_step_required=false (final step)
→ Stores COMPLETE PLAN summary in conversation memory
→ Returns continuation_id for future planning sessions

=== CONCRETE EXAMPLE ===

FIRST PLANNING SESSION (Feature A):
Call 1: planner(step="Plan user authentication", step_number=1, total_steps=3, next_step_required=true)
        → NEW thread created: "uuid-abc123"
        → Response: {"step_number": 1, "continuation_id": "uuid-abc123"}

Call 2: planner(step="Design login flow", step_number=2, total_steps=3, next_step_required=true, continuation_id="uuid-abc123")
        → Middle of current plan - NO context loading
        → Response: {"step_number": 2, "continuation_id": "uuid-abc123"}

Call 3: planner(step="Security implementation", step_number=3, total_steps=3, next_step_required=FALSE, continuation_id="uuid-abc123")
        → FINAL STEP: Stores "COMPLETE PLAN: Security implementation (3 steps completed)"
        → Response: {"step_number": 3, "planning_complete": true, "continuation_id": "uuid-abc123"}

LATER PLANNING SESSION (Feature B):
Call 1: planner(step="Plan dashboard system", step_number=1, total_steps=2, next_step_required=true, continuation_id="uuid-abc123")
        → Loads previous complete plan as context
        → Response includes: "=== PREVIOUS COMPLETE PLAN CONTEXT === Security implementation..."
        → Claude sees previous work and can build upon it

Call 2: planner(step="Dashboard widgets", step_number=2, total_steps=2, next_step_required=FALSE, continuation_id="uuid-abc123")
        → FINAL STEP: Stores new complete plan summary
        → Both planning sessions now available for future continuations

This enables Claude to say: "Continue planning feature C using the authentication and dashboard work"
and the tool will provide context from both previous completed planning sessions.
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_BALANCED
from systemprompts import PLANNER_PROMPT

from .base import BaseTool, ToolRequest

logger = logging.getLogger(__name__)

# Field descriptions to avoid duplication between Pydantic and JSON schema
PLANNER_FIELD_DESCRIPTIONS = {
    # Interactive planning fields for step-by-step planning
    "step": (
        "Your current planning step. For the first step, describe the task/problem to plan. "
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
    "continuation_id": "Thread continuation ID for multi-turn planning sessions (useful for seeding new plans with prior context)",
}


class PlanStep:
    """Represents a single step in the planning process."""

    def __init__(
        self, step_number: int, content: str, branch_id: Optional[str] = None, parent_step: Optional[int] = None
    ):
        self.step_number = step_number
        self.content = content
        self.branch_id = branch_id or "main"
        self.parent_step = parent_step
        self.children = []


class PlannerRequest(ToolRequest):
    """Request model for the planner tool - interactive step-by-step planning."""

    # Required fields for each planning step
    step: str = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=PLANNER_FIELD_DESCRIPTIONS["next_step_required"])

    # Optional revision/branching fields
    is_step_revision: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["is_step_revision"])
    revises_step_number: Optional[int] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["revises_step_number"])
    is_branch_point: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["is_branch_point"])
    branch_from_step: Optional[int] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["branch_from_step"])
    branch_id: Optional[str] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["branch_id"])
    more_steps_needed: Optional[bool] = Field(False, description=PLANNER_FIELD_DESCRIPTIONS["more_steps_needed"])

    # Optional continuation field
    continuation_id: Optional[str] = Field(None, description=PLANNER_FIELD_DESCRIPTIONS["continuation_id"])

    # Override inherited fields to exclude them from schema
    model: Optional[str] = Field(default=None, exclude=True)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)
    images: Optional[list] = Field(default=None, exclude=True)


class PlannerTool(BaseTool):
    """Sequential planning tool with step-by-step breakdown and refinement."""

    def __init__(self):
        super().__init__()
        self.step_history = []
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
            "- Branching for exploring alternative strategies\n"
            "- Revision capabilities to update earlier decisions\n"
            "- Dynamic step count adjustment\n\n"
            "Perfect for: complex project planning, system design with unknowns, "
            "migration strategies, architectural decisions, problem decomposition."
        )

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                # Interactive planning fields
                "step": {
                    "type": "string",
                    "description": PLANNER_FIELD_DESCRIPTIONS["step"],
                },
                "step_number": {
                    "type": "integer",
                    "description": PLANNER_FIELD_DESCRIPTIONS["step_number"],
                    "minimum": 1,
                },
                "total_steps": {
                    "type": "integer",
                    "description": PLANNER_FIELD_DESCRIPTIONS["total_steps"],
                    "minimum": 1,
                },
                "next_step_required": {
                    "type": "boolean",
                    "description": PLANNER_FIELD_DESCRIPTIONS["next_step_required"],
                },
                "is_step_revision": {
                    "type": "boolean",
                    "description": PLANNER_FIELD_DESCRIPTIONS["is_step_revision"],
                },
                "revises_step_number": {
                    "type": "integer",
                    "description": PLANNER_FIELD_DESCRIPTIONS["revises_step_number"],
                    "minimum": 1,
                },
                "is_branch_point": {
                    "type": "boolean",
                    "description": PLANNER_FIELD_DESCRIPTIONS["is_branch_point"],
                },
                "branch_from_step": {
                    "type": "integer",
                    "description": PLANNER_FIELD_DESCRIPTIONS["branch_from_step"],
                    "minimum": 1,
                },
                "branch_id": {
                    "type": "string",
                    "description": PLANNER_FIELD_DESCRIPTIONS["branch_id"],
                },
                "more_steps_needed": {
                    "type": "boolean",
                    "description": PLANNER_FIELD_DESCRIPTIONS["more_steps_needed"],
                },
                "continuation_id": {
                    "type": "string",
                    "description": PLANNER_FIELD_DESCRIPTIONS["continuation_id"],
                },
            },
            # Required fields for interactive planning
            "required": ["step", "step_number", "total_steps", "next_step_required"],
        }
        return schema

    def get_system_prompt(self) -> str:
        return PLANNER_PROMPT

    def get_request_model(self):
        return PlannerRequest

    def get_default_temperature(self) -> float:
        return TEMPERATURE_BALANCED

    def get_model_category(self) -> "ToolModelCategory":
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING  # Planning benefits from deep thinking

    def get_default_thinking_mode(self) -> str:
        return "high"  # Default to high thinking for comprehensive planning

    async def execute(self, arguments: dict[str, Any]) -> list:
        """
        Override execute to work like original TypeScript tool - no AI calls, just data processing.

        This method implements the core continuation logic that enables multi-session planning:

        CONTINUATION LOGIC:
        1. If no continuation_id + step_number=1: Create new planning thread
        2. If continuation_id + step_number=1: Load previous complete plan as context for NEW planning
        3. If continuation_id + step_number>1: Continue current plan (no context loading)
        4. If next_step_required=false: Mark complete and store plan summary for future use

        CONVERSATION MEMORY INTEGRATION:
        - Each step is stored in conversation memory for cross-tool continuation
        - Final steps store COMPLETE PLAN summaries that can be loaded as context
        - Only step 1 with continuation_id loads previous context (new planning session)
        - Steps 2+ with continuation_id continue current session without context interference
        """
        from mcp.types import TextContent

        from utils.conversation_memory import add_turn, create_thread, get_thread

        try:
            # Validate request like the original
            request_model = self.get_request_model()
            request = request_model(**arguments)

            # Process step like original TypeScript tool
            if request.step_number > request.total_steps:
                request.total_steps = request.step_number

            # === CONTINUATION LOGIC IMPLEMENTATION ===
            # This implements the 4 rules documented in the module docstring

            continuation_id = request.continuation_id
            previous_plan_context = ""

            # RULE 1: No continuation_id + step_number=1 → Create NEW planning thread
            if not continuation_id and request.step_number == 1:
                # Filter arguments to only include serializable data for conversation memory
                serializable_args = {
                    k: v
                    for k, v in arguments.items()
                    if not hasattr(v, "__class__") or v.__class__.__module__ != "utils.model_context"
                }
                continuation_id = create_thread("planner", serializable_args)
                # Result: New thread created, no previous context, returns continuation_id

            # RULE 2: continuation_id + step_number=1 → Load PREVIOUS COMPLETE PLAN as context
            elif continuation_id and request.step_number == 1:
                thread = get_thread(continuation_id)
                if thread:
                    # Search for most recent COMPLETE PLAN from previous planning sessions
                    for turn in reversed(thread.turns):  # Newest first
                        if turn.tool_name == "planner" and turn.role == "assistant":
                            # Try to parse as JSON first (new format)
                            try:
                                turn_data = json.loads(turn.content)
                                if isinstance(turn_data, dict) and turn_data.get("planning_complete"):
                                    # New JSON format
                                    plan_summary = turn_data.get("plan_summary", "")
                                    if plan_summary:
                                        previous_plan_context = plan_summary[:500]
                                        break
                            except (json.JSONDecodeError, ValueError):
                                # Fallback to old text format
                                if "planning_complete" in turn.content:
                                    try:
                                        if "COMPLETE PLAN:" in turn.content:
                                            plan_start = turn.content.find("COMPLETE PLAN:")
                                            previous_plan_context = turn.content[plan_start : plan_start + 500] + "..."
                                        else:
                                            previous_plan_context = turn.content[:300] + "..."
                                        break
                                    except Exception:
                                        pass

                    if previous_plan_context:
                        previous_plan_context = f"\\n\\n=== PREVIOUS COMPLETE PLAN CONTEXT ===\\n{previous_plan_context}\\n=== END CONTEXT ===\\n"
                # Result: NEW planning session with previous complete plan as context

            # RULE 3: continuation_id + step_number>1 → Continue current plan (no context loading)
            # This case is handled by doing nothing - we're in the middle of current planning
            # Result: Current planning continues without historical interference

            step_data = {
                "step": request.step,
                "step_number": request.step_number,
                "total_steps": request.total_steps,
                "next_step_required": request.next_step_required,
                "is_step_revision": request.is_step_revision,
                "revises_step_number": request.revises_step_number,
                "is_branch_point": request.is_branch_point,
                "branch_from_step": request.branch_from_step,
                "branch_id": request.branch_id,
                "more_steps_needed": request.more_steps_needed,
                "continuation_id": request.continuation_id,
            }

            # Store in local history like original
            self.step_history.append(step_data)

            # Handle branching like original
            if request.is_branch_point and request.branch_from_step and request.branch_id:
                if request.branch_id not in self.branches:
                    self.branches[request.branch_id] = []
                self.branches[request.branch_id].append(step_data)

            # Build structured JSON response like other tools (consensus, refactor)
            response_data = {
                "status": "planning_success",
                "step_number": request.step_number,
                "total_steps": request.total_steps,
                "next_step_required": request.next_step_required,
                "step_content": request.step,
                "metadata": {
                    "branches": list(self.branches.keys()),
                    "step_history_length": len(self.step_history),
                    "is_step_revision": request.is_step_revision or False,
                    "revises_step_number": request.revises_step_number,
                    "is_branch_point": request.is_branch_point or False,
                    "branch_from_step": request.branch_from_step,
                    "branch_id": request.branch_id,
                    "more_steps_needed": request.more_steps_needed or False,
                },
                "output": {
                    "instructions": "This is a structured planning response. Present the step_content as the main planning analysis. If next_step_required is true, continue with the next step. If planning_complete is true, present the complete plan in a well-structured format with clear sections, headings, numbered steps, and visual elements like ASCII charts for phases/dependencies. Use bullet points, sub-steps, sequences, and visual organization to make complex plans easy to understand and follow. IMPORTANT: Do NOT use emojis - use clear text formatting and ASCII characters only. Do NOT mention time estimates or costs unless explicitly requested.",
                    "format": "step_by_step_planning",
                    "presentation_guidelines": {
                        "completed_plans": "Use clear headings, numbered phases, ASCII diagrams for workflows/dependencies, bullet points for sub-tasks, and visual sequences where helpful. No emojis. No time/cost estimates unless requested.",
                        "step_content": "Present as main analysis with clear structure and actionable insights. No emojis. No time/cost estimates unless requested.",
                        "continuation": "Use continuation_id for related planning sessions or implementation planning",
                    },
                },
            }

            # Always include continuation_id if we have one (enables step chaining within session)
            if continuation_id:
                response_data["continuation_id"] = continuation_id

            # Add previous plan context if available
            if previous_plan_context:
                response_data["previous_plan_context"] = previous_plan_context.strip()

            # RULE 4: next_step_required=false → Mark complete and store plan summary
            if not request.next_step_required:
                response_data["planning_complete"] = True
                response_data["plan_summary"] = (
                    f"COMPLETE PLAN: {request.step} (Total {request.total_steps} steps completed)"
                )
                response_data["next_steps"] = (
                    "Planning complete. Present the complete plan to the user in a well-structured format with clear sections, "
                    "numbered steps, visual elements (ASCII charts/diagrams where helpful), sub-step breakdowns, and implementation guidance. "
                    "Use headings, bullet points, and visual organization to make the plan easy to follow. "
                    "If there are phases, dependencies, or parallel tracks, show these relationships visually. "
                    "IMPORTANT: Do NOT use emojis - use clear text formatting and ASCII characters only. "
                    "Do NOT mention time estimates or costs unless explicitly requested. "
                    "After presenting the plan, offer to either help implement specific parts or use the continuation_id to start related planning sessions."
                )
                # Result: Planning marked complete, summary stored for future context loading
            else:
                response_data["planning_complete"] = False
                remaining_steps = request.total_steps - request.step_number
                response_data["next_steps"] = (
                    f"Continue with step {request.step_number + 1}. Approximately {remaining_steps} steps remaining."
                )
                # Result: Intermediate step, planning continues

            # Convert to clean JSON response
            response_content = json.dumps(response_data, indent=2)

            # Store this step in conversation memory
            if continuation_id:
                add_turn(
                    thread_id=continuation_id,
                    role="assistant",
                    content=response_content,
                    tool_name="planner",
                    model_name="claude-planner",
                )

            # Return the JSON response directly as text content, like consensus tool
            return [TextContent(type="text", text=response_content)]

        except Exception as e:
            # Error handling - return JSON directly like consensus tool
            error_data = {"error": str(e), "status": "planning_failed"}
            return [TextContent(type="text", text=json.dumps(error_data, indent=2))]

    # Stub implementations for abstract methods (not used since we override execute)
    async def prepare_prompt(self, request: PlannerRequest) -> str:
        return ""  # Not used - execute() is overridden

    def format_response(self, response: str, request: PlannerRequest, model_info: dict = None) -> str:
        return response  # Not used - execute() is overridden
