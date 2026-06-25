"""PATH augmentation helpers for resolving npm-managed CLI executables."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def _dedupe_path_entries(entries: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        if entry and entry not in seen:
            seen.add(entry)
            ordered.append(entry)
    return ordered


def _nvm_node_bin_dirs(nvm_dir: Path) -> list[str]:
    """Return nvm node bin directories, preferring the default alias when set."""
    candidates: list[str] = []

    default_alias = nvm_dir / "alias" / "default"
    if default_alias.is_file():
        version = default_alias.read_text(encoding="utf-8").strip()
        if version and not version.startswith("v"):
            version = f"v{version}"
        alias_bin = nvm_dir / "versions" / "node" / version / "bin"
        if alias_bin.is_dir():
            candidates.append(str(alias_bin))

    versions_dir = nvm_dir / "versions" / "node"
    if versions_dir.is_dir():

        def version_key(path: Path) -> list[int]:
            return [int(part) for part in re.findall(r"\d+", path.parent.name)]

        for node_bin in sorted(versions_dir.glob("*/bin"), key=version_key, reverse=True):
            candidates.append(str(node_bin))

    return candidates


def collect_cli_path_candidates() -> list[str]:
    """Collect directories where npm-managed global CLIs are commonly installed."""
    home = Path.home()
    candidates: list[str] = []

    nvm_dir = Path(os.environ.get("NVM_DIR", str(home / ".nvm")))
    if nvm_dir.is_dir():
        candidates.extend(_nvm_node_bin_dirs(nvm_dir))

    fnm_multishell = os.environ.get("FNM_MULTISHELL_PATH")
    if fnm_multishell:
        candidates.append(fnm_multishell)

    for path in (
        home / ".local" / "share" / "fnm" / "aliases" / "default" / "bin",
        home / ".volta" / "bin",
        home / ".asdf" / "shims",
        home / ".local" / "share" / "mise" / "shims",
        home / ".local" / "bin",
        home / ".npm-global" / "bin",
    ):
        if path.is_dir():
            candidates.append(str(path))

    return _dedupe_path_entries(candidates)


def augment_path(path: str | None = None) -> str:
    """Prepend common npm/node version-manager bin directories to PATH."""
    current = path if path is not None else os.environ.get("PATH", "")
    current_parts = current.split(os.pathsep) if current else []
    return os.pathsep.join(_dedupe_path_entries(collect_cli_path_candidates() + current_parts))


def resolve_executable(executable_name: str, *, path: str | None = None) -> str | None:
    """Resolve a CLI executable, searching augmented PATH when needed."""
    search_path = augment_path(path)
    return shutil.which(executable_name, path=search_path)
