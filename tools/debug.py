"""
Debug tool - Systematic root cause analysis and debugging assistance

This tool provides a structured workflow for investigating complex bugs and issues.
It guides you through systematic investigation steps with forced pauses between each step
to ensure thorough code examination before proceeding. The tool supports backtracking,
hypothesis evolution, and expert analysis integration for comprehensive debugging.

Key features:
- Step-by-step investigation workflow with progress tracking
- Context-aware file embedding (references during investigation, full content for analysis)
- Automatic conversation threading and history preservation
- Expert analysis integration with external models
- Support for visual debugging with image context
- Confidence-based workflow optimization
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import DEBUG_ISSUE_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions matching original debug tool
DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS = {
    "step": (
        "Describe what you're currently investigating by thinking deeply about the issue and its possible causes. "
        "In step 1, clearly state the issue and begin forming an investigative direction after thinking carefully"
        "about the described problem. Ask further questions from the user if you think these will help with your"
        "understanding and investigation. CRITICAL: Remember that reported symptoms might originate from code far from "
        "where they manifest. Also be aware that after thorough investigation, you might find NO BUG EXISTS - it could "
        "be a misunderstanding or expectation mismatch. Consider not only obvious failures, but also subtle "
        "contributing factors like upstream logic, invalid inputs, missing preconditions, or hidden side effects. "
        "Map out the flow of related functions or modules. Identify call paths where input values or branching logic "
        "could cause instability. In concurrent systems, watch for race conditions, shared state, or timing "
        "dependencies. In all later steps, continue exploring with precision: trace deeper dependencies, verify "
        "hypotheses, and adapt your understanding as you uncover more evidence."
        "IMPORTANT: When referring to code, use the relevant_files parameter to pass relevant files and only use the prompt to refer to "
        "function / method names or very small code snippets if absolutely necessary to explain the issue. Do NOT "
        "pass large code snippets in the prompt as this is exclusively reserved for descriptive text only. "
    ),
    "step_number": (
        "The index of the current step in the investigation sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the investigation. "
        "Adjust as new findings emerge. IMPORTANT: When continuation_id is provided (continuing a previous "
        "conversation), set this to 1 as we're not starting a new multi-step investigation."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the root "
        "cause is known or the investigation is complete. IMPORTANT: When continuation_id is "
        "provided (continuing a previous conversation), set this to False to immediately proceed with expert analysis."
    ),
    "findings": (
        "Summarize everything discovered in this step. Include new clues, unexpected behavior, evidence from code or "
        "logs, or disproven theories. Be specific and avoid vague language—document what you now know and how it "
        "affects your hypothesis. IMPORTANT: If you find no evidence supporting the reported issue after thorough "
        "investigation, document this clearly. Finding 'no bug' is a valid outcome if the "
        "investigation was comprehensive. "
        "In later steps, confirm or disprove past findings with reason."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during "
        "the investigation so far. "
        "Include even files ruled out, as this tracks your exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked (as full absolute paths) that contain code directly relevant to the issue. Only list "
        "those that are directly tied to the root cause or its effects. This could include the cause, trigger, or "
        "place of manifestation."
    ),
    "relevant_context": (
        "List methods or functions that are central to the issue, in the format "
        "'ClassName.methodName' or 'functionName'. "
        "Prioritize those that influence or process inputs, drive branching, or pass state between modules."
    ),
    "hypothesis": (
        "A concrete theory for what's causing the issue based on the evidence so far. This can include suspected "
        "failures, incorrect assumptions, or violated constraints. VALID HYPOTHESES INCLUDE: 'No bug found - possible "
        "user misunderstanding' or 'Symptoms appear unrelated to any code issue' if evidence supports this. When "
        "no bug is found, consider suggesting: 'Recommend discussing with thought partner/engineering assistant for "
        "clarification of expected behavior.' You are encouraged to revise or abandon hypotheses in later steps as "
        "needed based on evidence."
    ),
    "confidence": (
        "Indicate your current confidence in the hypothesis. Use: 'exploring' (starting out), 'low' (early idea), "
        "'medium' (some supporting evidence), 'high' (strong evidence), 'very_high' (very strong evidence), "
        "'almost_certain' (nearly confirmed), 'certain' (200% confidence - root cause and minimal fix are both "
        "confirmed locally with no need for external model validation). Do NOT use 'certain' unless the issue can be "
        "fully resolved with a fix, use 'very_high' or 'almost_certain' instead when not 200% sure. Using 'certain' "
        "means you have ABSOLUTE confidence locally and prevents external model validation. Also do "
        "NOT set confidence to 'certain' if the user has strongly requested that external validation MUST be performed."
    ),
    "backtrack_from_step": (
        "If an earlier finding or hypothesis needs to be revised or discarded, specify the step number from which to "
        "start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "images": (
        "Optional list of absolute paths to screenshots or UI visuals that clarify the issue. "
        "Only include if they materially assist understanding or hypothesis formulation."
    ),
}


class DebugInvestigationRequest(WorkflowRequest):
    """Request model for debug investigation steps matching original debug tool exactly"""

    # Required fields for each investigation step
    step: str = Field(..., description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["next_step_required"])

    # Investigation tracking fields
    findings: str = Field(..., description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["findings"])
    files_checked: list[str] = Field(
        default_factory=list, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["files_checked"]
    )
    relevant_files: list[str] = Field(
        default_factory=list, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["relevant_files"]
    )
    relevant_context: list[str] = Field(
        default_factory=list, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["relevant_context"]
    )
    hypothesis: Optional[str] = Field(None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["hypothesis"])
    confidence: Optional[str] = Field("low", description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )

    # Optional images for visual debugging
    images: Optional[list[str]] = Field(default=None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["images"])

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)


class DebugIssueTool(WorkflowTool):
    """
    Debug tool for systematic root cause analysis and issue investigation.

    This tool implements a structured debugging workflow that guides users through
    methodical investigation steps, ensuring thorough code examination and evidence
    gathering before reaching conclusions. It supports complex debugging scenarios
    including race conditions, memory leaks, performance issues, and integration problems.
    """

    def __init__(self):
        super().__init__()
        self.initial_issue = None

    def get_name(self) -> str:
        return "debug"

    def get_description(self) -> str:
        return (
            "DEBUG & ROOT CAUSE ANALYSIS - Use this tool to perform any kind of debugging, bug hunting, or issue tracking. "
            "This tool guides you through a step-by-step investigation process where you:\n\n"
            "1. Start with step 1: describe the issue to investigate\n"
            "2. STOP and investigate using appropriate tools\n"
            "3. Report findings in step 2 with concrete evidence from actual code\n"
            "4. Continue investigating between each debug step\n"
            "5. Track findings, relevant files, and methods throughout\n"
            "6. Update hypotheses as understanding evolves\n"
            "7. Once investigation is complete, receive expert analysis\n\n"
            "IMPORTANT: This tool enforces investigation between steps:\n"
            "- After each debug call, you MUST investigate before calling debug again\n"
            "- Each step must include NEW evidence from code examination\n"
            "- No recursive debug calls without actual investigation work\n"
            "- The tool will specify which step number to use next\n"
            "- Follow the required_actions list for investigation guidance\n\n"
            "Perfect for: complex bugs, mysterious errors, performance issues, "
            "race conditions, memory leaks, integration problems."
        )

    def get_system_prompt(self) -> str:
        return DEBUG_ISSUE_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Debug requires deep analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_workflow_request_model(self):
        """Return the debug-specific request model."""
        return DebugInvestigationRequest

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with debug-specific overrides."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Debug-specific field overrides
        debug_field_overrides = {
            "step": {
                "type": "string",
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step"],
            },
            "step_number": {
                "type": "integer",
                "minimum": 1,
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step_number"],
            },
            "total_steps": {
                "type": "integer",
                "minimum": 1,
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["total_steps"],
            },
            "next_step_required": {
                "type": "boolean",
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["next_step_required"],
            },
            "findings": {
                "type": "string",
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["findings"],
            },
            "files_checked": {
                "type": "array",
                "items": {"type": "string"},
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["files_checked"],
            },
            "relevant_files": {
                "type": "array",
                "items": {"type": "string"},
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["relevant_files"],
            },
            "confidence": {
                "type": "string",
                "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["confidence"],
            },
            "hypothesis": {
                "type": "string",
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["hypothesis"],
            },
            "backtrack_from_step": {
                "type": "integer",
                "minimum": 1,
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["backtrack_from_step"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["images"],
            },
        }

        # Use WorkflowSchemaBuilder with debug-specific tool fields
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=debug_field_overrides,
            model_field_schema=self.get_model_field_schema(),
            auto_mode=self.is_effective_auto_mode(),
            tool_name=self.get_name(),
        )

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for each investigation phase."""
        if step_number == 1:
            # Initial investigation tasks
            return [
                "Search for code related to the reported issue or symptoms",
                "Examine relevant files and understand the current implementation",
                "Understand the project structure and locate relevant modules",
                "Identify how the affected functionality is supposed to work",
            ]
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return [
                "Examine the specific files you've identified as relevant",
                "Trace method calls and data flow through the system",
                "Check for edge cases, boundary conditions, and assumptions in the code",
                "Look for related configuration, dependencies, or external factors",
            ]
        elif confidence in ["medium", "high", "very_high"]:
            # Close to root cause - need confirmation
            return [
                "Examine the exact code sections where you believe the issue occurs",
                "Trace the execution path that leads to the failure",
                "Verify your hypothesis with concrete code evidence",
                "Check for any similar patterns elsewhere in the codebase",
            ]
        elif confidence == "almost_certain":
            # Almost certain - final verification before conclusion
            return [
                "Finalize your root cause analysis with specific evidence",
                "Document the complete chain of causation from symptom to root cause",
                "Verify the minimal fix approach is correct",
                "Consider if expert analysis would provide additional insights",
            ]
        else:
            # General investigation needed
            return [
                "Continue examining the code paths identified in your hypothesis",
                "Gather more evidence using appropriate investigation tools",
                "Test edge cases and boundary conditions",
                "Look for patterns that confirm or refute your theory",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """
        Decide when to call external model based on investigation completeness.

        Don't call expert analysis if the CLI agent has certain confidence - trust their judgment.
        """
        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # Check if we have meaningful investigation data
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call matching original debug tool format."""
        context_parts = [
            f"=== ISSUE DESCRIPTION ===\n{self.initial_issue or 'Investigation initiated'}\n=== END DESCRIPTION ==="
        ]

        # Add special note if confidence is almost_certain
        if consolidated_findings.confidence == "almost_certain":
            context_parts.append(
                "\n=== IMPORTANT: ALMOST CERTAIN CONFIDENCE ===\n"
                "The agent has reached 'almost_certain' confidence but has NOT confirmed the bug with 100% certainty. "
                "Your role is to:\n"
                "1. Validate the agent's hypothesis and investigation\n"
                "2. Identify any missing evidence or overlooked aspects\n"
                "3. Provide additional insights that could confirm or refute the hypothesis\n"
                "4. Help finalize the root cause analysis with complete certainty\n"
                "=== END IMPORTANT ==="
            )

        # Add investigation summary
        investigation_summary = self._build_investigation_summary(consolidated_findings)
        context_parts.append(f"\n=== AGENT'S INVESTIGATION FINDINGS ===\n{investigation_summary}\n=== END FINDINGS ===")

        # Add error context if available
        error_context = self._extract_error_context(consolidated_findings)
        if error_context:
            context_parts.append(f"\n=== ERROR CONTEXT/STACK TRACE ===\n{error_context}\n=== END CONTEXT ===")

        # Add relevant methods/functions if available
        if consolidated_findings.relevant_context:
            methods_text = "\n".join(f"- {method}" for method in consolidated_findings.relevant_context)
            context_parts.append(f"\n=== RELEVANT METHODS/FUNCTIONS ===\n{methods_text}\n=== END METHODS ===")

        # Add hypothesis evolution if available
        if consolidated_findings.hypotheses:
            hypotheses_text = "\n".join(
                f"Step {h['step']} ({h['confidence']} confidence): {h['hypothesis']}"
                for h in consolidated_findings.hypotheses
            )
            context_parts.append(f"\n=== HYPOTHESIS EVOLUTION ===\n{hypotheses_text}\n=== END HYPOTHESES ===")

        # Add images if available
        if consolidated_findings.images:
            images_text = "\n".join(f"- {img}" for img in consolidated_findings.images)
            context_parts.append(
                f"\n=== VISUAL DEBUGGING INFORMATION ===\n{images_text}\n=== END VISUAL INFORMATION ==="
            )

        # Add file content if we have relevant files
        if consolidated_findings.relevant_files:
            file_content, _ = self._prepare_file_content_for_prompt(
                list(consolidated_findings.relevant_files), None, "Essential debugging files"
            )
            if file_content:
                context_parts.append(
                    f"\n=== ESSENTIAL FILES FOR DEBUGGING ===\n{file_content}\n=== END ESSENTIAL FILES ==="
                )

        return "\n".join(context_parts)

    def _build_investigation_summary(self, consolidated_findings) -> str:
        """Prepare a comprehensive summary of the investigation."""
        summary_parts = [
            "=== SYSTEMATIC INVESTIGATION SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(consolidated_findings.relevant_files)}",
            f"Methods/functions involved: {len(consolidated_findings.relevant_context)}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            summary_parts.append(finding)

        return "\n".join(summary_parts)

    def _extract_error_context(self, consolidated_findings) -> Optional[str]:
        """Extract error context from investigation findings."""
        error_patterns = ["error", "exception", "stack trace", "traceback", "failure"]
        error_context_parts = []

        for finding in consolidated_findings.findings:
            if any(pattern in finding.lower() for pattern in error_patterns):
                error_context_parts.append(finding)

        return "\n".join(error_context_parts) if error_context_parts else None

    def get_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance matching original debug tool behavior.

        This method generates debug-specific guidance that's used by get_step_guidance_message().
        """
        # Generate the next steps instruction based on required actions
        required_actions = self.get_required_actions(step_number, confidence, request.findings, request.total_steps)

        if step_number == 1:
            next_steps = (
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first investigate "
                f"the codebase using appropriate tools. CRITICAL AWARENESS: The reported symptoms might be "
                f"caused by issues elsewhere in the code, not where symptoms appear. Also, after thorough "
                f"investigation, it's possible NO BUG EXISTS - the issue might be a misunderstanding or "
                f"user expectation mismatch. Search broadly, examine implementations, understand the logic flow. "
                f"Only call {self.get_name()} again AFTER gathering concrete evidence. When you call "
                f"{self.get_name()} next time, "
                f"use step_number: {step_number + 1} and report specific files examined and findings discovered."
            )
        elif confidence in ["exploring", "low"]:
            next_steps = (
                f"STOP! Do NOT call {self.get_name()} again yet. Based on your findings, you've identified potential areas "
                f"but need concrete evidence. MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nOnly call {self.get_name()} again with step_number: {step_number + 1} AFTER "
                + "completing these investigations."
            )
        elif confidence in ["medium", "high", "very_high"]:
            next_steps = (
                f"WAIT! Your hypothesis needs verification. DO NOT call {self.get_name()} immediately. REQUIRED ACTIONS:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nREMEMBER: If you cannot find concrete evidence of a bug causing the reported symptoms, "
                f"'no bug found' is a valid conclusion. Consider suggesting discussion with your thought partner "
                f"or engineering assistant for clarification. Document findings with specific file:line references, "
                f"then call {self.get_name()} with step_number: {step_number + 1}."
            )
        elif confidence == "almost_certain":
            next_steps = (
                "ALMOST CERTAIN - Prepare for final analysis. REQUIRED ACTIONS:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + "\n\nIMPORTANT: You're almost certain about the root cause. If you have NOT found the bug with "
                "100% certainty, consider setting next_step_required=false to invoke expert analysis. The expert "
                "can validate your hypotheses and provide additional insights. If you ARE 100% certain and have "
                "identified the exact bug and fix, proceed to confidence='certain'. Otherwise, let expert analysis "
                "help finalize the investigation."
            )
        else:
            next_steps = (
                f"PAUSE INVESTIGATION. Before calling {self.get_name()} step {step_number + 1}, you MUST examine code. "
                + "Required: "
                + ", ".join(required_actions[:2])
                + ". "
                + f"Your next {self.get_name()} call (step_number: {step_number + 1}) must include "
                f"NEW evidence from actual code examination, not just theories. If no bug evidence "
                f"is found, suggesting "
                f"collaboration with thought partner is valuable. NO recursive {self.get_name()} calls "
                f"without investigation work!"
            )

        return {"next_steps": next_steps}

    # Hook method overrides for debug-specific behavior

    def prepare_step_data(self, request) -> dict:
        """
        Prepare debug-specific step data for processing.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": request.files_checked,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "issues_found": [],  # Debug tool doesn't use issues_found field
            "confidence": request.confidence,
            "hypothesis": request.hypothesis,
            "images": request.images or [],
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Debug tool skips expert analysis when agent has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

    # Override inheritance hooks for debug-specific behavior

    def get_completion_status(self) -> str:
        """Debug tools use debug-specific status."""
        return "certain_confidence_proceed_with_fix"

    def get_completion_data_key(self) -> str:
        """Debug uses 'complete_investigation' key."""
        return "complete_investigation"

    def get_final_analysis_from_request(self, request):
        """Debug tools use 'hypothesis' field."""
        return request.hypothesis

    def get_confidence_level(self, request) -> str:
        """Debug tools use 'certain' for high confidence."""
        return "certain"

    def get_completion_message(self) -> str:
        """Debug-specific completion message."""
        return (
            "Investigation complete with CERTAIN confidence. You have identified the exact "
            "root cause and a minimal fix. MANDATORY: Present the user with the root cause analysis "
            "and IMMEDIATELY proceed with implementing the simple fix without requiring further "
            "consultation. Focus on the precise, minimal change needed."
        )

    def get_skip_reason(self) -> str:
        """Debug-specific skip reason."""
        return "Identified exact root cause with minimal fix requirement locally"

    def get_request_relevant_context(self, request) -> list:
        """Get relevant_context for debug tool."""
        try:
            return request.relevant_context or []
        except AttributeError:
            return []

    def get_skip_expert_analysis_status(self) -> str:
        """Debug-specific expert analysis skip status."""
        return "skipped_due_to_certain_confidence"

    def prepare_work_summary(self) -> str:
        """Debug-specific work summary."""
        return self._build_investigation_summary(self.consolidated_findings)

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Debug-specific completion message.

        Args:
            expert_analysis_used: True if expert analysis was successfully executed
        """
        base_message = (
            "INVESTIGATION IS COMPLETE. YOU MUST now summarize and present ALL key findings, confirmed "
            "hypotheses, and exact recommended fixes. Clearly identify the most likely root cause and "
            "provide concrete, actionable implementation guidance. Highlight affected code paths and display "
            "reasoning that led to this conclusion—make it easy for a developer to understand exactly where "
            "the problem lies. Where necessary, show cause-and-effect / bug-trace call graph."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Get additional guidance for handling expert analysis results in debug context.

        Returns:
            Additional guidance text for validating and using expert analysis findings
        """
        return (
            "IMPORTANT: Expert debugging analysis has been provided above. You MUST validate "
            "the expert's root cause analysis and proposed fixes against your own investigation. "
            "Ensure the expert's findings align with the evidence you've gathered and that the "
            "recommended solutions address the actual problem, not just symptoms. If the expert "
            "suggests a different root cause than you identified, carefully consider both perspectives "
            "and present a balanced assessment to the user."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Debug-specific step guidance with detailed investigation instructions.
        """
        step_guidance = self.get_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match original debug tool format.
        """
        # Store initial issue on first step
        if request.step_number == 1:
            self.initial_issue = request.step

        # Convert generic status names to debug-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "investigation_in_progress",
            f"pause_for_{tool_name}": "pause_for_investigation",
            f"{tool_name}_required": "investigation_required",
            f"{tool_name}_complete": "investigation_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match debug tool
        if f"{tool_name}_status" in response_data:
            response_data["investigation_status"] = response_data.pop(f"{tool_name}_status")
            # Add debug-specific status fields
            response_data["investigation_status"]["hypotheses_formed"] = len(self.consolidated_findings.hypotheses)

        # Rename complete investigation data
        if f"complete_{tool_name}" in response_data:
            response_data["complete_investigation"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match original debug tool
        if f"{tool_name}_complete" in response_data:
            response_data["investigation_complete"] = response_data.pop(f"{tool_name}_complete")

        # Map the required flag to match original debug tool
        if f"{tool_name}_required" in response_data:
            response_data["investigation_required"] = response_data.pop(f"{tool_name}_required")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the debug-specific request model."""
        return DebugInvestigationRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
