"""
Test file protection mechanisms to ensure MCP doesn't scan:
1. Its own directory
2. User's home directory root
3. Excluded directories
"""

from pathlib import Path
from unittest.mock import patch

from utils.file_utils import (
    expand_paths,
    get_user_home_directory,
    is_home_directory_root,
    is_mcp_directory,
)


class TestMCPDirectoryDetection:
    """Test MCP self-detection to prevent scanning its own code."""

    def test_detect_mcp_directory_dynamically(self, tmp_path):
        """Test dynamic MCP directory detection based on script location."""
        # The is_mcp_directory function now uses __file__ to detect MCP location
        # It checks if the given path is a subdirectory of the MCP server
        from pathlib import Path

        import utils.file_utils

        # Get the actual MCP server directory
        mcp_server_dir = Path(utils.file_utils.__file__).parent.parent.resolve()

        # Test that the MCP server directory itself is detected
        assert is_mcp_directory(mcp_server_dir) is True

        # Test that a subdirectory of MCP is also detected
        if (mcp_server_dir / "tools").exists():
            assert is_mcp_directory(mcp_server_dir / "tools") is True

    def test_no_detection_on_non_mcp_directory(self, tmp_path):
        """Test no detection on directories outside MCP."""
        # Any directory outside the MCP server should not be detected
        non_mcp_dir = tmp_path / "some_other_project"
        non_mcp_dir.mkdir()

        assert is_mcp_directory(non_mcp_dir) is False

    def test_no_detection_on_regular_directory(self, tmp_path):
        """Test no detection on regular project directories."""
        # Create some random Python files
        (tmp_path / "app.py").touch()
        (tmp_path / "main.py").touch()
        (tmp_path / "utils.py").touch()

        assert is_mcp_directory(tmp_path) is False

    def test_no_detection_on_file(self, tmp_path):
        """Test no detection when path is a file, not directory."""
        file_path = tmp_path / "test.py"
        file_path.touch()

        assert is_mcp_directory(file_path) is False

    def test_mcp_directory_excluded_from_scan(self, tmp_path):
        """Test that MCP directories are excluded during path expansion."""
        # For this test, we need to mock is_mcp_directory since we can't
        # actually create the MCP directory structure in tmp_path
        from unittest.mock import patch as mock_patch

        # Create a project with a subdirectory we'll pretend is MCP
        project_root = tmp_path / "my_project"
        project_root.mkdir()

        # Add some project files
        (project_root / "app.py").write_text("# My app")
        (project_root / "config.py").write_text("# Config")

        # Create a subdirectory that we'll mock as MCP
        fake_mcp_dir = project_root / "gemini-mcp-server"
        fake_mcp_dir.mkdir()
        (fake_mcp_dir / "server.py").write_text("# MCP server")
        (fake_mcp_dir / "test.py").write_text("# Should not be included")

        # Mock is_mcp_directory to return True for our fake MCP dir
        def mock_is_mcp(path):
            return str(path).endswith("gemini-mcp-server")

        # Scan the project with mocked MCP detection
        with mock_patch("utils.file_utils.is_mcp_directory", side_effect=mock_is_mcp):
            files = expand_paths([str(project_root)])

        # Verify project files are included but MCP files are not
        file_names = [Path(f).name for f in files]
        assert "app.py" in file_names
        assert "config.py" in file_names
        assert "test.py" not in file_names  # From MCP dir
        assert "server.py" not in file_names  # From MCP dir


class TestHomeDirectoryProtection:
    """Test protection against scanning user's home directory root."""

    def test_detect_exact_home_directory(self):
        """Test detection of exact home directory path."""
        with patch("utils.file_utils.get_user_home_directory") as mock_home:
            mock_home.return_value = Path("/Users/testuser")

            assert is_home_directory_root(Path("/Users/testuser")) is True
            assert is_home_directory_root(Path("/Users/testuser/")) is True

    def test_allow_home_subdirectories(self):
        """Test that subdirectories of home are allowed."""
        with patch("utils.file_utils.get_user_home_directory") as mock_home:
            mock_home.return_value = Path("/Users/testuser")

            assert is_home_directory_root(Path("/Users/testuser/projects")) is False
            assert is_home_directory_root(Path("/Users/testuser/Documents/code")) is False

    def test_detect_home_patterns_macos(self):
        """Test detection of macOS home directory patterns."""
        # Test various macOS home patterns
        assert is_home_directory_root(Path("/Users/john")) is True
        assert is_home_directory_root(Path("/Users/jane")) is True
        # But subdirectories should be allowed
        assert is_home_directory_root(Path("/Users/john/projects")) is False

    def test_detect_home_patterns_linux(self):
        """Test detection of Linux home directory patterns."""
        assert is_home_directory_root(Path("/home/ubuntu")) is True
        assert is_home_directory_root(Path("/home/user")) is True
        # But subdirectories should be allowed
        assert is_home_directory_root(Path("/home/ubuntu/code")) is False

    def test_detect_home_patterns_windows(self):
        """Test detection of Windows home directory patterns."""
        assert is_home_directory_root(Path("C:\\Users\\John")) is True
        assert is_home_directory_root(Path("C:/Users/Jane")) is True
        # But subdirectories should be allowed
        assert is_home_directory_root(Path("C:\\Users\\John\\Documents")) is False

    def test_home_directory_excluded_from_scan(self, tmp_path):
        """Test that home directory root is excluded during path expansion."""
        with patch("utils.file_utils.get_user_home_directory") as mock_home:
            mock_home.return_value = tmp_path
            # Try to scan home directory
            files = expand_paths([str(tmp_path)])
            # Should return empty as home root is skipped
            assert files == []


