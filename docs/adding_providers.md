# Adding a New Provider

This guide explains how to add support for a new AI model provider to the Zen MCP Server. Follow these steps to integrate providers like Anthropic, Cohere, or any API that provides AI model access.

## Overview

The provider system in Zen MCP Server is designed to be extensible. Each provider:
- Inherits from a base class (`ModelProvider` or `OpenAICompatibleProvider`)
- Implements required methods for model interaction
- Is registered in the provider registry by the server
- Has its API key configured via environment variables

## Implementation Paths

You have two options when implementing a new provider:

### Option A: Native Provider (Full Implementation)
Inherit from `ModelProvider` when:
- Your API has unique features not compatible with OpenAI's format
- You need full control over the implementation
- You want to implement custom features like extended thinking

### Option B: OpenAI-Compatible Provider (Simplified)
Inherit from `OpenAICompatibleProvider` when:
- Your API follows OpenAI's chat completion format
- You want to reuse existing implementation for most functionality
- You only need to define model capabilities and validation

⚠️ **CRITICAL**: If your provider has model aliases (shorthands), you **MUST** override `generate_content()` to resolve aliases before API calls. See implementation example below.

## Step-by-Step Guide

### 1. Add Provider Type to Enum

First, add your provider to the `ProviderType` enum in `providers/base.py`:

```python
class ProviderType(Enum):
    """Supported model provider types."""
    
    GOOGLE = "google"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"
    EXAMPLE = "example"  # Add your provider here
```

### 2. Create the Provider Implementation

#### Option A: Native Provider Implementation

Create a new file in the `providers/` directory (e.g., `providers/example.py`):

```python
"""Example model provider implementation."""

import logging
from typing import Optional
from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)
from utils.model_restrictions import get_restriction_service

logger = logging.getLogger(__name__)


class ExampleModelProvider(ModelProvider):
    """Example model provider implementation."""
    
    SUPPORTED_MODELS = {
        "example-large-v1": {
            "context_window": 100_000,
            "supports_extended_thinking": False,
        },
        "example-small-v1": {
            "context_window": 50_000,
            "supports_extended_thinking": False,
        },
        # Shorthands
        "large": "example-large-v1",
        "small": "example-small-v1",
    }
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        # Initialize your API client here
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        resolved_name = self._resolve_model_name(model_name)
        
        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")
        
        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
            raise ValueError(f"Model '{model_name}' is not allowed by restriction policy.")
        
        config = self.SUPPORTED_MODELS[resolved_name]
        
        return ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name=resolved_name,
            friendly_name="Example",
            context_window=config["context_window"],
            supports_extended_thinking=config["supports_extended_thinking"],
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
        )
    
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        resolved_name = self._resolve_model_name(model_name)
        self.validate_parameters(resolved_name, temperature)
        
        # Call your API here
        # response = your_api_call(...)
        
        return ModelResponse(
            content="",  # From API response
            usage={
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            model_name=resolved_name,
            friendly_name="Example",
            provider=ProviderType.EXAMPLE,
        )
    
    def count_tokens(self, text: str, model_name: str) -> int:
        # Implement your tokenization or use estimation
        return len(text) // 4
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.EXAMPLE
    
    def validate_model_name(self, model_name: str) -> bool:
        resolved_name = self._resolve_model_name(model_name)
        
        if resolved_name not in self.SUPPORTED_MODELS or not isinstance(self.SUPPORTED_MODELS[resolved_name], dict):
            return False
        
        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
            logger.debug(f"Example model '{model_name}' -> '{resolved_name}' blocked by restrictions")
            return False
        
        return True
    
    def supports_thinking_mode(self, model_name: str) -> bool:
        capabilities = self.get_capabilities(model_name)
        return capabilities.supports_extended_thinking
    
    def _resolve_model_name(self, model_name: str) -> str:
        shorthand_value = self.SUPPORTED_MODELS.get(model_name)
        if isinstance(shorthand_value, str):
            return shorthand_value
        return model_name
```

#### Option B: OpenAI-Compatible Provider Implementation

For providers with OpenAI-compatible APIs, the implementation is much simpler:

