"""Regression tests for the executor-level authorization boundary (authz.py)
and its enforcement inside Toolbelt.execute. These prove a model CANNOT widen
the user's authorized scope regardless of what it emits."""

from __future__ import annotations

import os

import pytest

from providers.tooling import authz
from providers.tooling.authz import ToolScope


def _explicit(paths, cwd="/repo"):
    return ToolScope(intent="git_push", authorized_paths=tuple(paths),
                     scope_mode="explicit", cwd=cwd)


# --- git command analysis --------------------------------------------------
def test_analyze_detects_stage_all():
    for cmd in ("git add .", "git add -A", "git add --all", "git add -u"):
        ops = authz.analyze_git_command(cmd)
        assert ops and ops[0].stages_all, cmd


def test_analyze_commit_a_stages_all():
    assert authz.analyze_git_command("git commit -am 'x'")[0].stages_all
    assert authz.analyze_git_command("git commit -a")[0].stages_all


def test_analyze_explicit_paths():
    op = authz.analyze_git_command("git add README.md src/app.js")[0]
    assert op.sub == "add" and op.paths == ["README.md", "src/app.js"]
    assert not op.stages_all


def test_analyze_compound_and_global_flags():
    ops = authz.analyze_git_command("cd /repo && git -C /repo add . && git push")
    subs = {o.sub for o in ops}
    assert "add" in subs and "push" in subs
    assert any(o.stages_all for o in ops if o.sub == "add")


def test_analyze_dynamic_pathspec_fails_closed():
    op = authz.analyze_git_command("git add $(ls)")[0]
    assert op.stages_all  # unverifiable pathspec -> treated as unbounded stage


def test_analyze_unbalanced_quotes_fails_closed():
    op = authz.analyze_git_command("git add 'unterminated")[0]
    assert op.sub == "?unparsed" and op.stages_all and op.external


# --- path matching ---------------------------------------------------------
def test_path_in_scope_glob_and_dir():
    s = _explicit(["README.md", "src/**"])
    assert authz.path_in_scope("README.md", s)
    assert authz.path_in_scope("src/app.js", s)
    assert authz.path_in_scope("src/deep/nested.js", s)
    assert not authz.path_in_scope(".env", s)
    assert not authz.path_in_scope("docs/x.md", s)


def test_bare_dir_pattern_authorizes_subtree():
    s = _explicit(["src"])
    assert authz.path_in_scope("src/app.js", s)
    assert not authz.path_in_scope("lib/app.js", s)


# --- enforce(): model scope expansion is rejected --------------------------
def test_model_git_add_all_rejected():
    s = _explicit(["README.md"])
    denial = authz.enforce("bash", {"command": "git add ."}, s)
    assert denial and "scope violation" in denial


def test_model_unrelated_path_rejected():
    s = _explicit(["README.md"])
    denial = authz.enforce("bash", {"command": "git add .env credentials.json"}, s)
    assert denial and ".env" in denial


def test_authorized_path_allowed():
    s = _explicit(["README.md", "src/**"])
    assert authz.enforce("bash", {"command": "git add README.md"}, s) is None
    assert authz.enforce("bash", {"command": "git add src/app.js"}, s) is None


def test_commit_a_rejected_with_explicit_scope():
    s = _explicit(["README.md"])
    assert authz.enforce("bash", {"command": "git commit -am wip"}, s)


def test_non_git_command_not_gated():
    s = _explicit(["README.md"])
    assert authz.enforce("bash", {"command": "ls -la && cat README.md"}, s) is None


def test_downstream_model_cannot_widen_scope():
    """A nested push that tries to broaden src/** to include docs/ + .env is
    intersected down to the parent's allow-list."""
    parent = _explicit(["src/**"])
    tok = authz.push_scope(parent)
    try:
        child = ToolScope(scope_mode="explicit",
                          authorized_paths=("src/**", "docs/**", ".env"), cwd="/repo")
        ctok = authz.push_scope(child)
        try:
            eff = authz.current_scope()
            assert ".env" not in eff.authorized_paths
            assert "docs/**" not in eff.authorized_paths
            assert "src/**" in eff.authorized_paths
        finally:
            authz.pop_scope(ctok)
    finally:
        authz.pop_scope(tok)


