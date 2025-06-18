"""
Tests for utility functions
"""

from utils import check_token_limit, estimate_tokens, read_file_content, read_files


class TestFileUtils:
    """Test file reading utilities"""

    def test_read_file_content_success(self, project_path):
        """Test successful file reading"""
        test_file = project_path / "test.py"
        test_file.write_text("def hello():\n    return 'world'", encoding="utf-8")

        content, tokens = read_file_content(str(test_file))
        assert "--- BEGIN FILE:" in content
        assert "--- END FILE:" in content
        assert "def hello():" in content
        assert "return 'world'" in content
        assert tokens > 0  # Should have estimated tokens

    def test_read_file_content_not_found(self, project_path):
        """Test reading non-existent file"""
        # Use a non-existent file within the project path
        nonexistent = project_path / "nonexistent" / "file.py"
        content, tokens = read_file_content(str(nonexistent))
        assert "--- FILE NOT FOUND:" in content
        assert "Error: File does not exist" in content
        assert tokens > 0

    def test_read_file_content_safe_files_allowed(self):
        """Test that safe files outside the original project root are now allowed"""
        # In the new security model, safe files like /etc/passwd
        # can be read as they're not in the dangerous paths list
        content, tokens = read_file_content("/etc/passwd")
        # Should successfully read the file
        assert "--- BEGIN FILE: /etc/passwd ---" in content
        assert "--- END FILE: /etc/passwd ---" in content
        assert tokens > 0

    def test_read_file_content_relative_path_rejected(self):
        """Test that relative paths are rejected"""
        # Try to use a relative path
        content, tokens = read_file_content("./some/relative/path.py")
        assert "--- ERROR ACCESSING FILE:" in content
        assert "Relative paths are not supported" in content
        assert tokens > 0

    def test_read_file_content_directory(self, project_path):
        """Test reading a directory"""
        content, tokens = read_file_content(str(project_path))
        assert "--- NOT A FILE:" in content
        assert "Error: Path is not a file" in content
        assert tokens > 0

    def test_read_files_multiple(self, project_path):
        """Test reading multiple files"""
        file1 = project_path / "file1.py"
        file1.write_text("print('file1')", encoding="utf-8")
        file2 = project_path / "file2.py"
        file2.write_text("print('file2')", encoding="utf-8")

        content = read_files([str(file1), str(file2)])

        assert "--- BEGIN FILE:" in content
        assert "file1.py" in content
        assert "file2.py" in content
        assert "print('file1')" in content
        assert "print('file2')" in content

        # Check that both files are included
        assert "file1.py" in content and "file2.py" in content

    def test_read_files_with_code(self):
        """Test reading with direct code"""
        code = "def test():\n    pass"
        content = read_files([], code)

        assert "--- BEGIN DIRECT CODE ---" in content
        assert "--- END DIRECT CODE ---" in content
        assert code in content

        # Check that direct code is included
        assert code in content

    def test_read_files_directory_support(self, project_path):
        """Test reading all files from a directory"""
        # Create directory structure
        (project_path / "file1.py").write_text("print('file1')", encoding="utf-8")
        (project_path / "file2.js").write_text("console.log('file2')", encoding="utf-8")
        (project_path / "readme.md").write_text("# README", encoding="utf-8")

        # Create subdirectory
        subdir = project_path / "src"
        subdir.mkdir()
        (subdir / "module.py").write_text("class Module: pass", encoding="utf-8")

        # Create hidden file (should be skipped)
        (project_path / ".hidden").write_text("secret", encoding="utf-8")

        # Read the directory
        content = read_files([str(project_path)])

        # Check files are included
        assert "file1.py" in content
        assert "file2.js" in content
        assert "readme.md" in content
        # Handle both forward and backslashes for cross-platform compatibility
        assert "module.py" in content
        assert "class Module: pass" in content

        # Check content
        assert "print('file1')" in content
        assert "console.log('file2')" in content
        assert "# README" in content
        assert "class Module: pass" in content

        # Hidden file should not be included
        assert ".hidden" not in content
        assert "secret" not in content

        # Check that all files are included
        assert all(filename in content for filename in ["file1.py", "file2.js", "readme.md", "module.py"])

    def test_read_files_mixed_paths(self, project_path):
        """Test reading mix of files and directories"""
        # Create files
        file1 = project_path / "direct.py"
        file1.write_text("# Direct file", encoding="utf-8")

        # Create directory with files
        subdir = project_path / "subdir"
        subdir.mkdir()
        (subdir / "sub1.py").write_text("# Sub file 1", encoding="utf-8")
        (subdir / "sub2.py").write_text("# Sub file 2", encoding="utf-8")

        # Read mix of direct file and directory
        content = read_files([str(file1), str(subdir)])

        assert "direct.py" in content
        assert "sub1.py" in content
        assert "sub2.py" in content
        assert "# Direct file" in content
        assert "# Sub file 1" in content
        assert "# Sub file 2" in content

        # Check that all files are included
        assert all(filename in content for filename in ["direct.py", "sub1.py", "sub2.py"])

    def test_read_files_token_limit(self, project_path):
        """Test token limit handling"""
        # Create files with known token counts
        # ~250 tokens each (1000 chars)
        large_content = "x" * 1000

        for i in range(5):
            (project_path / f"file{i}.txt").write_text(large_content, encoding="utf-8")

        # Read with small token limit (should skip some files)
        # Reserve 50k tokens, limit to 51k total = 1k available
        # Each file ~250 tokens, so should read ~3-4 files
        content = read_files([str(project_path)], max_tokens=51_000)

        # Check that token limit handling is present
        assert "--- SKIPPED FILES (TOKEN LIMIT) ---" in content

        # Count how many files were read
        read_count = content.count("--- BEGIN FILE:")
        assert 2 <= read_count <= 4  # Should read some but not all

    def test_read_files_large_file(self, project_path):
        """Test handling of large files"""
        # Create a file larger than max_size (1MB)
        large_file = project_path / "large.txt"
        large_file.write_text("x" * 2_000_000, encoding="utf-8")  # 2MB

        content = read_files([str(large_file)])

        assert "--- FILE TOO LARGE:" in content
        assert "2,000,000 bytes" in content
        # File too large message should be present
        assert "--- FILE TOO LARGE:" in content

    def test_read_files_file_extensions(self, project_path):
        """Test file extension filtering"""
        # Create various file types
        (project_path / "code.py").write_text("python", encoding="utf-8")
        (project_path / "style.css").write_text("css", encoding="utf-8")
        (project_path / "binary.exe").write_text("exe", encoding="utf-8")
        (project_path / "image.jpg").write_text("jpg", encoding="utf-8")

        content = read_files([str(project_path)])

        # Code files should be included
        assert "code.py" in content
        assert "style.css" in content

        # Binary files should not be included (not in CODE_EXTENSIONS)
        assert "binary.exe" not in content
        assert "image.jpg" not in content


class TestTokenUtils:
    """Test token counting utilities"""

    def test_estimate_tokens(self):
        """Test token estimation"""
        # Rough estimate: 1 token ≈ 4 characters
        text = "a" * 400  # 400 characters
        assert estimate_tokens(text) == 100

    def test_check_token_limit_within(self):
        """Test token limit check - within limit"""
        text = "a" * 4000  # 1000 tokens
        within_limit, tokens = check_token_limit(text)
        assert within_limit is True
        assert tokens == 1000

    def test_check_token_limit_exceeded(self):
        """Test token limit check - exceeded"""
        text = "a" * 5_000_000  # 1.25M tokens
        within_limit, tokens = check_token_limit(text)
        assert within_limit is False
        assert tokens == 1_250_000
