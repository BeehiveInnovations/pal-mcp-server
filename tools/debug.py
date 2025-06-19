"""
Debug Issue tool - Root cause analysis and debugging assistance with systematic investigation
"""

import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import DEBUG_ISSUE_PROMPT

from .base import BaseTool, ToolRequest

logger = logging.getLogger(__name__)

# Field descriptions for the investigation steps
DEBUG_INVESTIGATION_FIELD_DESCRIPTIONS = {
    "step": (
        "Your current investigation step. For the first step, describe the issue/error to investigate. "
        "For subsequent steps, describe what you're investigating, what code you're examining, "
        "what patterns you're looking for, or what hypothesis you're testing."
    ),
    "step_number": "Current step number in the investigation sequence (starts at 1)",
    "total_steps": "Current estimate of total investigation steps needed (can be adjusted as investigation progresses)",
    "next_step_required": "Whether another investigation step is required",
    "findings": (
        "Current findings from this investigation step. Include code patterns discovered, "
        "potential causes identified, hypotheses formed, or evidence gathered."
    ),
    "files_checked": (
        "List of files you've examined so far in the investigation (cumulative list). "
        "Include all files you've looked at, even if they turned out to be irrelevant."
    ),
    "relevant_files": (
        "List of files that are definitely related to the issue (subset of files_checked). "
        "Only include files that contain code directly related to the problem."
    ),
    "relevant_methods": (
        "List of specific methods/functions that are involved in the issue. "
        "Format: 'ClassName.methodName' or 'functionName'"
    ),
    "hypothesis": (
        "Your current working hypothesis about the root cause. This can be updated/revised "
        "as the investigation progresses."
    ),
    "confidence": "Your confidence level in the current hypothesis: 'low', 'medium', or 'high'",
    "backtrack_from_step": "If you need to revise a previous finding, which step number to backtrack from",
    "continuation_id": "Thread continuation ID for multi-turn investigation sessions",
    "images": (
        "Optional images showing error screens, UI issues, logs displays, or visual debugging information "
        "that help understand the issue (must be FULL absolute paths - DO NOT SHORTEN)"
    ),
}

# Field descriptions for the final debug request
DEBUG_FIELD_DESCRIPTIONS = {
    "initial_issue": "The original issue description that started the investigation",
    "investigation_summary": "Complete summary of the systematic investigation performed",
    "findings": "Consolidated findings from all investigation steps",
    "files": "Essential files identified during investigation (must be FULL absolute paths - DO NOT SHORTEN)",
    "error_context": "Stack trace, logs, or error context discovered during investigation",
    "relevant_methods": "List of methods/functions identified as involved in the issue",
    "hypothesis": "Final hypothesis about the root cause after investigation",
    "images": "Optional images showing error screens, UI issues, or visual debugging information",
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

    # Override inherited fields to exclude them
    model: Optional[str] = Field(default=None, exclude=True)
    temperature: Optional[float] = Field(default=None, exclude=True)
    thinking_mode: Optional[str] = Field(default=None, exclude=True)
    use_websearch: Optional[bool] = Field(default=None, exclude=True)


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
            "2. Continue with investigation steps: examine code, trace errors, test hypotheses\n"
            "3. Track findings, relevant files, and methods throughout\n"
            "4. Update hypotheses as understanding evolves\n"
            "5. Backtrack and revise findings when needed\n"
            "6. Once investigation is complete, receive expert analysis\n\n"
            "The tool enforces systematic investigation methodology:\n"
            "- Methodical code examination and evidence collection\n"
            "- Hypothesis formation and validation\n"
            "- File and method tracking for context\n"
            "- Confidence assessment and revision capabilities\n\n"
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
                    "enum": ["low", "medium", "high"],
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
            },
            # Required fields for investigation
            "required": ["step", "step_number", "total_steps", "next_step_required", "findings"],
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
        Debug tool manages its own model interactions.
        It doesn't need model during investigation steps, only for final analysis.
        """
        return False

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
                continuation_id = create_thread("debug", arguments)
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
                "output": {
                    "instructions": "Continue systematic investigation. Present findings clearly and proceed to next step if required.",
                    "format": "systematic_investigation",
                },
            }

            if continuation_id:
                response_data["continuation_id"] = continuation_id

            # If investigation is complete, call the AI model for expert analysis
            if not request.next_step_required:
                response_data["status"] = "calling_expert_analysis"
                response_data["investigation_complete"] = True

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
                    model_info=arguments.get("_model_context"),
                    model_override=arguments.get("model"),  # Pass model selection from final step
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
                    "Investigation complete with expert analysis. Present the findings, hypotheses, "
                    "and recommended fixes to the user. Focus on the most likely root cause and "
                    "provide actionable implementation guidance."
                )
            else:
                response_data["next_steps"] = (
                    f"Continue investigation with step {request.step_number + 1}. "
                    f"Focus on: examining relevant code, testing hypotheses, gathering evidence."
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
        model_override: Optional[str] = None,
    ) -> dict:
        """Call AI model for expert analysis of the investigation"""
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

        # Get appropriate model and provider
        from config import DEFAULT_MODEL
        from providers.registry import ModelProviderRegistry

        model_name = model_override or DEFAULT_MODEL  # Use override if provided
        provider = ModelProviderRegistry.get_provider_for_model(model_name)

        if not provider:
            return {"error": f"No provider available for model {model_name}", "status": "provider_error"}

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