```python
"""Example provider using OpenAI-compatible interface."""

import logging
from typing import Optional

from .base import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)
from .openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)


class ExampleProvider(OpenAICompatibleProvider):
    """Example provider using OpenAI-compatible API."""
    
    FRIENDLY_NAME = "Example"
    
    # Define supported models
    SUPPORTED_MODELS = {
        "example-model-large": {
            "context_window": 128_000,
            "supports_extended_thinking": False,
        },
        "example-model-small": {
            "context_window": 32_000,
            "supports_extended_thinking": False,
        },
        # Shorthands
        "large": "example-model-large",
        "small": "example-model-small",
    }
    
    def __init__(self, api_key: str, **kwargs):
        """Initialize provider with API key."""
        # Set your API base URL
        kwargs.setdefault("base_url", "https://api.example.com/v1")
        super().__init__(api_key, **kwargs)
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific model."""
        resolved_name = self._resolve_model_name(model_name)
        
        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}")
        
        # Check restrictions
        from utils.model_restrictions import get_restriction_service
        
        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
            raise ValueError(f"Model '{model_name}' is not allowed by restriction policy.")
        
        config = self.SUPPORTED_MODELS[resolved_name]
        
        return ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name=resolved_name,
            friendly_name=self.FRIENDLY_NAME,
            context_window=config["context_window"],
            supports_extended_thinking=config["supports_extended_thinking"],
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            temperature_constraint=RangeTemperatureConstraint(0.0, 1.0, 0.7),
        )
    
    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.EXAMPLE
    
    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported."""
        resolved_name = self._resolve_model_name(model_name)
        
        if resolved_name not in self.SUPPORTED_MODELS or not isinstance(self.SUPPORTED_MODELS[resolved_name], dict):
            return False
        
        # Check restrictions
        from utils.model_restrictions import get_restriction_service
        
        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
            return False
        
        return True
    
    def _resolve_model_name(self, model_name: str) -> str:
        """Resolve model shorthand to full name."""
        shorthand_value = self.SUPPORTED_MODELS.get(model_name)
        if isinstance(shorthand_value, str):
            return shorthand_value
        return model_name
    
    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using API with proper model name resolution."""
        # CRITICAL: Resolve model alias before making API call
        # This ensures aliases like "large" get sent as "example-model-large" to the API
        resolved_model_name = self._resolve_model_name(model_name)
        
        # Call parent implementation with resolved model name
        return super().generate_content(
            prompt=prompt,
            model_name=resolved_model_name,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            **kwargs,
        )
    
    # Note: count_tokens is inherited from OpenAICompatibleProvider
```

### 3. Update Registry Configuration

#### 3.1. Add Environment Variable Mapping

Update `providers/registry.py` to map your provider's API key:

```python
@classmethod
def _get_api_key_for_provider(cls, provider_type: ProviderType) -> Optional[str]:
    """Get API key for a provider from environment variables."""
    key_mapping = {
        ProviderType.GOOGLE: "GEMINI_API_KEY",
        ProviderType.OPENAI: "OPENAI_API_KEY",
        ProviderType.OPENROUTER: "OPENROUTER_API_KEY",
        ProviderType.CUSTOM: "CUSTOM_API_KEY",
        ProviderType.EXAMPLE: "EXAMPLE_API_KEY",  # Add this line
    }
    # ... rest of the method
```

### 4. Register Provider in server.py

The `configure_providers()` function in `server.py` handles provider registration. You need to:

**Note**: The provider priority is hardcoded in `registry.py`. If you're adding a new native provider (like Example), you'll need to update the `PROVIDER_PRIORITY_ORDER` in `get_provider_for_model()`:

```python
# In providers/registry.py
PROVIDER_PRIORITY_ORDER = [
    ProviderType.GOOGLE,      # Direct Gemini access
    ProviderType.OPENAI,      # Direct OpenAI access
    ProviderType.EXAMPLE,     # Add your native provider here
    ProviderType.CUSTOM,      # Local/self-hosted models
    ProviderType.OPENROUTER,  # Catch-all (must stay last)
]
```

Native providers should be placed BEFORE CUSTOM and OPENROUTER to ensure they get priority for their models.

1. **Import your provider class** at the top of `server.py`:
```python
from providers.example import ExampleModelProvider
```

2. **Add API key checking** in the `configure_providers()` function:
```python
def configure_providers():
    """Configure and validate AI providers based on available API keys."""
    # ... existing code ...
    
    # Check for Example API key
    example_key = os.getenv("EXAMPLE_API_KEY")
    if example_key and example_key != "your_example_api_key_here":
        valid_providers.append("Example")
        has_native_apis = True
        logger.info("Example API key found - Example models available")
```

