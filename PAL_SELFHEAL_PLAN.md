# PAL run-path resilience fixes — plan (self-applied, limit-aware)

Fix the failure modes seen 2026-10-01/02 (provider 429, Groq TPM 413, small-model
hallucination, tool-loop rewrite spiral, --plan line-split). KEY FINDING: the
resilience modules already exist (`providers/router/fallback_chain.py`,
`size_guard.py`, `rate_limit.py`) and are wired into `dispatch.py` (the MCP path)
— but `headless.py` (the `pal run` CLI) calls `chat_repl._tools_loop` directly
(headless.py:65) and bypasses them. So most fixes = WIRING, small diffs.

## Limits this plan is built around (do not violate)
- **Groq TPM ~7-8k tok/min, shared across keys** → every subtask edits ONE file,
  reads only that file + the small module it wires in. No whole-repo reads. Never
  feed a model more than ~1 file of context.
- **Per-subtask model + fallback is mandatory** (model-manager rule). Chain:
  primary `flash-lite` (1M ctx, reliable tool exec, no TPM wall) → fallback
  `gpt-oss-120b` (code-strong but SMALL diffs only, Groq TPM) → `openrouter/free`.
- **No `--plan` line-splitting**: each fix handed as its own `pal run "<task string>"`
  invocation (one fix = one process), NOT a multi-line plan file. This isolates
  failures and keeps context tiny.
- **Deterministic validation gate is run by the orchestrator (Claude), not an LLM**:
  after each edit → `.pal_venv/bin/python -m py_compile <file>` + targeted
  `pytest`. LLM never self-certifies success (today's rewrite spiral came from a
  model distrusting its own tool output).
- **Same-file edits are serialized** (never parallel) to avoid edit races:
  headless.py track and chat_repl.py track run in parallel with each other, serial
  within each.

## Track A — headless.py (serial: A1 → A2 → A3)

**A1. Wire failover into the run path.** In `headless.py:main`, wrap the
`chat_repl._tools_loop(...)` call (line ~65) so a provider error (429 /
insufficient_quota / RESOURCE_EXHAUSTED / 413) retries the next model from
`fallback_chain.chain_for(model)` instead of dying. Reuse
`fallback_chain.should_fallback()` to decide. Do NOT reimplement the chain.

**A2. Pre-send size guard.** Before the loop sends file content, call
`size_guard.check_or_reroute(model, prompt, files)`; if it says reroute, switch to
the bigger-context alt it returns. Import from `providers.router.size_guard`.

**A3. Prose-plan mode.** `_read_plan` (headless.py:76) splits a file into one
step per line, which mangled a prose plan into 30 fragments. Add a `--task-file`
CLI flag (in `cli.py` + `headless.main`) that reads the whole file as a SINGLE
task string. Leave `--plan` as-is for genuine bullet lists.

## Track B — chat_repl.py (serial: B1 → B2 → B3)

**B1. Strengthen the idempotency guard.** `_tools_loop` keeps `seen_calls`
(chat_repl.py:297,340,350) keyed on `(name, args)`. A `write_file` that the model
re-emits with slightly different `content` slips past it → rewrite spiral. Fix:
for `write_file`, key the signature on `path` ALONE. On a repeat write to the same
path, short-circuit with "already wrote <path> this loop; proceed to next step or
finalize." Keep existing behavior for other tools.

**B2. cwd consistency for bash vs write_file.** The model's `bash` checks and its
`write_file` resolved relative paths against different roots, so self-checks looked
like failures. Ensure both resolve relative paths against the SAME `cwd` passed
into `_tools_loop`: prepend `cd <cwd> && ` to bash commands (or run bash with
`cwd=` kwarg) and resolve `write_file`/`read_file` paths against that same `cwd`.

**B3. Rate-limit downshift.** Before each step's send, call
`rate_limit.should_downshift(provider, model, est_tokens)`; if true, either sleep
on `honor_retry_after` or downshift to the fallback model for that step. Wire the
existing `rate_limit` module; do not write a new bucket.

## After both tracks
- Orchestrator runs full targeted test set:
  `.pal_venv/bin/python -m pytest tests/test_cli.py tests/test_chat_router.py -q`
  plus `py_compile` on both edited files.
- Smoke test the real path: `pal run "write hello to /tmp/pal_smoke.txt" --model flash-lite`
  and confirm the file appears (proves cwd + write_file + no-spiral end to end).
- Log every edit in `PENDING_CHANGES.md` (batched infra-repo convention); do NOT
  commit/push unless the user asks.
