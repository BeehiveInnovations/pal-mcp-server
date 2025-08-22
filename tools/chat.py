"""
Chat tool - General development chat and collaborative thinking

This tool provides a conversational interface for general development assistance,
brainstorming, problem-solving, and collaborative thinking. It supports file context,
images, and conversation continuation for seamless multi-turn interactions.
"""

from typing import TYPE_CHECKING, Any, Optional

from pydantic import Field

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from config import TEMPERATURE_BALANCED
from systemprompts import CHAT_PROMPT
from tools.shared.base_models import COMMON_FIELD_DESCRIPTIONS, ToolRequest

from .simple.base import SimpleTool

# Field descriptions matching the original Chat tool exactly
CHAT_FIELD_DESCRIPTIONS = {
    "prompt": (
        "Your question or idea for collaborative thinking. Provide detailed context, including your goal, what you've tried, and any specific challenges. "
        "CRITICAL: To discuss code, provide file paths using the 'files' parameter instead of pasting large code blocks here."
    ),
    "files": "Absolute full-paths to existing files / folders for context. DO NOT SHORTEN.",
    "images": (
        "Optional images for visual context (must be FULL absolute paths to real files / folders - DO NOT SHORTEN - OR these can be bas64 data)"
    ),
}


class ChatRequest(ToolRequest):
    """Request model for Chat tool"""

    prompt: str = Field(..., description=CHAT_FIELD_DESCRIPTIONS["prompt"])
    files: Optional[list[str]] = Field(default_factory=list, description=CHAT_FIELD_DESCRIPTIONS["files"])
    images: Optional[list[str]] = Field(default_factory=list, description=CHAT_FIELD_DESCRIPTIONS["images"])


class ChatTool(SimpleTool):
    """
    General development chat and collaborative thinking tool using SimpleTool architecture.

    This tool provides identical functionality to the original Chat tool but uses the new
    SimpleTool architecture for cleaner code organization and better maintainability.

    Migration note: This tool is designed to be a drop-in replacement for the original
    Chat tool with 100% behavioral compatibility.
    """

    def get_name(self) -> str:
        return "chat"

    def get_description(self) -> str:
        return (
            "General chat and collaborative thinking partner for brainstorming, development discussion, getting second opinions, and exploring ideas. "
            "Use for bouncing ideas, validating approaches, asking questions, and getting explanations. "
        )

    def get_system_prompt(self) -> str:
        return CHAT_PROMPT

    def get_default_temperature(self) -> float:
        return TEMPERATURE_BALANCED

    def get_model_category(self) -> "ToolModelCategory":
        """Chat prioritizes fast responses and cost efficiency"""
        from tools.models import ToolModelCategory

        return ToolModelCategory.FAST_RESPONSE

    def get_request_model(self):
        """Return the Chat-specific request model"""
        return ChatRequest

    # === Schema Generation ===
    # For maximum compatibility, we override get_input_schema() to match the original Chat tool exactly

    def get_input_schema(self) -> dict[str, Any]:
        """
        Generate input schema matching the original Chat tool exactly.

        This maintains 100% compatibility with the original Chat tool by using
        the same schema generation approach while still benefiting from SimpleTool
        convenience methods.
        """
        schema = {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": CHAT_FIELD_DESCRIPTIONS["prompt"],
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CHAT_FIELD_DESCRIPTIONS["files"],
                },
                "images": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": CHAT_FIELD_DESCRIPTIONS["images"],
                },
                "model": self.get_model_field_schema(),
                "temperature": {
                    "type": "number",
                    "description": COMMON_FIELD_DESCRIPTIONS["temperature"],
                    "minimum": 0,
                    "maximum": 1,
                },
                "thinking_mode": {
                    "type": "string",
                    "enum": ["minimal", "low", "medium", "high", "max"],
                    "description": COMMON_FIELD_DESCRIPTIONS["thinking_mode"],
                },
                "use_websearch": {
                    "type": "boolean",
                    "description": COMMON_FIELD_DESCRIPTIONS["use_websearch"],
                    "default": True,
                },
                "continuation_id": {
                    "type": "string",
                    "description": COMMON_FIELD_DESCRIPTIONS["continuation_id"],
                },
            },
            "required": ["prompt"] + (["model"] if self.is_effective_auto_mode() else []),
        }

        return schema

    # === Tool-specific field definitions (alternative approach for reference) ===
    # These aren't used since we override get_input_schema(), but they show how
    # the tool could be implemented using the automatic SimpleTool schema building

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """
        Tool-specific field definitions for ChatSimple.

        Note: This method isn't used since we override get_input_schema() for
        exact compatibility, but it demonstrates how ChatSimple could be
        implemented using automatic schema building.
        """
        return {
            "prompt": {
                "type": "string",
                "description": CHAT_FIELD_DESCRIPTIONS["prompt"],
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": CHAT_FIELD_DESCRIPTIONS["files"],
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": CHAT_FIELD_DESCRIPTIONS["images"],
            },
        }

    def get_required_fields(self) -> list[str]:
        """Required fields for ChatSimple tool"""
        return ["prompt"]

    # === Hook Method Implementations ===

    async def prepare_prompt(self, request: ChatRequest) -> str:
        """
        Prepare the chat prompt with optional context files.

        This implementation matches the original Chat tool exactly while using
        SimpleTool convenience methods for cleaner code.
        """
        # Use SimpleTool's Chat-style prompt preparation
        return self.prepare_chat_style_prompt(request)

    def format_response(self, response: str, request: ChatRequest, model_info: Optional[dict] = None) -> str:
        """
        Format the chat response to match the original Chat tool exactly.
        """
        return (
            f"{response}\n\n---\n\nAGENT'S TURN: Evaluate this perspective alongside your analysis to "
            "form a comprehensive solution and continue with the user's request and task at hand."
        )

    def get_websearch_guidance(self) -> str:
        """
        Return Chat tool-style web search guidance.
        """
        return self.get_chat_style_websearch_guidance()
