"""Configuration registry for clink CLI integrations."""

from __future__ import annotations

import json
import logging
import shlex
from collections.abc import Iterable
from pathlib import Path

from clink.constants import (
    CONFIG_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    INTERNAL_DEFAULTS,
    PROJECT_ROOT,
    USER_CONFIG_DIR,
    CLIInternalDefaults,
)
from clink.models import (
    CLIClientConfig,
    CLIRoleConfig,
    ResolvedCLIClient,
    ResolvedCLIRole,
)
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
        if internal_defaults is None:
            raise RegistryLoadError(f"CLI '{raw.name}' is not supported by clink")

        executable = self._resolve_executable(raw, internal_defaults, source_path)

        internal_args = list(internal_defaults.additional_args) if internal_defaults else []
        config_args = list(raw.additional_args)

        timeout_seconds = raw.timeout_seconds or (
            internal_defaults.timeout_seconds if internal_defaults else DEFAULT_TIMEOUT_SECONDS
        )

        parser_name = internal_defaults.parser
        if not parser_name:
            raise RegistryLoadError(
                f"CLI '{raw.name}' must define a parser either in configuration or internal defaults"
            )

        runner_name = internal_defaults.runner if internal_defaults else None

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
