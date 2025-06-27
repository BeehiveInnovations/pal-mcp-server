#!/usr/bin/env python3
"""
Validation script for all cross-platform fixes.

This script runs a series of tests to validate that all applied fixes
work correctly on Windows.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add parent directory to Python path to import from workspace root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions to test
from utils.file_utils import (
    expand_paths,
    is_home_directory_root,
    read_file_content,
    resolve_and_validate_path,
)


def test_home_directory_patterns():
    """Test 1: Home directory patterns on Windows."""
    print("🧪 Test 1: Home directory patterns on Windows")
    print("-" * 60)

    test_cases = [
        ("/home/ubuntu", True, "Linux home directory"),
        ("/home/testuser", True, "Linux home directory"),
        ("/Users/john", True, "macOS home directory"),
        ("/Users/developer", True, "macOS home directory"),
        ("C:\\Users\\John", True, "Windows home directory"),
        ("C:/Users/Jane", True, "Windows home directory"),
        ("/home/ubuntu/projects", False, "Linux home subdirectory"),
        ("/Users/john/Documents", False, "macOS home subdirectory"),
        ("C:\\Users\\John\\Documents", False, "Windows home subdirectory"),
    ]

    passed = 0
    for path_str, expected, description in test_cases:
        try:
            result = is_home_directory_root(Path(path_str))
            status = "✅" if result == expected else "❌"
            print(f"  {status} {path_str:<30} -> {result} ({description})")
            if result == expected:
                passed += 1
        except Exception as e:
            print(f"  ❌ {path_str:<30} -> Exception: {e}")

    success = passed == len(test_cases)
    print(f"\nResult: {passed}/{len(test_cases)} tests passed")
    return success


def test_unix_path_validation():
    """Test 2: Unix path validation on Windows."""
    print("\n🧪 Test 2: Unix path validation on Windows")
    print("-" * 60)

    test_cases = [
        ("/etc/passwd", True, "Unix system file"),
        ("/home/user/file.txt", True, "Unix user file"),
        ("/usr/local/bin/python", True, "Unix binary path"),
        ("./relative/path", False, "Relative path"),
        ("relative/file.txt", False, "Relative file"),
        ("C:\\Windows\\System32", True, "Windows absolute path"),
    ]

    passed = 0
    for path_str, should_pass, description in test_cases:
        try:
            resolve_and_validate_path(path_str)
            result = True
            status = "✅" if should_pass else "❌"
            print(f"  {status} {path_str:<30} -> Accepted ({description})")
        except ValueError:
            result = False
            status = "✅" if not should_pass else "❌"
            print(f"  {status} {path_str:<30} -> Rejected ({description})")
        except PermissionError:
            result = True  # Rejected for security, not path format
            status = "✅" if should_pass else "❌"
            print(f"  {status} {path_str:<30} -> Secured ({description})")
        except Exception as e:
            result = False
            status = "❌"
            print(f"  {status} {path_str:<30} -> Error: {e}")

        if result == should_pass:
            passed += 1

    success = passed == len(test_cases)
    print(f"\nResult: {passed}/{len(test_cases)} tests passed")
    return success


def test_safe_files_functionality():
    """Test 3: Safe files functionality."""
    print("\n🧪 Test 3: Safe files functionality")
    print("-" * 60)

    # Create a temporary file to test
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("test content for validation")
        temp_file = f.name

    try:
        # Test reading existing file
        content, tokens = read_file_content(temp_file)

        has_begin = f"--- BEGIN FILE: {temp_file} ---" in content
        has_content = "test content for validation" in content
        has_end = "--- END FILE:" in content
        has_tokens = tokens > 0

        print(f"  ✅ BEGIN FILE found: {has_begin}")
        print(f"  ✅ Correct content: {has_content}")
        print(f"  ✅ END FILE found: {has_end}")
        print(f"  ✅ Tokens > 0: {has_tokens}")

        success1 = all([has_begin, has_content, has_end, has_tokens])

        # Test nonexistent Unix path
        # (should return FILE NOT FOUND, not path error)
        content, tokens = read_file_content("/etc/nonexistent")
        not_found = "--- FILE NOT FOUND:" in content
        no_path_error = "Relative paths are not supported" not in content
        has_tokens2 = tokens > 0

        print(f"  ✅ Nonexistent Unix file: {not_found}")
        print(f"  ✅ No path error: {no_path_error}")
        print(f"  ✅ Tokens > 0: {has_tokens2}")

        success2 = all([not_found, no_path_error, has_tokens2])

        success = success1 and success2
        status = "passed" if success else "failed"
        print(f"\nResult: Safe files tests {status}")

    finally:
        # Clean up
        try:
            Path(temp_file).unlink()
        except Exception:
            pass

    return success


def test_cross_platform_file_discovery():
    """Test 4: Cross-platform file discovery."""
    print("\n🧪 Test 4: Cross-platform file discovery")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create test structure
        project = tmp_path / "test-project"
        project.mkdir()

        (project / "README.md").write_text("# Test Project")
        (project / "main.py").write_text("print('Hello')")

        src = project / "src"
        src.mkdir()
        (src / "app.py").write_text("# App code")

        # Test with mock MCP
        def mock_is_mcp(path):
            return False  # No MCP in this test

        with patch("utils.file_utils.is_mcp_directory", side_effect=mock_is_mcp):
            files = expand_paths([str(project)])

        file_paths = [str(f) for f in files]

        # Use Path.parts for cross-platform checks
        readme_found = any(Path(p).parts[-2:] == ("test-project", "README.md") for p in file_paths)
        main_found = any(Path(p).parts[-2:] == ("test-project", "main.py") for p in file_paths)
        app_found = any(Path(p).parts[-2:] == ("src", "app.py") for p in file_paths)

        print(f"  ✅ README.md found: {readme_found}")
        print(f"  ✅ main.py found: {main_found}")
        print(f"  ✅ app.py found: {app_found}")
        print(f"  ℹ️  Files found: {len(file_paths)}")

        success = all([readme_found, main_found, app_found])
        print(f"\nResult: Cross-platform discovery {'passed' if success else 'failed'}")

        return success


def main():
    """Main validation function."""
    print("🔧 Final validation of cross-platform fixes")
    print("=" * 70)
    print("This script validates that all fixes work on Windows.")
    print("=" * 70)

    # Run all tests
    results = []

    results.append(("Home directory patterns", test_home_directory_patterns()))
    results.append(("Unix path validation", test_unix_path_validation()))
    results.append(("Safe files", test_safe_files_functionality()))
    results.append(("Cross-platform discovery", test_cross_platform_file_discovery()))

    # Final summary
    print("\n" + "=" * 70)
    print("📊 FINAL SUMMARY")
    print("=" * 70)

    passed_tests = 0
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:<10} {test_name}")
        if success:
            passed_tests += 1

    total_tests = len(results)
    print(f"\nOverall result: {passed_tests}/{total_tests} test groups passed")

    if passed_tests == total_tests:
        print("\n🎉 COMPLETE SUCCESS!")
        print("All cross-platform fixes work correctly.")
        return 0
    else:
        print("\n❌ FAILURES DETECTED")
        print("Some fixes need adjustments.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
