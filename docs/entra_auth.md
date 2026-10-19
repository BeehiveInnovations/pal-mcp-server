# Entra ID (Azure AD) Authentication

PAL can call two Azure-hosted providers with your own Microsoft Entra ID identity instead of a static API key:

| Provider | Turn on with | Replaces |
|----------|--------------|----------|
| Azure OpenAI | `AZURE_OPENAI_USE_ENTRA=true` + `AZURE_OPENAI_ENDPOINT` | `AZURE_OPENAI_API_KEY` |
| Claude on Azure AI Foundry | `ANTHROPIC_USE_ENTRA=true` + `ANTHROPIC_FOUNDRY_BASE_URL` | `ANTHROPIC_API_KEY` |

Both modes are opt-in. With a flag unset (or anything other than `true`), the provider authenticates with its API
key as before. With a flag on, no API key is needed or sent, even if one is also set.

## 1. Sign in and check your role

1. Run `az login` (and `az account set --subscription <id>` if you have several). PAL uses
   `DefaultAzureCredential` from `azure-identity`, which picks up the Azure CLI login. On a VM or in CI it
   uses a managed identity or workload identity instead.
2. Your identity needs a **data-plane** role on the resource (or its resource group). Owner or Contributor
   alone is not enough. Examples:
   - Azure OpenAI: **Cognitive Services OpenAI User**
   - Azure AI Foundry: **Foundry User** (formerly Azure AI User) or **Cognitive Services User**

   Without one, requests fail with HTTP 401/403 even though `az login` succeeded.
3. `azure-identity` must be installed (it is in `requirements.txt`). PAL imports it only when an Entra
   flag is on. If it is missing, startup logs an error and requests fail with an install hint.

To skip `DefaultAzureCredential`'s other sources and use only the CLI login, set
`AZURE_TOKEN_CREDENTIALS=AzureCliCredential`.

**MCP clients.** The flags can live in `.env` or in the client's `env` block. The Azure CLI credential
runs the `az` command, and Claude Desktop starts MCP servers with a minimal `PATH` that usually lacks
Homebrew's `bin` folder. For Claude Desktop, add a `PATH` that includes the folder from `which az`:

```json
"env": {
  "AZURE_OPENAI_USE_ENTRA": "true",
  "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
  "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
}
```

Claude Code inherits your shell's `PATH` and needs no change.

## 2. Azure OpenAI

```env
AZURE_OPENAI_USE_ENTRA=true
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_MODELS_CONFIG_PATH=/absolute/path/to/your_azure_models.json
# AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

Deployments are defined exactly as in key mode (see [Azure OpenAI](azure_openai.md)). Set
`"supports_extended_thinking": true` on GPT-5.x and other reasoning deployments so PAL sends
`max_completion_tokens` instead of `max_tokens`, which those deployments reject.

## 3. Claude on Azure AI Foundry

```env
ANTHROPIC_USE_ENTRA=true
ANTHROPIC_FOUNDRY_BASE_URL=https://your-resource.services.ai.azure.com/anthropic
ANTHROPIC_ALLOWED_MODELS=claude-opus-5,claude-sonnet-4-5
```

PAL uses the Anthropic SDK's `AnthropicFoundry` client (`anthropic>=0.74.0`). Foundry deployment names must
match the Claude model IDs in `conf/anthropic_models.json` (for example `claude-opus-5`), because PAL sends the
model ID as the deployment. Set `ANTHROPIC_ALLOWED_MODELS` to the models you deployed: otherwise auto mode
may pick a catalogue model your resource doesn't serve, and the call returns 404.

Don't also set `ANTHROPIC_FOUNDRY_RESOURCE`. The SDK reads it from the environment and rejects it
alongside a base URL.

## 4. What gets logged

PAL never logs tokens. On the first request it logs the credential type and the endpoint host, for example:

```
Azure OpenAI: Entra ID token acquired via AzureCliCredential for your-resource.openai.azure.com
```

The Anthropic SDK writes request headers to its DEBUG log, and in Foundry mode those headers include the
bearer token. PAL's log level defaults to DEBUG, so in Entra mode PAL filters that logger and replaces
`Authorization`, `api-key` and `x-api-key` header values with `<redacted>`.
