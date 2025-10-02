# Adding a New Provider

This guide explains how to add support for a new AI model provider to the Zen MCP Server. The provider system is designed to be extensible and follows a simple pattern.

## Overview

Each provider:
- Inherits from `ModelProvider` (base class) or `OpenAICompatibleProvider` (for OpenAI-compatible APIs)
- Defines supported models using `ModelCapabilities` objects
- Implements a few core abstract methods
- Gets registered automatically via environment variables

## Choose Your Implementation Path

**Option A: Full Provider (`ModelProvider`)**
- For APIs with unique features or custom authentication
- Complete control over API calls and response handling
- Required methods: `generate_content()`, `get_capabilities()`, `validate_model_name()`, `get_provider_type()` (override `count_tokens()` only when you have a provider-accurate tokenizer)

**Option B: OpenAI-Compatible (`OpenAICompatibleProvider`)**
- For APIs that follow OpenAI's chat completion format
- Only need to define: model configurations, capabilities, and validation
- Inherits all API handling automatically

⚠️ **Important**: If using aliases (like `"gpt"` → `"gpt-4"`), override `generate_content()` to resolve them before API calls.

## Step-by-Step Guide

### 1. Add Provider Type

Add your provider to the `ProviderType` enum in `providers/shared/provider_type.py`:

```python
class ProviderType(Enum):
    GOOGLE = "google"
    OPENAI = "openai"
    EXAMPLE = "example"  # Add this
```

### 2. Create the Provider Implementation

#### Option A: Full Provider (Native Implementation)

Create `providers/example.py`:

```python
"""Example model provider implementation."""

import logging
from typing import Optional

from .base import ModelProvider
from .shared import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)

logger = logging.getLogger(__name__)


class ExampleModelProvider(ModelProvider):
    """Example model provider implementation."""
    
    # Define models using ModelCapabilities objects (like Gemini provider)
    MODEL_CAPABILITIES = {
        "example-large": ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name="example-large",
            friendly_name="Example Large",
            context_window=100_000,
            max_output_tokens=50_000,
            supports_extended_thinking=False,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
            description="Large model for complex tasks",
            aliases=["large", "big"],
        ),
        "example-small": ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name="example-small",
            friendly_name="Example Small",
            context_window=32_000,
            max_output_tokens=16_000,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
            description="Fast model for simple tasks",
            aliases=["small", "fast"],
        ),
    }
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key, **kwargs)
        # Initialize your API client here
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        resolved_name = self._resolve_model_name(model_name)
        
        if resolved_name not in self.MODEL_CAPABILITIES:
            raise ValueError(f"Unsupported model: {model_name}")
        
        # Apply restrictions if needed
        from utils.model_restrictions import get_restriction_service
        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.EXAMPLE, resolved_name, model_name):
            raise ValueError(f"Model '{model_name}' is not allowed.")
        
        return self.MODEL_CAPABILITIES[resolved_name]
    
    def generate_content(self, prompt: str, model_name: str, system_prompt: Optional[str] = None, 
                        temperature: float = 0.7, max_output_tokens: Optional[int] = None, **kwargs) -> ModelResponse:
        resolved_name = self._resolve_model_name(model_name)
        
        # Your API call logic here
        # response = your_api_client.generate(...)
        
        return ModelResponse(
            content="Generated response",  # From your API
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            model_name=resolved_name,
            friendly_name="Example",
            provider=ProviderType.EXAMPLE,
        )
    def get_provider_type(self) -> ProviderType:
        return ProviderType.EXAMPLE
    
    def validate_model_name(self, model_name: str) -> bool:
        resolved_name = self._resolve_model_name(model_name)
        return resolved_name in self.MODEL_CAPABILITIES
```

`ModelProvider.count_tokens()` uses a simple 4-characters-per-token estimate so
providers work out of the box. Override the method only when you can call into
the provider's real tokenizer (for example, the OpenAI-compatible base class
already integrates `tiktoken`).

#### Option B: OpenAI-Compatible Provider (Simplified)

For OpenAI-compatible APIs:

