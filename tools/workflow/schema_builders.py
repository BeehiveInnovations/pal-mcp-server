"""
Schema builders for workflow MCP tools.

This module provides workflow-specific schema generation functionality,
keeping workflow concerns separated from simple tool concerns.
"""

from typing import Any

from ..shared.base_models import WORKFLOW_FIELD_DESCRIPTIONS
from ..shared.schema_builders import SchemaBuilder


class WorkflowSchemaBuilder:
    """
    Schema builder for workflow MCP tools.

    This class extends the base SchemaBuilder with workflow-specific fields
    and schema generation logic, maintaining separation of concerns.
    """

    # Workflow-specific field schemas
    WORKFLOW_FIELD_SCHEMAS = {
        "step": {
            "type": "string",
            "description": WORKFLOW_FIELD_DESCRIPTIONS["step"],
        },
        "step_number": {
            "type": "integer",
            "minimum": 1,
            "description": WORKFLOW_FIELD_DESCRIPTIONS["step_number"],
        },
        "total_steps": {
            "type": "integer",
            "minimum": 1,
            "description": WORKFLOW_FIELD_DESCRIPTIONS["total_steps"],
        },
        "next_step_required": {
            "type": "boolean",
            "description": WORKFLOW_FIELD_DESCRIPTIONS["next_step_required"],
        },
        "findings": {
            "type": "string",
            "description": WORKFLOW_FIELD_DESCRIPTIONS["findings"],
        },
        "files_checked": {
            "type": "array",
            "items": {"type": "string"},
            "description": WORKFLOW_FIELD_DESCRIPTIONS["files_checked"],
        },
        "relevant_files": {
            "type": "array",
            "items": {"type": "string"},
            "description": WORKFLOW_FIELD_DESCRIPTIONS["relevant_files"],
        },
        "relevant_context": {
            "type": "array",
            "items": {"type": "string"},
            "description": WORKFLOW_FIELD_DESCRIPTIONS["relevant_context"],
        },
        "issues_found": {
            "type": "array",
            "items": {"type": "object"},
            "description": WORKFLOW_FIELD_DESCRIPTIONS["issues_found"],
        },
        "confidence": {
            "type": "string",
            "enum": ["exploring", "low", "medium", "high", "very_high", "almost_certain", "certain"],
            "description": WORKFLOW_FIELD_DESCRIPTIONS["confidence"],
        },
        "hypothesis": {
            "type": "string",
            "description": WORKFLOW_FIELD_DESCRIPTIONS["hypothesis"],
        },
        "backtrack_from_step": {
            "type": "integer",
            "minimum": 1,
            "description": WORKFLOW_FIELD_DESCRIPTIONS["backtrack_from_step"],
        },
        "use_assistant_model": {
            "type": "boolean",
            "default": True,
            "description": WORKFLOW_FIELD_DESCRIPTIONS["use_assistant_model"],
        },
    }

    @staticmethod
    def build_schema(
        tool_specific_fields: dict[str, dict[str, Any]] = None,
        required_fields: list[str] = None,
        model_field_schema: dict[str, Any] = None,
        auto_mode: bool = False,
        tool_name: str = None,
        excluded_workflow_fields: list[str] = None,
        excluded_common_fields: list[str] = None,
    ) -> dict[str, Any]:
        """
        Build complete schema for workflow tools.

        Args:
            tool_specific_fields: Additional fields specific to the tool
            required_fields: List of required field names (beyond workflow defaults)
            model_field_schema: Schema for the model field
            auto_mode: Whether the tool is in auto mode (affects model requirement)
            tool_name: Name of the tool (for schema title)
            excluded_workflow_fields: Workflow fields to exclude from schema (e.g., for planning tools)
            excluded_common_fields: Common fields to exclude from schema

        Returns:
            Complete JSON schema for the workflow tool
        """
        properties = {}

        # Add workflow fields first, excluding any specified fields
        workflow_fields = WorkflowSchemaBuilder.WORKFLOW_FIELD_SCHEMAS.copy()
        if excluded_workflow_fields:
            for field in excluded_workflow_fields:
                workflow_fields.pop(field, None)
        properties.update(workflow_fields)

        # Add common fields (temperature, thinking_mode, etc.) from base builder, excluding any specified fields
        common_fields = SchemaBuilder.COMMON_FIELD_SCHEMAS.copy()
        if excluded_common_fields:
            for field in excluded_common_fields:
                common_fields.pop(field, None)
        properties.update(common_fields)

        # Add model field if provided
        if model_field_schema:
            properties["model"] = model_field_schema

        # Add tool-specific fields if provided
        if tool_specific_fields:
            properties.update(tool_specific_fields)

        # Build required fields list - workflow tools have standard required fields
        standard_required = ["step", "step_number", "total_steps", "next_step_required", "findings"]

        # Filter out excluded fields from required fields
        if excluded_workflow_fields:
            standard_required = [field for field in standard_required if field not in excluded_workflow_fields]

        required = standard_required + (required_fields or [])

        if auto_mode and "model" not in required:
            required.append("model")

        # Build the complete schema
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

        if tool_name:
            schema["title"] = f"{tool_name.capitalize()}Request"

        return schema

    @staticmethod
    def get_workflow_fields() -> dict[str, dict[str, Any]]:
        """Get the standard field schemas for workflow tools."""
        combined = {}
        combined.update(WorkflowSchemaBuilder.WORKFLOW_FIELD_SCHEMAS)
        combined.update(SchemaBuilder.COMMON_FIELD_SCHEMAS)
        return combined

    @staticmethod
    def get_workflow_only_fields() -> dict[str, dict[str, Any]]:
        """Get only the workflow-specific field schemas."""
        return WorkflowSchemaBuilder.WORKFLOW_FIELD_SCHEMAS.copy()