class TestUserHomeEnvironmentVariable:
    """Test USER_HOME environment variable handling."""

    def test_user_home_from_pathlib(self):
        """Test that get_user_home_directory uses Path.home()."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/Users/testuser")
            home = get_user_home_directory()
            assert home == Path("/Users/testuser")

    def test_get_home_directory_uses_pathlib(self):
        """Test that get_user_home_directory always uses Path.home()."""
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path("/home/testuser")
            home = get_user_home_directory()
            assert home == Path("/home/testuser")
            # Verify Path.home() was called
            mock_home.assert_called_once()

    def test_home_directory_on_different_platforms(self):
        """Test home directory detection on different platforms."""
        # Test different platform home directories
        test_homes = [
            Path("/Users/john"),  # macOS
            Path("/home/ubuntu"),  # Linux
            Path("C:\\Users\\John"),  # Windows
        ]

        for test_home in test_homes:
            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = test_home
                home = get_user_home_directory()
                assert home == test_home


class TestExcludedDirectories:
    """Test that excluded directories are properly filtered."""

    def test_excluded_dirs_not_scanned(self, tmp_path):
        """Test that directories in EXCLUDED_DIRS are skipped."""
        # Create a project with various directories
        project = tmp_path / "project"
        project.mkdir()

        # Create some allowed files
        (project / "main.py").write_text("# Main")
        (project / "app.py").write_text("# App")

        # Create excluded directories with files
        for excluded in ["node_modules", ".git", "build", "__pycache__", ".venv"]:
            excluded_dir = project / excluded
            excluded_dir.mkdir()
            (excluded_dir / "test.py").write_text("# Should not be included")
            (excluded_dir / "data.json").write_text("{}")

        # Create a nested allowed directory
        src = project / "src"
        src.mkdir()
        (src / "utils.py").write_text("# Utils")

        files = expand_paths([str(project)])

        file_names = [Path(f).name for f in files]

        # Check allowed files are included
        assert "main.py" in file_names
        assert "app.py" in file_names
        assert "utils.py" in file_names

        # Check excluded files are not included
        assert "test.py" not in file_names
        assert "data.json" not in file_names

    def test_new_excluded_directories(self, tmp_path):
        """Test newly added excluded directories like .next, .nuxt, etc."""
        project = tmp_path / "webapp"
        project.mkdir()

        # Create files in new excluded directories
        for excluded in [".next", ".nuxt", "bower_components", ".expo"]:
            excluded_dir = project / excluded
            excluded_dir.mkdir()
            (excluded_dir / "generated.js").write_text("// Generated")

        # Create an allowed file
        (project / "index.js").write_text("// Index")

        files = expand_paths([str(project)])

        file_names = [Path(f).name for f in files]

        assert "index.js" in file_names
        assert "generated.js" not in file_names


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_project_with_mcp_clone_inside(self, tmp_path):
        """Test scanning a project that has MCP cloned inside it."""
        # Setup: User project with MCP cloned as a tool
        user_project = tmp_path / "my-awesome-project"
        user_project.mkdir()

        # User's project files
        (user_project / "README.md").write_text("# My Project")
        (user_project / "main.py").write_text("print('Hello')")
        src = user_project / "src"
        src.mkdir()
        (src / "app.py").write_text("# App code")

        # MCP cloned inside the project
        mcp = user_project / "tools" / "gemini-mcp-server"
        mcp.mkdir(parents=True)
        # Create typical MCP files
        (mcp / "server.py").write_text("# MCP server code")
        (mcp / "config.py").write_text("# MCP config")
        tools_dir = mcp / "tools"
        tools_dir.mkdir()
        (tools_dir / "chat.py").write_text("# Chat tool")
        (mcp / "LICENSE").write_text("MIT License")
        (mcp / "README.md").write_text("# Gemini MCP")

        # Also add node_modules (should be excluded)
        node_modules = user_project / "node_modules"
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}")

        # Mock is_mcp_directory for this test
        def mock_is_mcp(path):
            return "gemini-mcp-server" in str(path)

        with patch("utils.file_utils.is_mcp_directory", side_effect=mock_is_mcp):
            files = expand_paths([str(user_project)])

        file_paths = [str(f) for f in files]

        # User files should be included
        assert any("my-awesome-project/README.md" in p for p in file_paths)
        assert any("my-awesome-project/main.py" in p for p in file_paths)
        assert any("src/app.py" in p for p in file_paths)

        # MCP files should NOT be included
        assert not any("gemini-mcp-server" in p for p in file_paths)
        assert not any("server.py" in p for p in file_paths)

        # node_modules should NOT be included
        assert not any("node_modules" in p for p in file_paths)

    def test_security_without_workspace_root(self, tmp_path):
        """Test that security still works with the new security model."""
        # The system now relies on is_dangerous_path and is_home_directory_root
        # for security protection

        # Test that we can scan regular project directories
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("# App")

        files = expand_paths([str(project_dir)])
        assert len(files) == 1
        assert "app.py" in files[0]

        # Test that home directory root is still protected
        with patch("utils.file_utils.get_user_home_directory") as mock_home:
            mock_home.return_value = tmp_path
            # Scanning home root should return empty
            files = expand_paths([str(tmp_path)])
            assert files == []