# --- secret / sensitive detection ------------------------------------------
def test_scan_name_flags_sensitive():
    for p in (".env", "id_rsa", "server.pem", "credentials.json", "aws.key",
              "client-engagement-notes.md", "pentest-report.pdf"):
        assert authz.scan_name(p), p
    assert authz.scan_name("README.md") is None
    assert authz.scan_name("src/app.js") is None


def test_scan_content_flags_secrets():
    assert authz.scan_content("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
    assert authz.scan_content("aws_access_key_id = AKIAIOSFODNN7EXAMPLE")
    assert authz.scan_content("export TOKEN=ghp_0123456789abcdefghijklmnopqrstuvwx")
    assert authz.scan_content("api_key: 'sk-abcdef0123456789abcdef'")
    assert authz.scan_content("the quick brown fox jumps over the lazy dog") is None


def test_content_scan_does_not_trust_filename(tmp_path):
    """A harmless-looking filename with a key inside still trips detection."""
    f = tmp_path / "notes.txt"
    f.write_text("my key is AKIAIOSFODNN7EXAMPLE do not share")
    hits = authz.scan_paths_for_secrets(["notes.txt"], cwd=str(tmp_path))
    assert hits and hits[0][0] == "notes.txt"


# --- push with sensitive files present -------------------------------------
def test_push_blocked_when_change_set_has_secret(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_text("# ok")
    (tmp_path / ".env").write_text("SECRET=AKIAIOSFODNN7EXAMPLE")
    monkeypatch.setattr(authz, "_effective_push_set", lambda cwd: ["README.md", ".env"])
    s = ToolScope(intent="git_push", scope_mode="open", cwd=str(tmp_path))
    denial = authz.enforce("bash", {"command": "git push"}, s)
    assert denial and "secret" in denial.lower()


def test_push_explicit_scope_rejects_out_of_scope_file(tmp_path, monkeypatch):
    monkeypatch.setattr(authz, "_effective_push_set",
                        lambda cwd: ["README.md", "pentest-report.pdf"])
    s = _explicit(["README.md"], cwd=str(tmp_path))
    denial = authz.enforce("bash", {"command": "git push"}, s)
    assert denial and "pentest-report.pdf" in denial


def test_allow_secrets_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_AUTHZ_ALLOW_SECRETS", "1")
    monkeypatch.setattr(authz, "_effective_push_set", lambda cwd: ["README.md", ".env"])
    s = ToolScope(intent="git_push", scope_mode="open", cwd=str(tmp_path))
    assert authz.enforce("bash", {"command": "git push"}, s) is None


def test_disabled_env_bypasses(monkeypatch):
    monkeypatch.setenv("PAL_AUTHZ_DISABLE", "1")
    s = _explicit(["README.md"])
    assert authz.enforce("bash", {"command": "git add ."}, s) is None


# --- write_file credential guard -------------------------------------------
def test_write_file_credential_blocked():
    assert authz.enforce("write_file", {"path": ".env", "content": "x"}, None)
    assert authz.enforce("write_file", {"path": "id_rsa", "content": "x"}, None)
    assert authz.enforce("write_file", {"path": "notes.md", "content": "x"}, None) is None


# --- gh external op secret-scan --------------------------------------------
def test_gh_pr_create_secret_scanned(tmp_path, monkeypatch):
    monkeypatch.setattr(authz, "_effective_push_set", lambda cwd: [".env"])
    s = ToolScope(scope_mode="open", external_ok=True, cwd=str(tmp_path))
    assert authz.enforce("gh", {"subcommand": "pr create --fill"}, s)
    # read-only gh is never gated
    assert authz.enforce("gh", {"subcommand": "pr view 1"}, s) is None


# --- end-to-end through Toolbelt.execute -----------------------------------
def test_toolbelt_execute_blocks_add_all(monkeypatch, tmp_path):
    from providers.tooling import toolbelt as tb_mod

    tb = tb_mod.get_toolbelt()
    tb.enable("bash")
    s = _explicit(["README.md"], cwd=str(tmp_path))
    tok = authz.push_scope(s)
    try:
        out = tb.execute("bash", {"command": "git add -A"}, caller_model="evil-model")
        assert "scope violation" in out
    finally:
        authz.pop_scope(tok)
