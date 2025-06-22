"""
Documentation Generation tool - Automated code documentation with complexity analysis

This tool provides a structured workflow for adding comprehensive documentation to codebases.
It guides you through systematic code analysis to generate modern documentation with:
- Function/method parameter documentation
- Big O complexity analysis
- Call flow and dependency documentation
- Inline comments for complex logic
- Smart updating of existing documentation

Key features:
- Step-by-step documentation workflow with progress tracking
- Context-aware file embedding (references during analysis, full content for documentation)
- Automatic conversation threading and history preservation
- Expert analysis integration with external models
- Support for multiple programming languages and documentation styles
- Configurable documentation features via parameters
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_ANALYTICAL
from systemprompts import DOCGEN_PROMPT
from tools.shared.base_models import WorkflowRequest

from .workflow.base import WorkflowTool

logger = logging.getLogger(__name__)

# Tool-specific field descriptions for documentation generation
DOCGEN_FIELD_DESCRIPTIONS = {
    "step": (
        "For step 1: DISCOVERY PHASE ONLY - describe your plan to discover ALL files that need documentation in the current directory. "
        "DO NOT document anything yet. Count all files, list them clearly, report the total count, then IMMEDIATELY proceed to step 2. "
        "For step 2 and beyond: DOCUMENTATION PHASE - describe what you're currently documenting, focusing on ONE FILE at a time "
        "to ensure complete coverage of all functions and methods within that file. CRITICAL: DO NOT ALTER ANY CODE LOGIC - "
        "only add documentation (docstrings, comments). ALWAYS use MODERN documentation style for the programming language "
        '(e.g., /// for Objective-C, /** */ for Java/JavaScript, """ for Python, // for Swift/C++, etc. - NEVER use legacy styles). '
        "Consider complexity analysis, call flow information, and parameter descriptions. "
        "If you find bugs or logic issues, TRACK THEM but DO NOT FIX THEM - report after documentation is complete. "
        "Report progress using num_files_documented out of total_files_to_document counters."
    ),
    "step_number": (
        "The index of the current step in the documentation generation sequence, beginning at 1. Each step should build upon or "
        "revise the previous one."
    ),
    "total_steps": (
        "Total steps needed to complete documentation: 1 (discovery) + number of files to document. "
        "This is calculated dynamically based on total_files_to_document counter."
    ),
    "next_step_required": (
        "Set to true if you plan to continue the documentation analysis with another step. False means you believe the "
        "documentation plan is complete and ready for implementation."
    ),
    "findings": (
        "Summarize everything discovered in this step about the code and its documentation needs. Include analysis of missing "
        "documentation, complexity assessments, call flow understanding, and opportunities for improvement. Be specific and "
        "avoid vague language—document what you now know about the code structure and how it affects your documentation plan. "
        "IMPORTANT: Document both well-documented areas (good examples to follow) and areas needing documentation. "
        "ALWAYS use MODERN documentation style appropriate for the programming language (/// for Objective-C, /** */ for Java/JavaScript, "
        '""" for Python, // for Swift/C++, etc. - NEVER use legacy /* */ style for languages that have modern alternatives). '
        "If you discover any glaring, super-critical bugs that could cause serious harm or data corruption, IMMEDIATELY STOP "
        "the documentation workflow and ask the user directly if this critical bug should be addressed first before continuing. "
        "For any other non-critical bugs, flaws, or potential improvements, note them here so they can be surfaced later for review. "
        "In later steps, confirm or update past findings with additional evidence."
    ),
    "relevant_files": (
        "Current focus files (as full absolute paths) for this step. In each step, focus on documenting "
        "ONE FILE COMPLETELY before moving to the next. This should contain only the file(s) being "
        "actively documented in the current step, not all files that might need documentation."
    ),
    "relevant_context": (
        "List methods, functions, or classes that need documentation, in the format "
        "'ClassName.methodName' or 'functionName'. "
        "Prioritize those with complex logic, important interfaces, or missing/inadequate documentation."
    ),
    "num_files_documented": (
        "CRITICAL COUNTER: Number of files you have COMPLETELY documented so far. Start at 0. "
        "Increment by 1 only when a file is 100% documented (all functions/methods have documentation). "
        "This counter prevents premature completion - you CANNOT set next_step_required=false "
        "unless num_files_documented equals total_files_to_document."
    ),
    "total_files_to_document": (
        "CRITICAL COUNTER: Total number of files discovered that need documentation in current directory. "
        "Set this in step 1 after discovering all files. This is the target number - when "
        "num_files_documented reaches this number, then and ONLY then can you set next_step_required=false. "
        "This prevents stopping after documenting just one file."
    ),
    "document_complexity": (
        "Whether to include algorithmic complexity (Big O) analysis in function/method documentation. "
        "Default: true. When enabled, analyzes and documents the computational complexity of algorithms."
    ),
    "document_flow": (
        "Whether to include call flow and dependency information in documentation. "
        "Default: true. When enabled, documents which methods this function calls and which methods call this function."
    ),
    "update_existing": (
        "Whether to update existing documentation when it's found to be incorrect or incomplete. "
        "Default: true. When enabled, improves existing docs rather than just adding new ones."
    ),
    "comments_on_complex_logic": (
        "Whether to add inline comments around complex logic within functions. "
        "Default: true. When enabled, adds explanatory comments for non-obvious algorithmic steps."
    ),
}


