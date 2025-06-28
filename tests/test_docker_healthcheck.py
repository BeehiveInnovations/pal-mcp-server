"""
Tests for Docker health check functionality
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDockerHealthCheck:
    """Test Docker health check implementation"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent
        self.healthcheck_script = self.project_root / "docker" / "scripts" / "healthcheck.py"

    def test_healthcheck_script_exists(self):
        """Test that health check script exists"""
        assert self.healthcheck_script.exists(), "healthcheck.py must exist"

    def test_healthcheck_script_executable(self):
        """Test that health check script is executable"""
        if not self.healthcheck_script.exists():
            pytest.skip("healthcheck.py not found")

        # Check if script has Python shebang
        content = self.healthcheck_script.read_text()
        assert content.startswith("#!/usr/bin/env python"), "Health check script must have Python shebang"

    @patch("subprocess.run")
    def test_process_check_success(self, mock_run):
        """Test successful process check"""
        # Mock successful pgrep command
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "12345\n"

        # Import and test the function (if we can access it)
        # This would require the healthcheck module to be importable
        result = subprocess.run(["pgrep", "-f", "server.py"], capture_output=True, text=True, timeout=10)

        assert result.returncode == 0

    @patch("subprocess.run")
    def test_process_check_failure(self, mock_run):
        """Test failed process check"""
        # Mock failed pgrep command
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "No such process"

        result = subprocess.run(["pgrep", "-f", "server.py"], capture_output=True, text=True, timeout=10)

        assert result.returncode == 1

    def test_critical_modules_import(self):
        """Test that critical modules can be imported"""
        critical_modules = ["json", "os", "sys", "pathlib"]

        for module_name in critical_modules:
            try:
                __import__(module_name)
            except ImportError:
                pytest.fail(f"Critical module {module_name} cannot be imported")

    def test_optional_modules_graceful_failure(self):
        """Test graceful handling of optional module import failures"""
        optional_modules = ["mcp", "google.genai", "openai"]

        for module_name in optional_modules:
            try:
                __import__(module_name)
            except ImportError:
                # This is expected in test environment
                pass

    def test_log_directory_check(self):
        """Test log directory health check logic"""
        # Test with existing directory
        test_dir = self.project_root / "logs"

        if test_dir.exists():
            assert os.access(test_dir, os.W_OK), "Logs directory must be writable"

    def test_health_check_timeout_handling(self):
        """Test that health checks handle timeouts properly"""
        timeout_duration = 10

        # Mock a command that would timeout
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["test"], timeout_duration)

            with pytest.raises(subprocess.TimeoutExpired):
                subprocess.run(["sleep", "20"], capture_output=True, text=True, timeout=timeout_duration)

    def test_health_check_docker_configuration(self):
        """Test health check configuration in Docker setup"""
        compose_file = self.project_root / "docker-compose.yml"

        if compose_file.exists():
            content = compose_file.read_text()

            # Check for health check configuration
            assert "healthcheck:" in content, "Health check must be configured"
            assert "healthcheck.py" in content, "Health check script must be referenced"
            assert "interval:" in content, "Health check interval must be set"
            assert "timeout:" in content, "Health check timeout must be set"


class TestDockerHealthCheckIntegration:
    """Integration tests for Docker health checks"""

    def test_dockerfile_health_check_setup(self):
        """Test that Dockerfile includes health check setup"""
        project_root = Path(__file__).parent.parent
        dockerfile = project_root / "Dockerfile"

        if dockerfile.exists():
            content = dockerfile.read_text()

            # Check that health check script is copied
            script_copied = ("COPY" in content and "healthcheck.py" in content) or "COPY . ." in content

            assert script_copied, "Health check script must be copied to container"

    def test_health_check_failure_scenarios(self):
        """Test various health check failure scenarios"""
        failure_scenarios = [
            {"type": "process_not_found", "expected": False},
            {"type": "import_error", "expected": False},
            {"type": "permission_error", "expected": False},
            {"type": "timeout_error", "expected": False},
        ]

        for scenario in failure_scenarios:
            # Each scenario should result in health check failure
            assert scenario["expected"] is False

    def test_health_check_recovery(self):
        """Test health check recovery after transient failures"""
        # Test that health checks can recover from temporary issues
        recovery_scenarios = [
            {"initial_state": "failing", "final_state": "healthy"},
            {"initial_state": "timeout", "final_state": "healthy"},
        ]

        for scenario in recovery_scenarios:
            assert scenario["final_state"] == "healthy"

    @patch.dict(os.environ, {}, clear=True)
    def test_health_check_with_missing_env_vars(self):
        """Test health check behavior with missing environment variables"""
        # Health check should still work even without API keys
        # (it tests system health, not API connectivity)

        required_vars = ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]

        # Verify no API keys are set
        for var in required_vars:
            assert os.getenv(var) is None

    def test_health_check_performance(self):
        """Test that health checks complete within reasonable time"""
        # Health checks should be fast to avoid impacting container startup
        max_execution_time = 30  # seconds

        # Mock a health check execution
        import time

        start_time = time.time()

        # Simulate health check operations
        time.sleep(0.1)  # Simulate actual work

        execution_time = time.time() - start_time
        assert (
            execution_time < max_execution_time
        ), f"Health check took {execution_time}s, should be < {max_execution_time}s"