3. **Register the provider** in the appropriate section:
```python
    # Register providers in priority order:
    # 1. Native APIs first (most direct and efficient)
    if has_native_apis:
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.GOOGLE, GeminiModelProvider)
        if openai_key and openai_key != "your_openai_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.OPENAI, OpenAIModelProvider)
        if example_key and example_key != "your_example_api_key_here":
            ModelProviderRegistry.register_provider(ProviderType.EXAMPLE, ExampleModelProvider)
```

4. **Update error message** to include your provider:
```python
    if not valid_providers:
        raise ValueError(
            "At least one API configuration is required. Please set either:\n"
            "- GEMINI_API_KEY for Gemini models\n"
            "- OPENAI_API_KEY for OpenAI o3 model\n"
            "- EXAMPLE_API_KEY for Example models\n"  # Add this
            "- OPENROUTER_API_KEY for OpenRouter (multiple models)\n"
            "- CUSTOM_API_URL for local models (Ollama, vLLM, etc.)"
        )
```

### 6. Add Model Capabilities for Auto Mode

Update `config.py` to add your models to `MODEL_CAPABILITIES_DESC`:

```python
MODEL_CAPABILITIES_DESC = {
    # ... existing models ...
    
    # Example models - Available when EXAMPLE_API_KEY is configured
    "large": "Example Large (100K context) - High capacity model for complex tasks",
    "small": "Example Small (50K context) - Fast model for simple tasks",
    # Full model names
    "example-large-v1": "Example Large (100K context) - High capacity model",
    "example-small-v1": "Example Small (50K context) - Fast lightweight model",
}
```

### 7. Update Documentation

#### 7.1. Update README.md

Add your provider to the quickstart section:

```markdown
### 1. Get API Keys (at least one required)

**Option B: Native APIs**
- **Gemini**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI**: Visit [OpenAI Platform](https://platform.openai.com/api-keys)
- **Example**: Visit [Example API Console](https://example.com/api-keys)  # Add this
```

Also update the .env file example:

```markdown
# Edit .env to add your API keys
# GEMINI_API_KEY=your-gemini-api-key-here
# OPENAI_API_KEY=your-openai-api-key-here
# EXAMPLE_API_KEY=your-example-api-key-here  # Add this
```

### 8. Write Tests

#### 8.1. Unit Tests

Create `tests/test_example_provider.py`:

```python
"""Tests for Example provider implementation."""

import os
from unittest.mock import patch
import pytest

from providers.example import ExampleModelProvider
from providers.base import ProviderType


class TestExampleProvider:
    """Test Example provider functionality."""
    
    @patch.dict(os.environ, {"EXAMPLE_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = ExampleModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.EXAMPLE
    
    def test_model_validation(self):
        """Test model name validation."""
        provider = ExampleModelProvider("test-key")
        
        # Test valid models
        assert provider.validate_model_name("large") is True
        assert provider.validate_model_name("example-large-v1") is True
        
        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
    
    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = ExampleModelProvider("test-key")
        
        # Test shorthand resolution
        assert provider._resolve_model_name("large") == "example-large-v1"
        assert provider._resolve_model_name("small") == "example-small-v1"
        
        # Test full name passthrough
        assert provider._resolve_model_name("example-large-v1") == "example-large-v1"
    
    def test_get_capabilities(self):
        """Test getting model capabilities."""
        provider = ExampleModelProvider("test-key")
        
        capabilities = provider.get_capabilities("large")
        assert capabilities.model_name == "example-large-v1"
        assert capabilities.friendly_name == "Example"
        assert capabilities.context_window == 100_000
        assert capabilities.provider == ProviderType.EXAMPLE
        
        # Test temperature range
        assert capabilities.temperature_constraint.min_temp == 0.0
        assert capabilities.temperature_constraint.max_temp == 2.0
```

#### 8.2. Simulator Tests (Real-World Validation)

Create a simulator test to validate that your provider works correctly in real-world scenarios. Create `simulator_tests/test_example_models.py`:

```python
"""
Example Provider Model Tests

Tests that verify Example provider functionality including:
- Model alias resolution
- API integration
- Conversation continuity
- Error handling
"""

from .base_test import BaseSimulatorTest


class TestExampleModels(BaseSimulatorTest):
    """Test Example provider functionality"""

    @property
    def test_name(self) -> str:
        return "example_models"

    @property
    def test_description(self) -> str:
        return "Example provider model functionality and integration"

    def run_test(self) -> bool:
        """Test Example provider models"""
        try:
            self.logger.info("Test: Example provider functionality")

            # Check if Example API key is configured
            check_result = self.check_env_var("EXAMPLE_API_KEY")
            if not check_result:
                self.logger.info("  ⚠️  Example API key not configured - skipping test")
                return True  # Skip, not fail

            # Test 1: Shorthand alias mapping
            self.logger.info("  1: Testing 'large' alias mapping")
            
            response1, continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Example Large model!' and nothing else.",
                    "model": "large",  # Should map to example-large-v1
                    "temperature": 0.1,
                }
            )

            if not response1:
                self.logger.error("  ❌ Large alias test failed")
                return False

            self.logger.info("  ✅ Large alias call completed")

            # Test 2: Direct model name
            self.logger.info("  2: Testing direct model name (example-small-v1)")
            
            response2, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Say 'Hello from Example Small model!' and nothing else.",
                    "model": "example-small-v1",
                    "temperature": 0.1,
                }
            )

            if not response2:
                self.logger.error("  ❌ Direct model name test failed")
                return False

            self.logger.info("  ✅ Direct model name call completed")

            # Test 3: Conversation continuity
            self.logger.info("  3: Testing conversation continuity")
            
            response3, new_continuation_id = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "Remember this number: 99. What number did I just tell you?",
                    "model": "large",
                    "temperature": 0.1,
                }
            )

            if not response3 or not new_continuation_id:
                self.logger.error("  ❌ Failed to start conversation")
                return False

            # Continue conversation
            response4, _ = self.call_mcp_tool(
                "chat",
                {
                    "prompt": "What was the number I told you earlier?",
                    "model": "large",
                    "continuation_id": new_continuation_id,
                    "temperature": 0.1,
                }
            )

            if not response4:
                self.logger.error("  ❌ Failed to continue conversation")
                return False

            if "99" in response4:
                self.logger.info("  ✅ Conversation continuity working")
            else:
                self.logger.warning("  ⚠️  Model may not have remembered the number")

            # Test 4: Check logs for proper provider usage
            self.logger.info("  4: Validating Example provider usage in logs")
            logs = self.get_recent_server_logs()

            # Look for evidence of Example provider usage
            example_logs = [line for line in logs.split("\n") if "example" in line.lower()]
            model_resolution_logs = [
                line for line in logs.split("\n") 
                if "Resolved model" in line and "example" in line.lower()
            ]

            self.logger.info(f"   Example-related logs: {len(example_logs)}")
            self.logger.info(f"   Model resolution logs: {len(model_resolution_logs)}")

            # Success criteria
            api_used = len(example_logs) > 0
            models_resolved = len(model_resolution_logs) > 0

            if api_used and models_resolved:
                self.logger.info("  ✅ Example provider tests passed")
                return True
            else:
                self.logger.error("  ❌ Example provider tests failed")
                return False

        except Exception as e:
            self.logger.error(f"Example provider test failed: {e}")
            return False


def main():
    """Run the Example provider tests"""
    import sys

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    test = TestExampleModels(verbose=verbose)

    success = test.run_test()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

The simulator test is crucial because it:
- Validates your provider works in the actual server environment
- Tests real API integration, not just mocked behavior
- Verifies model name resolution works correctly
- Checks conversation continuity across requests
- Examines server logs to ensure proper provider selection

See `simulator_tests/test_openrouter_models.py` for a complete real-world example.

## Model Name Mapping and Provider Priority

### How Model Name Resolution Works

When a user requests a model (e.g., "pro", "o3", "example-large-v1"), the system:

1. **Checks providers in priority order** (defined in `registry.py`):
   ```python
   PROVIDER_PRIORITY_ORDER = [
       ProviderType.GOOGLE,      # Native Gemini API
       ProviderType.OPENAI,      # Native OpenAI API  
       ProviderType.CUSTOM,      # Local/self-hosted
       ProviderType.OPENROUTER,  # Catch-all for everything else
   ]
   ```

2. **For each provider**, calls `validate_model_name()`:
   - Native providers (Gemini, OpenAI) return `true` only for their specific models
   - OpenRouter returns `true` for ANY model (it's the catch-all)
   - First provider that validates the model handles the request

### Example: Model "gemini-2.5-pro"

1. **Gemini provider** checks: YES, it's in my SUPPORTED_MODELS → Gemini handles it
2. OpenAI skips (Gemini already handled it)
3. OpenRouter never sees it

### Example: Model "claude-3-opus" 

1. **Gemini provider** checks: NO, not my model → skip
2. **OpenAI provider** checks: NO, not my model → skip  
3. **Custom provider** checks: NO, not configured → skip
4. **OpenRouter provider** checks: YES, I accept all models → OpenRouter handles it

### Implementing Model Name Validation

Your provider's `validate_model_name()` should:

```python
def validate_model_name(self, model_name: str) -> bool:
    resolved_name = self._resolve_model_name(model_name)
    
    # Only accept models you explicitly support
    if resolved_name not in self.SUPPORTED_MODELS or not isinstance(self.SUPPORTED_MODELS[resolved_name], dict):
        return False
    
    # Check restrictions
    restriction_service = get_restriction_service()
    if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
        logger.debug(f"Example model '{model_name}' -> '{resolved_name}' blocked by restrictions")
        return False
    
    return True
