# Adding a New Provider

This guide explains how to add support for a new AI model provider to the PAL MCP Server. The provider system is designed to be extensible and follows a simple pattern.

## Overview

Each provider:
- Inherits from `ModelProvider` (base class) or `OpenAICompatibleProvider` (for OpenAI-compatible APIs)
- Defines supported models using `ModelCapabilities` objects
- Implements the minimal abstract hooks (`get_provider_type()` and `generate_content()`)
- Gets wired into `configure_providers()` so environment variables control activation
- Can leverage helper subclasses (e.g., `AzureOpenAIProvider`) when only client wiring differs

### Intelligence score cheatsheet

Set `intelligence_score` (1–20) when you want deterministic ordering in auto
mode or the `listmodels` output. The runtime rank starts from this human score
and adds smaller bonuses for context window, extended thinking, and other
features ([details here](model_ranking.md)).

## Choose Your Implementation Path

**Option A: Full Provider (`ModelProvider`)**
- For APIs with unique features or custom authentication
- Complete control over API calls and response handling
- Populate `MODEL_CAPABILITIES`, implement `generate_content()` and `get_provider_type()`, and only override `get_all_model_capabilities()` / `_lookup_capabilities()` when your catalogue comes from a registry or remote source (override `count_tokens()` only when you have a provider-accurate tokenizer)

**Option B: OpenAI-Compatible (`OpenAICompatibleProvider`)**
- For APIs that follow OpenAI's chat completion format
- Supply `MODEL_CAPABILITIES`, override `get_provider_type()`, and optionally adjust configuration (the base class handles alias resolution, validation, and request wiring)
- Inherits all API handling automatically

⚠️ **Important**: If you implement a custom `generate_content()`, call `_resolve_model_name()` before invoking the SDK so aliases (e.g. `"gpt"` → `"gpt-4"`) resolve correctly. The shared implementations already do this for you.

**Option C: Azure OpenAI (`AzureOpenAIProvider`)**
- For Azure-hosted deployments of OpenAI models
- Reuses the OpenAI-compatible pipeline but swaps in the `AzureOpenAI` client and a deployment mapping (canonical model → deployment ID)
- Define deployments in [`conf/azure_models.json`](../conf/azure_models.json) (or the file referenced by `AZURE_MODELS_CONFIG_PATH`).
- Entries follow the [`ModelCapabilities`](../providers/shared/model_capabilities.py) schema and must include a `deployment` identifier.
  See [Azure OpenAI Configuration](azure_openai.md) for a step-by-step walkthrough.

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

    MODEL_CAPABILITIES = {
        "example-large": ModelCapabilities(
            provider=ProviderType.EXAMPLE,
            model_name="example-large",
            friendly_name="Example Large",
            intelligence_score=18,
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
            intelligence_score=14,
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

    def get_all_model_capabilities(self) -> dict[str, ModelCapabilities]:
        return dict(self.MODEL_CAPABILITIES)

    def get_provider_type(self) -> ProviderType:
        return ProviderType.EXAMPLE

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

        # Your API call logic here
        # response = your_api_client.generate(...)

        return ModelResponse(
            content="Generated response",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            model_name=resolved_name,
            friendly_name="Example",
            provider=ProviderType.EXAMPLE,
        )
```

`ModelProvider.get_capabilities()` automatically resolves aliases, enforces the
shared restriction service, and returns the correct `ModelCapabilities`
instance. Override `_lookup_capabilities()` only when you source capabilities
from a registry or remote API. `ModelProvider.count_tokens()` uses a simple
4-characters-per-token estimate so providers work out of the box—override it
only when you can call the provider's real tokenizer (for example, the
OpenAI-compatible base class integrates `tiktoken`).

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

    def get_provider_type(self) -> ProviderType:
        return ProviderType.EXAMPLE
```

`OpenAICompatibleProvider` already exposes the declared models via
`MODEL_CAPABILITIES`, resolves aliases through the shared base pipeline, and
enforces restrictions. Most subclasses only need to provide the class metadata
shown above.

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

# Optional (OpenAI-compatible providers): Restrict accessible models
EXAMPLE_ALLOWED_MODELS=example-model-large,example-model-small
```

For Azure OpenAI deployments:

```bash
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# Models are defined in conf/azure_models.json (or AZURE_MODELS_CONFIG_PATH)
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
# AZURE_OPENAI_ALLOWED_MODELS=gpt-4o,gpt-4o-mini
# AZURE_MODELS_CONFIG_PATH=/absolute/path/to/custom_azure_models.json
```

You can also define Azure models in [`conf/azure_models.json`](../conf/azure_models.json) (the bundled file is empty so you can copy it safely). Each entry mirrors the `ModelCapabilities` schema and must include a `deployment` field. Set `AZURE_MODELS_CONFIG_PATH` if you maintain a custom copy outside the repository.

**Note**: The `description` field in `ModelCapabilities` helps Claude choose the best model in auto mode.

### 5. Test Your Provider

Create basic tests to verify your implementation:

```python
# Test capabilities
provider = ExampleModelProvider("test-key")
capabilities = provider.get_capabilities("large")
assert capabilities.context_window > 0
assert capabilities.provider == ProviderType.EXAMPLE
```



## Key Concepts

### Provider Priority
When a user requests a model, providers are checked in priority order:
1. **Native providers** (Gemini, OpenAI, Example) - handle their specific models
2. **Custom provider** - handles local/self-hosted models  
3. **OpenRouter** - catch-all for everything else

### Model Validation
`ModelProvider.validate_model_name()` delegates to `get_capabilities()` so most
providers can rely on the shared implementation. Override it only when you need
to opt out of that pipeline—for example, `CustomProvider` declines OpenRouter
models so they fall through to the dedicated OpenRouter provider.

### Model Aliases
Aliases declared on `ModelCapabilities` are applied automatically via
`_resolve_model_name()`, and both the validation and request flows call it
before touching your SDK. Override `generate_content()` only when your provider
needs additional alias handling beyond the shared behaviour.

## Important Notes

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
