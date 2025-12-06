#!/usr/bin/env python3
"""
Health check script for PAL MCP Server Docker container
"""

import os
import subprocess
import sys
from pathlib import Path

try:
    from utils.env import get_env
except ImportError:  # pragma: no cover - resolves module path inside container
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from utils.env import get_env  # type: ignore[import-error]


def check_process():
    """Check if the main server process is running"""
    result = subprocess.run(["pgrep", "-f", "server.py"], capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        return True
    print(f"Process check failed: {result.stderr}", file=sys.stderr)
    return False


def check_python_imports():
    """Check if critical Python modules can be imported"""
    critical_modules = ["mcp", "google.genai", "openai", "pydantic", "dotenv"]

    for module in critical_modules:
        try:
            __import__(module)
        except ImportError as e:
            print(f"Critical module {module} cannot be imported: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"Error importing {module}: {e}", file=sys.stderr)
            return False
    return True


def check_log_directory():
    """Check if logs directory is writable"""
    log_dir = "/app/logs"
    try:
        if not os.path.exists(log_dir):
            print(f"Log directory {log_dir} does not exist", file=sys.stderr)
            return False

        test_file = os.path.join(log_dir, ".health_check")
        with open(test_file, "w") as f:
            f.write("health_check")
        os.remove(test_file)
        return True
    except Exception as e:
        print(f"Log directory check failed: {e}", file=sys.stderr)
        return False


def check_environment():
    """Check if essential environment variables are present"""
    # At least one API key should be present
    api_keys = [
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "DIAL_API_KEY",
        "OPENROUTER_API_KEY",
    ]

    has_api_key = any(get_env(key) for key in api_keys)
    if not has_api_key:
        print("No API keys found in environment", file=sys.stderr)
        return False

    # Validate API key formats (basic checks)
    for key in api_keys:
        value = get_env(key)
        if value:
            if len(value.strip()) < 10:
                print(f"API key {key} appears too short or invalid", file=sys.stderr)
                return False

    return True


def main():
    """Main health check function"""
    checks = [
        ("Process", check_process),
        ("Python imports", check_python_imports),
        ("Log directory", check_log_directory),
        ("Environment", check_environment),
    ]

    failed_checks = []

    for check_name, check_func in checks:
        if not check_func():
            failed_checks.append(check_name)

    if failed_checks:
        print(f"Health check failed: {', '.join(failed_checks)}", file=sys.stderr)
        sys.exit(1)

    print("Health check passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
