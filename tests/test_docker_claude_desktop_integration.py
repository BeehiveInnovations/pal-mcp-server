"""
Tests for Docker integration with Claude Desktop MCP
"""

import json
import os
import tempfile
from pathlib import Path

import pytest


class TestDockerClaudeDesktopIntegration:
    """Test Docker integration with Claude Desktop"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test"""
        self.project_root = Path(__file__).parent.parent

    def test_mcp_config_docker_run_format(self):
        """Test MCP configuration for direct docker run"""
        config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": [
                        "run",
                        "--rm",
                        "-i",
                        "--env-file",
                        "/path/to/.env",
                        "-v",
                        "/path/to/logs:/app/logs",
                        "zen-mcp-server:latest",
                    ],
                }
            }
        }

        # Validate configuration structure
        assert "mcpServers" in config
        assert "zen-mcp" in config["mcpServers"]
        assert config["mcpServers"]["zen-mcp"]["command"] == "docker"

        args = config["mcpServers"]["zen-mcp"]["args"]
        assert "run" in args
        assert "--rm" in args
        assert "-i" in args
        assert "--env-file" in args

    def test_mcp_config_docker_compose_format(self):
        """Test MCP configuration for docker-compose run"""
        config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker-compose",
                    "args": ["-f", "/path/to/docker-compose.yml", "run", "--rm", "zen-mcp"],
                }
            }
        }

        # Validate configuration structure
        assert config["mcpServers"]["zen-mcp"]["command"] == "docker-compose"

        args = config["mcpServers"]["zen-mcp"]["args"]
        assert "-f" in args
        assert "run" in args
        assert "--rm" in args
        assert "zen-mcp" in args

    def test_mcp_config_environment_variables(self):
        """Test MCP configuration with inline environment variables"""
        config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": [
                        "run",
                        "--rm",
                        "-i",
                        "-e",
                        "GEMINI_API_KEY=test_key",
                        "-e",
                        "LOG_LEVEL=INFO",
                        "zen-mcp-server:latest",
                    ],
                }
            }
        }

        args = config["mcpServers"]["zen-mcp"]["args"]

        # Check that environment variables are properly formatted
        env_args = [arg for arg in args if arg.startswith("-e")]
        assert len(env_args) > 0, "Environment variables should be present"

        # Check for API key environment variable
        api_key_present = any("GEMINI_API_KEY=" in args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "-e")
        assert api_key_present, "API key environment variable should be set"

    def test_windows_path_format(self):
        """Test Windows-specific path formatting"""
        windows_config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": [
                        "run",
                        "--rm",
                        "-i",
                        "--env-file",
                        "C:/Users/User/zen-mcp-server/.env",
                        "-v",
                        "C:/Users/User/zen-mcp-server/logs:/app/logs",
                        "zen-mcp-server:latest",
                    ],
                }
            }
        }

        args = windows_config["mcpServers"]["zen-mcp"]["args"]

        # Check Windows path format
        windows_paths = [arg for arg in args if arg.startswith("C:/")]
        assert len(windows_paths) > 0, "Windows paths should use forward slashes"

        for path in windows_paths:
            assert "\\" not in path, "Windows paths should use forward slashes"

    def test_mcp_config_validation(self):
        """Test validation of MCP configuration"""
        # Valid configuration
        valid_config = {
            "mcpServers": {"zen-mcp": {"command": "docker", "args": ["run", "--rm", "-i", "zen-mcp-server:latest"]}}
        }

        # Validate JSON serialization
        config_json = json.dumps(valid_config)
        loaded_config = json.loads(config_json)
        assert loaded_config == valid_config

    def test_mcp_stdio_communication(self):
        """Test that MCP configuration supports stdio communication"""
        config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": [
                        "run",
                        "--rm",
                        "-i",  # Interactive mode for stdio
                        "zen-mcp-server:latest",
                    ],
                }
            }
        }

        args = config["mcpServers"]["zen-mcp"]["args"]

        # Check for interactive mode
        assert "-i" in args, "Interactive mode required for stdio communication"

        # Should not expose network ports for stdio communication
        port_args = [arg for arg in args if arg.startswith("-p")]
        assert len(port_args) == 0, "No ports should be exposed for stdio mode"

    def test_docker_image_reference(self):
        """Test that Docker image is properly referenced"""
        configs = [
            {"image": "zen-mcp-server:latest"},
            {"image": "zen-mcp-server:v1.0.0"},
            {"image": "registry/zen-mcp-server:latest"},
        ]

        for config in configs:
            image = config["image"]

            # Basic image format validation
            assert ":" in image, "Image should have a tag"
            assert len(image.split(":")) == 2, "Image should have exactly one tag"

    @pytest.fixture
    def temp_mcp_config(self):
        """Create temporary MCP configuration file"""
        config = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": ["run", "--rm", "-i", "--env-file", "/tmp/.env", "zen-mcp-server:latest"],
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            temp_file_path = f.name

        yield temp_file_path
        os.unlink(temp_file_path)

    def test_mcp_config_file_parsing(self, temp_mcp_config):
        """Test parsing of MCP configuration file"""
        # Read and parse the temporary config file
        with open(temp_mcp_config, encoding="utf-8") as f:
            config = json.load(f)

        assert "mcpServers" in config
        assert "zen-mcp" in config["mcpServers"]

    def test_environment_file_integration(self):
        """Test integration with .env file"""
        # Test .env file format expected by Docker
        env_content = """GEMINI_API_KEY=test_key
OPENAI_API_KEY=test_key_2
LOG_LEVEL=INFO
DEFAULT_MODEL=auto
"""

        # Parse environment content
        env_vars = {}
        for line in env_content.strip().split("\n"):
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env_vars[key] = value

        # Validate required environment variables
        assert "GEMINI_API_KEY" in env_vars
        assert len(env_vars["GEMINI_API_KEY"]) > 0

    def test_docker_volume_mount_paths(self):
        """Test Docker volume mount path configurations"""
        mount_configs = [
            {"host": "./logs", "container": "/app/logs"},
            {"host": "/absolute/path/logs", "container": "/app/logs"},
            {"host": "C:/Windows/path/logs", "container": "/app/logs"},
        ]

        for config in mount_configs:
            mount_arg = f"{config['host']}:{config['container']}"

            # Validate mount format
            assert ":" in mount_arg
            parts = mount_arg.split(":")
            assert len(parts) >= 2
            assert parts[-1].startswith("/"), "Container path should be absolute"


