"""Base class for CLI-based model providers.

CLI providers execute requests through locally installed CLI tools rather than
making direct API calls. This allows using OAuth-authenticated CLI tools with
subscription-based unlimited usage.

This module leverages the existing `clink` infrastructure for CLI execution.
"""

import asyncio
import logging
import shutil
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional, TypeVar

from clink import get_registry
from clink.agents import create_agent
from clink.models import ResolvedCLIClient
from providers.base import ModelProvider
from providers.shared import ModelCapabilities, ModelResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CLIModelProvider(ModelProvider):
    """Abstract base class for CLI-based model providers.

    CLI providers wrap locally installed CLI tools (gemini, claude, codex) and
    execute requests through the clink infrastructure. This enables using
    OAuth-authenticated CLI tools instead of API keys.

    The clink module handles:
    - CLI command building
    - Process execution and timeout handling
    - Output parsing
    - Error recovery

    Subclasses must implement:
    - get_provider_type(): Return the specific CLI provider type
    - get_cli_name(): Return the clink client name (gemini, claude, codex)
    - get_supported_models(): Return dict of model name -> ModelCapabilities
    """

    # Default timeout for CLI operations (in seconds)
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self, **kwargs):
        """Initialize CLI provider.

        Unlike API providers, CLI providers don't require an API key since
        they use the CLI tool's OAuth authentication.

        Args:
            **kwargs: Additional configuration options

        Raises:
            RuntimeError: If the CLI tool is not installed
        """
        # CLI providers don't need API keys - pass empty string to satisfy base class
        super().__init__(api_key="", **kwargs)

        self.cli_name = self.get_cli_name()

        # Check if CLI tool is installed
        if not shutil.which(self.cli_name):
            raise RuntimeError(
                f"CLI tool '{self.cli_name}' is not installed or not accessible. "
                f"Please install it and ensure it's in your PATH."
            )

        # Get clink client configuration
        try:
            self._registry = get_registry()
            self._client: ResolvedCLIClient = self._registry.get_client(self.cli_name)
        except KeyError as e:
            raise RuntimeError(
                f"CLI client '{self.cli_name}' is not configured in clink. "
                f"Ensure conf/cli_clients/{self.cli_name}.json exists."
            ) from e

        # Initialize model capabilities
        self._model_capabilities = self.get_supported_models()

        logger.info(
            f"Initialized {self.__class__.__name__} using {self.cli_name} CLI "
            f"with {len(self._model_capabilities)} supported models"
        )

    @abstractmethod
    def get_cli_name(self) -> str:
        """Return the clink client name this provider uses.

        Returns:
            CLI client name as configured in clink (e.g., 'gemini', 'claude', 'codex')
        """

    @abstractmethod
    def get_supported_models(self) -> dict[str, ModelCapabilities]:
        """Return the models supported by this CLI provider.

        Returns:
            Dict mapping model names to their ModelCapabilities
        """

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        """Return all supported model capabilities."""
        return self._model_capabilities

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the CLI tool.

        Args:
            prompt: The main user prompt
            model_name: Model to use for the request
            system_prompt: Optional system prompt
            temperature: Temperature setting for the model
            max_output_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with the generated content

        Raises:
            ValueError: If model is not supported
            RuntimeError: If CLI execution fails
        """
        self.validate_parameters(model_name, temperature)

        # Validate model
        resolved_model = self._resolve_model_name(model_name)
        if not self.validate_model_name(resolved_model):
            raise ValueError(f"Model '{model_name}' is not supported by {self.__class__.__name__}")

        # Get role from kwargs or use default
        role_name = kwargs.get("role", "default")

        # Collect all optional params for the clink agent
        cli_params = kwargs.copy()
        cli_params["temperature"] = temperature
        if max_output_tokens:
            cli_params["max_output_tokens"] = max_output_tokens

        result = self._run_coroutine_sync(
            lambda: self._execute_cli(prompt, system_prompt, role_name, resolved_model, cli_params)
        )

        return result

    def _run_coroutine_sync(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """Run an async coroutine from sync code safely.

        This provider is called from both sync and async code paths. When an event
        loop is already running in the current thread, we cannot call
        ``run_until_complete``. In that case we execute the coroutine on a fresh
        event loop in a dedicated thread.
        """

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_factory())

        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="pal-cli-provider") as executor:
            future = executor.submit(lambda: asyncio.run(coro_factory()))
            return future.result()

    async def _execute_cli(
        self,
        prompt: str,
        system_prompt: Optional[str],
        role_name: str,
        model_name: str,
        cli_params: dict,
    ) -> ModelResponse:
        """Execute CLI request asynchronously.

        Args:
            prompt: The prepared prompt
            system_prompt: The system prompt, if any
            role_name: The clink role to use
            model_name: The specific model to use for the request
            cli_params: Additional parameters for the clink agent

        Returns:
            ModelResponse with the generated content
        """
        from clink.agents import CLIAgentError

        # Get role configuration
        try:
            role_config = self._client.get_role(role_name)
        except KeyError:
            # Fall back to default role
            logger.warning(f"Role '{role_name}' not found for '{self.cli_name}', " f"falling back to 'default' role.")
            role_config = self._client.get_role("default")

        role_prompt_text = ""
        try:
            role_prompt_text = role_config.prompt_path.read_text(encoding="utf-8").strip()
        except Exception as exc:  # pragma: no cover - defensive against unexpected filesystem issues
            logger.warning("Failed to read role prompt for %s/%s: %s", self.cli_name, role_config.name, exc)

        user_system_prompt = (system_prompt or "").strip()
        system_prompt_parts = [part for part in (role_prompt_text, user_system_prompt) if part]
        effective_system_prompt = "\n\n".join(system_prompt_parts) if system_prompt_parts else None

        runner_name = (self._client.runner or self._client.name).lower()
        prompt_text = prompt
        system_prompt_arg = effective_system_prompt
        if effective_system_prompt and runner_name != "claude":
            # For CLIs without a system prompt flag, embed system prompt text into
            # the user prompt so behavior remains consistent across runners.
            prompt_text = f"{effective_system_prompt}\n\n{prompt}"
            system_prompt_arg = None

        # Create agent and execute
        agent = create_agent(self._client)

        # Extract files and images from cli_params, pass remaining as kwargs
        # Note: The clink agent.run() may not support all params - it will use what it can
        cli_params.pop("role", None)  # Remove role to avoid conflict with role_config
        files = cli_params.pop("files", [])
        images = cli_params.pop("images", [])
        try:
            result = await agent.run(
                role=role_config,
                prompt=prompt_text,
                system_prompt=system_prompt_arg,
                files=files,
                images=images,
                **cli_params,
            )
        except CLIAgentError as exc:
            raise RuntimeError(f"CLI '{self.cli_name}' execution failed: {exc}") from exc

        # Extract content and build response with robustness check
        if not result.parsed or not hasattr(result.parsed, "content"):
            raise RuntimeError(f"CLI '{self.cli_name}' returned unexpected or unparsable output.")
        content = result.parsed.content

        # Build usage estimate
        usage = self._create_usage_estimate(prompt, content)

        return ModelResponse(
            content=content,
            usage=usage,
            model_name=model_name,  # Use the requested model name
            friendly_name=f"{self.cli_name.title()} CLI",
            provider=self.get_provider_type(),
            metadata={
                "cli_name": self.cli_name,
                "role": role_config.name,
                "duration_seconds": result.duration_seconds,
                "return_code": result.returncode,
                **(result.parsed.metadata or {}),
            },
        )

    def _get_default_model_name(self) -> str:
        """Get the default model name for this CLI."""
        # Return first model in capabilities
        if self._model_capabilities:
            return next(iter(self._model_capabilities.keys()))
        return f"{self.cli_name}-default"

    def _create_usage_estimate(
        self,
        prompt: str,
        response: str,
    ) -> dict[str, Any]:
        """Create estimated token usage for CLI responses.

        CLI tools don't always report token usage, so we estimate it based on
        a rough heuristic of ~4 characters per token. This is not precise.

        Args:
            prompt: The input prompt
            response: The generated response

        Returns:
            Dict with estimated token counts
        """
        # Rough estimate: ~4 characters per token
        input_tokens = max(1, len(prompt) // 4)
        output_tokens = max(1, len(response) // 4)

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }


def is_cli_available(cli_name: str) -> bool:
    """Check if a CLI tool is installed and configured.

    Args:
        cli_name: Name of the CLI tool (gemini, claude, codex)

    Returns:
        True if the CLI is installed and configured in clink
    """
    # Check if command exists
    if not shutil.which(cli_name):
        return False

    # Check if configured in clink
    try:
        registry = get_registry()
        registry.get_client(cli_name)
        return True
    except KeyError:
        return False
    except (OSError, ValueError, TypeError) as e:
        logger.warning(f"Error checking clink config for {cli_name}: {e}")
        return False


def get_available_cli_tools() -> list[str]:
    """Get list of available CLI tools.

    Returns:
        List of CLI names that are installed and configured
    """
    return [cli_name for cli_name in ["gemini", "claude", "codex"] if is_cli_available(cli_name)]
