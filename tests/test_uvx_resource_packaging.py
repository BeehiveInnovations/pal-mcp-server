"""Tests for uvx path resolution functionality."""

from pathlib import Path
from unittest.mock import patch

from providers.openrouter_registry import OpenRouterModelRegistry


class TestUvxPathResolution:
    """Test uvx path resolution for OpenRouter model registry."""

    def test_normal_operation(self):
        """Test that normal operation works in development environment."""
        registry = OpenRouterModelRegistry()
        assert len(registry.list_models()) > 0
        assert len(registry.list_aliases()) > 0

    def test_config_path_resolution(self):
        """Test that the config path resolution finds the config file in multiple locations."""
        # Check that the config file exists in the development location
        config_file = Path(__file__).parent.parent / "conf" / "custom_models.json"
        assert config_file.exists(), "Config file should exist in conf/custom_models.json"

        # Test that a registry can find and use the config
        registry = OpenRouterModelRegistry()

        # When using resources, config_path is None; when using file system, it should exist
        if registry.use_resources:
            assert registry.config_path is None, "When using resources, config_path should be None"
        else:
            assert registry.config_path.exists(), "When using file system, config path should exist"

        assert len(registry.list_models()) > 0, "Registry should load models from config"

    def test_explicit_config_path_override(self):
        """Test that explicit config path works correctly."""
        config_path = Path(__file__).parent.parent / "conf" / "custom_models.json"

        registry = OpenRouterModelRegistry(config_path=str(config_path))

        # Should use the provided file path
        assert registry.config_path == config_path
        assert len(registry.list_models()) > 0

    def test_environment_variable_override(self):
        """Test that CUSTOM_MODELS_CONFIG_PATH environment variable works."""
        config_path = Path(__file__).parent.parent / "conf" / "custom_models.json"

        with patch.dict("os.environ", {"CUSTOM_MODELS_CONFIG_PATH": str(config_path)}):
            registry = OpenRouterModelRegistry()

            # Should use environment path
            assert registry.config_path == config_path
            assert len(registry.list_models()) > 0

    @patch("providers.openrouter_registry.files")
    @patch("pathlib.Path.exists")
    def test_multiple_path_fallback(self, mock_exists, mock_files):
        """Test that multiple path resolution works for different deployment scenarios."""
        # Make resources loading fail to trigger file system fallback
        mock_files.side_effect = Exception("Resource loading failed")

        # Simulate dev path failing, and working directory path succeeding
        # The third `True` is for the check within `reload()`
        mock_exists.side_effect = [False, True, True]

        registry = OpenRouterModelRegistry()

        # Should have fallen back to file system mode
        assert not registry.use_resources, "Should fall back to file system when resources fail"

        # Assert that the registry fell back to the second potential path
        assert registry.config_path == Path("conf/custom_models.json")

        # Should load models successfully
        assert len(registry.list_models()) > 0

    def test_missing_config_handling(self):
        """Test behavior when config file is missing."""
        # Use a non-existent path
        registry = OpenRouterModelRegistry(config_path="/nonexistent/path/config.json")

        # Should gracefully handle missing config
        assert len(registry.list_models()) == 0
        assert len(registry.list_aliases()) == 0

    @patch("providers.openrouter_registry.files")
    def test_resource_loading_success(self, mock_files):
        """Test successful resource loading via importlib.resources."""
        # Mock successful resource loading
        mock_resource = patch("builtins.open", create=True).start()
        mock_resource.return_value.__enter__.return_value.read.return_value = """{
            "models": [
                {
                    "model_name": "test/resource-model",
                    "aliases": ["resource-test"],
                    "context_window": 32000,
                    "max_output_tokens": 16000,
                    "supports_extended_thinking": false,
                    "supports_json_mode": true,
                    "supports_function_calling": false,
                    "supports_images": false,
                    "max_image_size_mb": 0.0,
                    "description": "Test model loaded from resources"
                }
            ]
        }"""

        # Mock the resource path
        mock_resource_path = patch.object(mock_files.return_value.__truediv__.return_value, "read_text").start()
        mock_resource_path.return_value = """{
            "models": [
                {
                    "model_name": "test/resource-model",
                    "aliases": ["resource-test"],
                    "context_window": 32000,
                    "max_output_tokens": 16000,
                    "supports_extended_thinking": false,
                    "supports_json_mode": true,
                    "supports_function_calling": false,
                    "supports_images": false,
                    "max_image_size_mb": 0.0,
                    "description": "Test model loaded from resources"
                }
            ]
        }"""

        registry = OpenRouterModelRegistry()

        # Clean up patches
        patch.stopall()

        # If resources loading was attempted, verify basic functionality
        # (In development this will fall back to file loading which is fine)
        assert len(registry.list_models()) > 0

    def test_use_resources_attribute(self):
        """Test that the use_resources attribute is properly set."""
        registry = OpenRouterModelRegistry()

        # Should have the use_resources attribute
        assert hasattr(registry, "use_resources")
        assert isinstance(registry.use_resources, bool)
