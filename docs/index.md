# PAL MCP Server Documentation

_Formerly known as PAL MCP. See the short [name change note](name-change.md) for context._

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Installation paths, prerequisite setup, and first-run guidance. |
| [Adding Providers](adding_providers.md) | How to register new AI providers and advertise capabilities. |
| [Azure OpenAI](azure_openai.md) | Configure Azure deployments, capability overrides, and env mappings. |
| [Entra ID Authentication](entra_auth.md) | Use your `az login` identity instead of API keys for Azure OpenAI and Claude on Azure AI Foundry. |
| [ChatGPT Models via Codex CLI](chatgpt_provider.md) | Use ChatGPT-plan models (`codex login`) from every PAL tool, without an API key. |
| [Model Ranking](model_ranking.md) | How intelligence scores translate into auto-mode ordering. |
| [Model Catalog](model_catalog.md) | Every measured model: score, per-effort AA Index values, routes, and aliases (generated). |
| [Custom Models](custom_models.md) | Configure OpenRouter/custom models and aliases. |
| [Adding Tools](adding_tools.md) | Create new tools using the shared base classes. |
| [Advanced Usage](advanced-usage.md) | Auto-mode tricks, workflow tools, and collaboration tips. |
| [Configuration](configuration.md) | .env options, restriction policies, logging levels. |
| [Testing](testing.md) | Test strategy, command cheats, and coverage notes. |
| [Troubleshooting](troubleshooting.md) | Common issues and resolutions. |

Additional docs live in this directory; start with the table above to orient yourself.
