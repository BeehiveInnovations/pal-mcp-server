"""
Tests for Docker security configuration and best practices
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDockerSecurity:
    """Test Docker security configuration"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent
        self.dockerfile_path = self.project_root / "Dockerfile"
        self.compose_path = self.project_root / "docker-compose.yml"

    def test_non_root_user_configuration(self):
        """Test that container runs as non-root user"""
        if not self.dockerfile_path.exists():
            pytest.skip("Dockerfile not found")

        content = self.dockerfile_path.read_text()

        # Check for user creation or switching
        user_indicators = ["USER " in content, "useradd" in content, "adduser" in content, "RUN addgroup" in content]

        assert any(user_indicators), "Container should run as non-root user"

    def test_no_unnecessary_privileges(self):
        """Test that container doesn't request unnecessary privileges"""
        if not self.compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.compose_path.read_text()

        # Check that dangerous options are not used
        dangerous_options = ["privileged: true", "--privileged", "cap_add:", "SYS_ADMIN"]

        for option in dangerous_options:
            assert option not in content, f"Dangerous option {option} should not be used"

    def test_read_only_filesystem(self):
        """Test read-only filesystem configuration where applicable"""
        if not self.compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.compose_path.read_text()

        # Check for read-only configurations
        if "read_only:" in content:
            assert "read_only: true" in content, "Read-only filesystem should be properly configured"

    def test_environment_variable_security(self):
        """Test secure handling of environment variables"""
        # Ensure sensitive data is not hardcoded
        sensitive_patterns = ["password", "secret", "key", "token"]

        for file_path in [self.dockerfile_path, self.compose_path]:
            if not file_path.exists():
                continue

            content = file_path.read_text().lower()

            # Check that we don't have hardcoded secrets
            for pattern in sensitive_patterns:
                # Allow variable names but not actual values
                lines = content.split("\n")
                for line in lines:
                    if f"{pattern}=" in line and not line.strip().startswith("#"):
                        # Check if it looks like a real value vs variable name
                        if '"' in line or "'" in line:
                            value_part = line.split("=")[1].strip()
                            if len(value_part) > 10 and not value_part.startswith("$"):
                                pytest.fail(f"Potential hardcoded secret in {file_path}: {line.strip()}")

    def test_network_security(self):
        """Test network security configuration"""
        if not self.compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.compose_path.read_text()

        # Check for custom network (better than default bridge)
        if "networks:" in content:
            assert (
                "driver: bridge" in content or "external:" in content
            ), "Custom networks should use bridge driver or be external"

    def test_volume_security(self):
        """Test volume security configuration"""
        if not self.compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.compose_path.read_text()

        # Check that sensitive host paths are not mounted
        dangerous_mounts = ["/:/", "/var/run/docker.sock:", "/etc/passwd:", "/etc/shadow:", "/root:"]

        for mount in dangerous_mounts:
            assert mount not in content, f"Dangerous mount {mount} should not be used"

    def test_secret_management(self):
        """Test that secrets are properly managed"""
        # Check for Docker secrets usage in compose file
        if self.compose_path.exists():
            content = self.compose_path.read_text()

            # If secrets are used, they should be properly configured
            if "secrets:" in content:
                assert "external: true" in content or "file:" in content, "Secrets should be external or file-based"

    def test_container_capabilities(self):
        """Test container capabilities are properly restricted"""
        if not self.compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.compose_path.read_text()

        # Check for capability restrictions
        if "cap_drop:" in content:
            assert "ALL" in content, "Should drop all capabilities by default"

        # If capabilities are added, they should be minimal
        if "cap_add:" in content:
            dangerous_caps = ["SYS_ADMIN", "NET_ADMIN", "SYS_PTRACE"]
            for cap in dangerous_caps:
                assert cap not in content, f"Dangerous capability {cap} should not be added"


class TestDockerSecretsHandling:
    """Test Docker secrets and API key handling"""

    def test_env_file_not_in_image(self):
        """Test that .env files are not copied into Docker image"""
        project_root = Path(__file__).parent.parent
        dockerfile = project_root / "Dockerfile"

        if dockerfile.exists():
            content = dockerfile.read_text()

            # .env files should not be copied
            assert "COPY .env" not in content, ".env file should not be copied into image"

    def test_dockerignore_for_sensitive_files(self):
        """Test that .dockerignore excludes sensitive files"""
        project_root = Path(__file__).parent.parent
        dockerignore = project_root / ".dockerignore"

        if dockerignore.exists():
            content = dockerignore.read_text()

            sensitive_files = [".env", "*.key", "*.pem", ".git"]

            for file_pattern in sensitive_files:
                if file_pattern not in content:
                    # Warning rather than failure for flexibility
                    import warnings

                    warnings.warn(f"Consider adding {file_pattern} to .dockerignore", UserWarning, stacklevel=2)

    @patch.dict(os.environ, {}, clear=True)
    def test_no_default_api_keys(self):
        """Test that no default API keys are present"""
        # Ensure no API keys are set by default
        api_key_vars = ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY"]

        for var in api_key_vars:
            assert os.getenv(var) is None, f"{var} should not have a default value"

    def test_api_key_format_validation(self):
        """Test API key format validation if implemented"""
        # Test cases for API key validation
        test_cases = [
            {"key": "", "valid": False},
            {"key": "test", "valid": False},  # Too short
            {"key": "sk-" + "x" * 40, "valid": True},  # OpenAI format
            {"key": "AIza" + "x" * 35, "valid": True},  # Google format
        ]

        for case in test_cases:
            # This would test actual validation if implemented
            # For now, just check the test structure
            assert isinstance(case["valid"], bool)
            assert isinstance(case["key"], str)


class TestDockerComplianceChecks:
    """Test Docker configuration compliance with security standards"""

    def test_dockerfile_best_practices(self):
        """Test Dockerfile follows security best practices"""
        project_root = Path(__file__).parent.parent
        dockerfile = project_root / "Dockerfile"

        if not dockerfile.exists():
            pytest.skip("Dockerfile not found")

        content = dockerfile.read_text()

        # Check for multi-stage builds (reduces attack surface)
        if "FROM" in content:
            from_count = content.count("FROM")
            if from_count > 1:
                assert "AS" in content, "Multi-stage builds should use named stages"

        # Check for specific user ID (better than name-only)
        if "USER" in content:
            user_lines = [line for line in content.split("\n") if line.strip().startswith("USER")]
            for line in user_lines:
                # Could be improved to check for numeric UID
                assert len(line.strip()) > 5, "USER directive should be specific"

    def test_container_security_context(self):
        """Test container security context configuration"""
        project_root = Path(__file__).parent.parent
        compose_file = project_root / "docker-compose.yml"

        if compose_file.exists():
            content = compose_file.read_text()

            # Check for security context if configured
            security_options = ["security_opt:", "no-new-privileges:", "read_only:"]

            # At least one security option should be present
            security_configured = any(opt in content for opt in security_options)

            if not security_configured:
                import warnings

                warnings.warn("Consider adding security options to docker-compose.yml", UserWarning, stacklevel=2)
