"""ChatGPT-plan models used as plain single-turn models through the Codex CLI.

The OpenAI API has no supported login flow for third-party apps, but the Codex CLI signs in with a
ChatGPT plan (``codex login``). This provider runs ``codex exec`` once per request with everything that
makes Codex an agent turned down: the user's Codex config (MCP servers, plugins) is not loaded, the
sandbox is read-only, the working directory is an empty temp dir, and no session is saved. PAL's system
prompt goes in as Codex developer instructions and the prompt goes in on stdin.

Model names are namespaced ``chatgpt/<codex model slug>`` (``conf/chatgpt_models.json``) so they never
collide with the OpenAI or Azure catalogues, and so nobody mistakes them for agentic Codex runs.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from tools.models import ToolModelCategory

from utils.env import get_env
from utils.image_utils import validate_image

from .base import ModelProvider
from .registries.chatgpt import ChatGPTModelRegistry
from .registry_provider_mixin import RegistryBackedProviderMixin
from .shared import ModelCapabilities, ModelResponse, ProviderType
from .shared.effort import resolve_reasoning_effort

logger = logging.getLogger(__name__)

MODEL_PREFIX = "chatgpt/"
DEFAULT_TIMEOUT_SECONDS = 600

# Codex sends its own agent instructions with every request. This note, placed before PAL's system
# prompt, keeps the model answering from the prompt instead of reaching for tools in an empty sandbox.
_MODEL_ONLY_NOTE = (
    "You are being called as a plain language model by another application. Everything you need is in "
    "the user message. Answer it directly in one reply. Do not run commands, read files or use tools."
)

# Credentials that would make Codex bill an API key instead of the ChatGPT login.
_API_KEY_ENV_VARS = ("OPENAI_API_KEY", "CODEX_API_KEY")

_TRANSIENT_ERROR_MARKERS = (
    "stream disconnected",
    "connection",
    "network",
    "temporarily unavailable",
    "500",
    "502",
    "503",
    "504",
)
_AUTH_ERROR_MARKERS = ("401", "unauthorized", "not logged in", "codex login", "please log in", "authentication")

_IMAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}


class ChatGPTCLIError(RuntimeError):
    """A ``codex exec`` run that failed, with whether trying again could help."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class ChatGPTModelProvider(RegistryBackedProviderMixin, ModelProvider):
    """Single-turn calls to ChatGPT-plan models through ``codex exec``."""

    FRIENDLY_NAME = "ChatGPT"
    REGISTRY_CLASS = ChatGPTModelRegistry
    MODEL_CAPABILITIES: ClassVar[dict[str, ModelCapabilities]] = {}

    def __init__(self, api_key: str = "", **kwargs):
        """Initialize the provider. ``api_key`` is unused: Codex authenticates with its own login.

        Optional kwargs: ``command`` (default ``CHATGPT_CODEX_COMMAND`` or ``codex``) and
        ``timeout_seconds`` (default ``CHATGPT_TIMEOUT_SECONDS`` or 600).
        """
        self._ensure_registry()
        super().__init__(api_key, **kwargs)
        self._command = kwargs.get("command") or codex_command()
        self._timeout_seconds = kwargs.get("timeout_seconds") or _env_timeout()
        self._invalidate_capability_cache()

    def get_provider_type(self) -> ProviderType:
        return ProviderType.CHATGPT

    # ------------------------------------------------------------------
    # Request execution
    # ------------------------------------------------------------------
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_output_tokens: int | None = None,
        thinking_mode: str | None = None,
        images: list[str] | None = None,
        **kwargs,
    ) -> ModelResponse:
        """Run one ``codex exec`` turn and return its final message.

        ``temperature`` and ``max_output_tokens`` cannot be set through the Codex CLI and are ignored.
        """
        capabilities = self.get_capabilities(model_name)
        resolved_model_name = self._resolve_model_name(model_name)
        slug = resolved_model_name.removeprefix(MODEL_PREFIX)
        effort = resolve_reasoning_effort(thinking_mode, capabilities)
        executable = self._resolve_executable()

        if max_output_tokens:
            logger.debug("ChatGPT (%s): max_output_tokens=%s is not supported and is ignored", slug, max_output_tokens)

        with tempfile.TemporaryDirectory(prefix="pal-chatgpt-") as workdir:
            image_paths: list[str] = []
            if images and capabilities.supports_images:
                image_paths = self._write_images(images, Path(workdir), capabilities.max_image_size_mb)
            elif images:
                logger.warning(
                    "Model %s does not support images, ignoring %d image(s)", resolved_model_name, len(images)
                )

            # Codex treats the -C directory as its workspace. Keep it empty: images live in a sibling
            # folder so the model has nothing to explore.
            workspace = Path(workdir) / "workspace"
            workspace.mkdir()
            command = self.build_command(
                executable=executable,
                slug=slug,
                workspace=str(workspace),
                effort=effort,
                system_prompt=system_prompt,
                image_paths=image_paths,
            )

            def _attempt() -> ModelResponse:
                return self._run_once(command, prompt, str(workspace), resolved_model_name, effort)

            return self._run_with_retries(
                operation=_attempt,
                max_attempts=2,
                delays=[2],
                log_prefix=f"ChatGPT via Codex CLI ({slug})",
            )

    @staticmethod
    def build_command(
        *,
        executable: str,
        slug: str,
        workspace: str,
        effort: str | None,
        system_prompt: str | None,
        image_paths: list[str],
    ) -> list[str]:
        """Return the ``codex exec`` argument list for one model-only turn (the prompt goes on stdin)."""
        instructions = _MODEL_ONLY_NOTE
        if system_prompt:
            instructions = f"{_MODEL_ONLY_NOTE}\n\n{system_prompt}"

        command = [
            executable,
            "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--cd",
            workspace,
            "--model",
            slug,
        ]
        # --image takes several values, so the images go before the next flag rather than before "-".
        for path in image_paths:
            command += ["--image", path]
        command += [
            "--config",
            'forced_login_method="chatgpt"',
            "--config",
            f"developer_instructions={_toml_string(instructions)}",
        ]
        if effort:
            command += ["--config", f"model_reasoning_effort={_toml_string(effort)}"]
        command.append("-")
        return command

    def _run_once(
        self,
        command: list[str],
        prompt: str,
        workspace: str,
        resolved_model_name: str,
        effort: str | None,
    ) -> ModelResponse:
        logger.debug("ChatGPT: running %s", " ".join(_redact_command(command)))
        start = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                input=prompt.encode("utf-8"),
                capture_output=True,
                cwd=workspace,
                env=_child_environment(),
                timeout=self._timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ChatGPTCLIError(
                f"Codex CLI did not answer within {self._timeout_seconds}s "
                "(raise CHATGPT_TIMEOUT_SECONDS for long prompts or high effort)"
            ) from exc
        except OSError as exc:
            raise ChatGPTCLIError(f"Could not start the Codex CLI ({command[0]}): {exc}") from exc
        duration = time.monotonic() - start

        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        result = parse_codex_events(stdout)

        if result["message"] is None:
            raise _classify_failure(completed.returncode, result["errors"], stderr)
        if completed.returncode != 0:
            logger.warning(
                "ChatGPT: Codex CLI exited with status %s but returned a reply; using it", completed.returncode
            )

        usage = _usage_from_codex(result["usage"])
        logger.debug(
            "ChatGPT: %s answered in %.1fs (%s input / %s output tokens)",
            resolved_model_name,
            duration,
            usage.get("input_tokens", "?"),
            usage.get("output_tokens", "?"),
        )
        return ModelResponse(
            content=result["message"],
            usage=usage,
            model_name=resolved_model_name,
            friendly_name=self.FRIENDLY_NAME,
            provider=ProviderType.CHATGPT,
            metadata={
                "reasoning_effort": effort,
                "duration_seconds": round(duration, 2),
                "cached_input_tokens": (result["usage"] or {}).get("cached_input_tokens"),
                "reasoning_output_tokens": (result["usage"] or {}).get("reasoning_output_tokens"),
                "finish_reason": "stop",
            },
        )

    def _resolve_executable(self) -> str:
        resolved = shutil.which(self._command)
        if resolved is None:
            raise ChatGPTCLIError(
                f"The Codex CLI ('{self._command}') was not found on PATH. Install it (for example "
                "`npm install -g @openai/codex` or `brew install codex`), run `codex login`, or set "
                "CHATGPT_CODEX_COMMAND to its full path."
            )
        return resolved

    @staticmethod
    def _write_images(images: list[str], directory: Path, max_size_mb: float | None) -> list[str]:
        """Validate each image (path or data URL) and copy it to a temp file Codex can attach."""
        image_dir = directory / "images"
        image_dir.mkdir()
        paths: list[str] = []
        for index, image in enumerate(images):
            try:
                data, mime_type = validate_image(image, max_size_mb)
            except ValueError as exc:
                logger.warning("ChatGPT: skipping image %d: %s", index + 1, exc)
                continue
            path = image_dir / f"image-{index + 1}{_IMAGE_EXTENSIONS.get(mime_type, '.png')}"
            path.write_bytes(data)
            paths.append(str(path))
        return paths

    def _is_error_retryable(self, error: Exception) -> bool:
        return isinstance(error, ChatGPTCLIError) and error.retryable

    # ------------------------------------------------------------------
    # Model selection
    # ------------------------------------------------------------------
    def get_preferred_model(self, category: ToolModelCategory, allowed_models: list[str]) -> str | None:
        """Pick a model for a tool category: the fastest tier for quick answers, else the highest scored."""
        from tools.models import ToolModelCategory

        capability_map = self.get_all_model_capabilities()
        candidates = [name for name in allowed_models if name in capability_map]
        if not candidates:
            return None

        def rank(name: str) -> tuple[int, float, str]:
            caps = capability_map[name]
            return (caps.intelligence_score, caps.aa_index if caps.aa_index is not None else -1.0, name)

        if category == ToolModelCategory.FAST_RESPONSE:
            luna = [name for name in candidates if name.endswith("-luna")]
            return max(luna, key=rank) if luna else min(candidates, key=rank)
        return max(candidates, key=rank)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def codex_command() -> str:
    """Return the configured Codex CLI command (``CHATGPT_CODEX_COMMAND``, default ``codex``)."""
    return get_env("CHATGPT_CODEX_COMMAND") or "codex"


