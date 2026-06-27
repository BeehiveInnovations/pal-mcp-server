"""Tests for clink CLI executable path resolution."""

from __future__ import annotations

import os
import stat

from clink.path_resolution import augment_path, resolve_cli_executable


def test_resolve_cli_executable_uses_existing_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    codex_path = bin_dir / "codex"
    codex_path.write_text("#!/bin/sh\necho codex\n")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("PATH", str(bin_dir))

    assert resolve_cli_executable("codex") == str(codex_path)


def test_resolve_cli_executable_finds_nvm_global_install(tmp_path, monkeypatch):
    nvm_bin = tmp_path / ".nvm" / "versions" / "node" / "v22.0.0" / "bin"
    nvm_bin.mkdir(parents=True)
    codex_path = nvm_bin / "codex"
    codex_path.write_text("#!/bin/sh\necho codex\n")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("NVM_DIR", str(tmp_path / ".nvm"))
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    assert resolve_cli_executable("codex") == str(codex_path)


def test_resolve_cli_executable_returns_none_when_missing(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("HOME", "/nonexistent-home")

    assert resolve_cli_executable("definitely-missing-cli") is None


def test_augment_path_prepends_candidate_dirs(tmp_path, monkeypatch):
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))

    augmented = augment_path("/usr/bin")
    assert str(local_bin) in augmented.split(os.pathsep)
    assert augmented.endswith("/usr/bin") or "/usr/bin" in augmented.split(os.pathsep)
