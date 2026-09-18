"""Pydantic models for clink configuration and runtime structures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, PositiveInt, field_validator, model_validator

from clink.constants import (
    DEFAULT_PROMPT_DELIVERY,
    PROMPT_PLACEHOLDER,
    TIMEOUT_PLACEHOLDER,
    PromptDelivery,
)


class OutputCaptureConfig(BaseModel):
    """Optional configuration for CLIs that write output to disk."""

    flag_template: str = Field(..., description="Template used to inject the output path, e.g. '--output {path}'.")
    cleanup: bool = Field(
        default=True,
        description="Whether the temporary file should be removed after reading.",
    )


class CLIRoleConfig(BaseModel):
    """Role-specific configuration loaded from JSON manifests."""

    prompt_path: str | None = Field(
        default=None,
        description="Path to the prompt file that seeds this role.",
    )
    role_args: list[str] = Field(default_factory=list)
    description: str | None = Field(default=None)

    @field_validator("role_args", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [value]
        raise TypeError("role_args must be a list of strings or a single string")


class CLIClientConfig(BaseModel):
    """Raw CLI client configuration before internal defaults are applied."""

    name: str
    command: str | None = None
    working_dir: str | None = None
    additional_args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: PositiveInt | None = Field(default=None)
    roles: dict[str, CLIRoleConfig] = Field(default_factory=dict)
    output_to_file: OutputCaptureConfig | None = None
    parser: str | None = Field(
        default=None,
        description="Parser used to interpret CLI output. Overrides the internal default for this CLI.",
    )
    runner: str | None = Field(
        default=None,
        description="Agent runner providing CLI-specific behaviour. Defaults to the generic runner.",
    )
    parser_options: dict[str, Any] = Field(
        default_factory=dict,
        description="Parser-specific options, e.g. content_path for the generic json parser.",
    )
    prompt_delivery: PromptDelivery | None = Field(
        default=None,
        description="How the prompt reaches the CLI: piped to stdin, or appended to the command line.",
    )
    prompt_args: list[str] = Field(
        default_factory=list,
        description=(
            "Argument template used when prompt_delivery is 'argv'. Exactly one entry must contain "
            "the '{prompt}' placeholder, e.g. ['-p', '{prompt}']."
        ),
    )

    @field_validator("prompt_args", mode="before")
    @classmethod
    def _ensure_prompt_args_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [value]
        raise TypeError("prompt_args must be a list of strings or a single string")

    @field_validator("additional_args", mode="before")
    @classmethod
    def _ensure_args_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value]
        if isinstance(value, str):
            return [value]
        raise TypeError("additional_args must be a list of strings or a single string")


class ResolvedCLIRole(BaseModel):
    """Runtime representation of a CLI role with resolved prompt path."""

    name: str
    prompt_path: Path
    role_args: list[str] = Field(default_factory=list)
    description: str | None = None


class ResolvedCLIClient(BaseModel):
    """Runtime configuration after merging defaults and validating paths."""

    name: str
    executable: list[str]
    working_dir: Path | None
    internal_args: list[str] = Field(default_factory=list)
    config_args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int
    parser: str
    runner: str | None = None
    parser_options: dict[str, Any] = Field(default_factory=dict)
    prompt_delivery: PromptDelivery = DEFAULT_PROMPT_DELIVERY
    prompt_args: list[str] = Field(default_factory=list)
    roles: dict[str, ResolvedCLIRole]
    output_to_file: OutputCaptureConfig | None = None

    @model_validator(mode="after")
    def _check_prompt_delivery(self) -> ResolvedCLIClient:
        """Reject an argv client with no template.

        The registry enforces this when loading configuration, but a client
        constructed directly would otherwise fall back to stdin silently.
        """

        if self.prompt_delivery != "argv":
            return self
        occurrences = sum(arg.count(PROMPT_PLACEHOLDER) for arg in self.prompt_args)
        if occurrences != 1:
            raise ValueError(
                f"CLI '{self.name}' uses prompt_delivery 'argv' and must contain exactly one "
                f"'{PROMPT_PLACEHOLDER}' across prompt_args, found {occurrences}"
            )
        return self

    def build_prompt_args(self, prompt: str) -> list[str]:
        """Render the argv prompt template for this client.

        Returns an empty list when the prompt is delivered on stdin.
        """

        if self.prompt_delivery != "argv":
            return []
        return [
            arg.replace(TIMEOUT_PLACEHOLDER, str(self.timeout_seconds)).replace(PROMPT_PLACEHOLDER, prompt)
            for arg in self.prompt_args
        ]

    def list_roles(self) -> list[str]:
        return list(self.roles.keys())

    def get_role(self, role_name: str | None) -> ResolvedCLIRole:
        key = role_name or "default"
        if key not in self.roles:
            available = ", ".join(sorted(self.roles.keys()))
            raise KeyError(f"Role '{role_name}' not configured for CLI '{self.name}'. Available roles: {available}")
        return self.roles[key]