```

**Important**: Native providers should ONLY return `true` for models they explicitly support. This ensures they get priority over proxy providers like OpenRouter.

### Model Shorthands

Each provider can define shorthands in their SUPPORTED_MODELS:

```python
SUPPORTED_MODELS = {
    "example-large-v1": { ... },  # Full model name
    "large": "example-large-v1",   # Shorthand mapping
}
```

The `_resolve_model_name()` method handles this mapping automatically.

## Critical Implementation Requirements

### Alias Resolution for OpenAI-Compatible Providers

If you inherit from `OpenAICompatibleProvider` and define model aliases, you **MUST** override `generate_content()` to resolve aliases before API calls. This is because:

1. **The base `OpenAICompatibleProvider.generate_content()`** sends the original model name directly to the API
2. **Your API expects the full model name**, not the alias
3. **Without resolution**, requests like `model="large"` will fail with 404/400 errors

**Examples of providers that need this:**
- XAI provider: `"grok"` → `"grok-3"`
- OpenAI provider: `"mini"` → `"o4-mini"`
- Custom provider: `"fast"` → `"llama-3.1-8b-instruct"`

**Example implementation pattern:**
```python
def generate_content(self, prompt: str, model_name: str, **kwargs) -> ModelResponse:
    # CRITICAL: Resolve alias before API call
    resolved_model_name = self._resolve_model_name(model_name)
    
    # Pass resolved name to parent
    return super().generate_content(prompt=prompt, model_name=resolved_model_name, **kwargs)
```

**Providers that DON'T need this:**
- Gemini provider (has its own generate_content implementation)
- OpenRouter provider (already implements this pattern)
- Providers without aliases

## Best Practices

1. **Always validate model names** against supported models and restrictions
2. **Be specific in validation** - only accept models you actually support
3. **Handle API errors gracefully** with proper error messages
4. **Include retry logic** for transient errors (see `gemini.py` for example)
5. **Log important events** for debugging (initialization, model resolution, errors)
6. **Support model shorthands** for better user experience
7. **Document supported models** clearly in your provider class
8. **Test thoroughly** including error cases and edge conditions

## Checklist

Before submitting your PR:

- [ ] Provider type added to `ProviderType` enum in `providers/base.py`
- [ ] Provider implementation complete with all required methods
- [ ] API key mapping added to `_get_api_key_for_provider()` in `providers/registry.py`
- [ ] Provider added to `PROVIDER_PRIORITY_ORDER` in `registry.py` (if native provider)
- [ ] **Environment variables added to `.env` file** (API key and restrictions)
- [ ] Provider imported and registered in `server.py`'s `configure_providers()`
- [ ] API key checking added to `configure_providers()` function
- [ ] Error message updated to include new provider
- [ ] Model capabilities added to `config.py` for auto mode
- [ ] Documentation updated (README.md)
- [ ] Unit tests written and passing (`tests/test_<provider>.py`)
- [ ] Simulator tests written and passing (`simulator_tests/test_<provider>_models.py`)
- [ ] Integration tested with actual API calls
- [ ] Code follows project style (run linting)
- [ ] PR follows the template requirements

## Need Help?

- Look at existing providers (`gemini.py`, `openai.py`) for examples
- Check the base classes for method signatures and requirements
- Run tests frequently during development
- Ask questions in GitHub issues if stuck