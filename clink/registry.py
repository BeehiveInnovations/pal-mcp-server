"""Configuration registry for clink CLI integrations."""

from __future__ import annotations

import json
import logging
import shlex
import shutil
from collections.abc import Iterable
from pathlib import Path

from clink.agents import available_runners
from clink.constants import (
    CONFIG_DIR,
    DEFAULT_PROMPT_DELIVERY,
    DEFAULT_TIMEOUT_SECONDS,
    INTERNAL_DEFAULTS,
    PROJECT_ROOT,
    PROMPT_PLACEHOLDER,
    USER_CONFIG_DIR,
    CLIInternalDefaults,
)
from clink.models import (
    CLIClientConfig,
    CLIRoleConfig,
    ResolvedCLIClient,
    ResolvedCLIRole,
)
from clink.parsers import available_parsers
from utils.env import get_env
from utils.file_utils import read_json_file

logger = logging.getLogger("clink.registry")

CONFIG_ENV_VAR = "CLI_CLIENTS_CONFIG_PATH"


class RegistryLoadError(RuntimeError):
    """Raised when configuration files are invalid or missing critical data."""


class ClinkRegistry:
    """Loads CLI client definitions and exposes them for schema generation/runtime use."""

    def __init__(self) -> None:
        self._clients: dict[str, ResolvedCLIClient] = {}
        self._load()

    def _load(self) -> None:
        self._clients.clear()
        for config_path in self._iter_config_files():
            try:
                data = read_json_file(str(config_path))
            except json.JSONDecodeError as exc:
                raise RegistryLoadError(f"Invalid JSON in {config_path}: {exc}") from exc

            if not data:
                logger.debug("Skipping empty configuration file: %s", config_path)
                continue

            config = CLIClientConfig.model_validate(data)
            resolved = self._resolve_config(config, source_path=config_path)
            key = resolved.name.lower()
            if key in self._clients:
                logger.info("Overriding CLI configuration for '%s' from %s", resolved.name, config_path)
            else:
                logger.debug("Loaded CLI configuration for '%s' from %s", resolved.name, config_path)
            self._clients[key] = resolved

        if not self._clients:
            raise RegistryLoadError(
                "No CLI clients configured. Ensure conf/cli_clients contains at least one definition or set "
                f"{CONFIG_ENV_VAR}."
            )

    def reload(self) -> None:
        """Reload configurations from disk."""
        self._load()

    def list_clients(self) -> list[str]:
        return sorted(client.name for client in self._clients.values())

    def list_roles(self, cli_name: str) -> list[str]:
        config = self.get_client(cli_name)
        return sorted(config.roles.keys())

    def get_client(self, cli_name: str) -> ResolvedCLIClient:
        key = cli_name.lower()
        if key not in self._clients:
            available = ", ".join(self.list_clients())
            raise KeyError(f"CLI '{cli_name}' is not configured. Available clients: {available}")
        return self._clients[key]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _iter_config_files(self) -> Iterable[Path]:
        search_paths: list[Path] = []

        # 1. Built-in configs
        search_paths.append(CONFIG_DIR)

        # 2. CLI_CLIENTS_CONFIG_PATH environment override (file or directory)
        env_path_raw = get_env(CONFIG_ENV_VAR)
        if env_path_raw:
            env_path = Path(env_path_raw).expanduser()
            search_paths.append(env_path)

        # 3. User overrides in ~/.pal/cli_clients
        search_paths.append(USER_CONFIG_DIR)

        seen: set[Path] = set()

        for base in search_paths:
            if not base:
                continue
            if base in seen:
                continue
            seen.add(base)

            if base.is_file() and base.suffix.lower() == ".json":
                yield base
                continue

            if base.is_dir():
                for path in sorted(base.glob("*.json")):
                    if path.is_file():
                        yield path
            else:
                logger.debug("Configuration path does not exist: %s", base)

    def _resolve_config(self, raw: CLIClientConfig, *, source_path: Path) -> ResolvedCLIClient:
        if not raw.name:
            raise RegistryLoadError(f"CLI configuration at {source_path} is missing a 'name' field")

        normalized_name = raw.name.strip()
        internal_defaults = INTERNAL_DEFAULTS.get(normalized_name.lower())

        executable = self._resolve_executable(raw, internal_defaults, source_path)

        internal_args = list(internal_defaults.additional_args) if internal_defaults else []
        config_args = list(raw.additional_args)

        timeout_seconds = raw.timeout_seconds or (
            internal_defaults.timeout_seconds if internal_defaults else DEFAULT_TIMEOUT_SECONDS
        )

        parser_name = raw.parser or (internal_defaults.parser if internal_defaults else None)
        if not parser_name:
            raise RegistryLoadError(
                f"CLI '{raw.name}' must define a parser either in configuration or internal defaults. "
                f"Set \"parser\" in {source_path.name} to one of: {', '.join(available_parsers())}"
            )

        if parser_name.lower() not in available_parsers():
            raise RegistryLoadError(
                f"CLI '{raw.name}' refers to unknown parser '{parser_name}'. "
                f"Valid parsers: {', '.join(available_parsers())}"
            )

        runner_name = raw.runner or (internal_defaults.runner if internal_defaults else None)
        if runner_name and runner_name.lower() not in available_runners():
            # Without this an unknown runner silently falls back to the generic
            # agent, dropping CLI-specific error recovery with no diagnostic.
            raise RegistryLoadError(
                f"CLI '{raw.name}' refers to unknown runner '{runner_name}'. "
                f"Valid runners: {', '.join(available_runners())}"
            )

        prompt_delivery = raw.prompt_delivery or (
            internal_defaults.prompt_delivery if internal_defaults else DEFAULT_PROMPT_DELIVERY
        )
        if raw.prompt_args:
            prompt_args = list(raw.prompt_args)
        elif raw.prompt_delivery and internal_defaults and raw.prompt_delivery != internal_defaults.prompt_delivery:
            # The config deliberately changed delivery, so the bundled template
            # for the other mode must not be inherited on top of it.
            prompt_args = []
        else:
            prompt_args = list(internal_defaults.prompt_args) if internal_defaults else []
        if prompt_delivery == "argv":
            occurrences = sum(arg.count(PROMPT_PLACEHOLDER) for arg in prompt_args)
            if occurrences != 1:
                raise RegistryLoadError(
                    f"CLI '{raw.name}' uses prompt_delivery 'argv' and must contain exactly one "
                    f'\'{PROMPT_PLACEHOLDER}\' across prompt_args, e.g. ["-p", "{PROMPT_PLACEHOLDER}"]'
                )
        elif prompt_args:
            # Silently discarding these would look like the prompt was delivered.
            raise RegistryLoadError(
                f"CLI '{raw.name}' defines prompt_args but uses prompt_delivery '{prompt_delivery}'. "
                f"Set prompt_delivery to 'argv' or remove prompt_args."
            )

        env = self._merge_env(raw, internal_defaults)
        working_dir = self._resolve_optional_path(raw.working_dir, source_path.parent)
        roles = self._resolve_roles(raw, internal_defaults, source_path)

        output_to_file = raw.output_to_file

        return ResolvedCLIClient(
            name=normalized_name,
            executable=executable,
            internal_args=internal_args,
            config_args=config_args,
            env=env,
            timeout_seconds=int(timeout_seconds),
            parser=parser_name,
            runner=runner_name,
            parser_options=dict(raw.parser_options),
            prompt_delivery=prompt_delivery,
            prompt_args=prompt_args,
            roles=roles,
            output_to_file=output_to_file,
            working_dir=working_dir,
        )

    def _resolve_executable(
        self,
        raw: CLIClientConfig,
        internal_defaults: CLIInternalDefaults | None,
        source_path: Path,
    ) -> list[str]:
        command = raw.command
        if not command:
            raise RegistryLoadError(f"CLI '{raw.name}' must specify a 'command' in configuration")
        return shlex.split(command)

    def _merge_env(
        self,
        raw: CLIClientConfig,
        internal_defaults: CLIInternalDefaults | None,
    ) -> dict[str, str]:
        merged: dict[str, str] = {}
        if internal_defaults and internal_defaults.env:
            merged.update(internal_defaults.env)
        merged.update(raw.env)
        return merged

    def _resolve_roles(
        self,
        raw: CLIClientConfig,
        internal_defaults: CLIInternalDefaults | None,
        source_path: Path,
    ) -> dict[str, ResolvedCLIRole]:
        roles: dict[str, CLIRoleConfig] = dict(raw.roles)

        default_role_prompt = internal_defaults.default_role_prompt if internal_defaults else None
        if "default" not in roles:
            roles["default"] = CLIRoleConfig(prompt_path=default_role_prompt)
        elif roles["default"].prompt_path is None and default_role_prompt:
            roles["default"].prompt_path = default_role_prompt

        resolved: dict[str, ResolvedCLIRole] = {}
        for role_name, role_config in roles.items():
            prompt_path_str = role_config.prompt_path or default_role_prompt
            if not prompt_path_str:
                raise RegistryLoadError(f"Role '{role_name}' for CLI '{raw.name}' must define a prompt_path")
            prompt_path = self._resolve_prompt_path(prompt_path_str, source_path.parent)
            resolved[role_name] = ResolvedCLIRole(
                name=role_name,
                prompt_path=prompt_path,
                role_args=list(role_config.role_args),
                description=role_config.description,
            )
        return resolved

    def _resolve_prompt_path(self, prompt_path: str, base_dir: Path) -> Path:
        resolved = self._resolve_path(prompt_path, base_dir)
        if not resolved.exists():
            raise RegistryLoadError(f"Prompt file not found: {resolved}")
        return resolved

    def _resolve_optional_path(self, candidate: str | None, base_dir: Path) -> Path | None:
        if not candidate:
            return None
        return self._resolve_path(candidate, base_dir)

    def _resolve_path(self, candidate: str, base_dir: Path) -> Path:
        path = Path(candidate)
        if path.is_absolute():
            return path

        candidate_path = (base_dir / path).resolve()
        if candidate_path.exists():
            return candidate_path

        project_relative = (PROJECT_ROOT / path).resolve()
        return project_relative


_REGISTRY: ClinkRegistry | None = None


def get_registry() -> ClinkRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ClinkRegistry()
    return _REGISTRY


def available_cli_clients() -> list[str]:
    """Return the names of configured CLI clients whose executable is on PATH.

    Used to decide whether the server can run without an API provider: clink
    shells out to CLIs that authenticate themselves, so a machine with one of
    them installed needs no API key.
    """

    try:
        registry = get_registry()
    except RegistryLoadError:
        # Report the config problem, but do not let it replace the caller's
        # own diagnosis: this runs on the no-API-key path, where the missing
        # key is usually the real blocker.
        logger.warning("Could not load clink CLI clients while probing for installed CLIs", exc_info=True)
        return []

    available: list[str] = []
    for name in registry.list_clients():
        try:
            client = registry.get_client(name)
        except Exception:  # pragma: no cover - defensive
            continue
        if client.executable and shutil.which(client.executable[0]):
            available.append(name)
    return sorted(available)
