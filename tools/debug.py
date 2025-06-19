"""
Debug Issue tool - Root cause analysis and debugging assistance with systematic investigation
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field, field_validator

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import DEBUG_ISSUE_PROMPT

from .base import BaseTool, ToolRequest

logger = logging.getLogger(__name__)

# Field descriptions for the investigation steps
DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS = {
    "step": (
        "Describe what you're currently investigating by thinking deeply about the issue and its possible causes. "
        "In step 1, clearly state the issue and begin forming an investigative direction. CRITICAL: Remember that "
        "reported symptoms might originate from code far from where they manifest. Also be aware that after thorough "
        "investigation, you might find NO BUG EXISTS - it could be a misunderstanding or expectation mismatch. "
        "Consider not only obvious failures, but also subtle contributing factors like upstream logic, invalid inputs, "
        "missing preconditions, or hidden side effects. Map out the flow of related functions or modules. Identify "
        "call paths where input values or branching logic could cause instability. In concurrent systems, watch for "
        "race conditions, shared state, or timing dependencies. In all later steps, continue exploring with precision: "
        "trace deeper dependencies, verify hypotheses, and adapt your understanding as you uncover more evidence."
    ),
    "step_number": (
        "The index of the current step in the investigation sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Your current estimate for how many steps will be needed to complete the investigation. Adjust as new findings emerge."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the investigation with another step. False means you believe the root "
        "cause is known or the investigation is complete."
    ),
    "findings": (
        "Summarize everything discovered in this step. Include new clues, unexpected behavior, evidence from code or "
        "logs, or disproven theories. Be specific and avoid vague language—document what you now know and how it "
        "affects your hypothesis. IMPORTANT: If you find no evidence supporting the reported issue after thorough "
        "investigation, document this clearly. Finding 'no bug' is a valid outcome if the investigation was comprehensive. "
        "In later steps, confirm or disprove past findings with reason."
    ),
    "files_checked": (
        "List all files (as absolute paths, do not clip or shrink file names) examined during the investigation so far. "
        "Include even files ruled out, as this tracks your exploration path."
    ),
    "relevant_files": (
        "Subset of files_checked (as full absolute paths) that contain code directly relevant to the issue. Only list "
        "those that are directly tied to the root cause or its effects. This could include the cause, trigger, or "
        "place of manifestation."
    ),
    "relevant_methods": (
        "List methods or functions that are central to the issue, in the format 'ClassName.methodName' or 'functionName'. "
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
        "'medium' (some supporting evidence), 'high' (strong evidence), 'certain' (only when the root cause and minimal "
        "fix are both confirmed). Do NOT use 'certain' unless the issue can be fully resolved with a fix, use 'high' "
        "instead when in doubt. Using 'certain' prevents you from taking assistance from another thought-partner."
    ),
    "backtrack_from_step": (
        "If an earlier finding or hypothesis needs to be revised or discarded, specify the step number from which to "
        "start over. Use this to acknowledge investigative dead ends and correct the course."
    ),
    "continuation_id": "Continuation token used for linking multi-step investigations and continuing conversations after discovery.",
    "images": (
        "Optional list of absolute paths to screenshots or UI visuals that clarify the issue. "
        "Only include if they materially assist understanding or hypothesis formulation."
    ),
}

DEBUG_FIELD_DESCRIPTIONS = {
    "initial_issue": "Describe the original problem that triggered the investigation.",
    "investigation_summary": (
        "Full overview of the systematic investigation process. Reflect deep thinking and each step's contribution to narrowing down the issue."
    ),
    "findings": "Final list of critical insights and discoveries across all steps.",
    "files": "Essential files referenced during investigation (must be full absolute paths).",
    "error_context": "Logs, tracebacks, or execution details that support the root cause hypothesis.",
    "relevant_methods": "List of all methods/functions identified as directly involved.",
    "hypothesis": "Final, most likely explanation of the root cause based on evidence.",
    "images": "Optional screenshots or visual materials that helped diagnose the issue.",
}


class DebugInvestigationRequest(ToolRequest):
    """Request model for debug investigation steps"""

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
    relevant_methods: list[str] = Field(
        default_factory=list, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["relevant_methods"]
    )
    hypothesis: Optional[str] = Field(None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["hypothesis"])
    confidence: Optional[str] = Field("low", description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["confidence"])

    # Optional backtracking field
    backtrack_from_step: Optional[int] = Field(
        None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["backtrack_from_step"]
    )

    # Optional continuation field
    continuation_id: Optional[str] = Field(None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["continuation_id"])

    # Optional images for visual debugging
    images: Optional[list[str]] = Field(default=None, description=DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["images"])

    # Override inherited fields to exclude them from schema (except model which needs to be available)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)

    @field_validator("files_checked", "relevant_files", "relevant_methods", mode="before")
    @classmethod
    def convert_string_to_list(cls, v):
        """Convert string inputs to empty lists to handle malformed inputs gracefully."""
        if isinstance(v, str):
            logger.warning(f"Field received string '{v}' instead of list, converting to empty list")
            return []
        return v


class DebugIssueTool(BaseTool):
    """Advanced debugging tool with systematic self-investigation"""

    def __init__(self):
        super().__init__()
        self.investigation_history = []
        self.consolidated_findings = {
            "files_checked": set(),
            "relevant_files": set(),
            "relevant_methods": set(),
            "findings": [],
            "hypotheses": [],
            "images": [],
        }

    def get_name(self) -> str:
        return "debug"

    def get_description(self) -> str:
        return (
            "DEBUG & ROOT CAUSE ANALYSIS - Systematic self-investigation followed by expert analysis. "
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

    def get_input_schema(self) -> dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                # Investigation step fields
                "step": {
                    "type": "string",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step"],
                },
                "step_number": {
                    "type": "integer",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["step_number"],
                    "minimum": 1,
                },
                "total_steps": {
                    "type": "integer",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["total_steps"],
                    "minimum": 1,
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
                "relevant_methods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["relevant_methods"],
                },
                "hypothesis": {
                    "type": "string",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["hypothesis"],
                },
                "confidence": {
                    "type": "string",
                    "enum": ["exploring", "low", "medium", "high", "certain"],
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["confidence"],
                },
                "backtrack_from_step": {
                    "type": "integer",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["backtrack_from_step"],
                    "minimum": 1,
                },
                "continuation_id": {
                    "type": "string",
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["continuation_id"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS["images"],
                },
                # Add model field for proper model selection
                "model": self.get_model_field_schema(),
            },
            # Required fields for investigation
            "required": ["step", "step_number", "total_steps", "next_step_required", "findings"]
            + (["model"] if self.is_effective_auto_mode() else []),
        }
        return schema

    def get_system_prompt(self) -> str:
        return DEBUG_ISSUE_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Debug requires deep analysis and reasoning"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def get_request_model(self):
        return DebugInvestigationRequest

    def requires_model(self) -> bool:
        """
        Debug tool requires a model for expert analysis after investigation.
        """
        return True

    async def execute(self, arguments: dict[str, Any]) -> list:
        """
        Override execute to implement self-investigation pattern.

        Investigation Flow:
        1. Claude calls debug with investigation steps
        2. Tool tracks findings, files, methods progressively
        3. Once investigation is complete, tool calls AI model for expert analysis
        4. Returns structured response combining investigation + expert analysis
        """
        from mcp.types import TextContent

        from utils.conversation_memory import add_turn, create_thread

        try:
            # Validate request
            request = DebugInvestigationRequest(**arguments)

            # Adjust total steps if needed
            if request.step_number > request.total_steps:
                request.total_steps = request.step_number

            # Handle continuation
            continuation_id = request.continuation_id

            # Create thread for first step
            if not continuation_id and request.step_number == 1:
                # Clean arguments to remove non-serializable fields
                clean_args = {k: v for k, v in arguments.items() if k not in ["_model_context", "_resolved_model_name"]}
                continuation_id = create_thread("debug", clean_args)
                # Store initial issue description
                self.initial_issue = request.step

            # Handle backtracking first if requested
            if request.backtrack_from_step:
                # Remove findings after the backtrack point
                self.investigation_history = [
                    s for s in self.investigation_history if s["step_number"] < request.backtrack_from_step
                ]
                # Reprocess consolidated findings to match truncated history
                self._reprocess_consolidated_findings()

                # Log if step number needs correction
                expected_step_number = len(self.investigation_history) + 1
                if request.step_number != expected_step_number:
                    logger.debug(
                        f"Step number adjusted from {request.step_number} to {expected_step_number} after backtracking"
                    )

            # Process investigation step
            step_data = {
                "step": request.step,
                "step_number": request.step_number,
                "findings": request.findings,
                "files_checked": request.files_checked,
                "relevant_files": request.relevant_files,
                "relevant_methods": request.relevant_methods,
                "hypothesis": request.hypothesis,
                "confidence": request.confidence,
                "images": request.images,
            }

            # Store in history
            self.investigation_history.append(step_data)

            # Update consolidated findings
            self.consolidated_findings["files_checked"].update(request.files_checked)
            self.consolidated_findings["relevant_files"].update(request.relevant_files)
            self.consolidated_findings["relevant_methods"].update(request.relevant_methods)
            self.consolidated_findings["findings"].append(f"Step {request.step_number}: {request.findings}")
            if request.hypothesis:
                self.consolidated_findings["hypotheses"].append(
                    {"step": request.step_number, "hypothesis": request.hypothesis, "confidence": request.confidence}
                )
            if request.images:
                self.consolidated_findings["images"].extend(request.images)

            # Build response
            response_data = {
                "status": "investigation_in_progress",
                "step_number": request.step_number,
                "total_steps": request.total_steps,
                "next_step_required": request.next_step_required,
                "investigation_status": {
                    "files_checked": len(self.consolidated_findings["files_checked"]),
                    "relevant_files": len(self.consolidated_findings["relevant_files"]),
                    "relevant_methods": len(self.consolidated_findings["relevant_methods"]),
                    "hypotheses_formed": len(self.consolidated_findings["hypotheses"]),
                    "images_collected": len(set(self.consolidated_findings["images"])),
                    "current_confidence": request.confidence,
                },
            }

            if continuation_id:
                response_data["continuation_id"] = continuation_id

            # If investigation is complete, decide whether to call expert analysis or proceed with minimal fix
            if not request.next_step_required:
                response_data["investigation_complete"] = True

                # Check if Claude has absolute certainty and can proceed with minimal fix
                if request.confidence == "certain":
                    # Trust Claude's judgment completely - if it says certain, skip expert analysis
                    response_data["status"] = "certain_confidence_proceed_with_fix"

                    investigation_summary = self._prepare_investigation_summary()
                    response_data["complete_investigation"] = {
                        "initial_issue": getattr(self, "initial_issue", request.step),
                        "steps_taken": len(self.investigation_history),
                        "files_examined": list(self.consolidated_findings["files_checked"]),
                        "relevant_files": list(self.consolidated_findings["relevant_files"]),
                        "relevant_methods": list(self.consolidated_findings["relevant_methods"]),
                        "investigation_summary": investigation_summary,
                        "final_hypothesis": request.hypothesis,
                        "confidence_level": "certain",
                    }
                    response_data["next_steps"] = (
                        "Investigation complete with CERTAIN confidence. You have identified the exact "
                        "root cause and a minimal fix. MANDATORY: Present the user with the root cause analysis"
                        "and IMMEDIATELY proceed with implementing the simple fix without requiring further "
                        "consultation. Focus on the precise, minimal change needed."
                    )
                    response_data["skip_expert_analysis"] = True
                    response_data["expert_analysis"] = {
                        "status": "skipped_due_to_certain_confidence",
                        "reason": "Claude identified exact root cause with minimal fix requirement",
                    }
                else:
                    # Standard expert analysis for certain/high/medium/low/exploring confidence
                    response_data["status"] = "calling_expert_analysis"

                    # Prepare consolidated investigation summary
                    investigation_summary = self._prepare_investigation_summary()

                    # Call the AI model with full context
                    expert_analysis = await self._call_expert_analysis(
                        initial_issue=getattr(self, "initial_issue", request.step),
                        investigation_summary=investigation_summary,
                        relevant_files=list(self.consolidated_findings["relevant_files"]),
                        relevant_methods=list(self.consolidated_findings["relevant_methods"]),
                        final_hypothesis=request.hypothesis,
                        error_context=self._extract_error_context(),
                        images=list(set(self.consolidated_findings["images"])),  # Unique images
                        model_info=arguments.get("_model_context"),  # Use pre-resolved model context from server.py
                        arguments=arguments,  # Pass arguments for model resolution
                        request=request,  # Pass request for model resolution
                    )

                    # Combine investigation and expert analysis
                    response_data["expert_analysis"] = expert_analysis
                    response_data["complete_investigation"] = {
                        "initial_issue": getattr(self, "initial_issue", request.step),
                        "steps_taken": len(self.investigation_history),
                        "files_examined": list(self.consolidated_findings["files_checked"]),
                        "relevant_files": list(self.consolidated_findings["relevant_files"]),
                        "relevant_methods": list(self.consolidated_findings["relevant_methods"]),
                        "investigation_summary": investigation_summary,
                    }
                    response_data["next_steps"] = (
                        "INVESTIGATION IS COMPLETE. YOU MUST now summarize and present ALL key findings, confirmed "
                        "hypotheses, and exact recommended fixes. Clearly identify the most likely root cause and "
                        "provide concrete, actionable implementation guidance. Highlight affected code paths and display "
                        "reasoning that led to this conclusion—make it easy for a developer to understand exactly where "
                        "the problem lies."
                    )
            else:
                # CRITICAL: Force Claude to actually investigate before calling debug again
                response_data["status"] = "pause_for_investigation"
                response_data["investigation_required"] = True

                if request.step_number == 1:
                    # Initial investigation tasks
                    response_data["required_actions"] = [
                        "Search for code related to the reported issue or symptoms",
                        "Examine relevant files and understand the current implementation",
                        "Understand the project structure and locate relevant modules",
                        "Identify how the affected functionality is supposed to work",
                    ]
                    response_data["next_steps"] = (
                        f"MANDATORY: DO NOT call the debug tool again immediately. You MUST first investigate "
                        f"the codebase using appropriate tools. CRITICAL AWARENESS: The reported symptoms might be "
                        f"caused by issues elsewhere in the code, not where symptoms appear. Also, after thorough "
                        f"investigation, it's possible NO BUG EXISTS - the issue might be a misunderstanding or "
                        f"user expectation mismatch. Search broadly, examine implementations, understand the logic flow. "
                        f"Only call debug again AFTER gathering concrete evidence. When you call debug next time, "
                        f"use step_number: {request.step_number + 1} and report specific files examined and findings discovered."
                    )
                elif request.step_number >= 2 and request.confidence in ["exploring", "low"]:
                    # Need deeper investigation
                    response_data["required_actions"] = [
                        "Examine the specific files you've identified as relevant",
                        "Trace method calls and data flow through the system",
                        "Check for edge cases, boundary conditions, and assumptions in the code",
                        "Look for related configuration, dependencies, or external factors",
                    ]
                    response_data["next_steps"] = (
                        f"STOP! Do NOT call debug again yet. Based on your findings, you've identified potential areas "
                        f"but need concrete evidence. MANDATORY ACTIONS before calling debug step {request.step_number + 1}:\n"
                        f"1. Examine ALL files in your relevant_files list\n"
                        f"2. Trace how data flows through {', '.join(request.relevant_methods[:3]) if request.relevant_methods else 'the identified components'}\n"
                        f"3. Look for logic errors, incorrect assumptions, missing validations\n"
                        f"4. Check interactions between components and external dependencies\n"
                        f"Only call debug again with step_number: {request.step_number + 1} AFTER completing these investigations."
                    )
                elif request.confidence in ["medium", "high"]:
                    # Close to root cause - need confirmation
                    response_data["required_actions"] = [
                        "Examine the exact code sections where you believe the issue occurs",
                        "Trace the execution path that leads to the failure",
                        "Verify your hypothesis with concrete code evidence",
                        "Check for any similar patterns elsewhere in the codebase",
                    ]
                    response_data["next_steps"] = (
                        f"WAIT! Your hypothesis needs verification. DO NOT call debug immediately. REQUIRED ACTIONS:\n"
                        f"1. Examine the exact lines where the issue occurs\n"
                        f"2. Trace backwards: how does data get to this point? What transforms it?\n"
                        f"3. Check all assumptions: are inputs validated? Are nulls handled?\n"
                        f"4. Look for the EXACT line where expected != actual behavior\n"
                        f"REMEMBER: If you cannot find concrete evidence of a bug causing the reported symptoms, "
                        f"'no bug found' is a valid conclusion. Consider suggesting discussion with your thought partner "
                        f"or engineering assistant for clarification. Document findings with specific file:line references, "
                        f"then call debug with step_number: {request.step_number + 1}."
                    )
                else:
                    # General investigation needed
                    response_data["required_actions"] = [
                        "Continue examining the code paths identified in your hypothesis",
                        "Gather more evidence using appropriate investigation tools",
                        "Test edge cases and boundary conditions",
                        "Look for patterns that confirm or refute your theory",
                    ]
                    response_data["next_steps"] = (
                        f"PAUSE INVESTIGATION. Before calling debug step {request.step_number + 1}, you MUST examine code. "
                        f"Required: Read files from your files_checked list, search for patterns in your hypothesis, "
                        f"trace execution flow. Your next debug call (step_number: {request.step_number + 1}) must include "
                        f"NEW evidence from actual code examination, not just theories. If no bug evidence is found, suggesting "
                        f"collaboration with thought partner is valuable. NO recursive debug calls without investigation work!"
                    )

            # Store in conversation memory
            if continuation_id:
                add_turn(
                    thread_id=continuation_id,
                    role="assistant",
                    content=json.dumps(response_data, indent=2),
                    tool_name="debug",
                    files=list(self.consolidated_findings["relevant_files"]),
                    images=request.images,
                )

            return [TextContent(type="text", text=json.dumps(response_data, indent=2))]

        except Exception as e:
            logger.error(f"Error in debug investigation: {e}", exc_info=True)
            error_data = {
                "status": "investigation_failed",
                "error": str(e),
                "step_number": arguments.get("step_number", 0),
            }
            return [TextContent(type="text", text=json.dumps(error_data, indent=2))]

    def _reprocess_consolidated_findings(self):
        """Reprocess consolidated findings after backtracking"""
        self.consolidated_findings = {
            "files_checked": set(),
            "relevant_files": set(),
            "relevant_methods": set(),
            "findings": [],
            "hypotheses": [],
            "images": [],
        }

        for step in self.investigation_history:
            self.consolidated_findings["files_checked"].update(step.get("files_checked", []))
            self.consolidated_findings["relevant_files"].update(step.get("relevant_files", []))
            self.consolidated_findings["relevant_methods"].update(step.get("relevant_methods", []))
            self.consolidated_findings["findings"].append(f"Step {step['step_number']}: {step['findings']}")
            if step.get("hypothesis"):
                self.consolidated_findings["hypotheses"].append(
                    {
                        "step": step["step_number"],
                        "hypothesis": step["hypothesis"],
                        "confidence": step.get("confidence", "low"),
                    }
                )
            if step.get("images"):
                self.consolidated_findings["images"].extend(step["images"])

    def _prepare_investigation_summary(self) -> str:
        """Prepare a comprehensive summary of the investigation"""
        summary_parts = [
            "=== SYSTEMATIC INVESTIGATION SUMMARY ===",
            f"Total steps: {len(self.investigation_history)}",
            f"Files examined: {len(self.consolidated_findings['files_checked'])}",
            f"Relevant files identified: {len(self.consolidated_findings['relevant_files'])}",
            f"Methods/functions involved: {len(self.consolidated_findings['relevant_methods'])}",
            "",
            "=== INVESTIGATION PROGRESSION ===",
        ]

        for finding in self.consolidated_findings["findings"]:
            summary_parts.append(finding)

        if self.consolidated_findings["hypotheses"]:
            summary_parts.extend(
                [
                    "",
                    "=== HYPOTHESIS EVOLUTION ===",
                ]
            )
            for hyp in self.consolidated_findings["hypotheses"]:
                summary_parts.append(f"Step {hyp['step']} ({hyp['confidence']} confidence): {hyp['hypothesis']}")

        return "\n".join(summary_parts)

    def _extract_error_context(self) -> Optional[str]:
        """Extract error context from investigation findings"""
        error_patterns = ["error", "exception", "stack trace", "traceback", "failure"]
        error_context_parts = []

        for finding in self.consolidated_findings["findings"]:
            if any(pattern in finding.lower() for pattern in error_patterns):
                error_context_parts.append(finding)

        return "\n".join(error_context_parts) if error_context_parts else None

    async def _call_expert_analysis(
        self,
        initial_issue: str,
        investigation_summary: str,
        relevant_files: list[str],
        relevant_methods: list[str],
        final_hypothesis: Optional[str],
        error_context: Optional[str],
        images: list[str],
        model_info: Optional[Any] = None,
        arguments: Optional[dict] = None,
        request: Optional[Any] = None,
    ) -> dict:
        """Call AI model for expert analysis of the investigation"""
        # Set up model context when we actually need it for expert analysis
        # Use the same model resolution logic as the base class
        if model_info:
            # Use pre-resolved model context from server.py (normal case)
            self._model_context = model_info
            model_name = model_info.model_name
        else:
            # Use centralized model resolution from base class
            if arguments and request:
                try:
                    model_name, model_context = self._resolve_model_context(arguments, request)
                    self._model_context = model_context
                except ValueError as e:
                    # Model resolution failed, return error
                    return {"error": f"Model resolution failed: {str(e)}", "status": "model_resolution_error"}
            else:
                # Last resort fallback if no arguments/request provided
                from config import DEFAULT_MODEL
                from utils.model_context import ModelContext

                model_name = DEFAULT_MODEL
                self._model_context = ModelContext(model_name)

        # Store model name for use by other methods
        self._current_model_name = model_name
        provider = self.get_model_provider(model_name)

        # Prepare the debug prompt with all investigation context
        prompt_parts = [
            f"=== ISSUE DESCRIPTION ===\n{initial_issue}\n=== END DESCRIPTION ===",
            f"\n=== CLAUDE'S INVESTIGATION FINDINGS ===\n{investigation_summary}\n=== END FINDINGS ===",
        ]

        if error_context:
            prompt_parts.append(f"\n=== ERROR CONTEXT/STACK TRACE ===\n{error_context}\n=== END CONTEXT ===")

        if relevant_methods:
            prompt_parts.append(
                "\n=== RELEVANT METHODS/FUNCTIONS ===\n"
                + "\n".join(f"- {method}" for method in relevant_methods)
                + "\n=== END METHODS ==="
            )

        if final_hypothesis:
            prompt_parts.append(f"\n=== FINAL HYPOTHESIS ===\n{final_hypothesis}\n=== END HYPOTHESIS ===")

        if images:
            prompt_parts.append(
                "\n=== VISUAL DEBUGGING INFORMATION ===\n"
                + "\n".join(f"- {img}" for img in images)
                + "\n=== END VISUAL INFORMATION ==="
            )

        # Add file content if we have relevant files
        if relevant_files:
            file_content, _ = self._prepare_file_content_for_prompt(relevant_files, None, "Essential debugging files")
            if file_content:
                prompt_parts.append(
                    f"\n=== ESSENTIAL FILES FOR DEBUGGING ===\n{file_content}\n=== END ESSENTIAL FILES ==="
                )

        full_prompt = "\n".join(prompt_parts)

        # Generate AI response
        try:
            full_analysis_prompt = f"{self.get_system_prompt()}\n\n{full_prompt}\n\nPlease debug this issue following the structured format in the system prompt."

            # Prepare generation kwargs
            generation_kwargs = {
                "prompt": full_analysis_prompt,
                "model_name": model_name,
                "system_prompt": "",  # Already included in prompt
                "temperature": self.get_default_temperature(),
                "thinking_mode": "high",  # High thinking for debug analysis
            }

            # Add images if available
            if images:
                generation_kwargs["images"] = images

            model_response = provider.generate_content(**generation_kwargs)

            if model_response.content:
                # Try to parse as JSON
                try:
                    analysis_result = json.loads(model_response.content.strip())
                    return analysis_result
                except json.JSONDecodeError:
                    # Return as text if not valid JSON
                    return {
                        "status": "analysis_complete",
                        "raw_analysis": model_response.content,
                        "parse_error": "Response was not valid JSON",
                    }
            else:
                return {"error": "No response from model", "status": "empty_response"}

        except Exception as e:
            logger.error(f"Error calling expert analysis: {e}", exc_info=True)
            return {"error": str(e), "status": "analysis_error"}

    # Stub implementations for base class requirements
    async def prepare_prompt(self, request) -> str:
        return ""  # Not used - execute() is overridden

    def format_response(self, response: str, request, model_info: dict = None) -> str:
        return response  # Not used - execute() is overridden
