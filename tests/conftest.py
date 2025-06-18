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

# Set dummy API keys for tests if not already set
if "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = "dummy-key-for-tests"
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "dummy-key-for-tests"
if "XAI_API_KEY" not in os.environ:
    os.environ["XAI_API_KEY"] = "dummy-key-for-tests"

# Set default model to a specific value for tests to avoid auto mode
# This prevents all tests from failing due to missing model parameter
os.environ["DEFAULT_MODEL"] = "gemini-2.5-flash-preview-05-20"

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


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "no_mock_provider: disable automatic provider mocking")


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

    from unittest.mock import MagicMock

    original_get_provider = ModelProviderRegistry.get_provider_for_model

    def mock_get_provider_for_model(model_name):
        # If it's a test looking for unavailable models, return None
        if model_name in ["unavailable-model", "gpt-5-turbo", "o3"]:
            return None
        # For common test models, return a mock provider
        if model_name in ["gemini-2.5-flash-preview-05-20", "gemini-2.5-pro-preview-06-05", "pro", "flash"]:
            # Try to use the real provider first if it exists
            real_provider = original_get_provider(model_name)
            if real_provider:
                return real_provider

            # Otherwise create a mock
            provider = MagicMock()
            # Set up the model capabilities mock with actual values
            capabilities = MagicMock()
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
    from tools.base import BaseTool

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
