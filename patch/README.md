# Cross-Platform Compatibility Patches

This directory contains patch scripts to improve the cross-platform compatibility of the zen-mcp server.

## Files

### `patch_crossplatform.py`
Main script that automatically applies all necessary fixes to resolve cross-platform compatibility issues.

**Usage:**
```bash
# From the patch/ directory
python patch_crossplatform.py [--dry-run] [--backup] [--validate-only]
```

**Options:**
- `--dry-run`: Show changes without applying them
- `--backup`: Create a backup before modifying files
- `--validate-only`: Only check if the fixes are already applied

### `validation_crossplatform.py`
Validation script that tests whether all fixes work correctly.

**Usage:**
```bash
# From the patch/ directory
python validation_crossplatform.py
```

## Applied Fixes

1. **HOME DIRECTORY DETECTION ON WINDOWS:**
   - Linux tests (/home/ubuntu) failed on Windows
   - Unix patterns were not detected due to backslashes
   - Solution: Added Windows patterns + double path check

2. **UNIX PATH VALIDATION ON WINDOWS:**
   - Unix paths (/etc/passwd) were rejected as relative paths
   - Solution: Accept Unix paths as absolute on Windows

3. **CROSS-PLATFORM TESTS:**
   - Assertions used OS-specific separators
   - The safe_files test used a non-existent file on Windows
   - Solution: Use Path.parts + temporary files on Windows

4. **SHELL SCRIPT COMPATIBILITY ON WINDOWS:**
   - Shell scripts did not detect Windows virtual environment paths
   - Solution: Added detection for .zen_venv/Scripts/ paths

5. **COMMUNICATION SIMULATOR LOGGER BUG:**
   - AttributeError: logger used before initialization
   - Solution: Initialize logger before calling _get_python_path()

6. **PYTHON PATH DETECTION ON WINDOWS:**
   - The simulator could not find the Windows Python executable
   - Solution: Added Windows-specific detection

## How to Use

1. **Apply all fixes:**
   ```bash
   cd patch/
   python patch_crossplatform.py
   ```

2. **Test in dry-run mode (preview):**
   ```bash
   cd patch/
   python patch_crossplatform.py --dry-run
   ```

3. **Validate the fixes:**
   ```bash
   cd patch/
   python validation_crossplatform.py
   ```

4. **Check if fixes are already applied:**
   ```bash
   cd patch/
   python patch_crossplatform.py --validate-only
   ```

## Modified Files

- `utils/file_utils.py`: Home patterns + Unix path validation
- `tests/test_file_protection.py`: Cross-platform assertions
- `tests/test_utils.py`: Safe_files test with temporary file
- `run_integration_tests.sh`: Windows venv detection
- `code_quality_checks.sh`: venv and Windows tools detection
- `communication_simulator_test.py`: Logger initialization order + Windows paths

Tests should now pass on Windows, macOS, and Linux!