class DocgenRequest(WorkflowRequest):
    """Request model for documentation generation steps"""

    # Required workflow fields
    step: str = Field(..., description=DOCGEN_FIELD_DESCRIPTIONS["step"])
    step_number: int = Field(..., description=DOCGEN_FIELD_DESCRIPTIONS["step_number"])
    total_steps: int = Field(..., description=DOCGEN_FIELD_DESCRIPTIONS["total_steps"])
    next_step_required: bool = Field(..., description=DOCGEN_FIELD_DESCRIPTIONS["next_step_required"])

    # Documentation analysis tracking fields
    findings: str = Field(..., description=DOCGEN_FIELD_DESCRIPTIONS["findings"])
    relevant_files: list[str] = Field(default_factory=list, description=DOCGEN_FIELD_DESCRIPTIONS["relevant_files"])
    relevant_context: list[str] = Field(default_factory=list, description=DOCGEN_FIELD_DESCRIPTIONS["relevant_context"])

    # Critical completion tracking counters
    num_files_documented: int = Field(0, description=DOCGEN_FIELD_DESCRIPTIONS["num_files_documented"])
    total_files_to_document: int = Field(0, description=DOCGEN_FIELD_DESCRIPTIONS["total_files_to_document"])

    # Documentation generation configuration parameters
    document_complexity: Optional[bool] = Field(True, description=DOCGEN_FIELD_DESCRIPTIONS["document_complexity"])
    document_flow: Optional[bool] = Field(True, description=DOCGEN_FIELD_DESCRIPTIONS["document_flow"])
    update_existing: Optional[bool] = Field(True, description=DOCGEN_FIELD_DESCRIPTIONS["update_existing"])
    comments_on_complex_logic: Optional[bool] = Field(
        True, description=DOCGEN_FIELD_DESCRIPTIONS["comments_on_complex_logic"]
    )


