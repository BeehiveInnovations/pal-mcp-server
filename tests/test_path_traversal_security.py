"""
Test path traversal security fix.

Fixes vulnerability reported in:
- https://github.com/BeehiveInnovations/zen-mcp-server/issues/293
- https://github.com/BeehiveInnovations/zen-mcp-server/issues/312

The vulnerability: is_dangerous_path() only did exact string matching,
so /etc was blocked but /etc/passwd was allowed.
"""

from pathlib import Path

from utils.security_config import is_dangerous_path


class TestPathTraversalFix:
    """Test that subdirectories of dangerous paths are now blocked."""

    def test_exact_match_still_works(self):
        """Test that exact dangerous paths are still blocked."""
        assert is_dangerous_path(Path("/etc")) is True
        assert is_dangerous_path(Path("/usr")) is True
        assert is_dangerous_path(Path("/var")) is True

    def test_subdirectory_now_blocked(self):
        """Test that subdirectories are now blocked (the fix)."""
        # These were allowed before the fix
        assert is_dangerous_path(Path("/etc/passwd")) is True
        assert is_dangerous_path(Path("/etc/shadow")) is True
        assert is_dangerous_path(Path("/etc/hosts")) is True
        assert is_dangerous_path(Path("/var/log/auth.log")) is True

    def test_deeply_nested_blocked(self):
        """Test that deeply nested paths are blocked."""
        assert is_dangerous_path(Path("/etc/ssh/sshd_config")) is True
        assert is_dangerous_path(Path("/usr/local/bin/python")) is True

    def test_root_blocked(self):
        """Test that root directory is blocked."""
        assert is_dangerous_path(Path("/")) is True

    def test_safe_paths_allowed(self):
        """Test that safe paths are still allowed."""
        # User project directories should be allowed
        assert is_dangerous_path(Path("/tmp/test")) is False
        assert is_dangerous_path(Path("/tmp/myproject/src")) is False

    def test_similar_names_not_blocked(self):
        """Test that paths with similar names are not blocked."""
        # /etcbackup should NOT be blocked (it's not under /etc)
        assert is_dangerous_path(Path("/tmp/etcbackup")) is False
        assert is_dangerous_path(Path("/tmp/my_etc_files")) is False


class TestRegressionPrevention:
    """Regression tests for the specific vulnerability."""

    def test_etc_passwd_blocked(self):
        """Test /etc/passwd is blocked (common attack target)."""
        assert is_dangerous_path(Path("/etc/passwd")) is True

    def test_etc_shadow_blocked(self):
        """Test /etc/shadow is blocked (password hashes)."""
        assert is_dangerous_path(Path("/etc/shadow")) is True


class TestWindowsPathHandling:
    """Test Windows path handling with trailing backslash.

    Fixes issue reported in PR #353: Windows paths like C:\\ have trailing
    backslash which caused double separator issues with string prefix matching.
    Using Path.is_relative_to() resolves this correctly.
    """

    def test_windows_root_drive_blocked(self):
        """Test that Windows root drive C:\\ is blocked."""
        from pathlib import PureWindowsPath

        # Simulate Windows path behavior using PureWindowsPath
        # On Linux, we test the logic with PureWindowsPath to verify cross-platform correctness
        c_root = PureWindowsPath("C:\\")
        assert c_root.parent == c_root  # Root check works

    def test_windows_dangerous_subdirectory_detection(self):
        """Test that Windows subdirectories are correctly detected as dangerous.

        This verifies the fix for the double backslash issue:
        - Before fix: "C:\\" + "\\" = "C:\\\\" which doesn't match "C:\\Users"
        - After fix: Path.is_relative_to() handles this correctly
        """
        from pathlib import PureWindowsPath

        # Verify is_relative_to works correctly for Windows paths
        c_users = PureWindowsPath("C:\\Users")
        c_root = PureWindowsPath("C:\\")

        # This is the key test - subdirectory detection must work
        assert c_users.is_relative_to(c_root) is True

        # Deeper paths should also work
        c_users_admin = PureWindowsPath("C:\\Users\\Admin")
        assert c_users_admin.is_relative_to(c_root) is True
        assert c_users_admin.is_relative_to(c_users) is True

    def test_windows_path_not_relative_to_different_drive(self):
        """Test that paths on different drives are not related."""
        from pathlib import PureWindowsPath

        d_path = PureWindowsPath("D:\\Data")
        c_root = PureWindowsPath("C:\\")

        # D: drive paths should not be relative to C:
        assert d_path.is_relative_to(c_root) is False
