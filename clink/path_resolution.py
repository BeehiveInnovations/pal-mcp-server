"""Resolve CLI executables when the host PATH omits user-local installs."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _candidate_path_dirs() -> list[str]:
    """Return common directories for globally installed CLIs (nvm, npm, etc.)."""
    home = Path.home()
    candidates: list[str] = []

    nvm_dir = Path(os.environ.get("NVM_DIR", str(home / ".nvm")))
    versions_dir = nvm_dir / "versions" / "node"
    if versions_dir.is_dir():
        version_bins = sorted(versions_dir.glob("*/bin"), reverse=True)
        candidates.extend(str(path) for path in version_bins)

    for relative in (".local/bin", ".npm-global/bin", ".cargo/bin", "bin"):
        candidate = home / relative
        if candidate.is_dir():
            candidates.append(str(candidate))

    for system_path in ("/opt/homebrew/bin", "/usr/local/bin"):
        if Path(system_path).is_dir():
            candidates.append(system_path)

    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def augment_path(path: str | None, extra_dirs: list[str] | None = None) -> str:
    """Prepend discovered user-local directories to PATH."""
    dirs = extra_dirs if extra_dirs is not None else _candidate_path_dirs()
    if not dirs:
        return path or ""
    prefix = os.pathsep.join(dirs)
    if not path:
        return prefix
    return f"{prefix}{os.pathsep}{path}"


def resolve_cli_executable(name: str, *, path: str | None = None) -> str | None:
    """Locate a CLI executable, including npm/nvm global install locations."""
    current_path = path if path is not None else os.environ.get("PATH")

    resolved = shutil.which(name, path=current_path)
    if resolved is not None:
        return resolved

    augmented = augment_path(current_path)
    if augmented == current_path:
        return None

    return shutil.which(name, path=augmented)