def codex_login_problem(executable: str) -> str | None:
    """Return why the installed Codex CLI cannot serve ChatGPT models, or None when it is signed in to ChatGPT.

    Runs ``codex login status``, which reads the local login without calling a model.
    """
    try:
        status = subprocess.run(
            [executable, "login", "status"],
            capture_output=True,
            env=_child_environment(),
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"`codex login status` failed: {exc}"
    output = (status.stdout + status.stderr).decode("utf-8", errors="replace").strip()
    if status.returncode != 0:
        return f"the Codex CLI is not signed in (run `codex login`): {_last_lines(output)}"
    if "chatgpt" not in output.lower():
        return f"the Codex CLI is not signed in with ChatGPT (run `codex login` and choose ChatGPT): {output}"
    return None


def parse_codex_events(stdout: str) -> dict[str, Any]:
    """Pull the final reply, usage and errors out of ``codex exec --json`` output.

    Codex prints one JSON event per line. The reply is the last ``agent_message`` item; an earlier one
    would be commentary before a tool call. Error events never count as a reply.
    """
    message: str | None = None
    usage: dict[str, Any] | None = None
    errors: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "item.completed":
            item = event.get("item") or {}
            text = item.get("text")
            if item.get("type") == "agent_message" and isinstance(text, str) and text.strip():
                message = text.strip()
        elif event_type == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
        elif event_type == "error" and event.get("message"):
            errors.append(str(event["message"]))
        elif event_type == "turn.failed":
            error = event.get("error") or {}
            if error.get("message"):
                errors.append(str(error["message"]))
    return {"message": message, "usage": usage, "errors": errors}


def _classify_failure(returncode: int, errors: list[str], stderr: str) -> ChatGPTCLIError:
    detail = "; ".join(errors) or _last_lines(stderr) or "no reply and no error message"
    lowered = detail.lower()
    if any(marker in lowered for marker in ("usage limit", "rate limit", "429")):
        return ChatGPTCLIError(f"ChatGPT plan usage limit reached: {detail}")
    if any(marker in lowered for marker in _AUTH_ERROR_MARKERS):
        return ChatGPTCLIError(f"Codex CLI is not signed in to ChatGPT (run `codex login`): {detail}")
    retryable = any(marker in lowered for marker in _TRANSIENT_ERROR_MARKERS)
    return ChatGPTCLIError(f"Codex CLI failed (exit status {returncode}): {detail}", retryable=retryable)


def _usage_from_codex(usage: dict[str, Any] | None) -> dict[str, int]:
    if not usage:
        return {}
    result: dict[str, int] = {}
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if isinstance(input_tokens, int):
        result["input_tokens"] = input_tokens
    if isinstance(output_tokens, int):
        result["output_tokens"] = output_tokens
    if "input_tokens" in result and "output_tokens" in result:
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"]
    return result


def _toml_string(value: str) -> str:
    """Quote ``value`` as a TOML basic string for ``codex --config key=value``.

    JSON string escapes (``\\"``, ``\\\\``, ``\\n``, ``\\uXXXX``) are all valid TOML. Non-ASCII stays
    literal because TOML rejects the surrogate pairs JSON would emit for characters outside the BMP.
    """
    return json.dumps(value, ensure_ascii=False)


def _redact_command(command: list[str]) -> list[str]:
    """Replace the developer instructions (PAL's system prompt) with their length for logging."""
    redacted = []
    for arg in command:
        if arg.startswith("developer_instructions="):
            arg = f"developer_instructions=<{len(arg) - len('developer_instructions=')} chars>"
        redacted.append(arg)
    return redacted


def _child_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in _API_KEY_ENV_VARS:
        env.pop(name, None)
    return env


def _env_timeout() -> int:
    raw = get_env("CHATGPT_TIMEOUT_SECONDS")
    if not raw:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        value = int(raw)
    except ValueError:
        logger.warning("CHATGPT_TIMEOUT_SECONDS=%r is not a whole number; using %ss", raw, DEFAULT_TIMEOUT_SECONDS)
        return DEFAULT_TIMEOUT_SECONDS
    return value if value > 0 else DEFAULT_TIMEOUT_SECONDS


def _last_lines(text: str, count: int = 3) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return " | ".join(lines[-count:])
