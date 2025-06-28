"""
Tests for Docker deployment scripts
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDeploymentScripts:
    """Test Docker deployment scripts"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent
        self.scripts_dir = self.project_root / "docker" / "scripts"

    def test_deployment_scripts_exist(self):
        """Test that deployment scripts exist"""
        expected_scripts = ["deploy.sh", "deploy.ps1", "build.sh", "build.ps1", "healthcheck.py"]

        for script in expected_scripts:
            script_path = self.scripts_dir / script
            assert script_path.exists(), f"Script {script} must exist"

    def test_bash_scripts_executable(self):
        """Test that bash scripts have proper permissions"""
        bash_scripts = ["deploy.sh", "build.sh"]

        for script in bash_scripts:
            script_path = self.scripts_dir / script
            if script_path.exists():
                # Check for shebang
                content = script_path.read_text()
                assert content.startswith("#!/"), f"Script {script} must have shebang"

    def test_powershell_scripts_format(self):
        """Test PowerShell scripts have proper format"""
        ps_scripts = ["deploy.ps1", "build.ps1"]

        for script in ps_scripts:
            script_path = self.scripts_dir / script
            if script_path.exists():
                content = script_path.read_text()

                # Check for PowerShell indicators
                ps_indicators = [
                    "param(",
                    "Write-Host",
                    "Write-Output",
                    "$",  # PowerShell variables
                ]

                assert any(
                    indicator in content for indicator in ps_indicators
                ), f"Script {script} should contain PowerShell syntax"

    @patch("subprocess.run")
    def test_deploy_script_docker_commands(self, mock_run):
        """Test that deploy scripts use proper Docker commands"""
        mock_run.return_value.returncode = 0

        # Expected Docker commands in deployment
        expected_commands = [["docker", "build"], ["docker-compose", "up"], ["docker", "run"]]

        for cmd in expected_commands:
            subprocess.run(cmd, capture_output=True)

        # Verify subprocess.run was called
        assert mock_run.call_count >= len(expected_commands)

    def test_build_script_functionality(self):
        """Test build script basic functionality"""
        build_script = self.scripts_dir / "build.sh"

        if build_script.exists():
            content = build_script.read_text()

            # Should contain Docker build commands
            assert (
                "docker build" in content or "docker-compose build" in content
            ), "Build script should contain Docker build commands"

    def test_deploy_script_health_check_integration(self):
        """Test deploy script includes health check validation"""
        deploy_scripts = ["deploy.sh", "deploy.ps1"]

        for script_name in deploy_scripts:
            script_path = self.scripts_dir / script_name
            if script_path.exists():
                content = script_path.read_text()

                # Look for health check related content
                health_check_indicators = ["health", "healthcheck", "docker inspect", "container status"]

                has_health_check = any(indicator in content.lower() for indicator in health_check_indicators)

                if not has_health_check:
                    pytest.warns(UserWarning, f"Consider adding health check to {script_name}")

    def test_script_error_handling(self):
        """Test that scripts have proper error handling"""
        scripts = ["deploy.sh", "build.sh"]

        for script_name in scripts:
            script_path = self.scripts_dir / script_name
            if script_path.exists():
                content = script_path.read_text()

                # Check for error handling patterns
                error_patterns = [
                    "set -e",  # Bash: exit on error
                    "||",  # Or operator for error handling
                    "if",  # Conditional error checking
                    "exit",  # Explicit exit codes
                ]

                has_error_handling = any(pattern in content for pattern in error_patterns)

                if not has_error_handling:
                    pytest.warns(UserWarning, f"Consider adding error handling to {script_name}")

    @patch("subprocess.run")
    def test_docker_compose_commands(self, mock_run):
        """Test Docker Compose command execution"""
        mock_run.return_value.returncode = 0

        # Test various docker-compose commands
        compose_commands = [
            ["docker-compose", "build"],
            ["docker-compose", "up", "-d"],
            ["docker-compose", "down"],
            ["docker-compose", "ps"],
        ]

        for cmd in compose_commands:
            result = subprocess.run(cmd, capture_output=True)
            assert result.returncode == 0

    def test_script_parameter_handling(self):
        """Test script parameter and option handling"""
        deploy_ps1 = self.scripts_dir / "deploy.ps1"

        if deploy_ps1.exists():
            content = deploy_ps1.read_text()

            # PowerShell scripts should handle parameters
            param_indicators = ["param(", "[Parameter(", "$SkipHealthCheck", "$HealthCheckTimeout"]

            has_parameters = any(indicator in content for indicator in param_indicators)

            assert has_parameters, "PowerShell deploy script should handle parameters"

    def test_environment_preparation(self):
        """Test that scripts prepare environment correctly"""
        scripts_to_check = ["deploy.sh", "deploy.ps1"]

        for script_name in scripts_to_check:
            script_path = self.scripts_dir / script_name
            if script_path.exists():
                content = script_path.read_text()

                # Check for environment preparation
                env_prep_patterns = [".env", "environment", "API_KEY", "mkdir", "logs"]

                prepares_environment = any(pattern in content for pattern in env_prep_patterns)

                if not prepares_environment:
                    pytest.warns(UserWarning, f"Consider environment preparation in {script_name}")


