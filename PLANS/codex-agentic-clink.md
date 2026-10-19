# Plan: agentic Codex runs through `clink`

Status: planned, not started. The single-turn ChatGPT provider (`chatgpt/<model>`, see
[docs/chatgpt_provider.md](../docs/chatgpt_provider.md)) ships first; this document covers the follow-up.

## Goal

Let PAL hand a task to Codex as an *agent*: it reads the repository, runs commands in a sandbox, uses its
own MCP servers and plugins, and can run Codex's native code review (`codex exec review`). This is a
different thing from the `chatgpt/<model>` provider, which treats a ChatGPT-plan model as a plain LLM
for one turn.

| | Model path (`chatgpt/<model>`, shipped) | Agent path (`clink`, this plan) |
|---|---|---|
| Called as | Any PAL tool, as a model | `clink` with `cli_name=codex` |
| Codex config, MCP servers, plugins | Not loaded | Loaded by default, each switchable off |
| Working directory | Empty temp dir | The caller's repository, per request |
| Sandbox | Read-only, always | Read-only by default, configurable |
| Turns | One, nothing persisted | Multi-turn; follow-ups resume the Codex session |
| Native `codex exec review` | No | Yes |

## Why `clink` and not the provider

Tools call `ModelProvider.generate_content()` synchronously and expect one reply, often in a set format.
An agent run can take 5–15 minutes, explore the repo, and ignore that format; inside a provider it would
also block PAL's event loop for the whole run. `clink` already runs CLIs as async subprocesses, with
roles, a 30-minute timeout, and conversation records, so the agent path extends it.

## Changes

### 1. Per-request working directory

Today `clink` runs the CLI in PAL's own working directory (or a fixed `working_dir` from the client
config), which is useless for reviewing the caller's repo.

- Add `working_directory` to `CLinkRequest`: an absolute path that must exist, checked with PAL's
  existing path-security helpers.
- Codex gets `-C <dir>`; Gemini and Claude run with that directory as `cwd`.

### 2. User-controlled sandbox, on by default

The shipped `conf/cli_clients/codex.json` passes `--dangerously-bypass-approvals-and-sandbox`. Once user
MCP servers and plugins (browser, computer-use) load, that gives an agent started by another agent full,
unapproved access to the machine.

- Remove the bypass flag from the shipped config.
- Add a `sandbox` setting with values `read-only` (default), `workspace-write`, and `off`:
  - set per role in the client config (`"sandbox": "read-only"`), and
  - overridable per request only toward *less* access unless `CLINK_ALLOW_SANDBOX_OVERRIDE=true`, so a
    calling agent cannot grant itself write access the user did not allow.
- `off` maps to `--dangerously-bypass-approvals-and-sandbox` and is accepted only from config, never from
  a request.
- Default roles: `default`, `planner`, `codereviewer`, `review` read-only; a new `implement` role uses
  `workspace-write`.
- This changes current `clink` behaviour, so it is its own commit. Users who relied on full access can
  restore it with a user config in `~/.pal/cli_clients/codex.json`.

### 3. User control over MCP servers, plugins, and user config

Agent mode loads the user's `~/.codex/config.toml` by default (that is the point), but each piece can be
turned off:

| Setting (client config / env) | Effect | Codex mechanism |
|---|---|---|
| `load_user_config` / `CLINK_CODEX_LOAD_USER_CONFIG` (default `true`) | Load `~/.codex/config.toml` at all | `--ignore-user-config` when false |
| `mcp_servers`: `"all"` (default), `"none"`, or a list of names | Which MCP servers start | `-c mcp_servers.<name>.enabled=false` for the excluded ones |
| `plugins`: `"all"` (default), `"none"`, or a list | Which plugins load | `-c plugins."<id>".enabled=false` |
| `features_disable`: list | Turn off specific Codex features (e.g. `browser_use`, `computer_use`) | `--disable <feature>` |
| `ignore_rules` (default `false`) | Skip execpolicy `.rules` files | `--ignore-rules` |

Notes to verify during implementation:

- The exact override keys for disabling a single MCP server or plugin in the installed Codex version
  (`codex debug prompt-input` renders the model-visible input offline and is a cheap way to confirm what
  loaded).
- Whether `--ignore-user-config` also drops skills under `~/.codex/skills`.

These settings live in the client config (and `~/.pal/cli_clients/` overrides). Per-request overrides
are allowed only to *narrow* what loads, for the same reason as the sandbox.

### 4. Native review role

- New Codex role `review` that runs `codex exec review --json` instead of `codex exec`.
- `review_target` request field: `uncommitted` (default), `base:<branch>`, or `commit:<sha>`, mapped to
  `--uncommitted`, `--base`, `--commit`. Invalid for any other CLI or role.
- `CodexAgent` builds this command itself: `review` is a subcommand that has to come right after `exec`,
  which the generic `executable + internal_args + config_args + role_args` order cannot express.

### 5. Model and effort per request

Optional `model` and `effort` fields on `CLinkRequest`. Codex maps them to `-m` and
`-c model_reasoning_effort=`. Each CLI client config declares its own flag templates, so Gemini and
Claude can support them too or reject them clearly.

### 6. Real session resume

- Agent mode keeps Codex's session file (no `--ephemeral`), reads `thread_id` from the
  `thread.started` event, and stores it with PAL's `continuation_id`.
- A follow-up with that `continuation_id` runs `codex exec resume <thread_id>`, so Codex keeps the files
  and command output it already gathered instead of receiving a text replay.
- Falls back to clink's existing text replay when no thread id is stored or resume fails.

### 7. Recursion guard

Loading the user's MCP servers means that if PAL is ever added to Codex's config, Codex can call PAL,
which calls `clink`, which starts Codex again.

- `clink` sets `PAL_CLINK_DEPTH=<n+1>` in the child environment; PAL refuses `clink` and `chatgpt/*`
  calls when the depth is above a small limit.
- To verify: whether Codex passes environment variables through to the MCP servers it starts. If it does
  not, add a startup check that warns when Codex's config lists a PAL server.

## Risks and open questions

- **MCP client timeouts.** A long review may outlast how long the MCP client (Claude Code) waits for a
  tool call, even though `clink` allows 30 minutes. Measure on a live run and document the client setting.
- **Quota.** Agent runs use far more of the ChatGPT plan than single model calls. Document it.
- **Codex CLI drift.** Flags and config keys change between Codex releases. Pin the tested version in
  the docs and fail with a clear message when a flag is rejected.

## Testing

Unit tests (subprocess mocked, no network):

- the command built for each role, including `exec review` and `exec resume`
- sandbox: default per role, narrowing allowed per request, widening rejected unless allowed, `off` only
  from config
- MCP server / plugin / feature filters render to the right flags; per-request widening rejected
- `working_directory` validation (relative, missing, outside allowed roots)
- each `review_target` form, and rejection for non-Codex CLIs
- resume: `thread_id` stored, follow-up uses it, fallback to text replay
- recursion guard

Live checks (small, throwaway data only):

- native review of a throwaway two-file git repo in a temp directory
- one follow-up that resumes that session
- one run that confirms the user's MCP servers load, and one with them disabled
- a check that the read-only sandbox blocks a write