```python
"""Example OpenAI-compatible provider."""

from typing import Optional

from .openai_compatible import OpenAICompatibleProvider
from .shared import (
    ModelCapabilities,
    ModelResponse,
    ProviderType,
    RangeTemperatureConstraint,
)


class ExampleProvider(OpenAICompatibleProvider):
    """Example OpenAI-compatible provider."""
    
    FRIENDLY_NAME = "Example"
    
    # Define models using ModelCapabilities (consistent with other providers)
    MODEL_CAPABILITIES = {
        "example-model-large": ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name="example-model-large",
            friendly_name="Example Large",
            context_window=128_000,
            max_output_tokens=64_000,
            temperature_constraint=RangeTemperatureConstraint(0.0, 2.0, 0.7),
            aliases=["large", "big"],
        ),
    }
    
    def __init__(self, api_key: str, **kwargs):
        kwargs.setdefault("base_url", "https://api.example.com/v1")
        super().__init__(api_key, **kwargs)
    
    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        resolved_name = self._resolve_model_name(model_name)
        if resolved_name not in self.MODEL_CAPABILITIES:
            raise ValueError(f"Unsupported model: {model_name}")
        return self.MODEL_CAPABILITIES[resolved_name]
    
    def get_provider_type(self) -> ProviderType:
        return ProviderType.EXAMPLE
    
    def validate_model_name(self, model_name: str) -> bool:
        resolved_name = self._resolve_model_name(model_name)
        return resolved_name in self.MODEL_CAPABILITIES
    
    def generate_content(self, prompt: str, model_name: str, **kwargs) -> ModelResponse:
        # IMPORTANT: Resolve aliases before API call
        resolved_model_name = self._resolve_model_name(model_name)
        return super().generate_content(prompt=prompt, model_name=resolved_model_name, **kwargs)
```

### 3. Register Your Provider

Add environment variable mapping in `providers/registry.py`:

```python
# In _get_api_key_for_provider (providers/registry.py), add:
    ProviderType.EXAMPLE: "EXAMPLE_API_KEY",
```

Add to `server.py`:

1. **Import your provider**:
```python
from providers.example import ExampleModelProvider
```

2. **Add to `configure_providers()` function**:
```python
# Check for Example API key
example_key = os.getenv("EXAMPLE_API_KEY")
if example_key:
    ModelProviderRegistry.register_provider(ProviderType.EXAMPLE, ExampleModelProvider)
    logger.info("Example API key found - Example models available")
```

3. **Add to provider priority** (edit `ModelProviderRegistry.PROVIDER_PRIORITY_ORDER` in `providers/registry.py`): insert your provider in the list at the appropriate point in the cascade of native → custom → catch-all providers.

### 4. Environment Configuration

Add to your `.env` file:
```bash
# Your provider's API key
EXAMPLE_API_KEY=your_api_key_here

# Optional: Disable specific tools
DISABLED_TOOLS=debug,tracer
```

**Note**: The `description` field in `ModelCapabilities` helps Claude choose the best model in auto mode.

### 5. Test Your Provider

Create basic tests to verify your implementation:

```python
# Test model validation
provider = ExampleModelProvider("test-key")
assert provider.validate_model_name("large") == True
assert provider.validate_model_name("unknown") == False

# Test capabilities
caps = provider.get_capabilities("large")
assert caps.context_window > 0
assert caps.provider == ProviderType.EXAMPLE
```



## Key Concepts

### Provider Priority
When a user requests a model, providers are checked in priority order:
1. **Native providers** (Gemini, OpenAI, Example) - handle their specific models
2. **Custom provider** - handles local/self-hosted models  
3. **OpenRouter** - catch-all for everything else

### Model Validation
Your `validate_model_name()` should **only** return `True` for models you explicitly support:

```python
def validate_model_name(self, model_name: str) -> bool:
    resolved_name = self._resolve_model_name(model_name)
    return resolved_name in self.MODEL_CAPABILITIES  # Be specific!
```

### Model Aliases
The base class handles alias resolution automatically via the `aliases` field in `ModelCapabilities`.

## Important Notes

### Alias Resolution in OpenAI-Compatible Providers
If using `OpenAICompatibleProvider` with aliases, **you must override `generate_content()`** to resolve aliases before API calls:

```python
def generate_content(self, prompt: str, model_name: str, **kwargs) -> ModelResponse:
    # Resolve alias before API call
    resolved_model_name = self._resolve_model_name(model_name)
    return super().generate_content(prompt=prompt, model_name=resolved_model_name, **kwargs)
```

Without this, API calls with aliases like `"large"` will fail because your API doesn't recognize the alias.

## Best Practices

- **Be specific in model validation** - only accept models you actually support
- **Use ModelCapabilities objects** consistently (like Gemini provider)
- **Include descriptive aliases** for better user experience  
- **Add error handling** and logging for debugging
- **Test with real API calls** to verify everything works
- **Follow the existing patterns** in `providers/gemini.py` and `providers/custom.py`

## Quick Checklist

- [ ] Added to `ProviderType` enum in `providers/shared/provider_type.py`
- [ ] Created provider class with all required methods
- [ ] Added API key mapping in `providers/registry.py`
- [ ] Added to provider priority order in `registry.py`
- [ ] Imported and registered in `server.py`
- [ ] Basic tests verify model validation and capabilities
- [ ] Tested with real API calls

## Examples

See existing implementations:
- **Full provider**: `providers/gemini.py`
- **OpenAI-compatible**: `providers/custom.py`
- **Base classes**: `providers/base.py`
