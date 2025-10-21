"""
Core schema building functionality for Zen MCP tools.

This module provides base schema generation functionality for simple tools.
Workflow-specific schema building is located in workflow/schema_builders.py
to maintain proper separation of concerns.
"""

from typing import Any

from .base_models import COMMON_FIELD_DESCRIPTIONS


class SchemaBuilder:
    """
    Base schema builder for simple MCP tools.

    This class provides static methods to build consistent schemas for simple tools.
    Workflow tools use WorkflowSchemaBuilder in workflow/schema_builders.py.
    """

    # Common field schemas that can be reused across all tool types
    COMMON_FIELD_SCHEMAS = {
        "temperature": {
            "type": "number",
            "description": COMMON_FIELD_DESCRIPTIONS["temperature"],
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "thinking_mode": {
            "type": "string",
            "enum": ["minimal", "low", "medium", "high", "max"],
            "description": COMMON_FIELD_DESCRIPTIONS["thinking_mode"],
        },
        "continuation_id": {
            "type": "string",
            "description": COMMON_FIELD_DESCRIPTIONS["continuation_id"],
        },
        "images": {
            "type": "array",
            "items": {"type": "string"},
            "description": COMMON_FIELD_DESCRIPTIONS["images"],
        },
    }

    # Simple tool-specific field schemas (workflow tools use relevant_files instead)
    SIMPLE_FIELD_SCHEMAS = {
        "absolute_file_paths": {
            "type": "array",
            "items": {"type": "string"},
            "description": COMMON_FIELD_DESCRIPTIONS["absolute_file_paths"],
        },
    }

    @staticmethod
    def build_schema(
        tool_specific_fields: dict[str, dict[str, Any]] = None,
        required_fields: list[str] = None,
        model_field_schema: dict[str, Any] = None,
        auto_mode: bool = False,
        require_model: bool = False,
    ) -> dict[str, Any]:
        """
        Build complete schema for simple tools.

        Args:
            tool_specific_fields: Additional fields specific to the tool
            required_fields: List of required field names
            model_field_schema: Schema for the model field
            auto_mode: Whether the tool is in auto mode (affects model requirement)

        Returns:
            Complete JSON schema for the tool
        """
        properties = {}

        # Add common fields (temperature, thinking_mode, etc.)
        properties.update(SchemaBuilder.COMMON_FIELD_SCHEMAS)

        # Add simple tool-specific fields (files field for simple tools)
        properties.update(SchemaBuilder.SIMPLE_FIELD_SCHEMAS)

        # Add model field if provided
        if model_field_schema:
            properties["model"] = model_field_schema

        # Add tool-specific fields if provided
        if tool_specific_fields:
            properties.update(tool_specific_fields)

        # Build required fields list
        required = list(required_fields) if required_fields else []
        if (auto_mode or require_model) and "model" not in required:
            required.append("model")

        # Build the complete schema
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
        }

        if required:
            schema["required"] = required

        return schema

    @staticmethod
    def get_common_fields() -> dict[str, dict[str, Any]]:
        """Get the standard field schemas for simple tools."""
        return SchemaBuilder.COMMON_FIELD_SCHEMAS.copy()

    @staticmethod
    def create_field_schema(
        field_type: str,
        description: str,
        enum_values: list[str] = None,
        minimum: float = None,
        maximum: float = None,
        items_type: str = None,
        default: Any = None,
    ) -> dict[str, Any]:
        """
        Helper method to create field schemas with common patterns.

        Args:
            field_type: JSON schema type ("string", "number", "array", etc.)
            description: Human-readable description of the field
            enum_values: For enum fields, list of allowed values
            minimum: For numeric fields, minimum value
            maximum: For numeric fields, maximum value
            items_type: For array fields, type of array items
            default: Default value for the field

        Returns:
            JSON schema object for the field
        """
        schema = {
            "type": field_type,
            "description": description,
        }

        if enum_values:
            schema["enum"] = enum_values

        if minimum is not None:
            schema["minimum"] = minimum

        if maximum is not None:
            schema["maximum"] = maximum

        if items_type and field_type == "array":
            schema["items"] = {"type": items_type}

        if default is not None:
            schema["default"] = default

        return schema
