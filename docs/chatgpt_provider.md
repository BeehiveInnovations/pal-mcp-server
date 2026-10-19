# ChatGPT Models via the Codex CLI

PAL can call the models included in a ChatGPT plan, using the login of the
[Codex CLI](https://github.com/openai/codex) instead of an OpenAI API key. Every PAL tool (`chat`,
`consensus`, `thinkdeep`, `codereview`, ...) can use them like any other model.

Calls go through `codex exec`, one process per request, with Codex's agent features turned down. Codex
is used as a **plain model for one turn**: it does not run commands, read your repository, or load your
Codex MCP servers and plugins. (Agentic Codex runs through `clink` are planned separately; see
[PLANS/codex-agentic-clink.md](../PLANS/codex-agentic-clink.md).)

## Setup

1. Install the Codex CLI (for example `npm install -g @openai/codex` or `brew install codex`).
2. Run `codex login` and choose **Sign in with ChatGPT**. `codex login status` should print
   `Logged in using ChatGPT`.
3. Enable the provider in `.env`, or in your MCP client's `env` block (see below):

   ```env
   CHATGPT_ENABLED=true
   # Optional
   CHATGPT_ALLOWED_MODELS=chatgpt/gpt-6.1-sol,chatgpt/gpt-6-luna
   CHATGPT_TIMEOUT_SECONDS=600
   CHATGPT_CODEX_COMMAND=codex
   ```

4. Restart PAL. The startup log shows `CHATGPT_ENABLED=true - ChatGPT-plan models available through the
   Codex CLI`; `listmodels` lists them under **ChatGPT (via Codex CLI)**.

At startup PAL checks that `codex` is on `PATH` (the provider stays off if it is not) and runs
`codex login status`. A missing or API-key login is logged as a warning; the provider stays on, so
running `codex login` fixes it without a restart.

| Variable | Default | Meaning |
|----------|---------|---------|
| `CHATGPT_ENABLED` | off | `true` turns the provider on. No API key is needed. |
| `CHATGPT_ALLOWED_MODELS` / `CHATGPT_DISALLOWED_MODELS` | all | Comma-separated model names or aliases, like other providers. |
| `CHATGPT_TIMEOUT_SECONDS` | `600` | Per-call limit. Raise it for long prompts at high effort. |
| `CHATGPT_CODEX_COMMAND` | `codex` | The Codex executable, if it is not on `PATH` under that name. |
| `CHATGPT_MODELS_CONFIG_PATH` | `conf/chatgpt_models.json` | Your own model catalogue. |

## Add PAL to your MCP client

PAL reads `CHATGPT_ENABLED` from its environment, so you can set it in the client config instead of
`.env`. These examples run PAL from a clone (paths are placeholders).

**Claude Code** (user scope, so every project sees it):

```bash
claude mcp add pal -s user -e CHATGPT_ENABLED=true -- \
  /path/to/pal-mcp-server/.pal_venv/bin/python /path/to/pal-mcp-server/server.py
claude mcp get pal   # should show "Connected"
```

**Claude Desktop** (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "pal": {
      "command": "/path/to/pal-mcp-server/.pal_venv/bin/python",
      "args": ["/path/to/pal-mcp-server/server.py"],
      "env": {
        "CHATGPT_ENABLED": "true",
        "CHATGPT_CODEX_COMMAND": "/opt/homebrew/bin/codex"
      }
    }
  }
}
```

Claude Desktop starts MCP servers with a minimal `PATH` that usually lacks Homebrew and npm global
folders, so give Codex's full path (`which codex`) in `CHATGPT_CODEX_COMMAND`. Restart Claude Desktop
after editing the file. Claude Code inherits your shell's `PATH`, so it does not need this.

## Model names

Models are named `chatgpt/<codex model slug>`, for example `chatgpt/gpt-6.1-sol`. The prefix names the
login and billing path (your ChatGPT plan), keeps the names apart from the OpenAI API and Azure
catalogues, and avoids suggesting an agentic Codex run. Short aliases: `chatgpt/sol`, `chatgpt/astra`,
`chatgpt/luna`, `chatgpt/terra`.

The shipped catalogue lists the models `codex debug models` showed for a ChatGPT plan in October 2026.
Plans differ and the list changes, so run `codex debug models` to see yours and copy
`conf/chatgpt_models.json` to `CHATGPT_MODELS_CONFIG_PATH` to add or remove entries. The part after
`chatgpt/` is passed to `codex exec --model`.

In auto mode they are listed for the calling agent with their scores, like any other model. When PAL
picks a model itself (its fallback for a tool category), it asks providers in priority order and the
ChatGPT provider comes after every native API provider (before custom endpoints and OpenRouter), so it
is only chosen when no native API provider is configured.

## How a call runs

```
codex exec --json --ephemeral --skip-git-repo-check --ignore-user-config --ignore-rules \
  --sandbox read-only --cd <empty temp dir> --model <slug> [--image <file> ...] \
  --config forced_login_method="chatgpt" --config developer_instructions="<note + PAL system prompt>" \
  --config model_reasoning_effort="<effort>" -
