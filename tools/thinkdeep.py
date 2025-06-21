"""
ThinkDeep Workflow Tool - Extended Reasoning with Systematic Investigation

This tool provides step-by-step deep thinking capabilities using a systematic workflow approach.
It enables comprehensive analysis of complex problems with expert validation at completion.

Key Features:
- Systematic step-by-step thinking process
- Multi-step analysis with evidence gathering
- Confidence-based investigation flow
- Expert analysis integration with external models
- Support for focused analysis areas (architecture, performance, security, etc.)
- Confidence-based workflow optimization
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_CREATIVE
from systemprompts import THINKDEEP_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)


class ThinkDeepWorkflowRequest(WorkflowRequest):
    """Request model for thinkdeep workflow tool with comprehensive investigation capabilities"""

    # Core workflow parameters
    step: str = Field(description="Current work step content and findings from your overall work")
    step_number: int = Field(description="Current step number in the work sequence (starts at 1)", ge=1)
    total_steps: int = Field(description="Estimated total steps needed to complete the work", ge=1)
    next_step_required: bool = Field(description="Whether another work step is needed after this one")
    findings: str = Field(
        description="Summarize everything discovered in this step about the problem/goal. Include new insights, "
        "connections made, implications considered, alternative approaches, potential issues identified, "
        "and evidence from thinking. Be specific and avoid vague language—document what you now know "
        "and how it affects your hypothesis or understanding. IMPORTANT: If you find compelling evidence "
        "that contradicts earlier assumptions, document this clearly. In later steps, confirm or update "
        "past findings with additional reasoning."
    )

    # Investigation tracking
    files_checked: list[str] = Field(
        default_factory=list,
        description="List all files (as absolute paths) examined during the investigation so far. "
        "Include even files ruled out or found unrelated, as this tracks your exploration path.",
    )
    relevant_files: list[str] = Field(
        default_factory=list,
        description="Subset of files_checked (as full absolute paths) that contain information directly "
        "relevant to the problem or goal. Only list those directly tied to the root cause, "
        "solution, or key insights. This could include the source of the issue, documentation "
        "that explains the expected behavior, configuration files that affect the outcome, or "
        "examples that illustrate the concept being analyzed.",
    )
    relevant_context: list[str] = Field(
        default_factory=list,
        description="Key concepts, methods, or principles that are central to the thinking analysis, "
        "in the format 'concept_name' or 'ClassName.methodName'. Focus on those that drive "
        "the core insights, represent critical decision points, or define the scope of the analysis.",
    )
    hypothesis: Optional[str] = Field(
        default=None,
        description="Current theory or understanding about the problem/goal based on evidence gathered. "
        "This should be a concrete theory that can be validated or refined through further analysis. "
        "You are encouraged to revise or abandon hypotheses in later steps based on new evidence.",
    )

    # Analysis metadata
    issues_found: list[dict] = Field(
        default_factory=list,
        description="Issues identified during work with severity levels - each as a dict with "
        "'severity' (critical, high, medium, low) and 'description' fields.",
    )
    confidence: str = Field(
        default="low",
        description="Indicate your current confidence in the analysis. Use: 'exploring' (starting analysis), "
        "'low' (early thinking), 'medium' (some insights gained), 'high' (strong understanding), "
        "'certain' (only when the analysis is complete and conclusions are definitive). "
        "Do NOT use 'certain' unless the thinking is comprehensively complete, use 'high' instead when in doubt. "
        "Using 'certain' prevents additional expert analysis to save time and money.",
    )

    # Advanced workflow features
    backtrack_from_step: Optional[int] = Field(
        default=None,
        description="If an earlier finding or hypothesis needs to be revised or discarded, "
        "specify the step number from which to start over. Use this to acknowledge analytical "
        "dead ends and correct the course.",
        ge=1,
    )

    # Expert analysis configuration - keep these fields available for configuring the final assistant model
    # in expert analysis (commented out exclude=True)
    temperature: Optional[float] = Field(
        default=None,
        description="Temperature for creative thinking (0-1, default 0.7)",
        ge=0.0,
        le=1.0,
        # exclude=True  # Excluded from MCP schema but available for internal use
    )
    thinking_mode: Optional[str] = Field(
        default=None,
        description="Thinking depth: minimal (0.5% of model max), low (8%), medium (33%), high (67%), max (100% of model max). Defaults to 'high' if not specified.",
        # exclude=True  # Excluded from MCP schema but available for internal use
    )
    use_websearch: Optional[bool] = Field(
        default=None,
        description="Enable web search for documentation, best practices, and current information. Particularly useful for: brainstorming sessions, architectural design discussions, exploring industry best practices, working with specific frameworks/technologies, researching solutions to complex problems, or when current documentation and community insights would enhance the analysis.",
        # exclude=True  # Excluded from MCP schema but available for internal use
    )

    # Context files and investigation scope
    problem_context: Optional[str] = Field(
        default=None,
        description="Provide additional context about the problem or goal. Be as expressive as possible. More information will be very helpful for the analysis.",
    )
    focus_areas: Optional[list[str]] = Field(
        default=None,
        description="Specific aspects to focus on (architecture, performance, security, etc.)",
    )


class ThinkDeepTool(WorkflowTool):
    """
    ThinkDeep Workflow Tool - Systematic Deep Thinking Analysis

    Provides comprehensive step-by-step thinking capabilities with expert validation.
    Uses workflow architecture for systematic investigation and analysis.
    """

    name = "thinkdeep"
    description = (
        "COMPREHENSIVE INVESTIGATION & REASONING - Multi-stage workflow for complex problem analysis. "
        "Use this when you need structured evidence-based investigation, systematic hypothesis testing, or expert validation. "
        "Perfect for: architecture decisions, complex bugs, performance challenges, security analysis. "
        "Provides methodical investigation with assumption validation, alternative solution exploration, and rigorous analysis. "
        "IMPORTANT: Choose the appropriate mode based on task complexity - 'low' for quick investigation, "
        "'medium' for standard problems, 'high' for complex issues (default), 'max' for extremely complex "
        "challenges requiring exhaustive investigation. When in doubt, err on the side of a higher mode for thorough "
        "systematic analysis and expert validation. Note: If you're not currently using a top-tier model such as Opus 4 or above, "
        "these tools can provide enhanced capabilities."
    )

    def __init__(self):
        """Initialize the ThinkDeep workflow tool"""
        super().__init__()
        # Storage for request parameters to use in expert analysis
        self.stored_request_params = {}

    def get_name(self) -> str:
        """Return the tool name"""
        return self.name

    def get_description(self) -> str:
        """Return the tool description"""
        return self.description

    def get_model_category(self) -> "ToolModelCategory":
        """Return the model category for this tool"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the workflow request model for this tool"""
        return ThinkDeepWorkflowRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with thinkdeep-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # ThinkDeep workflow-specific field overrides
        thinkdeep_field_overrides = {
            "problem_context": {
                "type": "string",
                "description": "Provide additional context about the problem or goal. Be as expressive as possible. More information will be very helpful for the analysis.",
            },
            "focus_areas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific aspects to focus on (architecture, performance, security, etc.)",
            },
        }

        # Use WorkflowSchemaBuilder with thinkdeep-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=thinkdeep_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    def get_system_prompt(self) -> str:
        """Return the system prompt for this workflow tool"""
        return THINKDEEP_PROMPT

    def get_default_temperature(self) -> float:
        """Return default temperature for deep thinking"""
        return TEMPERATURE_CREATIVE

    def get_default_thinking_mode(self) -> str:
        """Return default thinking mode for thinkdeep"""
        from config import DEFAULT_THINKING_MODE_THINKDEEP

        return DEFAULT_THINKING_MODE_THINKDEEP

    def customize_workflow_response(self, response_data: dict, request, **kwargs) -> dict:
        """
        Customize the workflow response for thinkdeep-specific needs
        """
        # Store request parameters for later use in expert analysis
        self.stored_request_params = {}
        try:
            self.stored_request_params["temperature"] = request.temperature
        except AttributeError:
            self.stored_request_params["temperature"] = None

        try:
            self.stored_request_params["thinking_mode"] = request.thinking_mode
        except AttributeError:
            self.stored_request_params["thinking_mode"] = None

        try:
            self.stored_request_params["use_websearch"] = request.use_websearch
        except AttributeError:
            self.stored_request_params["use_websearch"] = None

        # Add thinking-specific context to response
        response_data.update(
            {
                "thinking_status": {
                    "current_step": request.step_number,
                    "total_steps": request.total_steps,
                    "files_checked": len(request.files_checked),
                    "relevant_files": len(request.relevant_files),
                    "thinking_confidence": request.confidence,
                    "analysis_focus": request.focus_areas or ["general"],
                }
            }
        )

        # Add thinking_complete field for final steps (test expects this)
        if not request.next_step_required:
            response_data["thinking_complete"] = True

            # Add complete_thinking summary (test expects this)
            response_data["complete_thinking"] = {
                "steps_completed": len(self.work_history),
                "final_confidence": request.confidence,
                "relevant_context": list(self.consolidated_findings.relevant_context),
                "key_findings": self.consolidated_findings.findings,
                "issues_identified": self.consolidated_findings.issues_found,
                "files_analyzed": list(self.consolidated_findings.relevant_files),
            }

        # Add thinking-specific completion message based on confidence
        if request.confidence == "certain":
            response_data["completion_message"] = (
                "Deep thinking analysis is complete with high certainty. "
                "All aspects have been thoroughly considered and conclusions are definitive."
            )
        elif not request.next_step_required:
            response_data["completion_message"] = (
                "Deep thinking analysis phase complete. Expert validation will provide additional insights and recommendations."
            )

        return response_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        ThinkDeep tool skips expert analysis when Claude has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

    def get_completion_status(self) -> str:
        """ThinkDeep tools use thinking-specific status."""
        return "deep_thinking_complete_ready_for_implementation"

    def get_completion_data_key(self) -> str:
        """ThinkDeep uses 'complete_thinking' key."""
        return "complete_thinking"

    def get_final_analysis_from_request(self, request):
        """ThinkDeep tools use 'findings' field."""
        return request.findings

    def get_skip_expert_analysis_status(self) -> str:
        """Status when skipping expert analysis for certain confidence."""
        return "skipped_due_to_certain_thinking_confidence"

    def get_skip_reason(self) -> str:
        """Reason for skipping expert analysis."""
        return "Claude expressed certain confidence in the deep thinking analysis - no additional validation needed"

    def get_completion_message(self) -> str:
        """Message for completion without expert analysis."""
        return "Deep thinking analysis complete with certain confidence. Proceed with implementation based on the analysis."

    def customize_expert_analysis_prompt(self, base_prompt: str, request, file_content: str = "") -> str:
        """
        Customize the expert analysis prompt for deep thinking validation
        """
        thinking_context = f"""
DEEP THINKING ANALYSIS VALIDATION

You are reviewing a comprehensive deep thinking analysis completed through systematic investigation.
Your role is to validate the thinking process, identify any gaps, challenge assumptions, and provide
additional insights or alternative perspectives.

ANALYSIS SCOPE:
- Problem Context: {self._get_problem_context(request)}
- Focus Areas: {', '.join(self._get_focus_areas(request))}
- Investigation Confidence: {request.confidence}
- Steps Completed: {request.step_number} of {request.total_steps}

THINKING SUMMARY:
{request.findings}

KEY INSIGHTS AND CONTEXT:
{', '.join(request.relevant_context) if request.relevant_context else 'No specific context identified'}

VALIDATION OBJECTIVES:
1. Assess the depth and quality of the thinking process
2. Identify any logical gaps, missing considerations, or flawed assumptions
3. Suggest alternative approaches or perspectives not considered
4. Validate the conclusions and recommendations
5. Provide actionable next steps for implementation

Be thorough but constructive in your analysis. Challenge the thinking where appropriate,
but also acknowledge strong insights and valid conclusions.
"""

        if file_content:
            thinking_context += f"\n\nFILE CONTEXT:\n{file_content}"

        return f"{thinking_context}\n\n{base_prompt}"

    def get_expert_analysis_instructions(self) -> str:
        """
        Return instructions for expert analysis specific to deep thinking validation
        """
        return (
            "DEEP THINKING ANALYSIS IS COMPLETE. You MUST now summarize and present ALL thinking insights, "
            "alternative approaches considered, risks and trade-offs identified, and final recommendations. "
            "Clearly prioritize the top solutions or next steps that emerged from the analysis. "
            "Provide concrete, actionable guidance based on the deep thinking—make it easy for the user to "
            "understand exactly what to do next and how to implement the best solution."
        )

    # Override hook methods to use stored request parameters for expert analysis

    def get_request_temperature(self, request) -> float:
        """Use stored temperature from initial request."""
        try:
            stored_params = self.stored_request_params
            if stored_params and stored_params.get("temperature") is not None:
                return stored_params["temperature"]
        except AttributeError:
            pass
        return super().get_request_temperature(request)

    def get_request_thinking_mode(self, request) -> str:
        """Use stored thinking mode from initial request."""
        try:
            stored_params = self.stored_request_params
            if stored_params and stored_params.get("thinking_mode") is not None:
                return stored_params["thinking_mode"]
        except AttributeError:
            pass
        return super().get_request_thinking_mode(request)

    def get_request_use_websearch(self, request) -> bool:
        """Use stored use_websearch from initial request."""
        try:
            stored_params = self.stored_request_params
            if stored_params and stored_params.get("use_websearch") is not None:
                return stored_params["use_websearch"]
        except AttributeError:
            pass
        return super().get_request_use_websearch(request)

    def _get_problem_context(self, request) -> str:
        """Get problem context from request. Override for custom context handling."""
        try:
            return request.problem_context or "General analysis"
        except AttributeError:
            return "General analysis"

    def _get_focus_areas(self, request) -> list[str]:
        """Get focus areas from request. Override for custom focus area handling."""
        try:
            return request.focus_areas or ["comprehensive analysis"]
        except AttributeError:
            return ["comprehensive analysis"]

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """
        Return required actions for the current thinking step.
        """
        actions = []

        if step_number == 1:
            actions.extend(
                [
                    "Begin systematic thinking analysis",
                    "Identify key aspects and assumptions to explore",
                    "Establish initial investigation approach",
                ]
            )
        elif confidence == "low":
            actions.extend(
                [
                    "Continue gathering evidence and insights",
                    "Test initial hypotheses",
                    "Explore alternative perspectives",
                ]
            )
        elif confidence == "medium":
            actions.extend(
                [
                    "Deepen analysis of promising approaches",
                    "Validate key assumptions",
                    "Consider implementation challenges",
                ]
            )
        elif confidence == "high":
            actions.extend(
                [
                    "Synthesize findings into cohesive recommendations",
                    "Validate conclusions against evidence",
                    "Prepare for expert analysis",
                ]
            )
        else:  # certain
            actions.append("Analysis complete - ready for implementation")

        return actions

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Determine if expert analysis should be called based on confidence and completion.
        """
        if request:
            try:
                # Don't call expert analysis if confidence is "certain"
                if request.confidence == "certain":
                    return False
            except AttributeError:
                pass

        # Call expert analysis if investigation is complete (when next_step_required is False)
        if request:
            try:
                return not request.next_step_required
            except AttributeError:
                pass

        # Fallback: call expert analysis if we have meaningful findings
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """
        Prepare context for expert analysis specific to deep thinking.
        """
        context_parts = []

        context_parts.append("DEEP THINKING ANALYSIS SUMMARY:")
        context_parts.append(f"Steps completed: {len(consolidated_findings.findings)}")
        context_parts.append(f"Final confidence: {consolidated_findings.confidence}")

        if consolidated_findings.findings:
            context_parts.append("\nKEY FINDINGS:")
            for i, finding in enumerate(consolidated_findings.findings, 1):
                context_parts.append(f"{i}. {finding}")

        if consolidated_findings.relevant_context:
            context_parts.append(f"\nRELEVANT CONTEXT:\n{', '.join(consolidated_findings.relevant_context)}")

        # Get hypothesis from latest hypotheses entry if available
        if consolidated_findings.hypotheses:
            latest_hypothesis = consolidated_findings.hypotheses[-1].get("hypothesis", "")
            if latest_hypothesis:
                context_parts.append(f"\nFINAL HYPOTHESIS:\n{latest_hypothesis}")

        if consolidated_findings.issues_found:
            context_parts.append(f"\nISSUES IDENTIFIED: {len(consolidated_findings.issues_found)} issues")
            for issue in consolidated_findings.issues_found:
                context_parts.append(
                    f"- {issue.get('severity', 'unknown')}: {issue.get('description', 'No description')}"
                )

        return "\n".join(context_parts)

    def get_step_guidance_message(self, request) -> str:
        """
        Generate guidance for the next step in thinking analysis
        """
        if request.next_step_required:
            next_step_number = request.step_number + 1

            if request.confidence == "certain":
                guidance = (
                    f"Your thinking analysis confidence is CERTAIN. Consider if you truly need step {next_step_number} "
                    f"or if you should complete the analysis now with expert validation."
                )
            elif request.confidence == "high":
                guidance = (
                    f"Your thinking analysis confidence is HIGH. For step {next_step_number}, consider: "
                    f"validation of conclusions, stress-testing assumptions, or exploring edge cases."
                )
            elif request.confidence == "medium":
                guidance = (
                    f"Your thinking analysis confidence is MEDIUM. For step {next_step_number}, focus on: "
                    f"deepening insights, exploring alternative approaches, or gathering additional evidence."
                )
            else:  # low or exploring
                guidance = (
                    f"Your thinking analysis confidence is {request.confidence.upper()}. For step {next_step_number}, "
                    f"continue investigating: gather more evidence, test hypotheses, or explore different angles."
                )

            # Add specific thinking guidance based on progress
            if request.step_number == 1:
                guidance += (
                    " Consider: What are the key assumptions? What evidence supports or contradicts initial theories? "
                    "What alternative approaches exist?"
                )
            elif request.step_number >= request.total_steps // 2:
                guidance += (
                    " Consider: Synthesis of findings, validation of conclusions, identification of implementation "
                    "challenges, and preparation for expert analysis."
                )

            return guidance
        else:
            return "Thinking analysis is ready for expert validation and final recommendations."

    def format_final_response(self, assistant_response: str, request, **kwargs) -> dict:
        """
        Format the final response from the assistant for thinking analysis
        """
        response_data = {
            "thinking_analysis": assistant_response,
            "analysis_metadata": {
                "total_steps_completed": request.step_number,
                "final_confidence": request.confidence,
                "files_analyzed": len(request.relevant_files),
                "key_insights": len(request.relevant_context),
                "issues_identified": len(request.issues_found),
            },
        }

        # Add completion status
        if request.confidence == "certain":
            response_data["completion_status"] = "analysis_complete_with_certainty"
        else:
            response_data["completion_status"] = "analysis_complete_pending_validation"

        return response_data

    def format_step_response(
        self,
        assistant_response: str,
        request,
        status: str = "pause_for_thinkdeep",
        continuation_id: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """
        Format intermediate step responses for thinking workflow
        """
        response_data = super().format_step_response(assistant_response, request, status, continuation_id, **kwargs)

        # Add thinking-specific step guidance
        step_guidance = self.get_step_guidance_message(request)
        response_data["thinking_guidance"] = step_guidance

        # Add analysis progress indicators
        response_data["analysis_progress"] = {
            "step_completed": request.step_number,
            "remaining_steps": max(0, request.total_steps - request.step_number),
            "confidence_trend": request.confidence,
            "investigation_depth": "expanding" if request.next_step_required else "finalizing",
        }

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the thinkdeep workflow-specific request model."""
        return ThinkDeepWorkflowRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
