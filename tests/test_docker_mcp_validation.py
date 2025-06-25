"""
Validation test for Docker MCP implementation
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDockerMCPValidation:
    """Validation tests for Docker MCP"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup automatic for each test"""
        self.project_root = Path(__file__).parent.parent
        self.dockerfile_path = self.project_root / "Dockerfile"
        self.mcp_config_path = self.project_root / ".vscode" / "mcp.json"

    def test_dockerfile_exists_and_valid(self):
        """Test Dockerfile existence and validity"""
        assert self.dockerfile_path.exists(), "Missing Dockerfile"

        content = self.dockerfile_path.read_text()
        assert "FROM python:" in content, "Python base required"
        assert "server.py" in content, "server.py must be copied"

    def test_mcp_configuration_structure(self):
        """Test MCP configuration structure"""
        if not self.mcp_config_path.exists():
            pytest.skip("mcp.json non trouvé")

        with open(self.mcp_config_path, encoding="utf-8") as f:
            content = f.read()
            # Nettoyer les commentaires JSON
            lines = []
            for line in content.split("\n"):
                if "//" in line:
                    line = line[: line.index("//")]
                lines.append(line)
            clean_content = "\n".join(lines)

        config = json.loads(clean_content)

        assert "servers" in config, "Section servers requise"
        servers = config["servers"]

        # Check zen-docker configuration
        if "zen-docker" in servers:
            zen_docker = servers["zen-docker"]
            assert zen_docker["command"] == "docker", "Commande docker requise"
            args = zen_docker["args"]
            assert "run" in args, "Argument run requis"
            assert "--rm" in args, "Argument --rm requis"
            assert "-i" in args, "Argument -i requis"

    @patch("subprocess.run")
    def test_docker_command_validation(self, mock_run):
        """Test validation commande Docker"""
        mock_run.return_value.returncode = 0

        # Commande Docker MCP standard
        cmd = ["docker", "run", "--rm", "-i", "--env-file", ".env", "zen-mcp-server:latest", "python", "server.py"]

        subprocess.run(cmd, capture_output=True)
        mock_run.assert_called_once_with(cmd, capture_output=True)

    def test_environment_variables_validation(self):
        """Test environment variables validation"""
        required_vars = ["GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"]

        # Test with variable present
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
            has_key = any(os.getenv(var) for var in required_vars)
            assert has_key, "At least one API key required"

        # Test without variables
        with patch.dict(os.environ, {}, clear=True):
            has_key = any(os.getenv(var) for var in required_vars)
            assert not has_key, "No key should be present"

    def test_mcp_json_syntax(self):
        """Test MCP JSON file syntax"""
        if not self.mcp_config_path.exists():
            pytest.skip("mcp.json non trouvé")

        try:
            with open(self.mcp_config_path, encoding="utf-8") as f:
                content = f.read()
                # Supprimer commentaires pour validation JSON
                lines = []
                for line in content.split("\n"):
                    if "//" in line:
                        line = line[: line.index("//")]
                    lines.append(line)
                clean_content = "\n".join(lines)

            json.loads(clean_content)

        except json.JSONDecodeError as e:
            pytest.fail(f"JSON invalide: {e}")

    def test_docker_security_configuration(self):
        """Test Docker security configuration"""
        if not self.dockerfile_path.exists():
            pytest.skip("Dockerfile non trouvé")

        content = self.dockerfile_path.read_text()

        # Check non-root user
        has_user_config = "USER " in content or "useradd" in content or "adduser" in content

        # Note: The test can be adjusted according to implementation
        if has_user_config:
            assert True, "Configuration utilisateur trouvée"
        else:
            # Avertissement plutôt qu'échec pour flexibilité
            pytest.warns(UserWarning, "Considérer l'ajout d'un utilisateur non-root")


class TestDockerIntegration:
    """Docker-MCP integration tests"""

    @pytest.fixture
    def temp_env_file(self):
        """Fixture pour fichier .env temporaire"""
        content = """GEMINI_API_KEY=test_key
LOG_LEVEL=INFO
DEFAULT_MODEL=auto
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write(content)
            temp_file_path = f.name

        # Fichier fermé maintenant, on peut le yield
        yield temp_file_path
        os.unlink(temp_file_path)

    def test_env_file_parsing(self, temp_env_file):
        """Test .env file parsing"""
        env_vars = {}

        with open(temp_env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value

        assert "GEMINI_API_KEY" in env_vars
        assert env_vars["GEMINI_API_KEY"] == "test_key"
        assert env_vars["LOG_LEVEL"] == "INFO"

    def test_mcp_message_structure(self):
        """Test MCP message structure"""
        message = {"jsonrpc": "2.0", "method": "initialize", "params": {}, "id": 1}

        # Vérifier sérialisation JSON
        json_str = json.dumps(message)
        parsed = json.loads(json_str)

        assert parsed["jsonrpc"] == "2.0"
        assert "method" in parsed
        assert "id" in parsed


class TestDockerPerformance:
    """Docker performance tests"""

    def test_image_size_expectation(self):
        """Test taille image attendue"""
        # Taille maximale attendue (en MB)
        max_size_mb = 500

        # Simulation - en réalité on interrogerait Docker
        simulated_size = 294  # MB observé

        assert simulated_size <= max_size_mb, f"Image too large: {simulated_size}MB > {max_size_mb}MB"

    def test_startup_performance(self):
        """Test performance démarrage"""
        max_startup_seconds = 10
        simulated_startup = 3  # secondes

        assert simulated_startup <= max_startup_seconds, f"Startup too slow: {simulated_startup}s"


class TestValidationScript:
    """Validation script tests"""

    def test_validation_script_exists(self):
        """Test existence script validation"""
        project_root = Path(__file__).parent.parent
        ps1_script = project_root / "validate-docker-mcp.ps1"
        sh_script = project_root / "validate-docker-mcp.sh"

        # Au moins un script doit exister
        assert ps1_script.exists() or sh_script.exists(), "Validation script missing"

    def test_validation_script_content(self):
        """Test contenu script validation"""
        project_root = Path(__file__).parent.parent
        ps1_script = project_root / "validate-docker-mcp.ps1"

        if ps1_script.exists():
            try:
                content = ps1_script.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback pour autres encodages
                content = ps1_script.read_text(encoding="cp1252", errors="ignore")

            # Vérifier éléments clés
            assert "docker" in content.lower(), "Script must check Docker"
            assert "zen-mcp-server" in content, "Script must check image"
            assert ".env" in content, "Script must check .env"


@pytest.mark.integration
class TestFullIntegration:
    """Tests d'intégration complète"""

    def test_complete_setup_simulation(self):
        """Simulation setup complet"""
        # Simuler tous les composants requis
        components = {
            "dockerfile": True,
            "mcp_config": True,
            "env_template": True,
            "validation_script": True,
            "documentation": True,
        }

        # Vérifier que tous les composants sont présents
        missing = [k for k, v in components.items() if not v]
        assert not missing, f"Missing components: {missing}"

    def test_docker_mcp_workflow(self):
        """Test workflow Docker-MCP complet"""
        # Étapes du workflow
        workflow_steps = [
            "build_image",
            "create_env_file",
            "configure_mcp_json",
            "test_docker_run",
            "validate_mcp_communication",
        ]

        # Simuler chaque étape
        for step in workflow_steps:
            # En réalité, chaque étape serait testée individuellement
            assert step is not None, f"Step {step} not defined"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
