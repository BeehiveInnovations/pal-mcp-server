"""Tests for CLI executable PATH augmentation (issue #442)."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from clink.path_utils import augment_path, collect_cli_path_candidates, resolve_executable


def test_collect_cli_path_candidates_includes_nvm_default_alias(tmp_path, monkeypatch):
    nvm_dir = tmp_path / ".nvm"
    bin_dir = nvm_dir / "versions" / "node" / "v22.1.0" / "bin"
    bin_dir.mkdir(parents=True)
    (nvm_dir / "alias" / "default").parent.mkdir(parents=True)
    (nvm_dir / "alias" / "default").write_text("v22.1.0", encoding="utf-8")

    monkeypatch.setenv("NVM_DIR", str(nvm_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    candidates = collect_cli_path_candidates()
    assert str(bin_dir) in candidates


def test_collect_cli_path_candidates_includes_nvm_versions_without_alias(tmp_path, monkeypatch):
    nvm_dir = tmp_path / ".nvm"
    bin_dir = nvm_dir / "versions" / "node" / "v20.11.0" / "bin"
    bin_dir.mkdir(parents=True)

    monkeypatch.setenv("NVM_DIR", str(nvm_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    candidates = collect_cli_path_candidates()
    assert str(bin_dir) in candidates


def test_collect_cli_path_candidates_orders_nvm_versions_semantically(tmp_path, monkeypatch):
    nvm_dir = tmp_path / ".nvm"
    older_bin = nvm_dir / "versions" / "node" / "v9.0.0" / "bin"
    newer_bin = nvm_dir / "versions" / "node" / "v22.1.0" / "bin"
    older_bin.mkdir(parents=True)
    newer_bin.mkdir(parents=True)

    monkeypatch.setenv("NVM_DIR", str(nvm_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    candidates = collect_cli_path_candidates()
    assert candidates.index(str(newer_bin)) < candidates.index(str(older_bin))


def test_augment_path_prepends_candidates_before_existing_entries(tmp_path, monkeypatch):
    nvm_dir = tmp_path / ".nvm"
    bin_dir = nvm_dir / "versions" / "node" / "v22.1.0" / "bin"
    bin_dir.mkdir(parents=True)
    (nvm_dir / "alias" / "default").parent.mkdir(parents=True)
    (nvm_dir / "alias" / "default").write_text("v22.1.0", encoding="utf-8")

    monkeypatch.setenv("NVM_DIR", str(nvm_dir))
    monkeypatch.setenv("HOME", str(tmp_path))

    augmented = augment_path("/usr/bin")
    parts = augmented.split(os.pathsep)
    assert parts[0] == str(bin_dir)
    assert parts[-1] == "/usr/bin"


def test_resolve_executable_finds_binary_in_nvm_bin_dir(tmp_path, monkeypatch):
    nvm_dir = tmp_path / ".nvm"
    bin_dir = nvm_dir / "versions" / "node" / "v22.1.0" / "bin"
    bin_dir.mkdir(parents=True)
    codex_path = bin_dir / "codex"
    codex_path.write_text("#!/bin/sh\necho codex\n", encoding="utf-8")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    (nvm_dir / "alias" / "default").parent.mkdir(parents=True)
    (nvm_dir / "alias" / "default").write_text("v22.1.0", encoding="utf-8")

    monkeypatch.setenv("NVM_DIR", str(nvm_dir))
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")

    resolved = resolve_executable("codex")
    assert resolved == str(codex_path)


def test_resolve_executable_prefers_existing_path_entry(tmp_path, monkeypatch):
    primary_bin = tmp_path / "primary" / "bin"
    primary_bin.mkdir(parents=True)
    codex_path = primary_bin / "codex"
    codex_path.write_text("#!/bin/sh\necho primary\n", encoding="utf-8")
    codex_path.chmod(codex_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", str(primary_bin))

    resolved = resolve_executable("codex")
    assert resolved == str(codex_path)
