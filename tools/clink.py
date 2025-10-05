"""clink tool - bridge Zen MCP requests to external AI CLIs."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.types import TextContent
from pydantic import BaseModel, Field

from clink import get_registry
from clink.agents import AgentOutput, CLIAgentError, create_agent
from clink.models import ResolvedCLIClient, ResolvedCLIRole
from config import TEMPERATURE_BALANCED
from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import COMMON_FIELD_DESCRIPTIONS
from tools.simple.base import SchemaBuilder, SimpleTool

logger = logging.getLogger(__name__)


class CLinkRequest(BaseModel):
    """Request model for clink tool."""

    prompt: str = Field(..., description="Prompt forwarded to the target CLI.")
    cli_name: str | None = Field(
        default=None,
        description="Configured CLI client name to invoke. Defaults to the first configured CLI if omitted.",
    )
    role: str | None = Field(
        default=None,
        description="Optional role preset defined in the CLI configuration (defaults to 'default').",
    )
    files: list[str] = Field(
        default_factory=list,
        description=COMMON_FIELD_DESCRIPTIONS["files"],
    )
    images: list[str] = Field(
        default_factory=list,
        description=COMMON_FIELD_DESCRIPTIONS["images"],
    )
    continuation_id: str | None = Field(
        default=None,
        description=COMMON_FIELD_DESCRIPTIONS["continuation_id"],
    )


class CLinkTool(SimpleTool):
    """Bridge MCP requests to configured CLI agents.

    Schema metadata is cached at construction time and execution relies on the shared
    SimpleTool hooks for conversation memory. Prompt preparation is customised so we
    pass instructions and file references suitable for another CLI agent.
    """

    def __init__(self) -> None:
        # Cache registry metadata so the schema surfaces concrete enum values.
        self._registry = get_registry()
        self._cli_names = self._registry.list_clients()
        self._role_map: dict[str, list[str]] = {name: self._registry.list_roles(name) for name in self._cli_names}
        self._all_roles: list[str] = sorted({role for roles in self._role_map.values() for role in roles})
        self._default_cli_name: str | None = self._cli_names[0] if self._cli_names else None
        self._active_system_prompt: str = ""
        super().__init__()

    def get_name(self) -> str:
        return "clink"

    def get_description(self) -> str:
        return (
            "Link a request to an external AI CLI (Gemini CLI, Qwen CLI, etc.) through Zen MCP to reuse "
            "their capabilities inside existing workflows."
        )

    def get_annotations(self) -> dict[str, Any]:
        return {"readOnlyHint": True}

    def requires_model(self) -> bool:
        return False

    def get_model_category(self) -> ToolModelCategory:
        return ToolModelCategory.BALANCED

    def get_default_temperature(self) -> float:
        return TEMPERATURE_BALANCED

    def get_system_prompt(self) -> str:
        return self._active_system_prompt or ""

    def get_request_model(self):
        return CLinkRequest

    def get_input_schema(self) -> dict[str, Any]:
        # Surface configured CLI names and roles directly in the schema so MCP clients
        # (and downstream agents) can discover available options without consulting
        # a separate registry call.
        role_descriptions = []
        for name in self._cli_names:
            roles = ", ".join(sorted(self._role_map.get(name, ["default"]))) or "default"
            role_descriptions.append(f"{name}: {roles}")

        if role_descriptions:
            cli_available = ", ".join(self._cli_names) if self._cli_names else "(none configured)"
            default_text = (
                f" Default: {self._default_cli_name}." if self._default_cli_name and len(self._cli_names) <= 1 else ""
            )
            cli_description = (
                "Configured CLI client name (from conf/cli_clients). Available: " + cli_available + default_text
            )
            role_description = (
                "Optional role preset defined for the selected CLI (defaults to 'default'). Roles per CLI: "
                + "; ".join(role_descriptions)
            )
        else:
            cli_description = "Configured CLI client name (from conf/cli_clients)."
            role_description = "Optional role preset defined for the selected CLI (defaults to 'default')."

        properties = {
            "prompt": {
                "type": "string",
                "description": "User request forwarded to the CLI (conversation context is pre-applied).",
            },
            "cli_name": {
                "type": "string",
                "enum": self._cli_names,
                "description": cli_description,
            },
            "role": {
                "type": "string",
                "enum": self._all_roles or ["default"],
                "description": role_description,
            },
            "files": SchemaBuilder.SIMPLE_FIELD_SCHEMAS["files"],
            "images": SchemaBuilder.COMMON_FIELD_SCHEMAS["images"],
            "continuation_id": SchemaBuilder.COMMON_FIELD_SCHEMAS["continuation_id"],
        }

        schema = {
            "type": "object",
            "properties": properties,
            "required": ["prompt"],
            "additionalProperties": False,
        }

        if len(self._cli_names) > 1:
            schema["required"].append("cli_name")

        return schema

    def get_tool_fields(self) -> dict[str, dict[str, Any]]:
        """Unused by clink because we override the schema end-to-end."""
        return {}

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        self._current_arguments = arguments
        request = self.get_request_model()(**arguments)

        path_error = self._validate_file_paths(request)
        if path_error:
            return [self._error_response(path_error)]

        selected_cli = request.cli_name or self._default_cli_name
        if not selected_cli:
            return [self._error_response("No CLI clients are configured for clink.")]

        try:
            client_config = self._registry.get_client(selected_cli)
        except KeyError as exc:
            return [self._error_response(str(exc))]

        try:
            role_config = client_config.get_role(request.role)
        except KeyError as exc:
            return [self._error_response(str(exc))]

        files = self.get_request_files(request)
        images = self.get_request_images(request)
        continuation_id = self.get_request_continuation_id(request)

        self._model_context = arguments.get("_model_context")

        try:
            prompt_text = await self._prepare_prompt_for_role(request, role_config)
        except Exception as exc:
            logger.exception("Failed to prepare clink prompt")
            return [self._error_response(f"Failed to prepare prompt: {exc}")]

        agent = create_agent(client_config)
        try:
            result = await agent.run(role=role_config, prompt=prompt_text, files=files, images=images)
        except CLIAgentError as exc:
            metadata = self._build_error_metadata(client_config, exc)
            error_output = ToolOutput(
                status="error",
                content=f"CLI '{client_config.name}' execution failed: {exc}",
                content_type="text",
                metadata=metadata,
            )
            return [TextContent(type="text", text=error_output.model_dump_json())]

        model_info = {
            "provider": client_config.name,
            "model_name": result.parsed.metadata.get("model_used"),
        }

        if continuation_id:
            try:
                self._record_assistant_turn(continuation_id, result.parsed.content, request, model_info)
            except Exception:
                logger.debug("Failed to record assistant turn for continuation %s", continuation_id, exc_info=True)

        metadata = self._build_success_metadata(client_config, role_config, result)

        continuation_offer = self._create_continuation_offer(request, model_info)
        if continuation_offer:
            tool_output = self._create_continuation_offer_response(
                result.parsed.content,
                continuation_offer,
                request,
                model_info,
            )
            tool_output.metadata = self._merge_metadata(tool_output.metadata, metadata)
        else:
            tool_output = ToolOutput(
                status="success",
                content=result.parsed.content,
                content_type="text",
                metadata=metadata,
            )

        return [TextContent(type="text", text=tool_output.model_dump_json())]

    async def prepare_prompt(self, request) -> str:
        client_config = self._registry.get_client(request.cli_name)
        role_config = client_config.get_role(request.role)
        return await self._prepare_prompt_for_role(request, role_config)

    async def _prepare_prompt_for_role(self, request: CLinkRequest, role: ResolvedCLIRole) -> str:
        """Load the role prompt and assemble the final user message."""
        self._active_system_prompt = role.prompt_path.read_text(encoding="utf-8")
        try:
            user_content = self.handle_prompt_file_with_fallback(request).strip()
            guidance = self._agent_capabilities_guidance()
            file_section = self._format_file_references(self.get_request_files(request))

            sections: list[str] = []
            active_prompt = self.get_system_prompt().strip()
            if active_prompt:
                sections.append(active_prompt)
            sections.append(guidance)
            sections.append("=== USER REQUEST ===\n" + user_content)
            if file_section:
                sections.append("=== FILE REFERENCES ===\n" + file_section)
            sections.append("Provide your response below using your own CLI tools as needed:")
            return "\n\n".join(sections)
        finally:
            self._active_system_prompt = ""

    def _merge_metadata(self, base: dict[str, Any] | None, extra: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base or {})
        merged.update(extra)
        return merged

    def _build_success_metadata(
        self,
        client: ResolvedCLIClient,
        role: ResolvedCLIRole,
        result: AgentOutput,
    ) -> dict[str, Any]:
        """Capture execution metadata for successful CLI calls."""
        metadata: dict[str, Any] = {
            "cli_name": client.name,
            "role": role.name,
            "command": result.sanitized_command,
            "duration_seconds": round(result.duration_seconds, 3),
            "parser": result.parser_name,
            "return_code": result.returncode,
        }
        metadata.update(result.parsed.metadata)

        if result.stderr.strip():
            metadata.setdefault("stderr", result.stderr.strip())
        if result.output_file_content and "raw" not in metadata:
            metadata["raw_output_file"] = result.output_file_content
        return metadata

    def _build_error_metadata(self, client: ResolvedCLIClient, exc: CLIAgentError) -> dict[str, Any]:
        """Assemble metadata for failed CLI calls."""
        metadata: dict[str, Any] = {
            "cli_name": client.name,
            "return_code": exc.returncode,
        }
        if exc.stdout:
            metadata["stdout"] = exc.stdout.strip()
        if exc.stderr:
            metadata["stderr"] = exc.stderr.strip()
        return metadata

    def _error_response(self, message: str) -> TextContent:
        error_output = ToolOutput(status="error", content=message, content_type="text")
        return TextContent(type="text", text=error_output.model_dump_json())

    def _agent_capabilities_guidance(self) -> str:
        return (
            "You are operating through the Gemini CLI agent. You have access to your full suite of "
            "CLI capabilities—including launching web searches, reading files, and using any other "
            "available tools. Gather current information yourself and deliver the final answer without "
            "asking the Zen MCP host to perform searches or file reads."
        )

    def _format_file_references(self, files: list[str]) -> str:
        if not files:
            return ""

        references: list[str] = []
        for file_path in files:
            try:
                path = Path(file_path)
                stat = path.stat()
                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                size = stat.st_size
                references.append(f"- {file_path} (last modified {modified}, {size} bytes)")
            except OSError:
                references.append(f"- {file_path} (unavailable)")
        return "\n".join(references)
