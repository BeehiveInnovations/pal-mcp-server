"""
Pytest configuration for Zen MCP Server tests
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest

# Ensure the parent directory is in the Python path for imports
parent_dir = Path(__file__).resolve().parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


# Set default model to a specific value for tests to avoid auto mode
# This prevents all tests from failing due to missing model parameter
os.environ["DEFAULT_MODEL"] = "gemini-2.5-flash"

# Force reload of config module to pick up the env var
import config  # noqa: E402

importlib.reload(config)

# Note: This creates a test sandbox environment
# Tests create their own temporary directories as needed

# Configure asyncio for Windows compatibility
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Register providers for all tests
from providers import ModelProviderRegistry  # noqa: E402
from providers.base import ProviderType  # noqa: E402
from providers.gemini import GeminiModelProvider  # noqa: E402
from providers.openai_provider import OpenAIModelProvider  # noqa: E402
from providers.xai import XAIModelProvider  # noqa: E402

# Register providers at test startup
ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

# Register CUSTOM provider if CUSTOM_API_URL is available (for integration tests)
# But only if we're actually running integration tests, not unit tests
if os.getenv("CUSTOM_API_URL") and "test_prompt_regression.py" in os.getenv("PYTEST_CURRENT_TEST", ""):
    from providers.custom import CustomProvider  # noqa: E402

    def custom_provider_factory(api_key=None):
        """Factory function that creates CustomProvider with proper parameters."""
        base_url = os.getenv("CUSTOM_API_URL", "")
        return CustomProvider(api_key=api_key or "", base_url=base_url)

    ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)


@pytest.fixture
def project_path(tmp_path):
    """
    Provides a temporary directory for tests.
    This ensures all file operations during tests are isolated.
    """
    # Create a subdirectory for this specific test
    test_dir = tmp_path / "test_workspace"
    test_dir.mkdir(parents=True, exist_ok=True)

    return test_dir


def _set_dummy_keys_if_missing():
    """Set dummy API keys only when they are completely absent."""
    for var in ("GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY"):
        if not os.environ.get(var):
            os.environ[var] = "dummy-key-for-tests"


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "no_mock_provider: disable automatic provider mocking")
    # Assume we need dummy keys until we learn otherwise
    config._needs_dummy_keys = True


def pytest_collection_modifyitems(session, config, items):
    """Hook that runs after test collection to check for no_mock_provider markers."""
    # Check if any test has the no_mock_provider marker
    for item in items:
        if item.get_closest_marker("no_mock_provider"):
            config._needs_dummy_keys = False
            break

    # Set dummy keys only if no test needs real keys
    if config._needs_dummy_keys:
        _set_dummy_keys_if_missing()


@pytest.fixture(autouse=True)
def mock_provider_availability(request, monkeypatch):
    """
    Automatically mock provider availability for all tests to prevent
    effective auto mode from being triggered when DEFAULT_MODEL is unavailable.

    This fixture ensures that when tests run with dummy API keys,
    the tools don't require model selection unless explicitly testing auto mode.
    """
    # Skip this fixture for tests that need real providers
    if hasattr(request, "node"):
        marker = request.node.get_closest_marker("no_mock_provider")
        if marker:
            return

    # Ensure providers are registered (in case other tests cleared the registry)
    from providers.base import ProviderType

    registry = ModelProviderRegistry()

    if ProviderType.GOOGLE not in registry._providers:
        ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
    if ProviderType.OPENAI not in registry._providers:
        ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
    if ProviderType.XAI not in registry._providers:
        ModelProviderRegistry.register_provider(ProviderType.XAI, XAIModelProvider)

    # Ensure CUSTOM provider is registered if needed for integration tests
    if (
        os.getenv("CUSTOM_API_URL")
        and "test_prompt_regression.py" in os.getenv("PYTEST_CURRENT_TEST", "")
        and ProviderType.CUSTOM not in registry._providers
    ):
        from providers.custom import CustomProvider

        def custom_provider_factory(api_key=None):
            base_url = os.getenv("CUSTOM_API_URL", "")
            return CustomProvider(api_key=api_key or "", base_url=base_url)

        ModelProviderRegistry.register_provider(ProviderType.CUSTOM, custom_provider_factory)

    from unittest.mock import MagicMock

    original_get_provider = ModelProviderRegistry.get_provider_for_model

    def mock_get_provider_for_model(model_name):
        # If it's a test looking for unavailable models, return None
        if model_name in ["unavailable-model", "gpt-5-turbo", "o3"]:
            return None
        # For common test models, return a mock provider
        if model_name in ["gemini-2.5-flash", "gemini-2.5-pro", "pro", "flash", "local-llama"]:
            # Try to use the real provider first if it exists
            real_provider = original_get_provider(model_name)
            if real_provider:
                return real_provider

            # Otherwise create a mock
            provider = MagicMock()
            # Set up the model capabilities mock with actual values
            capabilities = MagicMock()
            if model_name == "local-llama":
                capabilities.context_window = 128000  # 128K tokens for local-llama
                capabilities.supports_extended_thinking = False
                capabilities.input_cost_per_1k = 0.0  # Free local model
                capabilities.output_cost_per_1k = 0.0  # Free local model
            else:
                capabilities.context_window = 1000000  # 1M tokens for Gemini models
                capabilities.supports_extended_thinking = False
                capabilities.input_cost_per_1k = 0.075
                capabilities.output_cost_per_1k = 0.3
            provider.get_model_capabilities.return_value = capabilities
            return provider
        # Otherwise use the original logic
        return original_get_provider(model_name)

    monkeypatch.setattr(ModelProviderRegistry, "get_provider_for_model", mock_get_provider_for_model)

    # Also mock is_effective_auto_mode for all BaseTool instances to return False
    # unless we're specifically testing auto mode behavior
    from tools.shared.base_tool import BaseTool

    def mock_is_effective_auto_mode(self):
        # If this is an auto mode test file or specific auto mode test, use the real logic
        test_file = request.node.fspath.basename if hasattr(request, "node") and hasattr(request.node, "fspath") else ""
        test_name = request.node.name if hasattr(request, "node") else ""

        # Allow auto mode for tests in auto mode files or with auto in the name
        if (
            "auto_mode" in test_file.lower()
            or "auto" in test_name.lower()
            or "intelligent_fallback" in test_file.lower()
            or "per_tool_model_defaults" in test_file.lower()
        ):
            # Call original method logic
            from config import DEFAULT_MODEL

            if DEFAULT_MODEL.lower() == "auto":
                return True
            provider = ModelProviderRegistry.get_provider_for_model(DEFAULT_MODEL)
            return provider is None
        # For all other tests, return False to disable auto mode
        return False

    monkeypatch.setattr(BaseTool, "is_effective_auto_mode", mock_is_effective_auto_mode)