class DocgenTool(WorkflowTool):
    """
    Documentation generation tool for automated code documentation with complexity analysis.

    This tool implements a structured documentation workflow that guides users through
    methodical code analysis to generate comprehensive documentation including:
    - Function/method signatures and parameter descriptions
    - Algorithmic complexity (Big O) analysis
    - Call flow and dependency documentation
    - Inline comments for complex logic
    - Modern documentation style appropriate for the language/platform
    """

    def __init__(self):
        super().__init__()
        self.initial_request = None

    def get_name(self) -> str:
        return "docgen"

    def get_description(self) -> str:
        return (
            "COMPREHENSIVE DOCUMENTATION GENERATION - Step-by-step code documentation with expert analysis. "
            "This tool guides you through a systematic investigation process where you:\n\n"
            "1. Start with step 1: describe your documentation investigation plan\n"
            "2. STOP and investigate code structure, patterns, and documentation needs\n"
            "3. Report findings in step 2 with concrete evidence from actual code analysis\n"
            "4. Continue investigating between each step\n"
            "5. Track findings, relevant files, and documentation opportunities throughout\n"
            "6. Update assessments as understanding evolves\n"
            "7. Once investigation is complete, receive expert analysis\n\n"
            "IMPORTANT: This tool enforces investigation between steps:\n"
            "- After each call, you MUST investigate before calling again\n"
            "- Each step must include NEW evidence from code examination\n"
            "- No recursive calls without actual investigation work\n"
            "- The tool will specify which step number to use next\n"
            "- Follow the required_actions list for investigation guidance\n\n"
            "Perfect for: comprehensive documentation generation, code documentation analysis, "
            "complexity assessment, documentation modernization, API documentation."
        )

    def get_system_prompt(self) -> str:
        return DOCGEN_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_ANALYTICAL

    def get_model_category(self) -> "ToolModelCategory":
        """Docgen requires analytical and reasoning capabilities"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.EXTENDED_REASONING

    def requires_model(self) -> bool:
        """
        Docgen tool doesn't require model resolution at the MCP boundary.

        The docgen tool is a self-contained workflow tool that guides Claude through
        systematic documentation generation without calling external AI models.

        Returns:
            bool: False - docgen doesn't need external AI model access
        """
        return False

    def requires_expert_analysis(self) -> bool:
        """Docgen is self-contained and doesn't need expert analysis."""
        return False

    def get_workflow_request_model(self):
        """Return the docgen-specific request model."""
        return DocgenRequest

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Return the tool-specific fields for docgen."""
        return {
            "document_complexity": {
                "type": "boolean",
                "default": True,
                "description": DOCGEN_FIELD_DESCRIPTIONS["document_complexity"],
            },
            "document_flow": {
                "type": "boolean",
                "default": True,
                "description": DOCGEN_FIELD_DESCRIPTIONS["document_flow"],
            },
            "update_existing": {
                "type": "boolean",
                "default": True,
                "description": DOCGEN_FIELD_DESCRIPTIONS["update_existing"],
            },
            "comments_on_complex_logic": {
                "type": "boolean",
                "default": True,
                "description": DOCGEN_FIELD_DESCRIPTIONS["comments_on_complex_logic"],
            },
            "num_files_documented": {
                "type": "integer",
                "default": 0,
                "minimum": 0,
                "description": DOCGEN_FIELD_DESCRIPTIONS["num_files_documented"],
            },
            "total_files_to_document": {
                "type": "integer",
                "default": 0,
                "minimum": 0,
                "description": DOCGEN_FIELD_DESCRIPTIONS["total_files_to_document"],
            },
        }

    def get_required_fields(self) -> list[str]:
        """Return additional required fields beyond the standard workflow requirements."""
        return [
            "document_complexity",
            "document_flow",
            "update_existing",
            "comments_on_complex_logic",
            "num_files_documented",
            "total_files_to_document",
        ]

    def get_input_schema(self) -> dict[str, Any]:
        """Generate input schema using WorkflowSchemaBuilder with field exclusions."""
        from .workflow.schema_builders import WorkflowSchemaBuilder

        # Exclude workflow fields that documentation generation doesn't need
        excluded_workflow_fields = [
            "confidence",  # Documentation doesn't use confidence levels
            "hypothesis",  # Documentation doesn't use hypothesis
            "backtrack_from_step",  # Documentation uses simpler error recovery
            "files_checked",  # Documentation uses doc_files and doc_methods instead for better tracking
        ]

        # Exclude common fields that documentation generation doesn't need
        excluded_common_fields = [
            "model",  # Documentation doesn't need external model selection
            "temperature",  # Documentation doesn't need temperature control
            "thinking_mode",  # Documentation doesn't need thinking mode
            "use_websearch",  # Documentation doesn't need web search
            "images",  # Documentation doesn't use images
        ]

        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=self.get_tool_fields(),
            required_fields=self.get_required_fields(),  # Include docgen-specific required fields
            model_field_schema=None,  # Exclude model field - docgen doesn't need external model selection
            auto_mode=False,  # Force non-auto mode to prevent model field addition
            tool_name=self.get_name(),
            excluded_workflow_fields=excluded_workflow_fields,
            excluded_common_fields=excluded_common_fields,
        )

    def get_required_actions(self, step_number: int, confidence: str, findings: str, total_steps: int) -> list[str]:
        """Define required actions for comprehensive documentation analysis with step-by-step file focus."""
        if step_number == 1:
            # Initial discovery ONLY - no documentation yet
            return [
                "CRITICAL: DO NOT ALTER ANY CODE LOGIC! Only add documentation (docstrings, comments)",
                "Discover ALL files in the current directory (not nested) that need documentation",
                "COUNT the exact number of files that need documentation",
                "LIST all the files you found that need documentation by name",
                "IDENTIFY the programming language(s) to use MODERN documentation style (/// for Objective-C, /** */ for Java/JavaScript, etc.)",
                "DO NOT start documenting any files yet - this is discovery phase only",
                "Report the total count and file list clearly to the user",
                "IMMEDIATELY call docgen step 2 after discovery to begin documentation phase",
                "WHEN CALLING DOCGEN step 2: Set total_files_to_document to the exact count you found",
                "WHEN CALLING DOCGEN step 2: Set num_files_documented to 0 (haven't started yet)",
            ]
        elif step_number == 2:
            # Start documentation phase with first file
            return [
                "CRITICAL: DO NOT ALTER ANY CODE LOGIC! Only add documentation (docstrings, comments)",
                "Choose the FIRST file from your discovered list to start documentation",
                "For the chosen file: identify ALL functions, classes, and methods within it",
                'USE MODERN documentation style for the programming language (/// for Objective-C, /** */ for Java/JavaScript, """ for Python, etc.)',
                "Document ALL functions/methods in the chosen file - don't skip any - DOCUMENTATION ONLY",
                "When file is 100% documented, increment num_files_documented from 0 to 1",
                "Note any dependencies this file has (what it imports/calls) and what calls into it",
                "Track any logic bugs/issues found but DO NOT FIX THEM - report after documentation complete",
                "Report which specific functions you documented in this step for accountability",
                "Report progress: num_files_documented (1) out of total_files_to_document",
            ]
        elif step_number <= 4:
            # Continue with focused file-by-file approach
            return [
                "CRITICAL: DO NOT ALTER ANY CODE LOGIC! Only add documentation (docstrings, comments)",
                "Choose the NEXT undocumented file from your discovered list",
                "For the chosen file: identify ALL functions, classes, and methods within it",
                "USE MODERN documentation style for the programming language (NEVER use legacy /* */ style for languages with modern alternatives)",
                "Document ALL functions/methods in the chosen file - don't skip any - DOCUMENTATION ONLY",
                "When file is 100% documented, increment num_files_documented by 1",
                "Verify that EVERY function in the current file has proper documentation (no skipping)",
                "Track any bugs/issues found but DO NOT FIX THEM - document first, report issues later",
                "Report specific function names you documented for verification",
                "Report progress: current num_files_documented out of total_files_to_document",
            ]
        else:
            # Continue systematic file-by-file coverage
            return [
                "CRITICAL: DO NOT ALTER ANY CODE LOGIC! Only add documentation (docstrings, comments)",
                "Check counters: num_files_documented vs total_files_to_document",
                "If num_files_documented < total_files_to_document: choose NEXT undocumented file",
                "USE MODERN documentation style appropriate for each programming language (NEVER legacy styles)",
                "Document every function, method, and class in current file with no exceptions",
                "When file is 100% documented, increment num_files_documented by 1",
                "Track bugs/issues found but DO NOT FIX THEM - focus on documentation only",
                "Report progress: current num_files_documented out of total_files_to_document",
                "If num_files_documented < total_files_to_document: RESTART docgen with next step",
                "ONLY set next_step_required=false when num_files_documented equals total_files_to_document",
                "For nested dependencies: check if functions call into subdirectories and document those too",
                "Report any accumulated bugs/issues found during documentation for user decision",
            ]

    def should_call_expert_analysis(self, consolidated_findings, request=None) -> bool:
        """Docgen is self-contained and doesn't need expert analysis."""
        return False

    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Docgen doesn't use expert analysis."""
        return ""

    def get_step_guidance(self, step_number: int, confidence: str, request) -> dict[str, Any]:
        """
        Provide step-specific guidance for documentation generation workflow.

        This method generates docgen-specific guidance used by get_step_guidance_message().
        """
        # Generate the next steps instruction based on required actions
        # Calculate dynamic total_steps based on files to document
        total_files_to_document = self.get_request_total_files_to_document(request)
        calculated_total_steps = 1 + total_files_to_document if total_files_to_document > 0 else request.total_steps

        required_actions = self.get_required_actions(step_number, confidence, request.findings, calculated_total_steps)

        if step_number == 1:
            next_steps = (
                f"DISCOVERY PHASE ONLY - DO NOT START DOCUMENTING YET!\n"
                f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. You MUST first perform "
                f"FILE DISCOVERY step by step. DO NOT DOCUMENT ANYTHING YET. "
                f"MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nCRITICAL: When you call {self.get_name()} step 2, set total_files_to_document to the exact count "
                f"of files needing documentation and set num_files_documented to 0 (haven't started documenting yet). "
                f"Your total_steps will be automatically calculated as 1 (discovery) + number of files to document. "
                f"Step 2 will BEGIN the documentation phase. Report the count clearly and then IMMEDIATELY "
                f"proceed to call {self.get_name()} step 2 to start documenting the first file."
            )
        elif step_number == 2:
            next_steps = (
                f"DOCUMENTATION PHASE BEGINS! ABSOLUTE RULE: DO NOT ALTER ANY CODE LOGIC! DOCUMENTATION ONLY!\n"
                f"START FILE-BY-FILE APPROACH! Focus on ONE file until 100% complete. "
                f"MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nREPORT your progress: which specific functions did you document? Update num_files_documented from 0 to 1 when first file complete. "
                f"REPORT counters: current num_files_documented out of total_files_to_document. "
                f"If you found bugs/issues, LIST THEM but DO NOT FIX THEM - ask user what to do after documentation. "
                f"Do NOT move to a new file until the current one is completely documented. "
                f"When ready for step {step_number + 1}, report completed work with updated counters."
            )
        elif step_number <= 4:
            next_steps = (
                f"ABSOLUTE RULE: DO NOT ALTER ANY CODE LOGIC! DOCUMENTATION ONLY!\n"
                f"CONTINUE FILE-BY-FILE APPROACH! Focus on ONE file until 100% complete. "
                f"MANDATORY ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nREPORT your progress: which specific functions did you document? Update num_files_documented when file complete. "
                f"REPORT counters: current num_files_documented out of total_files_to_document. "
                f"If you found bugs/issues, LIST THEM but DO NOT FIX THEM - ask user what to do after documentation. "
                f"Do NOT move to a new file until the current one is completely documented. "
                f"When ready for step {step_number + 1}, report completed work with updated counters."
            )
        else:
            next_steps = (
                f"ABSOLUTE RULE: DO NOT ALTER ANY CODE LOGIC! DOCUMENTATION ONLY!\n"
                f"CRITICAL: Check if MORE FILES need documentation before finishing! "
                f"REQUIRED ACTIONS before calling {self.get_name()} step {step_number + 1}:\n"
                + "\n".join(f"{i+1}. {action}" for i, action in enumerate(required_actions))
                + f"\n\nREPORT which functions you documented and update num_files_documented when file complete. "
                f"CHECK: If num_files_documented < total_files_to_document, RESTART {self.get_name()} with next step! "
                f"CRITICAL: Only set next_step_required=false when num_files_documented equals total_files_to_document! "
                f"REPORT counters: current num_files_documented out of total_files_to_document. "
                f"If you accumulated bugs/issues during documentation, REPORT THEM and ask user for guidance. "
                f"NO recursive {self.get_name()} calls without actual documentation work!"
            )

        return {"next_steps": next_steps}

    # Hook method overrides for docgen-specific behavior

    async def handle_work_completion(self, response_data: dict, request, arguments: dict) -> dict:
        """
        Override work completion to enforce counter validation.

        The docgen tool MUST complete ALL files before finishing. If counters don't match,
        force continuation regardless of next_step_required setting.
        """
        # CRITICAL VALIDATION: Check if all files have been documented using proper inheritance hooks
        num_files_documented = self.get_request_num_files_documented(request)
        total_files_to_document = self.get_request_total_files_to_document(request)

        if num_files_documented < total_files_to_document:
            # Counters don't match - force continuation!
            logger.warning(
                f"Docgen stopping early: {num_files_documented} < {total_files_to_document}. "
                f"Forcing continuation to document remaining files."
            )

            # Override to continuation mode
            response_data["status"] = "documentation_analysis_required"
            response_data[f"pause_for_{self.get_name()}"] = True
            response_data["next_steps"] = (
                f"CRITICAL ERROR: You attempted to finish documentation with only {num_files_documented} "
                f"out of {total_files_to_document} files documented! You MUST continue documenting "
                f"the remaining {total_files_to_document - num_files_documented} files. "
                f"Call {self.get_name()} again with step {request.step_number + 1} and continue documentation "
                f"of the next undocumented file. DO NOT set next_step_required=false until ALL files are documented!"
            )
            return response_data

        # If counters match, proceed with normal completion
        return await super().handle_work_completion(response_data, request, arguments)

    def prepare_step_data(self, request) -> dict:
        """
        Prepare docgen-specific step data for processing.

        Calculates total_steps dynamically based on number of files to document:
        - Step 1: Discovery phase
        - Steps 2+: One step per file to document
        """
        # Calculate dynamic total_steps based on files to document
        total_files_to_document = self.get_request_total_files_to_document(request)
        if total_files_to_document > 0:
            # Discovery step (1) + one step per file
            calculated_total_steps = 1 + total_files_to_document
        else:
            # Fallback to request total_steps if no file count available
            calculated_total_steps = request.total_steps

        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "total_steps": calculated_total_steps,  # Use calculated value
            "findings": request.findings,
            "relevant_files": request.relevant_files,
            "relevant_context": request.relevant_context,
            "num_files_documented": request.num_files_documented,
            "total_files_to_document": request.total_files_to_document,
            "issues_found": [],  # Docgen uses this for documentation gaps
            "confidence": "medium",  # Default confidence for docgen
            "hypothesis": "systematic_documentation_needed",  # Default hypothesis
            "images": [],  # Docgen doesn't typically use images
            # CRITICAL: Include documentation configuration parameters so the model can see them
            "document_complexity": request.document_complexity,
            "document_flow": request.document_flow,
            "update_existing": request.update_existing,
            "comments_on_complex_logic": request.comments_on_complex_logic,
        }
        return step_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Docgen tool skips expert analysis when Claude has "certain" confidence.
        """
        return request.confidence == "certain" and not request.next_step_required

    # Override inheritance hooks for docgen-specific behavior

    def get_completion_status(self) -> str:
        """Docgen tools use docgen-specific status."""
        return "documentation_analysis_complete"

    def get_completion_data_key(self) -> str:
        """Docgen uses 'complete_documentation_analysis' key."""
        return "complete_documentation_analysis"

    def get_final_analysis_from_request(self, request):
        """Docgen tools use 'hypothesis' field for documentation strategy."""
        return request.hypothesis

    def get_confidence_level(self, request) -> str:
        """Docgen tools use 'certain' for high confidence."""
        return request.confidence or "high"

    def get_completion_message(self) -> str:
        """Docgen-specific completion message."""
        return (
            "Documentation analysis complete with high confidence. You have identified the comprehensive "
            "documentation needs and strategy. MANDATORY: Present the user with the documentation plan "
            "and IMMEDIATELY proceed with implementing the documentation without requiring further "
            "consultation. Focus on the precise documentation improvements needed."
        )

    def get_skip_reason(self) -> str:
        """Docgen-specific skip reason."""
        return "Claude completed comprehensive documentation analysis"

    def get_request_relevant_context(self, request) -> list:
        """Get relevant_context for docgen tool."""
        try:
            return request.relevant_context or []
        except AttributeError:
            return []

    def get_request_num_files_documented(self, request) -> int:
        """Get num_files_documented from request. Override for custom handling."""
        try:
            return request.num_files_documented or 0
        except AttributeError:
            return 0

    def get_request_total_files_to_document(self, request) -> int:
        """Get total_files_to_document from request. Override for custom handling."""
        try:
            return request.total_files_to_document or 0
        except AttributeError:
            return 0

    def get_skip_expert_analysis_status(self) -> str:
        """Docgen-specific expert analysis skip status."""
        return "skipped_due_to_complete_analysis"

    def prepare_work_summary(self) -> str:
        """Docgen-specific work summary."""
        try:
            return f"Completed {len(self.work_history)} documentation analysis steps"
        except AttributeError:
            return "Completed documentation analysis"

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Docgen-specific completion message.
        """
        return (
            "DOCUMENTATION ANALYSIS IS COMPLETE FOR ALL FILES (num_files_documented equals total_files_to_document). "
            "MANDATORY FINAL VERIFICATION: Before presenting your summary, you MUST perform a final verification scan. "
            "Read through EVERY file you documented and check EVERY function, method, class, and property to confirm "
            "it has proper documentation including complexity analysis and call flow information. If ANY items lack "
            "documentation, document them immediately before finishing. "
            "THEN present a clear summary showing: 1) Final counters: num_files_documented out of total_files_to_document, "
            "2) Complete accountability list of ALL files you documented with verification status, "
            "3) Detailed list of EVERY function/method you documented in each file (proving complete coverage), "
            "4) Any dependency relationships you discovered between files, 5) Recommended documentation improvements with concrete examples including "
            "complexity analysis and call flow information. 6) **CRITICAL**: List any bugs or logic issues you found "
            "during documentation but did NOT fix - present these to the user and ask what they'd like to do about them. "
            "Make it easy for a developer to see the complete documentation status across the entire codebase with full accountability."
        )

    def get_step_guidance_message(self, request) -> str:
        """
        Docgen-specific step guidance with detailed analysis instructions.
        """
        step_guidance = self.get_step_guidance(request.step_number, request.confidence, request)
        return step_guidance["next_steps"]

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Customize response to match docgen tool format.
        """
        # Store initial request on first step
        if request.step_number == 1:
            self.initial_request = request.step

        # Convert generic status names to docgen-specific ones
        tool_name = self.get_name()
        status_mapping = {
            f"{tool_name}_in_progress": "documentation_analysis_in_progress",
            f"pause_for_{tool_name}": "pause_for_documentation_analysis",
            f"{tool_name}_required": "documentation_analysis_required",
            f"{tool_name}_complete": "documentation_analysis_complete",
        }

        if response_data["status"] in status_mapping:
            response_data["status"] = status_mapping[response_data["status"]]

        # Rename status field to match docgen tool
        if f"{tool_name}_status" in response_data:
            response_data["documentation_analysis_status"] = response_data.pop(f"{tool_name}_status")
            # Add docgen-specific status fields
            response_data["documentation_analysis_status"]["documentation_strategies"] = len(
                self.consolidated_findings.hypotheses
            )

        # Rename complete documentation analysis data
        if f"complete_{tool_name}" in response_data:
            response_data["complete_documentation_analysis"] = response_data.pop(f"complete_{tool_name}")

        # Map the completion flag to match docgen tool
        if f"{tool_name}_complete" in response_data:
            response_data["documentation_analysis_complete"] = response_data.pop(f"{tool_name}_complete")

        # Map the required flag to match docgen tool
        if f"{tool_name}_required" in response_data:
            response_data["documentation_analysis_required"] = response_data.pop(f"{tool_name}_required")

        return response_data

    # Required abstract methods from BaseTool
    def get_request_model(self):
        """Return the docgen-specific request model."""
        return DocgenRequest

    async def prepare_prompt(self, request) -> str:
        """Not used - workflow tools use execute_workflow()."""
        return ""  # Workflow tools use execute_workflow() directly
