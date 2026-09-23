# LLM Proxy

PAL can use [LLM Proxy](https://github.com/tyemirov/llm-proxy) as a text model
provider for chat, consensus, and other model-backed tools. The official Python
client owns the proxy protocol and tenant authentication. Upstream provider
credentials stay in LLM Proxy; PAL uses a tenant secret.

## Install the optional client

Use Python 3.11+ for this provider. Install the official client in the **same
environment that runs PAL**. With Git and GitHub CLI installed, resolve the
latest published release and install its Python package:

```bash
proxy_release=$(gh release view --repo tyemirov/llm-proxy --json tagName --jq .tagName)
uv pip install --python .pal_venv/bin/python --upgrade \
  "llm-proxy-client @ git+https://github.com/tyemirov/llm-proxy.git@${proxy_release}#subdirectory=python"
```

The SDK is optional so PAL's existing providers retain their Python requirements
and dependencies. For a container installation, install it in the container's
PAL environment. Restart PAL after installing or changing configuration.

## Configure

Set these values in PAL's `.env` or MCP server environment:

```dotenv
LLM_PROXY_BASE_URL=https://your-proxy.example.com
LLM_PROXY_SECRET=your_tenant_secret
LLM_PROXY_PROVIDER=
LLM_PROXY_REQUEST_TIMEOUT_SECONDS=900
LLM_PROXY_MODELS_CONFIG_PATH=/absolute/path/to/llm_proxy_models.json
# Optional policy restriction (canonical model names or aliases):
# LLM_PROXY_ALLOWED_MODELS=your-model
```

`LLM_PROXY_BASE_URL`, `LLM_PROXY_SECRET`, and the positive integer request budget
are required when enabling this provider. An empty `LLM_PROXY_PROVIDER` delegates
upstream routing to the tenant; a provider identifier explicitly selects an
upstream. The SDK derives the `/v2` endpoint, including any base-path prefix,
and sends the budget as `X-LLM-Proxy-Request-Timeout-Seconds`.
Keep the secret in the ignored runtime environment, as with other PAL keys.

Define models enabled for your tenant using PAL's existing capability format:

```json
{
  "models": [
    {
      "model_name": "your-model",
      "aliases": ["proxy-reviewer"],
      "context_window": 32000,
      "max_output_tokens": 4096,
      "intelligence_score": 15,
      "description": "My tenant's review model",
      "default_reasoning_effort": "high"
    }
  ]
}
```

Replace the example model, budgets, score, and reasoning effort with values
appropriate to your tenant's model. Omit `default_reasoning_effort` when it is
not applicable. Without `LLM_PROXY_MODELS_CONFIG_PATH`, PAL loads
`conf/llm_proxy_models.json`, which ships empty. An empty catalog, invalid
connection configuration, missing SDK, or invalid request budget fails startup.

Run `listmodels` to see the catalog, then select a configured model or alias in
`chat` or `consensus`. Use distinct aliases such as `proxy-reviewer` to select
LLM Proxy when the same canonical model is also configured on a direct provider.
The selection order is native providers, custom endpoints, LLM Proxy, then
OpenRouter. Existing providers keep their relative priority.

## Supported behavior

- System and user text, model aliases, model restrictions, automatic model
  selection, output-token limits, and catalog-configured reasoning effort.
- The call's output limit overrides the catalog limit; otherwise PAL sends the
  catalog's `max_output_tokens` when nonzero.
- This adapter advertises text completion only. Temperature, streaming, images,
  function calling, and structured code generation are not exposed. Image input
  is rejected before dispatch. Reasoning effort comes from the catalog, rather
  than PAL's `thinking_mode` parameter.
- Responses contain text. Token usage remains empty because this SDK operation
  returns no usage counts. Provider and transport errors propagate without
  adapter retries, avoiding duplicate billable requests.

## Tests

After installing the optional SDK:

```bash
.pal_venv/bin/python -m pytest tests/test_llm_proxy_provider.py -v
```

These tests run the official client against a local HTTP server and verify
authentication, routing, messages, timeout headers, response/error handling,
startup, restrictions, and model discovery. They make no upstream model calls.
SDK-dependent tests skip when the optional client is absent.
