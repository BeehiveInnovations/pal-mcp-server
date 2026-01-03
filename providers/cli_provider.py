"""CLI Provider - Wraps external CLI tools as a standard ModelProvider interface.

This provider enables using CLI tools (Gemini CLI, Claude Code, Codex CLI) through
the same interface as API-based providers, allowing tools like Consensus to leverage
CLI free tiers for multi-model consultations.

Model naming convention:
    - cli:gemini      -> Gemini CLI with default role
    - cli:gemini:planner -> Gemini CLI with planner role
    - cli:claude      -> Claude Code CLI
    - cli:codex       -> Codex CLI
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, Optional

from .base import ModelProvider
from .shared import ModelCapabilities, ModelResponse, ProviderType

if TYPE_CHECKING:
    from clink import ClinkRegistry
    from clink.agents import AgentOutput
    from clink.models import ResolvedCLIClient, ResolvedCLIRole

logger = logging.getLogger(__name__)

# Model name prefix for CLI models
CLI_MODEL_PREFIX = "cli:"


class CLIProvider(ModelProvider):
    """Provider that wraps external CLI tools (Gemini CLI, Claude Code, Codex).

    This provider bridges the gap between PAL's provider interface and external
    CLI tools, enabling features like Consensus to use CLI free tiers instead
    of API calls.

    Key Features:
        - Supports Gemini CLI (1000 free requests/day)
        - Supports Claude Code CLI
        - Supports Codex CLI
        - Role-based execution (default, planner, codereviewer)
        - Thread-pool execution for async CLI calls in sync interface
    """

    FRIENDLY_NAME = "CLI"

    def __init__(self, api_key: str = "not-required", **kwargs):
        """Initialize CLI provider.

        Args:
            api_key: Not used for CLI provider, kept for interface compatibility.
            **kwargs: Additional configuration (unused).
        """
        super().__init__(api_key, **kwargs)

        # Lazy import to avoid circular dependencies
        from clink import get_registry

        self._registry: ClinkRegistry = get_registry()
        self._cli_names: list[str] = self._registry.list_clients()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=3,
            thread_name_prefix="cli-provider-",
        )

        # Build model capabilities dynamically from available CLIs
        self._build_model_capabilities()

        logger.info(
            "CLIProvider initialized with %d CLI clients: %s",
            len(self._cli_names),
            ", ".join(self._cli_names),
        )

    def _build_model_capabilities(self) -> None:
        """Build ModelCapabilities for each available CLI and role combination."""
        self.MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {}

        for cli_name in self._cli_names:
            roles = self._registry.list_roles(cli_name)

            for role in roles:
                # Build model name: cli:gemini, cli:gemini:planner
                if role == "default":
                    model_name = f"{CLI_MODEL_PREFIX}{cli_name}"
                    aliases = [f"cli-{cli_name}"]  # Alternative format
                else:
                    model_name = f"{CLI_MODEL_PREFIX}{cli_name}:{role}"
                    aliases = [f"cli-{cli_name}-{role}"]

                # Create capabilities for this CLI model
                self.MODEL_CAPABILITIES[model_name] = ModelCapabilities(
                    provider=ProviderType.CLI,
                    model_name=model_name,
                    friendly_name=f"CLI/{cli_name}" + (f" ({role})" if role != "default" else ""),
                    intelligence_score=15,  # High score - these are full CLI agents
                    description=f"External {cli_name.title()} CLI agent" + (f" with {role} role" if role != "default" else ""),
                    aliases=aliases,
                    context_window=200000,  # CLI can handle large contexts
                    max_output_tokens=32000,
                    max_thinking_tokens=0,
                    supports_extended_thinking=False,
                    supports_system_prompts=True,
                    supports_streaming=False,  # CLI output is not streamed
                    supports_function_calling=False,
                    supports_images=True,  # Most CLIs support images
                    supports_json_mode=False,
                    supports_temperature=False,  # CLI doesn't support temperature
                )

        logger.debug(
            "Built capabilities for %d CLI models: %s",
            len(self.MODEL_CAPABILITIES),
            list(self.MODEL_CAPABILITIES.keys()),
        )

    def get_provider_type(self) -> ProviderType:
        """Return the CLI provider type."""
        return ProviderType.CLI

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,  # Ignored for CLI
        max_output_tokens: Optional[int] = None,  # Ignored for CLI
        **kwargs,
    ) -> ModelResponse:
        """Generate content using an external CLI tool.

        Args:
            prompt: The prompt to send to the CLI.
            model_name: CLI model name (e.g., "cli:gemini", "cli:claude:planner").
            system_prompt: Optional system prompt (passed to CLI if supported).
            temperature: Ignored - CLI tools don't support temperature.
            max_output_tokens: Ignored - CLI tools manage their own output.
            **kwargs: Additional arguments:
                - files: List of file paths to include
                - images: List of image paths to include

        Returns:
            ModelResponse containing the CLI output.

        Raises:
            ValueError: If model name is invalid or CLI is not available.
            RuntimeError: If CLI execution fails.
        """
        # Resolve aliases first (e.g., cli-claude -> cli:claude)
        resolved_model = self._resolve_model_name(model_name)

        # Parse model name to get CLI name and role
        cli_name, role = self._parse_model_name(resolved_model)

        # Validate CLI is available
        if cli_name not in self._cli_names:
            raise ValueError(
                f"CLI '{cli_name}' is not configured. "
                f"Available CLIs: {', '.join(self._cli_names)}"
            )

        # Get CLI configuration
        try:
            client_config = self._registry.get_client(cli_name)
            role_config = client_config.get_role(role)
        except KeyError as exc:
            raise ValueError(f"Invalid CLI configuration: {exc}") from exc

        # Extract optional parameters
        files = kwargs.get("files", [])
        images = kwargs.get("images", [])

        logger.info(
            "CLIProvider: Executing %s (role=%s) with prompt length %d",
            cli_name,
            role,
            len(prompt),
        )

        # Execute CLI in thread pool (CLI execution is async, but Provider interface is sync)
        try:
            result = self._execute_cli_sync(
                client_config=client_config,
                role_config=role_config,
                prompt=prompt,
                system_prompt=system_prompt,
                files=files,
                images=images,
            )
        except Exception as exc:
            logger.exception("CLI execution failed for %s", model_name)
            raise RuntimeError(f"CLI '{cli_name}' execution failed: {exc}") from exc

        # Build response
        return ModelResponse(
            content=result.parsed.content,
            usage={
                "input_tokens": 0,  # CLI doesn't provide token counts
                "output_tokens": 0,
                "total_tokens": 0,
            },
            model_name=resolved_model,  # Use canonical name, not alias
            friendly_name=f"CLI/{cli_name}",
            provider=ProviderType.CLI,
            metadata={
                "cli_name": cli_name,
                "role": role,
                "return_code": result.returncode,
                "duration_seconds": round(result.duration_seconds, 3),
                "parser": result.parser_name,
                "original_model_name": model_name,  # Keep original for reference
            },
        )

    def _parse_model_name(self, model_name: str) -> tuple[str, str]:
        """Parse CLI model name into (cli_name, role).

        Args:
            model_name: Model name like "cli:gemini" or "cli:gemini:planner"

        Returns:
            Tuple of (cli_name, role)

        Raises:
            ValueError: If model name format is invalid.
        """
        if not model_name.startswith(CLI_MODEL_PREFIX):
            raise ValueError(
                f"Invalid CLI model name '{model_name}'. "
                f"Expected format: cli:<cli_name> or cli:<cli_name>:<role>"
            )

        parts = model_name[len(CLI_MODEL_PREFIX):].split(":")
        cli_name = parts[0]
        role = parts[1] if len(parts) > 1 else "default"

        return cli_name, role

    def _execute_cli_sync(
        self,
        client_config: "ResolvedCLIClient",
        role_config: "ResolvedCLIRole",
        prompt: str,
        system_prompt: Optional[str],
        files: list[str],
        images: list[str],
    ) -> "AgentOutput":
        """Execute CLI command synchronously using thread pool.

        This method bridges the async CLI execution with the sync Provider interface.
        """
        future = self._executor.submit(
            self._run_async_agent,
            client_config,
            role_config,
            prompt,
            system_prompt,
            files,
            images,
        )

        # Wait for result with timeout (CLI has its own timeout, add buffer)
        timeout = client_config.timeout_seconds + 30
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise RuntimeError(
                f"CLI execution timed out after {timeout}s"
            )

    def _run_async_agent(
        self,
        client_config: "ResolvedCLIClient",
        role_config: "ResolvedCLIRole",
        prompt: str,
        system_prompt: Optional[str],
        files: list[str],
        images: list[str],
    ) -> "AgentOutput":
        """Run async CLI agent in a new event loop.

        This runs in a separate thread to avoid blocking the main event loop.
        """
        from clink.agents import create_agent

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            agent = create_agent(client_config)
            return loop.run_until_complete(
                agent.run(
                    role=role_config,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    files=files,
                    images=images,
                )
            )
        finally:
            loop.close()

    def validate_model_name(self, model_name: str) -> bool:
        """Check if model name is a valid CLI model.

        Args:
            model_name: Model name to validate.

        Returns:
            True if this is a valid CLI model name.
        """
        # First, try to resolve aliases (e.g., cli-claude -> cli:claude)
        resolved = self._resolve_model_name(model_name)

        # Check if it's a CLI model (starts with cli:)
        if not resolved.startswith(CLI_MODEL_PREFIX):
            return False

        try:
            cli_name, role = self._parse_model_name(resolved)
        except ValueError:
            return False

        # Check if CLI is available
        if cli_name not in self._cli_names:
            return False

        # Check if role is valid
        roles = self._registry.list_roles(cli_name)
        return role in roles

    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model name (handles aliases).

        Args:
            model_name: Input model name or alias.

        Returns:
            Canonical model name.
        """
        # Check if it's already a valid model name
        if model_name in self.MODEL_CAPABILITIES:
            return model_name

        # Check aliases (case-insensitive)
        model_lower = model_name.lower()
        for canonical, caps in self.MODEL_CAPABILITIES.items():
            if canonical.lower() == model_lower:
                return canonical
            for alias in caps.aliases:
                if alias.lower() == model_lower:
                    return canonical

        return model_name

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Return capabilities for all CLI models."""
        return self.MODEL_CAPABILITIES

    def list_models(
        self,
        *,
        respect_restrictions: bool = True,
        include_aliases: bool = True,
        lowercase: bool = False,
        unique: bool = False,
    ) -> list[str]:
        """List available CLI models."""
        return ModelCapabilities.collect_model_names(
            self.MODEL_CAPABILITIES,
            include_aliases=include_aliases,
            lowercase=lowercase,
            unique=unique,
        )

    def close(self) -> None:
        """Clean up thread pool."""
        self._executor.shutdown(wait=False)
        logger.debug("CLIProvider thread pool shut down")
