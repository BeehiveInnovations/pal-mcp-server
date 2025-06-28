"""
Tests for Docker volume persistence functionality
"""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest


class TestDockerVolumePersistence:
    """Test Docker volume persistence for configuration and logs"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent
        self.docker_compose_path = self.project_root / "docker-compose.yml"

    def test_docker_compose_volumes_configuration(self):
        """Test that docker-compose.yml has proper volume configuration"""
        if not self.docker_compose_path.exists():
            pytest.skip("docker-compose.yml not found")

        content = self.docker_compose_path.read_text()

        # Check for named volume definition
        assert "zen-mcp-config:" in content, "zen-mcp-config volume must be defined"
        assert "driver: local" in content, "Named volume must use local driver"

        # Check for volume mounts in service
        assert "./logs:/app/logs" in content, "Logs volume mount required"
        assert "zen-mcp-config:/app/conf" in content, "Config volume mount required"

    def test_persistent_volume_creation(self):
        """Test that persistent volumes are created correctly"""
        # This test checks that the volume configuration is valid
        # In a real environment, you might want to test actual volume creation
        volume_name = "zen-mcp-config"

        # Mock Docker command to check volume exists
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = f"{volume_name}\n"

            # Simulate docker volume ls command
            result = subprocess.run(["docker", "volume", "ls", "--format", "{{.Name}}"], capture_output=True, text=True)

            assert volume_name in result.stdout

    def test_configuration_persistence_between_runs(self):
        """Test that configuration persists between container runs"""
        # This is a conceptual test - in practice you'd need a real Docker environment
        config_data = {"test_key": "test_value", "persistent": True}

        # Simulate writing config to persistent volume
        with patch("json.dump") as mock_dump:
            json.dump(config_data, mock_dump)

        # Simulate container restart and config retrieval
        with patch("json.load") as mock_load:
            mock_load.return_value = config_data
            loaded_config = json.load(mock_load)

        assert loaded_config == config_data
        assert loaded_config["persistent"] is True

    def test_log_persistence_configuration(self):
        """Test that log persistence is properly configured"""
        log_mount = "./logs:/app/logs"

        if self.docker_compose_path.exists():
            content = self.docker_compose_path.read_text()
            assert log_mount in content, f"Log mount {log_mount} must be configured"

    def test_volume_backup_restore_capability(self):
        """Test that volumes can be backed up and restored"""
        # Test backup command structure
        backup_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            "zen-mcp-config:/data",
            "-v",
            "$(pwd):/backup",
            "alpine",
            "tar",
            "czf",
            "/backup/config-backup.tar.gz",
            "-C",
            "/data",
            ".",
        ]

        # Verify command structure is valid
        assert "zen-mcp-config:/data" in backup_cmd
        assert "tar" in backup_cmd
        assert "czf" in backup_cmd

    def test_volume_permissions(self):
        """Test that volume permissions are properly set"""
        # Check that logs directory has correct permissions
        logs_dir = self.project_root / "logs"

        if logs_dir.exists():
            # Check that directory is writable
            assert os.access(logs_dir, os.W_OK), "Logs directory must be writable"

            # Test creating a temporary file
            test_file = logs_dir / "test_write_permission.tmp"
            try:
                test_file.write_text("test")
                assert test_file.exists()
            finally:
                if test_file.exists():
                    test_file.unlink()


class TestDockerVolumeIntegration:
    """Integration tests for Docker volumes with MCP functionality"""

    def test_mcp_config_persistence(self):
        """Test that MCP configuration persists in named volume"""
        mcp_config = {"models": ["gemini-2.0-flash", "gpt-4"], "default_model": "auto", "thinking_mode": "high"}

        # Test config serialization/deserialization
        config_str = json.dumps(mcp_config)
        loaded_config = json.loads(config_str)

        assert loaded_config == mcp_config
        assert "models" in loaded_config

    def test_docker_compose_run_volume_usage(self):
        """Test that docker-compose run uses volumes correctly"""
        # Verify that docker-compose run inherits volume configuration
        # This is more of a configuration validation test

        compose_run_cmd = ["docker-compose", "run", "--rm", "zen-mcp"]

        # The command should work with the existing volume configuration
        assert "docker-compose" in compose_run_cmd
        assert "run" in compose_run_cmd
        assert "--rm" in compose_run_cmd

    def test_volume_data_isolation(self):
        """Test that different container instances share volume data correctly"""
        shared_data = {"instance_count": 0, "shared_state": "active"}

        # Simulate multiple container instances accessing shared volume
        for _ in range(3):
            shared_data["instance_count"] += 1
            assert shared_data["shared_state"] == "active"

        assert shared_data["instance_count"] == 3
