# Azure OpenAI Configuration

Azure OpenAI support lets PAL MCP talk to GPT-4o, GPT-4.1, GPT-5, and o-series deployments that you expose through your Azure resource. This guide describes the configuration expected by the server: a couple of required environment variables plus a JSON manifest that lists every deployment you want to expose.

## 1. Required Environment Variables

Set these entries in your `.env` (or MCP `env` block).

```bash
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

Without the key and endpoint the provider is skipped entirely. Leave the key blank only if the endpoint truly allows anonymous access (rare for Azure).

## 2. Define Deployments in `conf/azure_models.json`

Azure models live in `conf/azure_models.json` (or the file pointed to by `AZURE_MODELS_CONFIG_PATH`). Each entry follows the same schema as [`ModelCapabilities`](../providers/shared/model_capabilities.py) with one additional required key: `deployment`. This field must exactly match the deployment name shown in the Azure Portal (for example `prod-gpt4o`). The provider routes requests by that value, so omitting it or using the wrong name will cause the server to skip the model. You can also opt into extra behaviour per model—for example set `use_openai_response_api` to `true` when an Azure deployment requires the `/responses` endpoint (O-series reasoning models), or leave it unset for standard chat completions.

```json
{
  "models": [
    {
      "model_name": "gpt-4o",
      "deployment": "prod-gpt4o",
      "friendly_name": "Azure GPT-4o EU",
      "intelligence_score": 18,
      "context_window": 600000,
      "max_output_tokens": 128000,
      "supports_temperature": false,
      "temperature_constraint": "fixed",
      "aliases": ["gpt4o-eu"],
      "use_openai_response_api": false
    }
  ]
}
```

Tips:

- Copy `conf/azure_models.json` into your repo and commit it, or point `AZURE_MODELS_CONFIG_PATH` at a custom path.
- Add one object per deployment. Aliases are optional but help when you want short names like `gpt4o-eu`.
- All capability fields are optional except `model_name`, `deployment`, and `friendly_name`. Anything you omit falls back to conservative defaults.
- Set `use_openai_response_api` to `true` for models that must call Azure's `/responses` endpoint (for example O3 deployments). Leave it unset for standard chat completions.

## 3. Optional Restrictions

Use `AZURE_OPENAI_ALLOWED_MODELS` to limit which Azure models Claude can access:

```bash
AZURE_OPENAI_ALLOWED_MODELS=gpt-4o,gpt-4o-mini
```

Aliases are matched case-insensitively.

## 4. Quick Checklist

- [ ] `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` are set
- [ ] `conf/azure_models.json` (or the file referenced by `AZURE_MODELS_CONFIG_PATH`) lists every deployment with the desired metadata
- [ ] Optional: `AZURE_OPENAI_ALLOWED_MODELS` to restrict usage
- [ ] Restart `./run-server.sh` and run `listmodels` to confirm the Azure entries appear with the expected metadata

See also: [`docs/adding_providers.md`](adding_providers.md) for the full provider architecture and [README (Provider Configuration)](../README.md#provider-configuration) for quick-start environment snippets.