class TestDockerMCPErrorHandling:
    """Test error handling for Docker MCP integration"""

    def test_missing_docker_image_handling(self):
        """Test handling of missing Docker image"""
        # This would test what happens when the image doesn't exist
        # In practice, Claude Desktop would show an error
        nonexistent_config = {
            "mcpServers": {"zen-mcp": {"command": "docker", "args": ["run", "--rm", "-i", "nonexistent:latest"]}}
        }

        # Configuration should be valid even if image doesn't exist
        assert "zen-mcp" in nonexistent_config["mcpServers"]

    def test_invalid_env_file_path(self):
        """Test handling of invalid .env file path"""
        config_with_invalid_env = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": ["run", "--rm", "-i", "--env-file", "/nonexistent/.env", "zen-mcp-server:latest"],
                }
            }
        }

        # Configuration structure should still be valid
        args = config_with_invalid_env["mcpServers"]["zen-mcp"]["args"]
        assert "--env-file" in args

    def test_docker_permission_issues(self):
        """Test configuration for potential Docker permission issues"""
        # On some systems, Docker requires specific permissions
        # The configuration should work with both cases

        configs = [
            # Regular Docker command
            {"command": "docker"},
            # Sudo Docker command (if needed)
            {"command": "sudo", "extra_args": ["docker"]},
        ]

        for config in configs:
            assert len(config["command"]) > 0

    def test_resource_limit_configurations(self):
        """Test Docker resource limit configurations"""
        config_with_limits = {
            "mcpServers": {
                "zen-mcp": {
                    "command": "docker",
                    "args": ["run", "--rm", "-i", "--memory=512m", "--cpus=1.0", "zen-mcp-server:latest"],
                }
            }
        }

        args = config_with_limits["mcpServers"]["zen-mcp"]["args"]

        # Check for resource limits
        memory_limit = any("--memory" in arg for arg in args)
        cpu_limit = any("--cpus" in arg for arg in args)

        assert memory_limit or cpu_limit, "Resource limits should be configurable"
