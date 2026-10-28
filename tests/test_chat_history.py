import base64
import stat

from providers.router.chat_history import JsonlSessionHistory, history_dir, mask_secrets


def test_basic_auth_header_masked():
    b64 = base64.b64encode(b"admin:hunter2hunter2").decode()
    out = mask_secrets(f"curl -H 'Authorization: Basic {b64}' https://x")
    assert b64 not in out
    assert "***" in out and "admin" not in out


def test_url_userinfo_masked():
    out = mask_secrets("git clone https://bob:s3cr3tpw@github.com/o/r.git")
    assert "s3cr3tpw" not in out and "bob" not in out
    assert "https://***:***@github.com" in out


def test_pem_block_masked():
    pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEabc\ndef123\n-----END RSA PRIVATE KEY-----"
    out = mask_secrets(f"here: {pem} thanks")
    assert "MIIEabc" not in out and "def123" not in out
    assert "thanks" in out


def test_pem_unterminated_masked():
    out = mask_secrets("-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC1rZXk")
    assert "b3BlbnNzaC1rZXk" not in out


def test_plain_text_untouched():
    assert mask_secrets("use Basic auth for the demo") == "use Basic auth for the demo"


def test_file_0600_and_dir_0700_after_first_write(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_CHAT_HISTORY_DIR", str(tmp_path / "h" / "nested"))
    b64 = base64.b64encode(b"u:p4ssw0rd!!").decode()
    h = JsonlSessionHistory("sess1")
    h.store_string(f"Authorization: Basic {b64}")
    assert stat.S_IMODE(h.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(history_dir().stat().st_mode) == 0o700
    assert b64 not in h.path.read_text()


def test_preexisting_loose_file_tightened(tmp_path, monkeypatch):
    monkeypatch.setenv("PAL_CHAT_HISTORY_DIR", str(tmp_path))
    h = JsonlSessionHistory("sess2")
    h.path.write_text("")
    h.path.chmod(0o644)
    h.store_string("hello")
    assert stat.S_IMODE(h.path.stat().st_mode) == 0o600
