"""Regression tests for intent classification + scope extraction.

Proves the "security-mission overinterpretation" bug is fixed: a security
keyword used as a filename/dirname/commit object is NOT a security task, while
an actual security verb against a target still is."""

from __future__ import annotations

from providers.router import intent


# --- security over-interpretation is fixed ---------------------------------
def test_create_directory_enumeration_is_fileops():
    it = intent.classify_intent("Create a directory called enumeration")
    assert it.kind == "fileops" and not it.is_security


def test_create_reports_directory_is_fileops():
    assert not intent.classify_intent("Create a reports directory").is_security


def test_commit_exploit_file_is_not_security():
    it = intent.classify_intent("commit exploit.py and push it")
    assert not it.is_security and it.kind == "git"


def test_actual_enumeration_is_security():
    it = intent.classify_intent("Enumerate example.com and save results to enumeration/")
    assert it.is_security and it.kind == "security"


def test_scan_hosts_is_security():
    assert intent.classify_intent("scan these hosts for open ports").is_security


def test_analyze_api_for_vulns_is_security():
    assert intent.classify_intent("test this API for vulnerabilities").is_security


def test_plain_analysis_not_security():
    assert not intent.classify_intent("analyze this CSV and summarize trends").is_security


# --- git scope extraction --------------------------------------------------
def test_single_file_push_explicit():
    it = intent.classify_intent("Push README.md")
    assert it.kind == "git" and it.git_op == "push"
    assert it.scope_mode == "explicit" and it.explicit_paths == ("README.md",)


def test_directory_push_explicit():
    it = intent.classify_intent("push src/")
    assert it.scope_mode == "explicit"
    assert any(p.startswith("src") for p in it.explicit_paths)


def test_explicit_file_list_commit():
    it = intent.classify_intent("Commit a.txt and b.txt")
    assert it.git_op == "commit" and it.scope_mode == "explicit"
    assert set(it.explicit_paths) == {"a.txt", "b.txt"}


def test_vague_push_is_open():
    it = intent.classify_intent("push all my changes")
    assert it.kind == "git" and it.scope_mode == "open"
    assert it.explicit_paths == ()


# --- scope_for_request builds the right boundary ---------------------------
def test_scope_for_single_file_push():
    s = intent.scope_for_request("Push README.md", cwd="/repo")
    assert s.scope_mode == "explicit"
    assert s.authorized_paths == ("README.md",)
    assert s.allow_scope_expansion is False


def test_scope_for_sensitive_env_still_scoped(tmp_path):
    """Visibility != authorization: even with .env/credentials present, a
    'push README.md' request authorizes ONLY README.md."""
    s = intent.scope_for_request("Push README.md", cwd=str(tmp_path))
    from providers.tooling import authz

    assert authz.path_in_scope("README.md", s)
    assert not authz.path_in_scope(".env", s)
    assert not authz.path_in_scope("credentials.json", s)
    assert not authz.path_in_scope("private-key.pem", s)


def test_scope_for_vague_git_is_open():
    s = intent.scope_for_request("commit my changes", cwd="/repo")
    assert s.scope_mode == "open"
