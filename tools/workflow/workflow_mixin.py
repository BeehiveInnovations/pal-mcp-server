"""
Workflow Mixin for Zen MCP Tools

This module provides a sophisticated workflow-based pattern that enables tools to
perform multi-step work with structured findings and expert analysis.

Key Components:
- BaseWorkflowMixin: Abstract base class providing comprehensive workflow functionality

The workflow pattern enables tools like debug, precommit, and codereview to perform
systematic multi-step work with pause/resume capabilities, context-aware file embedding,
and seamless integration with external AI models for expert analysis.

Features:
- Multi-step workflow orchestration with pause/resume
- Context-aware file embedding optimization
- Expert analysis integration with token budgeting
- Conversation memory and threading support
- Proper inheritance-based architecture (no hasattr/getattr)
- Comprehensive type annotations for IDE support
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

from mcp.types import TextContent

from config import MCP_PROMPT_SIZE_LIMIT
from utils.conversation_memory import add_turn, create_thread

from ..shared.base_models import ConsolidatedFindings
from ..shared.exceptions import ToolExecutionError

logger = logging.getLogger(__name__)


class BaseWorkflowMixin(ABC):
    """
    Abstract base class providing guided workflow functionality for tools.

    This class implements a sophisticated workflow pattern where the CLI performs
    systematic local work before calling external models for expert analysis.
    Tools can inherit from this class to gain comprehensive workflow capabilities.

    Architecture:
    - Uses proper inheritance patterns instead of hasattr/getattr
    - Provides hook methods with default implementations
    - Requires abstract methods to be implemented by subclasses
    - Fully type-annotated for excellent IDE support

    Context-Aware File Embedding:
    - Intermediate steps: Only reference file names (saves the CLI's context)
    - Final steps: Embed full file content for expert analysis
    - Integrates with existing token budgeting infrastructure

    Requirements:
    This class expects to be used with BaseTool and requires implementation of:
    - get_model_provider(model_name)
    - _resolve_model_context(arguments, request)
    - get_system_prompt()
    - get_default_temperature()
    - _prepare_file_content_for_prompt()
    """

    def __init__(self) -> None:
        super().__init__()
        self.work_history: list[dict[str, Any]] = []
        self.consolidated_findings: ConsolidatedFindings = ConsolidatedFindings()
        self.initial_request: Optional[str] = None

    # ================================================================================
    # Abstract Methods - Required Implementation by BaseTool or Subclasses
    # ================================================================================

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this tool. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def get_workflow_request_model(self) -> type:
        """Return the request model class for this workflow tool."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this tool. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def get_language_instruction(self) -> str:
        """Return the language instruction for localization. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def get_default_temperature(self) -> float:
        """Return the default temperature for this tool. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def get_model_provider(self, model_name: str) -> Any:
        """Get model provider for the given model. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def _resolve_model_context(self, arguments: dict[str, Any], request: Any) -> tuple[str, Any]:
        """Resolve model context from arguments. Usually provided by BaseTool."""
        pass

    @abstractmethod
    def _prepare_file_content_for_prompt(
        self,
        request_files: list[str],
        continuation_id: Optional[str],
        context_description: str = "New files",
        max_tokens: Optional[int] = None,
        reserve_tokens: int = 1_000,
        remaining_budget: Optional[int] = None,
        arguments: Optional[dict[str, Any]] = None,
        model_context: Optional[Any] = None,
    ) -> tuple[str, list[str]]:
        """Prepare file content for prompts. Usually provided by BaseTool."""
        pass

    # ================================================================================
    # Abstract Methods - Tool-Specific Implementation Required
    # ================================================================================

    @abstractmethod
    def get_work_steps(self, request: Any) -> list[str]:
        """Define tool-specific work steps and criteria"""
        pass

    @abstractmethod
    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int, request=None
    ) -> list[str]:
        """Define required actions for each work phase.

        Args:
            step_number: Current step (1-based)
            confidence: Current confidence level (exploring, low, medium, high, certain)
            findings: Current findings text
            total_steps: Total estimated steps for this work
            request: Optional request object for continuation-aware decisions

        Returns:
            List of specific actions the CLI should take before calling tool again
        """
        pass

    # ================================================================================
    # Hook Methods - Default Implementations with Override Capability
    # ================================================================================

    def should_call_expert_analysis(self, consolidated_findings: ConsolidatedFindings, request=None) -> bool:
        """
        Decide when to call external model based on tool-specific criteria.

        Default implementation for tools that don't use expert analysis.
        Override this for tools that do use expert analysis.

        Args:
            consolidated_findings: Findings from workflow steps
            request: Current request object (optional for backwards compatibility)
        """
        if not self.requires_expert_analysis():
            return False

        # Check if user requested to skip assistant model
        if request and not self.get_request_use_assistant_model(request):
            return False

        # Default logic for tools that support expert analysis
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_expert_analysis_context(self, consolidated_findings: ConsolidatedFindings) -> str:
        """
        Prepare context for external model call.

        Default implementation for tools that don't use expert analysis.
        Override this for tools that do use expert analysis.
        """
        if not self.requires_expert_analysis():
            return ""

        # Default context preparation
        context_parts = [
            f"=== {self.get_name().upper()} WORK SUMMARY ===",
            f"Total steps: {len(consolidated_findings.findings)}",
            f"Files examined: {len(consolidated_findings.files_checked)}",
            f"Relevant files: {len(consolidated_findings.relevant_files)}",
            "",
            "=== WORK PROGRESSION ===",
        ]

        for finding in consolidated_findings.findings:
            context_parts.append(finding)

        return "\n".join(context_parts)

    def requires_expert_analysis(self) -> bool:
        """
        Override this to completely disable expert analysis for the tool.

        Returns True if the tool supports expert analysis (default).
        Returns False if the tool is self-contained (like planner).
        """
        return True

    def should_include_files_in_expert_prompt(self) -> bool:
        """
        Whether to include file content in the expert analysis prompt.
        Override this to return True if your tool needs files in the prompt.
        """
        return False

    def should_embed_system_prompt(self) -> bool:
        """
        Whether to embed the system prompt in the main prompt.
        Override this to return True if your tool needs the system prompt embedded.
        """
        return False

    def get_expert_thinking_mode(self) -> str:
        """
        Get the thinking mode for expert analysis.
        Override this to customize the thinking mode.
        """
        return "high"

    def get_request_temperature(self, request) -> float:
        """Get temperature from request. Override for custom temperature handling."""
        try:
            return request.temperature if request.temperature is not None else self.get_default_temperature()
        except AttributeError:
            return self.get_default_temperature()

    def get_validated_temperature(self, request, model_context: Any) -> tuple[float, list[str]]:
        """
        Get temperature from request and validate it against model constraints.

        This is a convenience method that combines temperature extraction and validation
        for workflow tools. It ensures temperature is within valid range for the model.

        Args:
            request: The request object containing temperature
            model_context: Model context object containing model info

        Returns:
            Tuple of (validated_temperature, warning_messages)
        """
        temperature = self.get_request_temperature(request)
        return self.validate_and_correct_temperature(temperature, model_context)

    def get_request_thinking_mode(self, request) -> str:
        """Get thinking mode from request. Override for custom thinking mode handling."""
        try:
            return request.thinking_mode if request.thinking_mode is not None else self.get_expert_thinking_mode()
        except AttributeError:
            return self.get_expert_thinking_mode()

    def get_expert_analysis_instruction(self) -> str:
        """
        Get the instruction to append after the expert context.
        Override this to provide tool-specific instructions.
        """
        return "Please provide expert analysis based on the investigation findings."

    def get_request_use_assistant_model(self, request) -> bool:
        """
        Get use_assistant_model from request. Override for custom assistant model handling.

        Args:
            request: Current request object

        Returns:
            True if assistant model should be used, False otherwise
        """
        try:
            return request.use_assistant_model if request.use_assistant_model is not None else True
        except AttributeError:
            return True

    def get_step_guidance_message(self, request) -> str:
        """
        Get step guidance message. Override for tool-specific guidance.
        Default implementation uses required actions.
        """
        required_actions = self.get_required_actions(
            request.step_number, self.get_request_confidence(request), request.findings, request.total_steps, request
        )

        next_step_number = request.step_number + 1
        return (
            f"MANDATORY: DO NOT call the {self.get_name()} tool again immediately. "
            f"You MUST first work using appropriate tools. "
            f"REQUIRED ACTIONS before calling {self.get_name()} step {next_step_number}:\n"
            + "\n".join(f"{i + 1}. {action}" for i, action in enumerate(required_actions))
            + f"\n\nOnly call {self.get_name()} again with step_number: {next_step_number} "
            f"AFTER completing this work."
        )

    def _prepare_files_for_expert_analysis(self) -> str:
        """
        Prepare file content for expert analysis.

        EXPERT ANALYSIS REQUIRES ACTUAL FILE CONTENT:
        Expert analysis needs actual file content of all unique files marked as relevant
        throughout the workflow, regardless of conversation history optimization.

        SIMPLIFIED LOGIC:
        Expert analysis gets all unique files from relevant_files across the entire workflow.
        This includes:
        - Current step's relevant_files (consolidated_findings.relevant_files)
        - Plus any additional relevant_files from conversation history (if continued workflow)

        This ensures expert analysis has complete context without including irrelevant files.
        """
        all_relevant_files = set()

        # 1. Get files from current consolidated relevant_files
        all_relevant_files.update(self.consolidated_findings.relevant_files)

        # 2. Get additional relevant_files from conversation history (if continued workflow)
        try:
            current_arguments = self.get_current_arguments()
            if current_arguments:
                continuation_id = current_arguments.get("continuation_id")

                if continuation_id:
                    from utils.conversation_memory import get_conversation_file_list, get_thread

                    thread_context = get_thread(continuation_id)
                    if thread_context:
                        # Get all files from conversation (these were relevant_files in previous steps)
                        conversation_files = get_conversation_file_list(thread_context)
                        all_relevant_files.update(conversation_files)
                        logger.debug(
                            f"[WORKFLOW_FILES] {self.get_name()}: Added {len(conversation_files)} files from conversation history"
                        )
        except Exception as e:
            logger.warning(f"[WORKFLOW_FILES] {self.get_name()}: Could not get conversation files: {e}")

        # Convert to list and remove any empty/None values
        files_for_expert = [f for f in all_relevant_files if f and f.strip()]

        if not files_for_expert:
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: No relevant files found for expert analysis")
            return ""

        # Expert analysis needs actual file content, bypassing conversation optimization
        try:
            file_content, processed_files = self._force_embed_files_for_expert_analysis(files_for_expert)

            logger.info(
                f"[WORKFLOW_FILES] {self.get_name()}: Prepared {len(processed_files)} unique relevant files for expert analysis "
                f"(from {len(self.consolidated_findings.relevant_files)} current relevant files)"
            )

            return file_content

        except Exception as e:
            logger.error(f"[WORKFLOW_FILES] {self.get_name()}: Failed to prepare files for expert analysis: {e}")
            return ""

    def _force_embed_files_for_expert_analysis(self, files: list[str]) -> tuple[str, list[str]]:
        """
        Force embed files for expert analysis, bypassing conversation history filtering.

        Expert analysis has different requirements than normal workflow steps:
        - Normal steps: Optimize tokens by skipping files in conversation history
        - Expert analysis: Needs actual file content regardless of conversation history

        Args:
            files: List of file paths to embed

        Returns:
            tuple[str, list[str]]: (file_content, processed_files)
        """
        # Use read_files directly with token budgeting, bypassing filter_new_files
        from utils.file_utils import expand_paths, read_files

        # Get token budget for files
        current_model_context = self.get_current_model_context()
        if current_model_context:
            try:
                token_allocation = current_model_context.calculate_token_allocation()
                max_tokens = token_allocation.file_tokens
                logger.debug(
                    f"[WORKFLOW_FILES] {self.get_name()}: Using {max_tokens:,} tokens for expert analysis files"
                )
            except Exception as e:
                logger.warning(f"[WORKFLOW_FILES] {self.get_name()}: Failed to get token allocation: {e}")
                max_tokens = 100_000  # Fallback
        else:
            max_tokens = 100_000  # Fallback

        # Read files directly without conversation history filtering
        logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Force embedding {len(files)} files for expert analysis")
        file_content = read_files(
            files,
            max_tokens=max_tokens,
            reserve_tokens=1000,
            include_line_numbers=self.wants_line_numbers_by_default(),
        )

        # Expand paths to get individual files for tracking
        processed_files = expand_paths(files)

        logger.debug(
            f"[WORKFLOW_FILES] {self.get_name()}: Expert analysis embedding: {len(processed_files)} files, "
            f"{len(file_content):,} characters"
        )

        return file_content, processed_files

    def wants_line_numbers_by_default(self) -> bool:
        """
        Whether this tool wants line numbers in file content by default.
        Override this to customize line number behavior.
        """
        return True  # Most workflow tools benefit from line numbers for analysis

    def _add_files_to_expert_context(self, expert_context: str, file_content: str) -> str:
        """
        Add file content to the expert context.
        Override this to customize how files are added to the context.
        """
        return f"{expert_context}\n\n=== ESSENTIAL FILES ===\n{file_content}\n=== END ESSENTIAL FILES ==="

    # ================================================================================
    # Context-Aware File Embedding - Core Implementation
    # ================================================================================

    def _handle_workflow_file_context(self, request: Any, arguments: dict[str, Any]) -> None:
        """
        Handle file context appropriately based on workflow phase.

        CONTEXT-AWARE FILE EMBEDDING STRATEGY:
        1. Intermediate steps + continuation: Only reference file names (save the CLI's context)
        2. Final step: Embed full file content for expert analysis
        3. Expert analysis: Always embed relevant files with token budgeting

        This prevents wasting the CLI's limited context on intermediate steps while ensuring
        the final expert analysis has complete file context.
        """
        continuation_id = self.get_request_continuation_id(request)
        is_final_step = not self.get_request_next_step_required(request)
        step_number = self.get_request_step_number(request)

        # Extract model context for token budgeting
        model_context = arguments.get("_model_context")
        self._model_context = model_context

        # Clear any previous file context to ensure clean state
        self._embedded_file_content = ""
        self._file_reference_note = ""
        self._actually_processed_files = []

        # Determine if we should embed files or just reference them
        should_embed_files = self._should_embed_files_in_workflow_step(step_number, continuation_id, is_final_step)

        if should_embed_files:
            # Final step or expert analysis - embed full file content
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Embedding files for final step/expert analysis")
            self._embed_workflow_files(request, arguments)
        else:
            # Intermediate step with continuation - only reference file names
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Only referencing file names for intermediate step")
            self._reference_workflow_files(request)

    def _should_embed_files_in_workflow_step(
        self, step_number: int, continuation_id: Optional[str], is_final_step: bool
    ) -> bool:
        """
        Determine whether to embed file content based on workflow context.

        CORRECT LOGIC:
        - NEVER embed files when the CLI is getting the next step (next_step_required=True)
        - ONLY embed files when sending to external model (next_step_required=False)

        Args:
            step_number: Current step number
            continuation_id: Thread continuation ID (None for new conversations)
            is_final_step: Whether this is the final step (next_step_required == False)

        Returns:
            bool: True if files should be embedded, False if only referenced
        """
        # RULE 1: Final steps (no more steps needed) - embed files for expert analysis
        if is_final_step:
            logger.debug("[WORKFLOW_FILES] Final step - will embed files for expert analysis")
            return True

        # RULE 2: Any intermediate step (more steps needed) - NEVER embed files
        # This includes:
        # - New conversations with next_step_required=True
        # - Steps with continuation_id and next_step_required=True
        logger.debug("[WORKFLOW_FILES] Intermediate step (more work needed) - will only reference files")
        return False

    def _embed_workflow_files(self, request: Any, arguments: dict[str, Any]) -> None:
        """
        Embed full file content for final steps and expert analysis.
        Uses proper token budgeting like existing debug.py.
        """
        # Use relevant_files as the standard field for workflow tools
        request_files = self.get_request_relevant_files(request)
        if not request_files:
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: No relevant_files to embed")
            return

        try:
            # Model context should be available from early validation, but might be deferred for tests
            current_model_context = self.get_current_model_context()
            if not current_model_context:
                # Try to resolve model context now (deferred from early validation)
                try:
                    model_name, model_context = self._resolve_model_context(arguments, request)
                    self._model_context = model_context
                    self._current_model_name = model_name
                except Exception as e:
                    logger.error(f"[WORKFLOW_FILES] {self.get_name()}: Failed to resolve model context: {e}")
                    # Create fallback model context (preserves existing test behavior)
                    from utils.model_context import ModelContext

                    model_name = self.get_request_model_name(request)
                    self._model_context = ModelContext(model_name)
                    self._current_model_name = model_name

            # Use the same file preparation logic as BaseTool with token budgeting
            continuation_id = self.get_request_continuation_id(request)
            remaining_tokens = arguments.get("_remaining_tokens")

            file_content, processed_files = self._prepare_file_content_for_prompt(
                request_files,
                continuation_id,
                "Workflow files for analysis",
                remaining_budget=remaining_tokens,
                arguments=arguments,
                model_context=self._model_context,
            )

            # Store for use in expert analysis
            self._embedded_file_content = file_content
            self._actually_processed_files = processed_files

            logger.info(
                f"[WORKFLOW_FILES] {self.get_name()}: Embedded {len(processed_files)} relevant_files for final analysis"
            )

        except Exception as e:
            logger.error(f"[WORKFLOW_FILES] {self.get_name()}: Failed to embed files: {e}")
            # Continue without file embedding rather than failing
            self._embedded_file_content = ""
            self._actually_processed_files = []

    def _reference_workflow_files(self, request: Any) -> None:
        """
        Reference file names without embedding content for intermediate steps.
        Saves the CLI's context while still providing file awareness.
        """
        # Workflow tools use relevant_files, not files
        request_files = self.get_request_relevant_files(request)
        logger.debug(
            f"[WORKFLOW_FILES] {self.get_name()}: _reference_workflow_files called with {len(request_files)} relevant_files"
        )

        if not request_files:
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: No files to reference, skipping")
            return

        # Store file references for conversation context
        self._referenced_files = request_files

        # Create a simple reference note
        file_names = [os.path.basename(f) for f in request_files]
        reference_note = f"Files referenced in this step: {', '.join(file_names)}\n"

        self._file_reference_note = reference_note
        logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Set _file_reference_note: {self._file_reference_note}")

        logger.info(
            f"[WORKFLOW_FILES] {self.get_name()}: Referenced {len(request_files)} files without embedding content"
        )

    # ================================================================================
    # Main Workflow Orchestration
    # ================================================================================

    async def execute_workflow(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Main workflow orchestration following debug tool pattern.

        Comprehensive workflow implementation that handles all common patterns:
        1. Request validation and step management
        2. Continuation and backtracking support
        3. Step data processing and consolidation
        4. Tool-specific field mapping and customization
        5. Completion logic with optional expert analysis
        6. Generic "certain confidence" handling
        7. Step guidance and required actions
        8. Conversation memory integration
        """
        from mcp.types import TextContent

        try:
            # Store arguments for access by helper methods
            self._current_arguments = arguments

            # Validate request using tool-specific model
            request = self.get_workflow_request_model()(**arguments)

            # Validate step field size (basic validation for workflow instructions)
            # If step is too large, user should use shorter instructions and put details in files
            step_content = request.step
            if step_content and len(step_content) > MCP_PROMPT_SIZE_LIMIT:
                from tools.models import ToolOutput

                error_output = ToolOutput(
                    status="resend_prompt",
                    content="Step instructions are too long. Please use shorter instructions and provide detailed context via file paths instead.",
                    content_type="text",
                    metadata={"prompt_size": len(step_content), "limit": MCP_PROMPT_SIZE_LIMIT},
                )
                raise ValueError(f"MCP_SIZE_CHECK:{error_output.model_dump_json()}")

            # Validate file paths for security (same as base tool)
            # Use try/except instead of hasattr as per coding standards
            try:
                path_error = self.validate_file_paths(request)
                if path_error:
                    from tools.models import ToolOutput

                    error_output = ToolOutput(
                        status="error",
                        content=path_error,
                        content_type="text",
                    )
                    logger.error("Path validation failed for %s: %s", self.get_name(), path_error)
                    raise ToolExecutionError(error_output.model_dump_json())
            except AttributeError:
                # validate_file_paths method not available - skip validation
                pass

            # Try to validate model availability early for production scenarios
            # For tests, defer model validation to later to allow mocks to work
            try:
                model_name, model_context = self._resolve_model_context(arguments, request)
                # Store for later use
                self._current_model_name = model_name
                self._model_context = model_context
            except ValueError as e:
                # Model resolution failed - in production this would be an error,
                # but for tests we defer to allow mocks to handle model resolution
                logger.debug(f"Early model validation failed, deferring to later: {e}")
                self._current_model_name = None
                self._model_context = None

            # Handle continuation
            continuation_id = request.continuation_id

            # Restore workflow state on continuation
            if continuation_id:
                from utils.conversation_memory import get_thread

                thread = get_thread(continuation_id)
                if thread and thread.turns:
                    # Find the most recent assistant turn from this tool with workflow state
                    for turn in reversed(thread.turns):
                        if turn.role == "assistant" and turn.tool_name == self.get_name() and turn.model_metadata:
                            state = turn.model_metadata
                            if isinstance(state, dict) and "work_history" in state:
                                self.work_history = state.get("work_history", [])
                                self.initial_request = state.get("initial_request")
                                # Rebuild consolidated findings from restored history
                                self._reprocess_consolidated_findings()
                                logger.debug(
                                    f"[{self.get_name()}] Restored workflow state with {len(self.work_history)} history items"
                                )
                                break  # State restored, exit loop

            # Adjust total steps if needed
            if request.step_number > request.total_steps:
                request.total_steps = request.step_number

            # Create thread for first step
            if not continuation_id and request.step_number == 1:
                clean_args = {k: v for k, v in arguments.items() if k not in ["_model_context", "_resolved_model_name"]}
                continuation_id = create_thread(self.get_name(), clean_args)
                self.initial_request = request.step
                # Allow tools to store initial description for expert analysis
                self.store_initial_issue(request.step)

            # Process work step - allow tools to customize field mapping
            step_data = self.prepare_step_data(request)

            # Store in history
            self.work_history.append(step_data)

            # Update consolidated findings
            self._update_consolidated_findings(step_data)

            # Handle file context appropriately based on workflow phase
            self._handle_workflow_file_context(request, arguments)

            # Build response with tool-specific customization
            response_data = self.build_base_response(request, continuation_id)

            # If work is complete, handle completion logic
            if not request.next_step_required:
                response_data = await self.handle_work_completion(response_data, request, arguments)
            else:
                # Force CLI to work before calling tool again
                response_data = self.handle_work_continuation(response_data, request)

            # Allow tools to customize the final response
            response_data = self.customize_workflow_response(response_data, request)

            # Add metadata (provider_used and model_used) to workflow response
            self._add_workflow_metadata(response_data, arguments)

            # Store in conversation memory
            if continuation_id:
                self.store_conversation_turn(continuation_id, response_data, request)

            return [TextContent(type="text", text=json.dumps(response_data, indent=2, ensure_ascii=False))]

        except ToolExecutionError:
            raise
        except Exception as e:
            if str(e).startswith("MCP_SIZE_CHECK:"):
                payload = str(e)[len("MCP_SIZE_CHECK:") :]
                raise ToolExecutionError(payload)

            logger.error(f"Error in {self.get_name()} work: {e}", exc_info=True)
            error_data = {
                "status": f"{self.get_name()}_failed",
                "error": str(e),
                "step_number": arguments.get("step_number", 0),
            }

            # Add metadata to error responses too
            self._add_workflow_metadata(error_data, arguments)

            raise ToolExecutionError(json.dumps(error_data, indent=2, ensure_ascii=False)) from e

    # Hook methods for tool customization

    def prepare_step_data(self, request) -> dict:
        """
        Prepare step data from request. Tools can override to customize field mapping.
        """
        step_data = {
            "step": request.step,
            "step_number": request.step_number,
            "findings": request.findings,
            "files_checked": self.get_request_files_checked(request),
            "relevant_files": self.get_request_relevant_files(request),
            "relevant_context": self.get_request_relevant_context(request),
            "issues_found": self.get_request_issues_found(request),
            "confidence": self.get_request_confidence(request),
            "hypothesis": self.get_request_hypothesis(request),
            "images": self.get_request_images(request),
        }
        return step_data

    def build_base_response(self, request, continuation_id: str = None) -> dict:
        """
        Build the base response structure. Tools can override for custom response fields.
        """
        response_data = {
            "status": f"{self.get_name()}_in_progress",
            "step_number": request.step_number,
            "total_steps": request.total_steps,
            "next_step_required": request.next_step_required,
            f"{self.get_name()}_status": {
                "files_checked": len(self.consolidated_findings.files_checked),
                "relevant_files": len(self.consolidated_findings.relevant_files),
                "relevant_context": len(self.consolidated_findings.relevant_context),
                "issues_found": len(self.consolidated_findings.issues_found),
                "images_collected": len(self.consolidated_findings.images),
                "current_confidence": self.get_request_confidence(request),
            },
        }

        if continuation_id:
            response_data["continuation_id"] = continuation_id

        # Add file context information based on workflow phase
        embedded_content = self.get_embedded_file_content()
        reference_note = self.get_file_reference_note()
        processed_files = self.get_actually_processed_files()

        logger.debug(
            f"[WORKFLOW_FILES] {self.get_name()}: Building response - has embedded_content: {bool(embedded_content)}, has reference_note: {bool(reference_note)}"
        )

        # Prioritize embedded content over references for final steps
        if embedded_content:
            # Final step - include embedded file information
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Adding fully_embedded file context")
            response_data["file_context"] = {
                "type": "fully_embedded",
                "files_embedded": len(processed_files),
                "context_optimization": "Full file content embedded for expert analysis",
            }
        elif reference_note:
            # Intermediate step - include file reference note
            logger.debug(f"[WORKFLOW_FILES] {self.get_name()}: Adding reference_only file context")
            response_data["file_context"] = {
                "type": "reference_only",
                "note": reference_note,
                "context_optimization": "Files referenced but not embedded to preserve the context window",
            }

        return response_data

    def should_skip_expert_analysis(self, request, consolidated_findings) -> bool:
        """
        Determine if expert analysis should be skipped due to high certainty.

        Default: False (always call expert analysis)
        Override in tools like debug to check for "certain" confidence.
        """
        return False

    def handle_completion_without_expert_analysis(self, request, consolidated_findings) -> dict:
        """
        Handle completion when skipping expert analysis.

        Tools can override this for custom high-confidence completion handling.
        Default implementation provides generic response.
        """
        work_summary = self.prepare_work_summary()
        continuation_id = self.get_request_continuation_id(request)

        response_data = {
            "status": self.get_completion_status(),
            f"complete_{self.get_name()}": {
                "initial_request": self.get_initial_request(request.step),
                "steps_taken": len(consolidated_findings.findings),
                "files_examined": list(consolidated_findings.files_checked),
                "relevant_files": list(consolidated_findings.relevant_files),
                "relevant_context": list(consolidated_findings.relevant_context),
                "work_summary": work_summary,
                "final_analysis": self.get_final_analysis_from_request(request),
                "confidence_level": self.get_confidence_level(request),
            },
            "next_steps": self.get_completion_message(),
            "skip_expert_analysis": True,
            "expert_analysis": {
                "status": self.get_skip_expert_analysis_status(),
                "reason": self.get_skip_reason(),
            },
        }

        if continuation_id:
            response_data["continuation_id"] = continuation_id

        return response_data

    # ================================================================================
    # Inheritance Hook Methods - Replace hasattr/getattr Anti-patterns
    # ================================================================================

    def get_request_confidence(self, request: Any) -> str:
        """Get confidence from request. Override for custom confidence handling."""
        try:
            return request.confidence or "low"
        except AttributeError:
            return "low"

    def get_request_relevant_context(self, request: Any) -> list[str]:
        """Get relevant context from request. Override for custom field mapping."""
        try:
            return request.relevant_context or []
        except AttributeError:
            return []

    def get_request_issues_found(self, request: Any) -> list[str]:
        """Get issues found from request. Override for custom field mapping."""
        try:
            return request.issues_found or []
        except AttributeError:
            return []

    def get_request_hypothesis(self, request: Any) -> Optional[str]:
        """Get hypothesis from request. Override for custom field mapping."""
        try:
            return request.hypothesis
        except AttributeError:
            return None

    def get_request_images(self, request: Any) -> list[str]:
        """Get images from request. Override for custom field mapping."""
        try:
            return request.images or []
        except AttributeError:
            return []

    # File Context Access Methods

    def get_embedded_file_content(self) -> str:
        """Get embedded file content. Returns empty string if not available."""
        try:
            return self._embedded_file_content or ""
        except AttributeError:
            return ""

    def get_file_reference_note(self) -> str:
        """Get file reference note. Returns empty string if not available."""
        try:
            return self._file_reference_note or ""
        except AttributeError:
            return ""

    def get_actually_processed_files(self) -> list[str]:
        """Get list of actually processed files. Returns empty list if not available."""
        try:
            return self._actually_processed_files or []
        except AttributeError:
            return []

    def get_current_model_context(self):
        """Get current model context. Returns None if not available."""
        try:
            return self._model_context
        except AttributeError:
            return None

    def get_request_model_name(self, request: Any) -> str:
        """Get model name from request. Override for custom model handling."""
        try:
            return request.model or "flash"
        except AttributeError:
            return "flash"

    def get_request_continuation_id(self, request: Any) -> Optional[str]:
        """Get continuation ID from request. Override for custom continuation handling."""
        try:
            return request.continuation_id
        except AttributeError:
            return None

    def get_request_next_step_required(self, request: Any) -> bool:
        """Get next step required from request. Override for custom step handling."""
        try:
            return request.next_step_required
        except AttributeError:
            return True

    def get_request_step_number(self, request: Any) -> int:
        """Get step number from request. Override for custom step handling."""
        try:
            return request.step_number or 1
        except AttributeError:
            return 1

    def get_request_relevant_files(self, request: Any) -> list[str]:
        """Get relevant files from request. Override for custom file handling."""
        try:
            return request.relevant_files or []
        except AttributeError:
            return []

    def get_request_files_checked(self, request: Any) -> list[str]:
        """Get files checked from request. Override for custom file handling."""
        try:
            return request.files_checked or []
        except AttributeError:
            return []

    def get_current_arguments(self) -> dict[str, Any]:
        """Get current arguments. Returns empty dict if not available."""
        try:
            return self._current_arguments or {}
        except AttributeError:
            return {}

    def store_initial_issue(self, step_description: str):
        """Store initial issue description. Override for custom storage."""
        # Default implementation - tools can override to store differently
        self.initial_issue = step_description

    def get_initial_request(self, fallback_step: str) -> str:
        """Get initial request description. Override for custom retrieval."""
        try:
            return self.initial_request or fallback_step
        except AttributeError:
            return fallback_step

    # Default implementations for inheritance hooks

    def prepare_work_summary(self) -> str:
        """Prepare work summary. Override for custom implementation."""
        return f"Completed {len(self.consolidated_findings.findings)} work steps"

    def get_completion_status(self) -> str:
        """Get completion status. Override for tool-specific status."""
        return "high_confidence_completion"

    def get_final_analysis_from_request(self, request):
        """Extract final analysis from request. Override for tool-specific fields."""
        return self.get_request_hypothesis(request)

    def get_confidence_level(self, request) -> str:
        """Get confidence level. Override for tool-specific confidence handling."""
        return self.get_request_confidence(request) or "high"

    def get_completion_message(self) -> str:
        """Get completion message. Override for tool-specific messaging."""
        return (
            f"{self.get_name().capitalize()} complete with high confidence. Present results "
            "and proceed with implementation without requiring further consultation."
        )

    def get_skip_reason(self) -> str:
        """Get reason for skipping expert analysis. Override for tool-specific reasons."""
        return f"{self.get_name()} completed with sufficient confidence"

    def get_skip_expert_analysis_status(self) -> str:
        """Get status for skipped expert analysis. Override for tool-specific status."""
        return "skipped_by_tool_design"

    def get_completion_next_steps_message(self, expert_analysis_used: bool = False) -> str:
        """
        Get the message to show when work is complete.
        Tools can override for custom messaging.

        Args:
            expert_analysis_used: True if expert analysis was successfully executed
        """
        base_message = (
            f"{self.get_name().upper()} IS COMPLETE. You MUST now summarize and present ALL key findings, confirmed "
            "hypotheses, and exact recommended solutions. Clearly identify the most likely root cause and "
            "provide concrete, actionable implementation guidance. Highlight affected code paths and display "
            "reasoning that led to this conclusion—make it easy for a developer to understand exactly where "
            "the problem lies."
        )

        # Add expert analysis guidance only when expert analysis was actually used
        if expert_analysis_used:
            expert_guidance = self.get_expert_analysis_guidance()
            if expert_guidance:
                return f"{base_message}\n\n{expert_guidance}"

        return base_message

    def get_expert_analysis_guidance(self) -> str:
        """
        Get additional guidance for handling expert analysis results.

        Subclasses can override this to provide specific instructions about how
        to validate and use expert analysis findings. Returns empty string by default.

        When expert analysis is called, this guidance will be:
        1. Appended to the completion next steps message
        2. Added as "important_considerations" field in the response data

        Example implementation:
        ```python
        def get_expert_analysis_guidance(self) -> str:
            return (
                "IMPORTANT: Expert analysis provided above. You MUST validate "
                "the expert findings rather than accepting them blindly. "
                "Cross-reference with your own investigation and ensure "
                "recommendations align with the codebase context."
            )
        ```

        Returns:
            Additional guidance text or empty string if no guidance needed
        """
        return ""

    def customize_workflow_response(self, response_data: dict, request) -> dict:
        """
        Allow tools to customize the workflow response before returning.

        Tools can override this to add tool-specific fields, modify status names,
        customize field mapping, etc. Default implementation returns unchanged.
        """
        # Ensure file context information is preserved in all response paths
        if not response_data.get("file_context"):
            embedded_content = self.get_embedded_file_content()
            reference_note = self.get_file_reference_note()
            processed_files = self.get_actually_processed_files()

            # Prioritize embedded content over references for final steps
            if embedded_content:
                response_data["file_context"] = {
                    "type": "fully_embedded",
                    "files_embedded": len(processed_files),
                    "context_optimization": "Full file content embedded for expert analysis",
                }
            elif reference_note:
                response_data["file_context"] = {
                    "type": "reference_only",
                    "note": reference_note,
                    "context_optimization": "Files referenced but not embedded to preserve the context window",
                }

        return response_data

    def store_conversation_turn(self, continuation_id: str, response_data: dict, request):
        """
        Store the conversation turn. Tools can override for custom memory storage.
        """
        # CRITICAL: Extract clean content for conversation history (exclude internal workflow metadata)
        clean_content = self._extract_clean_workflow_content_for_history(response_data)

        # Serialize workflow state for persistence across stateless tool calls
        workflow_state = {"work_history": self.work_history, "initial_request": getattr(self, "initial_request", None)}

        add_turn(
            thread_id=continuation_id,
            role="assistant",
            content=clean_content,  # Use cleaned content instead of full response_data
            tool_name=self.get_name(),
            files=self.get_request_relevant_files(request),
            images=self.get_request_images(request),
            model_metadata=workflow_state,  # Persist the state
        )

    def _add_workflow_metadata(self, response_data: dict, arguments: dict[str, Any]) -> None:
        """
        Add metadata (provider_used and model_used) to workflow response.

        This ensures workflow tools have the same metadata as regular tools,
        making it consistent across all tool types for tracking which provider
        and model were used for the response.

        Args:
            response_data: The response data dictionary to modify
            arguments: The original arguments containing model context
        """
        try:
            # Get model information from arguments (set by server.py)
            resolved_model_name = arguments.get("_resolved_model_name")
            model_context = arguments.get("_model_context")

            if resolved_model_name and model_context:
                # Extract provider information from model context
                provider = model_context.provider
                provider_name = provider.get_provider_type().value if provider else "unknown"

                # Create metadata dictionary
                metadata = {
                    "tool_name": self.get_name(),
                    "model_used": resolved_model_name,
                    "provider_used": provider_name,
                }

                # Preserve existing metadata and add workflow metadata
                if "metadata" not in response_data:
                    response_data["metadata"] = {}
                response_data["metadata"].update(metadata)

                logger.debug(
                    f"[WORKFLOW_METADATA] {self.get_name()}: Added metadata - "
                    f"model: {resolved_model_name}, provider: {provider_name}"
                )
            else:
                # Fallback - try to get model info from request
                request = self.get_workflow_request_model()(**arguments)
                model_name = self.get_request_model_name(request)

                # Basic metadata without provider info
                metadata = {
                    "tool_name": self.get_name(),
                    "model_used": model_name,
                    "provider_used": "unknown",
                }

                # Preserve existing metadata and add workflow metadata
                if "metadata" not in response_data:
                    response_data["metadata"] = {}
                response_data["metadata"].update(metadata)

                logger.debug(
                    f"[WORKFLOW_METADATA] {self.get_name()}: Added fallback metadata - "
                    f"model: {model_name}, provider: unknown"
                )

        except Exception as e:
            # Don't fail the workflow if metadata addition fails
            logger.warning(f"[WORKFLOW_METADATA] {self.get_name()}: Failed to add metadata: {e}")
            # Still add basic metadata with tool name
            response_data["metadata"] = {"tool_name": self.get_name()}

    def _extract_clean_workflow_content_for_history(self, response_data: dict) -> str:
        """
        Extract clean content from workflow response suitable for conversation history.

        This method removes internal workflow metadata, continuation offers, and
        status information that should not appear when the conversation is
        reconstructed for expert models or other tools.

        Args:
            response_data: The full workflow response data

        Returns:
            str: Clean content suitable for conversation history storage
        """
        # Create a clean copy with only essential content for conversation history
        clean_data = {}

        # Include core content if present
        if "content" in response_data:
            clean_data["content"] = response_data["content"]

        # Include expert analysis if present (but clean it)
        if "expert_analysis" in response_data:
            expert_analysis = response_data["expert_analysis"]
            if isinstance(expert_analysis, dict):
                # Only include the actual analysis content, not metadata
                clean_expert = {}
                if "raw_analysis" in expert_analysis:
                    clean_expert["analysis"] = expert_analysis["raw_analysis"]
                elif "content" in expert_analysis:
                    clean_expert["analysis"] = expert_analysis["content"]
                if clean_expert:
                    clean_data["expert_analysis"] = clean_expert

        # Include findings/issues if present (core workflow output)
        if "complete_analysis" in response_data:
            complete_analysis = response_data["complete_analysis"]
            if isinstance(complete_analysis, dict):
                clean_complete = {}
                # Include essential analysis data without internal metadata
                for key in ["findings", "issues_found", "relevant_context", "insights"]:
                    if key in complete_analysis:
                        clean_complete[key] = complete_analysis[key]
                if clean_complete:
                    clean_data["analysis_summary"] = clean_complete

        # Include step information for context but remove internal workflow metadata
        if "step_number" in response_data:
            clean_data["step_info"] = {
                "step": response_data.get("step", ""),
                "step_number": response_data.get("step_number", 1),
                "total_steps": response_data.get("total_steps", 1),
            }

        # Exclude problematic fields that should never appear in conversation history:
        # - continuation_id (confuses LLMs with old IDs)
        # - status (internal workflow state)
        # - next_step_required (internal control flow)
        # - analysis_status (internal tracking)
        # - file_context (internal optimization info)
        # - required_actions (internal workflow instructions)

        return json.dumps(clean_data, indent=2, ensure_ascii=False)

    # Core workflow logic methods

    async def handle_work_completion(self, response_data: dict, request, arguments: dict) -> dict:
        """
        Handle work completion logic - expert analysis decision and response building.
        """
        response_data[f"{self.get_name()}_complete"] = True

        # Check if tool wants to skip expert analysis due to high certainty
        if self.should_skip_expert_analysis(request, self.consolidated_findings):
            # Handle completion without expert analysis
            completion_response = self.handle_completion_without_expert_analysis(request, self.consolidated_findings)
            response_data.update(completion_response)
        elif self.requires_expert_analysis() and self.should_call_expert_analysis(self.consolidated_findings, request):
            # Standard expert analysis path
            response_data["status"] = "calling_expert_analysis"

            # Call expert analysis
            expert_analysis = await self._call_expert_analysis(arguments, request)
            response_data["expert_analysis"] = expert_analysis

            # Handle special expert analysis statuses
            if isinstance(expert_analysis, dict) and expert_analysis.get("status") in [
                "files_required_to_continue",
                "investigation_paused",
                "refactoring_paused",
            ]:
                # Promote the special status to the main response
                special_status = expert_analysis["status"]
                response_data["status"] = special_status
                response_data["content"] = expert_analysis.get(
                    "raw_analysis", json.dumps(expert_analysis, ensure_ascii=False)
                )
                del response_data["expert_analysis"]

                # Update next steps for special status
                if special_status == "files_required_to_continue":
                    response_data["next_steps"] = "Provide the requested files and continue the analysis."
                else:
                    response_data["next_steps"] = expert_analysis.get(
                        "next_steps", "Continue based on expert analysis."
                    )
            elif isinstance(expert_analysis, dict) and expert_analysis.get("status") == "analysis_error":
                # Expert analysis failed - promote error status
                response_data["status"] = "error"
                response_data["content"] = expert_analysis.get("error", "Expert analysis failed")
                response_data["content_type"] = "text"
                del response_data["expert_analysis"]
            else:
                # Expert analysis was successfully executed - include expert guidance
                response_data["next_steps"] = self.get_completion_next_steps_message(expert_analysis_used=True)

                # Add expert analysis guidance as important considerations
                expert_guidance = self.get_expert_analysis_guidance()
                if expert_guidance:
                    response_data["important_considerations"] = expert_guidance

            # Prepare complete work summary
            work_summary = self._prepare_work_summary()
            response_data[f"complete_{self.get_name()}"] = {
                "initial_request": self.get_initial_request(request.step),
                "steps_taken": len(self.work_history),
                "files_examined": list(self.consolidated_findings.files_checked),
                "relevant_files": list(self.consolidated_findings.relevant_files),
                "relevant_context": list(self.consolidated_findings.relevant_context),
                "issues_found": self.consolidated_findings.issues_found,
                "work_summary": work_summary,
            }
        else:
            # Tool doesn't require expert analysis or local work was sufficient
            if not self.requires_expert_analysis():
                # Tool is self-contained (like planner)
                response_data["status"] = f"{self.get_name()}_complete"
                response_data["next_steps"] = (
                    f"{self.get_name().capitalize()} work complete. Present results to the user."
                )
            else:
                # Local work was sufficient for tools that support expert analysis
                response_data["status"] = "local_work_complete"
                response_data["next_steps"] = (
                    f"Local {self.get_name()} complete with sufficient confidence. Present findings "
                    "and recommendations to the user based on the work results."
                )

        return response_data

    def handle_work_continuation(self, response_data: dict, request) -> dict:
        """
        Handle work continuation - force pause and provide guidance.
        """
        response_data["status"] = f"pause_for_{self.get_name()}"
        response_data[f"{self.get_name()}_required"] = True

        # Get tool-specific required actions
        required_actions = self.get_required_actions(
            request.step_number, self.get_request_confidence(request), request.findings, request.total_steps, request
        )
        response_data["required_actions"] = required_actions

        # Generate step guidance
        response_data["next_steps"] = self.get_step_guidance_message(request)

        return response_data

    def _update_consolidated_findings(self, step_data: dict):
        """Update consolidated findings with new step data"""
        self.consolidated_findings.files_checked.update(step_data.get("files_checked", []))
        self.consolidated_findings.relevant_files.update(step_data.get("relevant_files", []))
        self.consolidated_findings.relevant_context.update(step_data.get("relevant_context", []))
        self.consolidated_findings.findings.append(f"Step {step_data['step_number']}: {step_data['findings']}")
        if step_data.get("hypothesis"):
            self.consolidated_findings.hypotheses.append(
                {
                    "step": step_data["step_number"],
                    "hypothesis": step_data["hypothesis"],
                    "confidence": step_data["confidence"],
                }
            )
        if step_data.get("issues_found"):
            self.consolidated_findings.issues_found.extend(step_data["issues_found"])
        if step_data.get("images"):
            self.consolidated_findings.images.extend(step_data["images"])
        # Update confidence to latest value from this step
        if step_data.get("confidence"):
            self.consolidated_findings.confidence = step_data["confidence"]

    def _reprocess_consolidated_findings(self):
        """Reprocess consolidated findings after backtracking"""
        self.consolidated_findings = ConsolidatedFindings()
        for step in self.work_history:
            self._update_consolidated_findings(step)

    def _prepare_work_summary(self) -> str:
        """Prepare a comprehensive summary of the work"""
        summary_parts = [
            f"=== {self.get_name().upper()} WORK SUMMARY ===",
            f"Total steps: {len(self.work_history)}",
            f"Files examined: {len(self.consolidated_findings.files_checked)}",
            f"Relevant files identified: {len(self.consolidated_findings.relevant_files)}",
            f"Methods/functions involved: {len(self.consolidated_findings.relevant_context)}",
            f"Issues found: {len(self.consolidated_findings.issues_found)}",
            "",
            "=== WORK PROGRESSION ===",
        ]

        for finding in self.consolidated_findings.findings:
            summary_parts.append(finding)

        if self.consolidated_findings.hypotheses:
            summary_parts.extend(
                [
                    "",
                    "=== HYPOTHESIS EVOLUTION ===",
                ]
            )
            for hyp in self.consolidated_findings.hypotheses:
                summary_parts.append(f"Step {hyp['step']} ({hyp['confidence']} confidence): {hyp['hypothesis']}")

        if self.consolidated_findings.issues_found:
            summary_parts.extend(
                [
                    "",
                    "=== ISSUES IDENTIFIED ===",
                ]
            )
            for issue in self.consolidated_findings.issues_found:
                severity = issue.get("severity", "unknown")
                description = issue.get("description", "No description")
                summary_parts.append(f"[{severity.upper()}] {description}")

        return "\n".join(summary_parts)

    async def _call_expert_analysis(self, arguments: dict, request) -> dict:
        """Call external model for expert analysis"""
        try:
            # Model context should be resolved from early validation, but handle fallback for tests
            if not self._model_context:
                # Try to resolve model context for expert analysis (deferred from early validation)
                try:
                    model_name, model_context = self._resolve_model_context(arguments, request)
                    self._model_context = model_context
                    self._current_model_name = model_name
                except Exception as e:
                    logger.error(f"Failed to resolve model context for expert analysis: {e}")
                    # Use request model as fallback (preserves existing test behavior)
                    model_name = self.get_request_model_name(request)
                    from utils.model_context import ModelContext

                    model_context = ModelContext(model_name)
                    self._model_context = model_context
                    self._current_model_name = model_name
            else:
                model_name = self._current_model_name

            provider = self._model_context.provider

            # Prepare expert analysis context
            expert_context = self.prepare_expert_analysis_context(self.consolidated_findings)

            # Check if tool wants to include files in prompt
            if self.should_include_files_in_expert_prompt():
                file_content = self._prepare_files_for_expert_analysis()
                if file_content:
                    expert_context = self._add_files_to_expert_context(expert_context, file_content)

            # Get system prompt for this tool with localization support
            base_system_prompt = self.get_system_prompt()
            capability_augmented_prompt = self._augment_system_prompt_with_capabilities(
                base_system_prompt, getattr(self._model_context, "capabilities", None)
            )
            language_instruction = self.get_language_instruction()
            system_prompt = language_instruction + capability_augmented_prompt

            # Check if tool wants system prompt embedded in main prompt
            if self.should_embed_system_prompt():
                prompt = f"{system_prompt}\n\n{expert_context}\n\n{self.get_expert_analysis_instruction()}"
                system_prompt = ""  # Clear it since we embedded it
            else:
                prompt = expert_context

            # Validate temperature against model constraints
            validated_temperature, temp_warnings = self.get_validated_temperature(request, self._model_context)

            # Log any temperature corrections
            for warning in temp_warnings:
                logger.warning(warning)

            # Generate AI response - use request parameters if available
            model_response = provider.generate_content(
                prompt=prompt,
                model_name=model_name,
                system_prompt=system_prompt,
                temperature=validated_temperature,
                thinking_mode=self.get_request_thinking_mode(request),
                images=list(set(self.consolidated_findings.images)) if self.consolidated_findings.images else None,
            )

            if model_response.content:
                content = model_response.content.strip()

                # Try to extract JSON from markdown code blocks if present
                if "```json" in content or "```" in content:
                    json_match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1).strip()

                try:
                    # Try to parse as JSON
                    analysis_result = json.loads(content)
                    return analysis_result
                except json.JSONDecodeError as e:
                    # Log the parse error with more details but don't fail
                    logger.info(
                        f"[{self.get_name()}] Expert analysis returned non-JSON response (this is OK for smaller models). "
                        f"Parse error: {str(e)}. Response length: {len(model_response.content)} chars."
                    )
                    logger.debug(f"First 500 chars of response: {model_response.content[:500]!r}")

                    # Still return the analysis as plain text - this is valid
                    return {
                        "status": "analysis_complete",
                        "raw_analysis": model_response.content,
                        "format": "text",  # Indicate it's plain text, not an error
                        "note": "Analysis provided in plain text format",
                    }
            else:
                return {"error": "No response from model", "status": "empty_response"}

        except Exception as e:
            logger.error(f"Error calling expert analysis: {e}", exc_info=True)
            return {"error": str(e), "status": "analysis_error"}

    def _process_work_step(self, step_data: dict):
        """
        Process a single work step and update internal state.

        This method is useful for testing and manual step processing.
        It adds the step to work history and updates consolidated findings.

        Args:
            step_data: Dictionary containing step information including:
                      step, step_number, findings, files_checked, etc.
        """
        # Store in history
        self.work_history.append(step_data)

        # Update consolidated findings
        self._update_consolidated_findings(step_data)

    # Common execute method for workflow-based tools

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        Common execute logic for workflow-based tools.

        This method provides common validation and delegates to execute_workflow.
        Tools that need custom execute logic can override this method.
        """
        try:
            # Common validation
            if not arguments:
                error_data = {"status": "error", "content": "No arguments provided"}
                # Add basic metadata even for validation errors
                error_data["metadata"] = {"tool_name": self.get_name()}
                raise ToolExecutionError(json.dumps(error_data, ensure_ascii=False))

            # Delegate to execute_workflow
            return await self.execute_workflow(arguments)

        except ToolExecutionError:
            raise
        except Exception as e:
            logger.error(f"Error in {self.get_name()} tool execution: {e}", exc_info=True)
            error_data = {
                "status": "error",
                "content": f"Error in {self.get_name()}: {str(e)}",
            }  # Add metadata to error responses
            self._add_workflow_metadata(error_data, arguments)
            raise ToolExecutionError(json.dumps(error_data, ensure_ascii=False)) from e

    # Default implementations for methods that workflow-based tools typically don't need

    async def prepare_prompt(self, request) -> str:
        """
        Base implementation for workflow tools - compatible with BaseTool signature.

        Workflow tools typically don't need to return a prompt since they handle
        their own prompt preparation internally through the workflow execution.

        Args:
            request: The validated request object

        Returns:
            Empty string since workflow tools manage prompts internally
        """
        # Workflow tools handle their prompts internally during workflow execution
        return ""

    def format_response(self, response: str, request, model_info=None):
        """
        Workflow tools handle their own response formatting.
        The BaseWorkflowMixin formats responses internally.
        """
        return response