```

- The prompt goes on stdin. PAL's system prompt becomes Codex developer instructions, after a short
  note telling the model to answer directly without tools.
- `--ignore-user-config` skips `~/.codex/config.toml`, so your Codex MCP servers, plugins and settings
  are not loaded. The login in `~/.codex` is still used.
- The sandbox is read-only and the working directory is an empty temp dir that is deleted afterwards.
  `--ephemeral` keeps the call out of Codex's session history.
- `forced_login_method="chatgpt"` and removing `OPENAI_API_KEY` / `CODEX_API_KEY` from Codex's
  environment ensure the call uses the ChatGPT login, never an API key.
- PAL's `thinking_mode` maps to Codex's reasoning effort (`minimal` becomes `low`; others pass through).
- Images are validated, copied to a temp folder outside the workspace, and attached with `--image`.
- The reply is Codex's last agent message. Error events are never returned as a reply.
- Transient failures (dropped stream, 5xx) are retried once. Login problems, usage limits and timeouts
  are not; their errors say what to do.
- Conversation history works as with any provider: PAL rebuilds it into each prompt, so each Codex call
  stays independent.

## Limits and costs

- **Plan quota.** Calls count against your ChatGPT plan's Codex usage limits, not API billing.
- **Overhead.** Codex sends its own agent instructions with every call: about 13K input tokens before
  your prompt (largely cached). Model context windows in the catalogue are Codex's (272K, or 500K for
  GPT-6.1 Sol), not the API's.
- **Speed.** Each call starts a process; a one-word reply takes about 4–5 seconds.
- **No temperature or output limit.** The Codex CLI has no setting for either, so PAL ignores them
  (`supports_temperature` is false).
- **Not a supported API.** This rides on the Codex CLI's command line and event output, which can change
  between Codex releases. Tested with Codex CLI 0.162.

## Troubleshooting

Startup messages go to `logs/mcp_server.log`; `grep -i chatgpt logs/mcp_server.log` shows the relevant ones.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CHATGPT_ENABLED=true but the Codex CLI ('codex') is not on PATH - ChatGPT models disabled` | PAL cannot find Codex, often because the MCP client's `PATH` is minimal | Set `CHATGPT_CODEX_COMMAND` to the full path from `which codex` |
| `... the Codex CLI is not signed in (run codex login)` | No Codex login | Run `codex login` and choose ChatGPT. No PAL restart needed |
| `... the Codex CLI is not signed in with ChatGPT` | Codex is signed in with an API key | Run `codex logout`, then `codex login` and choose ChatGPT |
| `ChatGPT plan usage limit reached` | The plan's Codex usage limit | Wait for the limit to reset, or use another provider meanwhile |
| `Codex CLI did not answer within 600s` | Long prompt or high effort | Raise `CHATGPT_TIMEOUT_SECONDS` |
| `Codex CLI failed (exit status 2): error: unexpected argument ...` | A Codex release changed its command line | Update PAL, or pin the Codex version listed under Limits and costs |
| `chatgpt/...` models missing from `listmodels` | Flag not set in the environment PAL actually runs with, or a `CHATGPT_ALLOWED_MODELS` filter | Check the client's `env` block and restart the client |

To check the setup without spending quota, `codex login status` should print `Logged in using ChatGPT`, and
`listmodels` should show **ChatGPT (via Codex CLI) ✅**.

## Logging

PAL logs the Codex command with the developer instructions replaced by their length, plus the model,
duration and token counts. Prompts are not written by this provider; Codex's login tokens are never
read or logged by PAL.

## Switching to an API provider later

When API access is available (for example Azure OpenAI with `AZURE_OPENAI_USE_ENTRA`), set
`CHATGPT_ENABLED=false` or remove it. Auto mode needs no other change. Anything that names
`chatgpt/...` models explicitly has to switch to the new provider's model names.