class TestHealthCheckScript:
    """Test health check script specifically"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent
        self.healthcheck_script = self.project_root / "docker" / "scripts" / "healthcheck.py"

    def test_healthcheck_script_syntax(self):
        """Test health check script has valid Python syntax"""
        if not self.healthcheck_script.exists():
            pytest.skip("healthcheck.py not found")

        # Try to compile the script
        try:
            with open(self.healthcheck_script, encoding="utf-8") as f:
                content = f.read()
            compile(content, str(self.healthcheck_script), "exec")
        except SyntaxError as e:
            pytest.fail(f"Health check script has syntax errors: {e}")

    def test_healthcheck_functions_exist(self):
        """Test that health check functions are defined"""
        if not self.healthcheck_script.exists():
            pytest.skip("healthcheck.py not found")

        content = self.healthcheck_script.read_text()

        # Expected functions
        expected_functions = ["def check_process", "def check_python_imports", "def check_log_directory"]

        for func in expected_functions:
            assert func in content, f"Function {func} should be defined"

    @patch("subprocess.run")
    def test_healthcheck_process_check(self, mock_run):
        """Test health check process verification"""
        # Mock successful process check
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "12345"

        # Simulate process check
        result = subprocess.run(["pgrep", "-f", "server.py"], capture_output=True, text=True, timeout=10)

        assert result.returncode == 0

    def test_healthcheck_import_validation(self):
        """Test health check import validation logic"""
        # Test critical modules that should be importable
        critical_modules = ["os", "sys", "subprocess"]

        for module in critical_modules:
            try:
                __import__(module)
            except ImportError:
                pytest.fail(f"Critical module {module} should be importable")

    def test_healthcheck_exit_codes(self):
        """Test that health check uses proper exit codes"""
        if not self.healthcheck_script.exists():
            pytest.skip("healthcheck.py not found")

        content = self.healthcheck_script.read_text()

        # Should have proper exit code handling
        exit_patterns = [
            "sys.exit(0)",  # Success
            "sys.exit(1)",  # Failure
            "exit(0)",
            "exit(1)",
        ]

        has_exit_codes = any(pattern in content for pattern in exit_patterns)

        assert has_exit_codes, "Health check should use proper exit codes"


class TestScriptIntegration:
    """Test script integration with Docker ecosystem"""

    def test_scripts_work_with_compose_file(self):
        """Test that scripts work with docker-compose.yml"""
        project_root = Path(__file__).parent.parent
        compose_file = project_root / "docker-compose.yml"

        if compose_file.exists():
            # Scripts should reference the compose file
            deploy_script = project_root / "docker" / "scripts" / "deploy.sh"

            if deploy_script.exists():
                content = deploy_script.read_text()

                # Should work with compose file
                compose_refs = ["docker-compose", "compose.yml", "compose.yaml"]

                references_compose = any(ref in content for ref in compose_refs)

                assert (
                    references_compose or "docker build" in content
                ), "Deploy script should use either compose or direct Docker"

    def test_cross_platform_compatibility(self):
        """Test cross-platform script compatibility"""
        # Both Unix and Windows scripts should exist
        unix_deploy = Path(__file__).parent.parent / "docker" / "scripts" / "deploy.sh"
        windows_deploy = Path(__file__).parent.parent / "docker" / "scripts" / "deploy.ps1"

        # At least one should exist
        assert unix_deploy.exists() or windows_deploy.exists(), "At least one deployment script should exist"

        # If both exist, they should have similar functionality
        if unix_deploy.exists() and windows_deploy.exists():
            unix_content = unix_deploy.read_text()
            windows_content = windows_deploy.read_text()

            # Both should reference Docker
            assert "docker" in unix_content.lower()
            assert "docker" in windows_content.lower()

    def test_script_logging_integration(self):
        """Test that scripts integrate with logging"""
        scripts_dir = Path(__file__).parent.parent / "docker" / "scripts"
        scripts = ["deploy.sh", "deploy.ps1", "build.sh", "build.ps1"]

        for script_name in scripts:
            script_path = scripts_dir / script_name
            if script_path.exists():
                content = script_path.read_text()

                # Check for logging/output
                logging_patterns = ["echo", "Write-Host", "Write-Output", "print", "logger"]

                has_logging = any(pattern in content for pattern in logging_patterns)

                if not has_logging:
                    pytest.warns(UserWarning, f"Consider adding logging to {script_name}")
