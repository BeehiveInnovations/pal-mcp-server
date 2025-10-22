"""
Base class for workflow MCP tools.

Workflow tools follow a multi-step pattern:
1. CLI calls tool with work step data
2. Tool tracks findings and progress
3. Tool forces the CLI to pause and investigate between steps
4. Once work is complete, tool calls external AI model for expert analysis
5. Tool returns structured response combining investigation + expert analysis

They combine BaseTool's capabilities with BaseWorkflowMixin's workflow functionality
and use SchemaBuilder for consistent schema generation.
"""

from abc import abstractmethod
from typing import Any, Optional

from tools.shared.base_models import WorkflowRequest
from tools.shared.base_tool import BaseTool

from .schema_builders import WorkflowSchemaBuilder
from .workflow_mixin import BaseWorkflowMixin


class WorkflowTool(BaseTool, BaseWorkflowMixin):
    """
    Base class for workflow (multi-step) tools.

    Workflow tools perform systematic multi-step work with expert analysis.
    They benefit from:
    - Automatic workflow orchestration from BaseWorkflowMixin
    - Automatic schema generation using SchemaBuilder
    - Inherited conversation handling and file processing from BaseTool
    - Progress tracking with ConsolidatedFindings
    - Expert analysis integration

    To create a workflow tool:
    1. Inherit from WorkflowTool
    2. Tool name is automatically provided by get_name() method
    3. Implement get_required_actions() for step guidance
    4. Implement should_call_expert_analysis() for completion criteria
    5. Implement prepare_expert_analysis_context() for expert prompts
    6. Optionally implement get_tool_fields() for additional fields
    7. Optionally override workflow behavior methods

    Example:
        class DebugTool(WorkflowTool):
            # get_name() is inherited from BaseTool

            def get_tool_fields(self) -> Dict[str, Dict[str, Any]]:
                return {
                    "hypothesis": {
                        "type": "string",
                        "description": "Current theory about the issue",
                    }
                }

            def get_required_actions(
                self, step_number: int, confidence: str, findings: str, total_steps: int
            ) -> List[str]:
                return ["Examine relevant code files", "Trace execution flow", "Check error logs"]

            def should_call_expert_analysis(self, consolidated_findings) -> bool:
                return len(consolidated_findings.relevant_files) > 0
    """

    def __init__(self):
        """Initialize WorkflowTool with proper multiple inheritance."""
        BaseTool.__init__(self)
        BaseWorkflowMixin.__init__(self)

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """
        Return tool-specific field definitions beyond the standard workflow fields.

        Workflow tools automatically get all standard workflow fields:
        - step, step_number, total_steps, next_step_required
        - findings, files_checked, relevant_files, relevant_context
        - issues_found, confidence, hypothesis
        - plus common fields (model, temperature, etc.)

        Override this method to add additional tool-specific fields.

        Returns:
            Dict mapping field names to JSON schema objects

        Example:
            return {
                "severity_filter": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Minimum severity level to report",
                }
            }
        """
        return {}

    def get_required_fields(self) -> list[str]:
        """
        Return additional required fields beyond the standard workflow requirements.

        Workflow tools automatically require:
        - step, step_number, total_steps, next_step_required, findings
        - model (if in auto mode)

        Override this to add additional required fields.

        Returns:
            List of additional required field names
        """
        return []

    def get_annotations(self) -> Optional[dict[str, Any]]:
        """
        Return tool annotations. Workflow tools are read-only by default.

        All workflow tools perform analysis and investigation without modifying
        the environment. They may call external AI models for expert analysis,
        but they don't write files or make system changes.

        Override this method if your workflow tool needs different annotations.

        Returns:
            Dictionary with readOnlyHint set to True
        """
        return {"readOnlyHint": True}

    def get_input_schema(self) -> dict[str, Any]:
        """
        Generate the complete input schema using SchemaBuilder.

        This method automatically combines:
        - Standard workflow fields (step, findings, etc.)
        - Common fields (temperature, thinking_mode, etc.)
        - Model field with proper auto-mode handling
        - Tool-specific fields from get_tool_fields()
        - Required fields from get_required_fields()

        Returns:
            Complete JSON schema for the workflow tool
        """
        requires_model = self.requires_model()
        model_field_schema = self.get_model_field_schema() if requires_model else None
        auto_mode = self.is_effective_auto_mode() if requires_model else False
        return WorkflowSchemaBuilder.build_schema(
            tool_specific_fields=self.get_tool_fields(),
            required_fields=self.get_required_fields(),
            model_field_schema=model_field_schema,
            auto_mode=auto_mode,
            tool_name=self.get_name(),
            require_model=requires_model,
        )

    def get_workflow_request_model(self):
        """
        Return the workflow request model class.

        Workflow tools use WorkflowRequest by default, which includes
        all the standard workflow fields. Override this if your tool
        needs a custom request model.
        """
        return WorkflowRequest

    # Implement the abstract method from BaseWorkflowMixin
    def get_work_steps(self, request) -> list[str]:
        """
        Default implementation - workflow tools typically don't need predefined steps.

        The workflow is driven by the CLI's investigation process rather than
        predefined steps. Override this if your tool needs specific step guidance.
        """
        return []

    # Default implementations for common workflow patterns

    def get_standard_required_actions(self, step_number: int, confidence: str, base_actions: list[str]) -> list[str]:
        """
        Helper method to generate standard required actions based on confidence and step.

        This provides common patterns that most workflow tools can use:
        - Early steps: broad exploration
        - Low confidence: deeper investigation
        - Medium/high confidence: verification and confirmation

        Args:
            step_number: Current step number
            confidence: Current confidence level
            base_actions: Tool-specific base actions

        Returns:
            List of required actions appropriate for the current state
        """
        if step_number == 1:
            # Initial investigation
            return [
                "Search for code related to the reported issue or symptoms",
                "Examine relevant files and understand the current implementation",
                "Understand the project structure and locate relevant modules",
                "Identify how the affected functionality is supposed to work",
            ]
        elif confidence in ["exploring", "low"]:
            # Need deeper investigation
            return base_actions + [
                "Trace method calls and data flow through the system",
                "Check for edge cases, boundary conditions, and assumptions in the code",
                "Look for related configuration, dependencies, or external factors",
            ]
        elif confidence in ["medium", "high"]:
            # Close to solution - need confirmation
            return base_actions + [
                "Examine the exact code sections where you believe the issue occurs",
                "Trace the execution path that leads to the failure",
                "Verify your hypothesis with concrete code evidence",
                "Check for any similar patterns elsewhere in the codebase",
            ]
        else:
            # General continued investigation
            return base_actions + [
                "Continue examining the code paths identified in your hypothesis",
                "Gather more evidence using appropriate investigation tools",
                "Test edge cases and boundary conditions",
                "Look for patterns that confirm or refute your theory",
            ]

    def should_call_expert_analysis_default(self, consolidated_findings) -> bool:
        """
        Default implementation for expert analysis decision.

        This provides a reasonable default that most workflow tools can use:
        - Call expert analysis if we have relevant files or significant findings
        - Skip if confidence is "certain" (handled by the workflow mixin)

        Override this for tool-specific logic.

        Args:
            consolidated_findings: The consolidated findings from all work steps

        Returns:
            True if expert analysis should be called
        """
        # Call expert analysis if we have relevant files or substantial findings
        return (
            len(consolidated_findings.relevant_files) > 0
            or len(consolidated_findings.findings) >= 2
            or len(consolidated_findings.issues_found) > 0
        )

    def prepare_standard_expert_context(
        self, consolidated_findings, initial_description: str, context_sections: dict[str, str] = None
    ) -> str:
        """
        Helper method to prepare standard expert analysis context.

        This provides a common structure that most workflow tools can use,
        with the ability to add tool-specific sections.

        Args:
            consolidated_findings: The consolidated findings from all work steps
            initial_description: Description of the initial request/issue
            context_sections: Optional additional sections to include

        Returns:
            Formatted context string for expert analysis
        """
        context_parts = [f"=== ISSUE DESCRIPTION ===\n{initial_description}\n=== END DESCRIPTION ==="]

        # Add work progression
        if consolidated_findings.findings:
            findings_text = "\n".join(consolidated_findings.findings)
            context_parts.append(f"\n=== INVESTIGATION FINDINGS ===\n{findings_text}\n=== END FINDINGS ===")

        # Add relevant methods if available
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

        # Add issues found if available
        if consolidated_findings.issues_found:
            issues_text = "\n".join(
                f"[{issue.get('severity', 'unknown').upper()}] {issue.get('description', 'No description')}"
                for issue in consolidated_findings.issues_found
            )
            context_parts.append(f"\n=== ISSUES IDENTIFIED ===\n{issues_text}\n=== END ISSUES ===")

        # Add tool-specific sections
        if context_sections:
            for section_title, section_content in context_sections.items():
                context_parts.append(
                    f"\n=== {section_title.upper()} ===\n{section_content}\n=== END {section_title.upper()} ==="
                )

        return "\n".join(context_parts)

    def handle_completion_without_expert_analysis(
        self, request, consolidated_findings, initial_description: str = None
    ) -> dict[str, Any]:
        """
        Generic handler for completion when expert analysis is not needed.

        This provides a standard response format for when the tool determines
        that external expert analysis is not required. All workflow tools
        can use this generic implementation or override for custom behavior.

        Args:
            request: The workflow request object
            consolidated_findings: The consolidated findings from all work steps
            initial_description: Optional initial description (defaults to request.step)

        Returns:
            Dictionary with completion response data
        """
        # Prepare work summary using inheritance hook
        work_summary = self.prepare_work_summary()

        return {
            "status": self.get_completion_status(),
            self.get_completion_data_key(): {
                "initial_request": initial_description or request.step,
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

    # Inheritance hooks for customization

    def prepare_work_summary(self) -> str:
        """
        Prepare a summary of the work performed. Override for custom summaries.
        Default implementation provides a basic summary.
        """
        try:
            return self._prepare_work_summary()
        except AttributeError:
            try:
                return f"Completed {len(self.work_history)} work steps"
            except AttributeError:
                return "Completed 0 work steps"

    def get_completion_status(self) -> str:
        """Get the status to use when completing without expert analysis."""
        return "high_confidence_completion"

    def get_completion_data_key(self) -> str:
        """Get the key name for completion data in the response."""
        return f"complete_{self.get_name()}"

    def get_final_analysis_from_request(self, request) -> Optional[str]:
        """Extract final analysis from request. Override for tool-specific extraction."""
        try:
            return request.hypothesis
        except AttributeError:
            return None

    def get_confidence_level(self, request) -> str:
        """Get confidence level from request. Override for tool-specific logic."""
        try:
            return request.confidence or "high"
        except AttributeError:
            return "high"

    def get_completion_message(self) -> str:
        """Get completion message. Override for tool-specific messaging."""
        return (
            f"{self.get_name().capitalize()} complete with high confidence. You have identified the exact "
            "analysis and solution. MANDATORY: Present the user with the results "
            "and proceed with implementing the solution without requiring further "
            "consultation. Focus on the precise, actionable steps needed."
        )

    def get_skip_reason(self) -> str:
        """Get reason for skipping expert analysis. Override for tool-specific reasons."""
        return f"{self.get_name()} completed with sufficient confidence"

    def get_skip_expert_analysis_status(self) -> str:
        """Get status for skipped expert analysis. Override for tool-specific status."""
        return "skipped_by_tool_design"

    def is_continuation_workflow(self, request) -> bool:
        """
        Check if this is a continuation workflow that should skip multi-step investigation.

        When continuation_id is provided, the workflow typically continues from a previous
        conversation and should go directly to expert analysis rather than starting a new
        multi-step investigation.

        Args:
            request: The workflow request object

        Returns:
            True if this is a continuation that should skip multi-step workflow
        """
        continuation_id = self.get_request_continuation_id(request)
        return bool(continuation_id)

    # Abstract methods that must be implemented by specific workflow tools
    # (These are inherited from BaseWorkflowMixin and must be implemented)

    @abstractmethod
    def get_required_actions(
        self, step_number: int, confidence: str, findings: str, total_steps: int, request=None
    ) -> list[str]:
        """Define required actions for each work phase.

        Args:
            step_number: Current step number
            confidence: Current confidence level
            findings: Current findings text
            total_steps: Total estimated steps
            request: Optional request object for continuation-aware decisions

        Returns:
            List of required actions for the current step
        """
        pass

    @abstractmethod
    def should_call_expert_analysis(self, consolidated_findings) -> bool:
        """Decide when to call external model based on tool-specific criteria"""
        pass

    @abstractmethod
    def prepare_expert_analysis_context(self, consolidated_findings) -> str:
        """Prepare context for external model call"""
        pass

    # Default execute method - delegates to workflow
    async def execute(self, arguments: dict[str, Any]) -> list:
        """Execute the workflow tool - delegates to BaseWorkflowMixin."""
        return await self.execute_workflow(arguments)
