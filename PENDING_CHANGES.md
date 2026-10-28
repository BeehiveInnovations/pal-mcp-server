
## Phase-1 learning substrate + anti-cascade penalty (2026-09-28)
- NEW providers/router/episode_store.py — durable JSONL episode store (~/.pal/episodes.jsonl); observability-only, makes no routing decision. Schema: model/category/outcome/err_class/latency_ms/reward(null,Phase2)/prompt_hash(sha256,no raw prompt)/tool/reason. In-mem ring + success_rate() read side for future bandit seeding. Env PAL_EPISODE_STORE/PAL_EPISODES_JSONL/PAL_EPISODE_MEM_CAP.
- PATCH providers/router/refusal_memory.py — error-class-aware penalties. classify_class()->policy|availability|client|unknown. Availability (5xx/429) NEVER blacklists on single hit: needs AVAIL_MIN(3) sustained within AVAIL_TTL(1800s), decays 1/AVAIL_DECAY_STEP(300s), auto-reprobes. Policy/client keep immediate skip + TTL(300s). Defeats flaky-5xx->permanent-blacklist cascade. Class change resets counter. Env PAL_REFUSAL_AVAIL_{TTL,MIN,DECAY_STEP}.
- PATCH providers/router/self_heal.py — migration probation: record_migration() commits permanent alias only after MIN_HINTS(2) identical hints; one-shot retry still recovers current call. Env PAL_SELF_HEAL_MIN_HINTS (1=old behavior).
- WIRE server.py — episode_store.record() at existing refusal hook points (success + failure) with latency.
- TESTS tests/test_episode_store.py, test_refusal_memory_penalty.py, test_self_heal_probation.py — 29 pass. No regression on quota_probe/rate_limit.
- Verdict source: 3-model debate (gpt-oss-120b FOR / gemini-flash AGAINST / qwen-27b NEUTRAL). Stop-line = Phase 2 human-gated diffs; NO autonomous self_modify auto-apply shipped.

## Phase-2 distiller + bandit seeding (2026-09-28)
- NEW providers/router/bandit.py — runtime candidate reordering by observed success (UCB-style: empirical rate when n>=MIN_SAMPLES(5) else prior order, + exploration bonus EXPLORE_C(0.7)*sqrt(ln(N+1)/(n+1))). NEVER drops a candidate (exploration floor); reversible/in-session; nothing persisted. reorder()/score()/explain(). Env PAL_BANDIT/PAL_BANDIT_{MIN_SAMPLES,EXPLORE_C,WINDOW}. Unseen candidates explored first (optimism under uncertainty).
- NEW providers/router/distill.py — OFFLINE distiller CLI `python -m providers.router.distill`. Reads episodes.jsonl, separates quality_rate=success/(success+policy_refusal) from reliability=1-avail_fail/n (transient 5xx never dents quality), proposes reordered CATEGORY_PREFERENCES per category, surfaces emerging unlisted models. Writes ~/.pal/distill/proposal-<ts>.json + report. HUMAN-GATED: never edits classifier.py, never auto-applied. Env PAL_DISTILL_{MIN_SAMPLES,DIR}.
- PATCH providers/router/episode_store.py — added observed(model,cat)->(n,successes) [bandit read side] and iter_file() [distiller disk read, corrupt-line tolerant].
- WIRE server.py — bandit.reorder(cat_tag, candidates) in auto-mode before blacklist filter.
- TESTS test_bandit.py(8), test_distill.py(8) — 62 total pass incl. regression. E2E CLI verified: refusing prior-#1 demoted, high-quality model promoted despite 8 transient 5xx.
- Stop line held: bandit=reversible runtime reorder (allowed); distill=proposal only (human-gated). No self_modify auto-apply.

## Unified `pal` CLI + teacher-sourced lessons (2026-09-28)
- NEW cli.py + [project.scripts] pal="cli:main" — subcommands: `pal serve` (server:run), `pal diag [--json]`, `pal distill ...` (passthrough, avoids argparse.REMAINDER leading-flag quirk). Needs `pip install -e .` for PATH; until then `python cli.py <cmd>`.
- NEW providers/router/diag.py — shared diag collector (defensive _safe wrappers). Adds episodes + bandit sections (bandit.explain per category) to the dump. scripts/pal-diag.py now thin-wraps it.
- NEW providers/router/lesson_store.py — teacher-sourced logic. emit_lesson(teacher_id, scope, rationale, ...) is the ONLY entry; requires teacher_id in TEACHERS allowlist (orchestrator 1.0/critic 0.7/panel 0.5/self 0.3) AND non-empty provenance. INJECTION DEFENSE AT ORIGIN CHANNEL: no transcript/task-text parser exists, so task content can never become a rule. Only scope=routing feeds the distiller; classifier/prompt/tool = human_review_only via pending_review(). ZERO inference-time loading. deactivate() writes tombstone; _load_disk applies tombstones on reload. Env PAL_LESSON_STORE/PAL_LESSONS_JSONL.
- PATCH distill.py — opt-in `--with-lessons` / build_proposal(use_lessons=True). Routing lessons nudge eff_quality by ±trust_weight*LESSON_NUDGE(1.0), attributed per-lesson in proposal["lessons_applied"] + report · lines. Lesson can't introduce a model absent from candidates. Strong telemetry + weak lesson => telemetry wins. Still human-gated proposal.
- TESTS test_cli.py(7), test_lesson_store.py(12), test_distill_lessons.py(5) — 85 total pass. E2E verified: orchestrator lesson promoted or-free #4->#1 as proposal.
- Debate source: gpt-oss-120b FOR (LLM-authored diffs) / gemini-flash AGAINST (inert log, injection kill-shot) / qwen NEUTRAL (stop at proposals). Verdict: teacher logic = human-gated proposals only; injection cut at channel auth, not diff content-scan.

## `pal` console script installed (2026-09-28)
- FIX pyproject.toml [tool.setuptools] py-modules — added "cli" (was ["server","config"]); without it the editable install exposed the `pal` entry point but `from cli import main` raised ModuleNotFoundError.
- INSTALLED: `pip install -e .` in .pal_venv (TMPDIR=/tmp; required freeing a stale sibling-session tmpfs dir that had filled /tmp to 100%). `pal` now on PATH at .pal_venv/bin/pal. Verified: `pal diag` (shows episodes+bandit sections), `pal distill --print-only`, `pal distill --with-lessons` all work as bare commands. `pal serve` = server:run.
- Package version unchanged (9.8.2).

## Interactive `pal chat` REPL (2026-09-28)
- NEW providers/router/chat_router.py — cheap-vs-smart tier selector. REUSES classifier.py (category signals) + model registry (availability); no new model-calling logic. classify_difficulty(): greeting/short -> cheap; classifier category OR code-authoring intent OR reasoning words OR len>280/3+ '?' -> smart. CHEAP_TIER=(gpt-oss-20b,groq-fast,flash-lite,...) SMART_TIER=(gpt-oss-120b,gemini-pro,gpt-5.2,...); env PAL_CHAT_CHEAP_MODEL/PAL_CHAT_SMART_MODEL/PAL_CHAT_HARD_LEN.
- NEW providers/router/chat_repl.py — async REPL. Every model call goes through server.handle_call_tool("chat"/...) so classifier+bandit+refusal+episode logging all apply (not a new router). Commands: plain msg=auto route; /cheap /smart force tier; /delegate <model> <q>; /debate <q> (fans across cheap+smart+flash panel); /model /help /exit. Strips chat tool's agent-boilerplate ("AGENT'S TURN", continuation_id note) for human readability. Threads continuation_id for context. Calls configure_providers() at startup (registry not populated on bare import).
- WIRE cli.py — `pal chat` subcommand. pyproject py-modules already includes cli (editable install auto-picks new router files).
- TESTS test_chat_router.py(20) — routing decisions + _clean/_extract helpers. 89 pass in the router suite.
- LIVE VERIFIED (Groq): 'hi'->gpt-oss-20b cheap; 'why sky blue'->gpt-oss-120b smart (Rayleigh); /delegate forces model; /debate returns 2 distinct panel views.
- Design: reused existing router (classifier/registry/handle_call_tool/hybrid) per "copy/reuse instead of build from scratch"; hybrid.py remains available as opt-in confidence-escalation (PAL_HYBRID=1).

## `pal chat` rich UI + log-flood fix (2026-09-28)
- REWRITE providers/router/chat_repl.py — rich terminal UI: header Panel (shows cheap/smart models + command hints), answers rendered as Markdown inside bordered bubbles (green=pal, blue=delegate, yellow=debate, red=error), console.status dots spinner while a model thinks. Routing tag shown dim (→ model · tier: reason).
- FIX log flood: the DEBUG spam users saw was all from server IMPORT time (LOG_LEVEL defaults to DEBUG, .env sets it, handler attached at import). run() now force-sets os.environ["LOG_LEVEL"]=PAL_CHAT_LOGLEVEL(default ERROR) AND logging.disable(WARNING) BEFORE importing server, then _quiet_logging() reasserts. Verified: 0 noise lines leaked (was 24). PAL_CHAT_LOGLEVEL overrides.
- FIX boilerplate: added markers for "Please continue this conversation using the continuation_id" variant + trailing markdown-rule stripping (_TRAILING_RULE).
- DEP: rich>=13.0 added to requirements.txt; installed into .pal_venv.
- TESTS test_chat_router.py still 21 pass (routing + _clean/_extract). Live-verified: clean header, markdown bubbles, cheap/smart routing, no DEBUG.

## `pal chat` /agent — full Claude Code capabilities (2026-09-28)
- NEW /agent <task> command in chat_repl.py — routes through handle_call_tool("clink", {cli_name:"claude", role:"default"}) to the local `claude` CLI (installed at ~/.local/bin/claude). This gives pal chat the REAL agentic Claude: bash, file read/edit, search, tools — running `claude --print --output-format json --permission-mode acceptEdits --model sonnet` in the current dir. model_used=claude-sonnet-5.
- One-time yellow safety notice on first /agent use (acceptEdits can modify files under cwd). _ask_agent() helper; magenta "agent" bubble.
- _clean() now strips <SUMMARY>…</SUMMARY> blocks clink appends.
- Distinction: /delegate <model> = raw model text (e.g. an OpenRouter Claude); /agent = full Claude Code CLI agent with tools. clink clients available: aider, claude, cline, codex, cursor-agent, gemini.
- LIVE VERIFIED: `/agent read note.txt` -> agent used file tools, returned contents; safety notice shown; SUMMARY stripped. Router tests still pass.

## /agent roles + permissions + cheap-models-use-Kali-tools (2026-09-28)
- (a) ROLES: /agent (read-only), /agent:edit (writes), /agent:plan (planner), /agent:review (codereviewer). Parsed from /agent:<suffix> in chat_repl.
- (b) PERMISSIONS: conf/cli_clients/claude.json — moved --permission-mode OUT of additional_args into per-role role_args (role_args append last, so they win). default/codereviewer=--permission-mode default (reads allowed, edits blocked headless=SAFE), edit=acceptEdits, planner=plan. Verified: default role reads note.txt but does NOT create files; edit role writes. Red warning shown only on first /agent:edit.
- (c) CHEAP MODELS USE KALI TOOLS: NEW /tools <task> — ReAct loop (_tools_loop) calls the PROVIDER DIRECTLY (not the chat tool, which blocks tool-shaped output), enabling PAL toolbelt (bash allowlist ls/cat/grep/find/curl/gh/git/wc/..., read_file, web_fetch, gh). Model emits <tool_call>, PAL runs it locally on Kali, feeds back <tool_result>, loops (max 5). Default tools model=qwen3 (gpt-oss trips Groq's output parser); override PAL_CHAT_TOOLS_MODEL. Tool calls shown as dim · lines. LIVE VERIFIED: qwen3 ran `wc -l data.env` -> answered 3.
- FIX providers/tooling/react.py — extract_calls now handles ALL open-model formats: {"args"}, {"arguments"} (str or dict), <function=NAME>{json}</function>, and <function=NAME><parameter=k>v</parameter></function> (Qwen XML). This was the blocker for cheap-model tool use.
- TESTS test_react_parser.py(8) — all formats. 29+ pass; full router suite green.
- SECURITY: bash adapter allowlist keeps /tools de-facto read-only (no rm/write binaries); runs in the launch cwd. /agent edit gated + warned.

## /tools write capability + parser hardening (2026-09-28)
- ROOTCAUSE of "(no answer)" on "create a file": (1) no write tool existed (bash allowlist is read-only, `touch` blocked); (2) qwen emitted a nameless call {"command":"touch hello"} the parser dropped.
- NEW write_file tool (providers/tooling/adapters/filesystem.py) — create/write UTF-8 files within PAL_FS_ROOTS (default cwd). Won't overwrite without overwrite=true; blocks paths outside roots (verified /etc/passwd rejected). Enabled in _ensure_toolbelt.
- FIX react.py extract_calls — now infers tool name when the model omits it (_infer_name: command→bash, path+content→write_file, path→read_file, url→web_fetch), and treats a bare object as the args when there's no args/arguments wrapper.
- _TOOLS_SYS updated: explicit tool guidance (bash=read-only, write_file=create files) + require "name" in the call. Header shows write_file.
- TESTS test_react_parser.py now 13 (added inference + nameless-drop). LIVE VERIFIED: /tools create file named hello -> qwen used write_file, file exists on disk.

## /tools:full — arbitrary command execution for authorized pentesting (2026-09-29)
- WHY: `/tools run burpsuite` refused — bash was locked to a read-only allowlist, so no real Kali tools (nmap/nuclei/burpsuite) could run.
- NEW /tools:full <task> — unlocks arbitrary bash for that run only. Red one-time warning (authorized-systems-only). max_steps=8, red bubble. Plain /tools stays read-only (default safe).
- bash adapter (adapters/bash.py): allowlist now read at CALL time; PAL_BASH_UNRESTRICTED=1 bypasses it. _tools_loop(full=True) sets the flag during the run and restores it in a finally (verified no leak to process env). Spec description mentions full mode + detached GUI launch.
- _TOOLS_SYS_FULL system prompt: offensive-security framing, real Kali tools, guidance to launch GUI/long-running apps DETACHED (`setsid <cmd> >/dev/null 2>&1 < /dev/null &`) and use higher timeout_s for scans.
- LIVE VERIFIED: /tools:full ran `whoami; hostname`; read-only /tools still blocks non-allowlisted binaries; flag does not leak between calls. 89 tests pass.
- SECURITY posture: destructive/arbitrary exec is opt-in per command via :full + explicit warning; default /tools read-only; /agent:edit remains the file-edit path. All gated behaviors require the user to choose them.

## /tools now full-power by default (2026-09-29)
- User choice: one /tools that runs ANY command + all tools, no :full needed. /tools:ro (aliases: readonly, safe) for a read-only session. /tools:full still accepted (same as default).
- chat_repl /tools handler: full = suffix not in (ro,readonly,safe) -> default True. One-time red safety notice on first full use ("runs ANY shell command by default... authorized systems only... use /tools:ro"). Header + usage updated. Blocked-in-ro hint now suggests plain /tools.
- Behavior verified: /tools run whoami -> executes (full); /tools:ro -> read-only allowlist. Bubble cyan; :ro tagged.
- All tests pass.

## /debate reads files then decides + files_required leak fixed (2026-09-29)
- BUG: /debate showed raw {"status":"files_required_to_continue",...} JSON — PAL's chat tool lets models request files, useless in a REPL debate.
- User need: debate models must READ files then decide. NEW two-phase /debate: (1) a tool-capable reader (qwen3, env PAL_CHAT_TOOLS_MODEL) uses read_file/bash to gather a <=250-word file digest from cwd; (2) the panel [gpt-oss-120b, qwen3, gpt-oss-20b] each give a verdict grounded in that digest via _ask_direct (direct provider call — no chat tool, so NO files_required envelope, no response-blocking). Only one model needs tools; all can debate.
- NEW _ask_direct(model, prompt, system) — provider.generate_content in a thread, _clean'd. Used for debate verdicts.
- _extract now humanizes a leaked files_required envelope ("(the model wanted to see files) <instructions>") instead of dumping JSON.
- LIVE VERIFIED: reader ran ls/read_file/grep on auth.py; gpt-oss-120b + qwen3 + gpt-oss-20b all correctly flagged plaintext compare/no-hashing/no-rate-limit. gpt-oss-120b works now (was blocked via chat tool).
- TEST: test_extract_files_required_envelope_humanized. All pass.

## Overcome recon refusals + Groq 413 token limit (2026-09-29)
- SYMPTOM: /debate "plan to continue recon on beon" -> qwen reader 413 (ITPM 7000 < 11740 requested) so no file evidence; then gpt-oss/qwen REFUSED ("can't help", "prohibit unauthorized access") on authorized recon.
- FIX 1 (refusals): _maybe_security(task, system) prepends _SECURITY_PREAMBLE (authorized in-scope testing, no refusals/disclaimers) when classifier.classify(task)=="security_permissive". Applied in _tools_loop (both modes) and the /debate panel _ask_direct. VERIFIED: recon debate now returns concrete plans (Shodan/Censys/crt.sh subdomain enum), no refusals.
- FIX 2 (413): token budget in _tools_loop — before each generate_content, if convo > PAL_TOOLS_CTX_CHARS (16000, ~4k tokens) keep task head + latest tool output tail, drop the middle. Keeps requests under Groq's small ITPM. VERIFIED: 40KB file trimmed, no 413.
- All tests pass.

## Per-command roles (2026-09-29)
- _ROLES dict: one-sentence system role per command (chat/delegate/smart/cheap/tools/debate/agent). _ask(role=) prepends "[Role: ...]" so every query — normal (cheap/smart by tier), /delegate, /debate, /tools, /agent — behaves specifically for its job. 22 tests pass.

## `pal run` — headless one-shot / plan runner (2026-09-29)
- NEW providers/router/headless.py + `pal run` subcommand (cli.py passthrough). Runs a task or a --plan file autonomously and prints ONLY the result — no REPL. Makes PAL callable like a function (pipe a task, read result), so the orchestrator (Claude) can delegate work without doing it.
  - `pal run "<task>"` (tools, full by default) · `--ro` (read-only) · `--agent` (full Claude Code CLI) · `--model <m>` · `--plan <file>` (one step per line / md bullets) · `--json` (structured: task/mode/model/tools_used/result).
  - Reuses _tools_loop / _ask_agent; quiets logging; configure_providers on start.
- VERIFIED: `pal run "count lines"` -> "3"; --json parseable (mode/model/tools/result); --plan ran 2 steps with per-step results; --agent --ro read a file.
- All tests pass.

## pal run --max-steps (2026-09-29)
- Added --max-steps N to `pal run` (headless.py): tool-call budget per task/plan-step, default 8 full / 5 ro. Fixes plan steps hitting [reached max tool steps]. Threaded run_task/run_plan -> _tools_loop.

## Phase 5: capability-aware model catalog + `pal models` (2026-09-30)
- NEW providers/router/catalog.py — one record per (service, model): provider(service: groq/openrouter/gemini/openai/xai/...)/adapter(ProviderType)/model/display/aliases/chat/tools/vision/structured_output/reasoning/context_limit/availability/quality_profile/cost_profile/source. Service identity split from adapter (Groq = custom adapter + CUSTOM_API_URL host). Merges static conf/*_models.json with live /models discovery (openrouter rich caps+pricing, gemini token limits, openai/xai/groq ids only -> unknown stays None, never name-guessed). TTL cache ~/.pal/model_catalog.json (0600, no credentials; PAL_CATALOG_TTL_S=21600, failures negative-cached PAL_CATALOG_FAIL_TTL_S=300, failed refresh keeps last good listing). availability: available|no_auth|unhealthy(quota_probe)|stale(static model absent from live listing)|discovered(uncurated, never routed).
- Only adapters PAL really serves + real creds are exposed (placeholder keys and keyless non-local custom = no_auth; deepseek/mistral/zai/requesty/cloudflare/hf keys in keys.env have no adapter -> never listed).
- Routing: select(Need)/order_for_category/pick_tier. Capabilities are a hard filter (None never satisfies a requirement; free-tier routes excluded unless category opts in — only long_context_bulk); legacy name lists (CATEGORY_PREFERENCES, CHEAP_TIER/SMART_TIER) demoted to tie-break priors and fallback. Routing reads cache only, never the network. PAL_CATALOG_ROUTING=0 = legacy behavior.
- NEW conf/model_profiles.json — cost-tier overlay (live pricing overrides; else estimated from intelligence_score, basis field says which).
- NEW providers/router/catalog_cli.py + WIRE cli.py `pal models [--provider X] [--refresh] [--json] [--all]`.
- WIRE server.py auto branch: catalog.order_for_category(pal_cat, candidates) or candidates (try/except -> legacy). WIRE chat_router._resolve: env > catalog.pick_tier > legacy.
- FIX urllib default UA got Groq /models 403 (Cloudflare) -> explicit User-Agent.
- TESTS tests/test_model_catalog.py (26). Full suite: 16 pre-existing failures unrelated (prompt_regression 'local-llama', clink live CLIs, large_prompt, model_restrictions) — identical with PAL_CATALOG_ROUTING=0.

## Phase 6: multi tool-capable model pool (2026-09-30)
- ROOTCAUSE: chat_repl.py hardcoded qwen3 as the sole tool executor in two places (`/tools`: `"qwen3" if _is_available("qwen3") else r["model"]`; `/debate` reader: `os.getenv("PAL_CHAT_TOOLS_MODEL") or ("qwen3" if _is_available("qwen3") else None)`) — single point of failure if qwen is rate-limited/unhealthy/blacklisted, and no way to add more tool-capable models without editing code.
- NEW providers/router/tools_pool.py — ordered, filtered candidate POOL instead of one name. Env PAL_TOOLS_MODELS (explicit pool, else derived from catalog tools=True entries + KNOWN_TOOL_FORMAT legacy list) / PAL_TOOLS_PRIMARY_MODEL (forced first candidate; PAL_CHAT_TOOLS_MODEL still honored as its legacy alias) / PAL_TOOLS_FALLBACK_MODELS (appended last-resort) / PAL_TOOLS_BLOCKLIST (never selected).
- Pipeline per role: capability (tool_executor requires KNOWN_TOOL_FORMAT or catalog tools=True — OpenAI/native `<tool_call>{"name":...,"arguments":...}` and Hermes/Qwen `<function=NAME>...</function>` both parseable by react.py; reviewer/reasoner/fallback don't need tool format) -> availability (registry) -> refusal_memory.is_blacklisted -> rate_limit.should_downshift -> size_guard.check_or_reroute (context fit) -> blocklist -> bandit.reorder(f"tools_pool:{role}") for learned ordering. Empty role-specific pool widens to the generic `fallback` role so a caller never gets stuck with zero candidates while ANY model is reachable.
- Roles: tool_executor (ReAct loop driver) / reviewer (/debate file reader) / reasoner (/debate panel) / fallback (least-strict, catch-all + auto-widen target). `select_pool(role, task, is_available=...)` returns the ordered list; `pick()` convenience for a single id; `assign_roles()` for `pal diag`-style introspection.
- WIRE chat_repl.py: NEW `_tools_loop_pool(task, pool, cwd, ...)` tries each pool candidate in order (skipping `__ERROR__` and refusal_memory-classified refusal text) until one gives a clean answer — fallover across the whole pool, distinct from fallback_chain's per-call provider retry which still runs underneath each candidate via dispatch.generate. `/tools` now calls `tools_pool.select_pool("tool_executor", ...)` and shows the pool + which model actually answered; `/debate` reader uses role="reviewer", panel uses role="reasoner" merged with the legacy 3-model list as a floor. Qwen is no longer sole/privileged — it's one KNOWN_TOOL_FORMAT candidate among several.
- TESTS tests/test_tools_pool.py (12): capability filter excludes untooled models, pool has >1 candidate when several are available (qwen not sole/privileged), PAL_TOOLS_PRIMARY_MODEL / legacy PAL_CHAT_TOOLS_MODEL / PAL_TOOLS_BLOCKLIST / PAL_TOOLS_MODELS+PAL_TOOLS_FALLBACK_MODELS all override ordering correctly, looser roles admit non-tool-format models via explicit PAL_TOOLS_MODELS, empty-pool widen-to-fallback, assign_roles labeling, pick() convenience, fully-unavailable pool returns []. Full suite: same pre-existing unrelated failures as Phase 5 baseline (prompt_regression 'local-llama', clink live CLIs, large_prompt, model_restrictions, chat_codegen/cross_model/consensus integration) — verified identical with git-stashed tracked changes.

## Phase 8: Claude-Code-like chat input UX (2026-09-30)
- WHY: `pal chat` used plain `console.input()` — no history, no Up/Down/Ctrl-P/Ctrl-N recall, no multiline, and any in-progress draft was destroyed the moment you touched history.
- NEW providers/router/chat_history.py — `JsonlSessionHistory(History)` (prompt_toolkit interface): one JSONL file per REPL session at `~/.pal/chat_history/<session_id>.jsonl` (mode 0700 dir / 0600 file) — "scoped to session" means its own file, so Up-arrow in one `pal chat` run never resurrects another run's lines. `mask_secrets()` redacts OpenAI/AWS/GitHub/Slack tokens, JWTs, `Bearer …`, and generic `key/token/secret/password=value` shapes before a line ever touches disk (recall shows the masked form too — accepted tradeoff over ever writing a secret to disk).
- WIRE chat_repl.py: `_build_prompt_session()` — `PromptSession(multiline=True, history=JsonlSessionHistory(...))`. Enter submits (custom binding overrides prompt_toolkit's multiline default of Enter=newline); Alt+Enter and Ctrl-J insert a literal newline. Up/Down are prompt_toolkit's own `auto_up`/`auto_down` — line-aware: move the cursor within a multiline draft, only fall through to history at the first/last visual line, and use the Buffer's built-in "working line" slot to restore an unsent draft exactly when paging back out of history (byte-for-byte, verified, not reimplemented). Ctrl-P/Ctrl-N added as unconditional history-prev/next (readline-emacs style) regardless of cursor line. `_read_line()` falls back to the old plain `console.input` if prompt_toolkit isn't installed or session construction fails (no real TTY) — headless callers (`pal run`) are unaffected, they never call this path.
- NEW `/models` chat command — same capability catalog as `pal models` (providers/router/catalog.py + catalog_cli.render), rendered in a panel without shelling out. All prior commands preserved unchanged: `/tools[:ro]`, `/debate`, `/delegate`, `/smart`, `/cheap`, `/agent[:edit|:plan|:review]`, `/diag` (via `pal diag`, untouched), `/model`, `/help`, `/exit`.
- DEPS: added `prompt_toolkit>=3.0.43` to requirements.txt + pyproject.toml (also backfilled `rich>=13.0` into pyproject, was requirements-only).
- LIVE VERIFIED (prompt_toolkit pipe-input harness, no real TTY needed): plain Enter submits; Alt+Enter inserts newline and a later Enter submits the full multiline text (`'line1\nline2'`); Up then Down after typing a draft restores the draft exactly (`'draftxyz'`); Ctrl-P then Ctrl-N round-trips back to the empty draft; Ctrl-P alone recalls the last submitted entry. `mask_secrets` + `JsonlSessionHistory` round-tripped correctly (secrets masked before write, plain text untouched, session-scoped file). `_models_table()` renders the live catalog.
- TESTS: full suite 1026 passed / 4 skipped (same pre-existing unrelated failures as prior phases: live clink CLI creds, prompt_regression 'local-llama', large_prompt, model_restrictions, chat_codegen/cross_model/consensus — identical baseline, none touched by this change).
- Phase 10: .env.example documents full PAL_* surface (~85 vars)

## Phase 11: `pal diag` upgrade (2026-09-30)
- providers/router/diag.py: new sections quota (probe stats, newest per provider), breaker (refusal_memory), fallback (chains/max_attempts), size_guard (caps), guardrail (mode + kind->count stats), headroom (compression stats), catalog (cache-only counts by service/availability + discovery age), tool_pool (per-role pools), debate; flags +PAL_FALLBACK/GUARDRAIL/HEADROOM/DEBATE.
- Safety: all output passes `_scrub()` (secret-ish keys -> `<redacted>`, token regexes, 200-char truncation); only counters/names/states are collected — no env keys, restore-maps, or prompts. Tests in tests/test_cli.py (10 pass).

## 2026-10-02 — `pal run` CLI resilience fixes (headless + tools-loop)
Applied surgically (PAL's own models did destructive wholesale rewrites on these
files, so Claude hand-edited; root-cause analysis was done against the live code).

- **headless.py** `run_task`:
  - **A2 size-guard**: `size_guard.check_or_reroute` up front → reroute to a
    bigger-context model before entering the loop (dispatch also guards per-call;
    this catches it earlier).
  - **A1 failover**: `_tools_loop` CATCHES provider errors and RETURNS
    `"__ERROR__…"` (never raises), so wrapped the loop to retry across
    `fallback_chain.chain_for(m)` on an error return; skips non-retryable errors
    (no tools / no provider / no model).
- **headless.py** `main` + arg: **A3 `--task-file`** reads the WHOLE file as one
  task (prose plans). `--plan` still line-splits by design. (Root cause of the
  30-fragment mangling earlier.)
- **chat_repl.py** `_tools_loop`:
  - **B1 idempotency**: `write_file` dedupe signature now keyed on PATH ALONE
    (ignores content) → a re-write of the same file with tweaked content is
    caught. This was the #1 cause of the rewrite spiral.
  - **B2 cwd consistency**: bash commands get `cd <cwd> &&` prefixed; relative
    `write_file`/`read_file` paths are joined to the loop `cwd`. Stops the
    "self-check looks failed → rewrite again" loop.
- **B3 (rate_limit.should_downshift) deliberately NOT added** — `dispatch.generate`
  already wraps size_guard + call_with_fallback, and the loop already caps Groq
  OTPM + trims context to budget. Adding it would double-sleep / duplicate.

Validation: `py_compile` both files; `pytest tests/test_cli.py tests/test_chat_router.py`
= 32 passed; live smoke `pal run --task-file … --model flash-lite` created the file
in cwd with a single write_file call, no stall. Diff: +64/-10 across the 2 files.

### 2026-10-02 (smoke-test follow-up) — failover category map was stale
Smoke-testing A1 revealed `fallback_chain.chain_for()` returned [] for every live
workhorse (flash-lite, qwen3, nemotron, openrouter/free): the category map in
`~/.pal/env.json` still listed dead model names (grok-4-fast, gemini-3-pro-preview,
nvidia/nemotron-nano-9b-v2). So A1 was correct but toothless. Refreshed the 4
categories (names kept — classifier.py routes on them) with the 2026-10-02 probed
live roster, aliases deduped so a chain never falls back to itself. Backup at
~/.pal/env.json.bak.*. NOTE: classifier.py:78-79 has its OWN hardcoded category
tuple map that is also stale (routing, not failover) — left for a separate pass.

Full smoke result: A1 advances chain + recovers; A1-neg (non-retryable) tries once;
A2 reroutes oversize to bigger model; A3 --task-file one-task; B1 blocks 2nd
same-path write; B2 resolves relative path to cwd; 51 tests pass.

### 2026-10-02 — openpyxl into .pal_venv + security-mission playbook proof
- Installed openpyxl 3.1.5 into .pal_venv so PAL's toolbelt python can write xlsx
  deliverables end-to-end (previously crashed on the xlsx step, wrote only csv).
- Quality-fix pipeline proven: PAL (cheap models, filled-spec + structured-JSON +
  orchestrator gate) rebuilt the beon asset inventory to EXACT parity with the
  hand-built ground truth (UNAUTH 59 / AUTH 191 / ALL 250, csv+xlsx).
- Authored SECURITY_MISSION_PLAYBOOK.md (in ~/Desktop/bughunting) — reusable
  10-rule anti-stuck template for handing security work to PAL. Proof mission
  (read-only attack-surface triage of 191 auth endpoints via a fixed rubric)
  completed in 3 steps, no spiral; independent orchestrator gate re-derived the
  rubric and confirmed 191/191 records, 100% tier-consistent (P1=22 P2=25 P3=144).

### 2026-10-02 — classifier.py CATEGORY_PREFERENCES refreshed (last stale map)
PAL (flash-lite, surgical exact-string patch via .classifier_fix/patch.py per the
security-mission playbook — no file rewrite) replaced the dead first-choice models
(grok-4-fast, nvidia/nemotron-nano-9b-v2, gemini-3-pro-preview, gemini-3.6-flash)
with the live probed roster, live model FIRST per category, dead names kept only as
trailing fallbacks. Diff +4/-4. Orchestrator gate: compiles; every category's first
pref is live; 51 tests pass (test_chat_router/test_router_guardrail/test_cli).
Both the failover map (~/.pal/env.json) AND the routing map (classifier.py) are now
on the live roster — no stale model references remain in PAL's routing/failover.

## 2026-10-06 — Ollama Cloud as orchestrator (MCP/toolbelt-capable)
- `~/.pal/keys.json`: added `ollama_cloud` entry (base https://ollama.com/v1, api openai, 17 models,
  key reused from existing `ollama` string). register_extras() picks it up → ProviderType.OLLAMA_CLOUD.
- `.env`: added PAL_MISSION_{WRITER,EXECUTOR,REVIEWER}_MODELS with Ollama-Cloud free models first
  (gpt-oss:120b, nemotron-3-ultra, gpt-oss:20b) + non-ollama fallbacks last.
- Verified: `pal run --model gpt-oss:120b` drives bash toolbelt (ORCH_MCP_OK); `pal mission` single-model
  path selects gpt-oss:120b and answers via tool. Free tier: gpt-oss:120b/20b, nemotron-3-ultra/nano:30b,
  gemma4:31b (200); glm-5.3/kimi-k3/minimax-m3/deepseek-* = 402 (need paid credits).
- KNOWN LIMIT: generic extra providers don't strip a `provider:` prefix, so call Ollama Cloud models by
  BARE name (`gpt-oss:120b`), not `ollama_cloud:gpt-oss:120b`. Optional follow-up: patch _make_provider
  in providers/extra_providers.py to strip the leading `<name>:`/`<name>/` prefix for all extras.
- MCP server (mcp__pal__*) must restart to expose ollama_cloud through the MCP tools (same
  configure_providers path); CLI path already live.

## 2026-10-06 (2) — Ollama Cloud interactive orchestrator in `pal chat`
- providers/router/chat_repl.py:
  - selected_model now seeds from env PAL_CHAT_MODEL (pins the chat to a model at launch).
  - NEW /plan <goal>: pinned/selected model drafts a numbered executable plan (plain chat, keeps
    conversation context), stored as last_answer.
  - NEW /feed [text] (aliases /topal /mission): writes last plan (or <text>) to ~/.pal/last_plan.md
    and runs `pal run --plan <file> --json` (+ --model selected_model) with PAL_TOOLBELT=1.
  - last_answer tracked in /ask-/cheap-/smart and default branches so /feed can grab the last reply.
- NEW launcher ~/.local/bin/ollama-orch: `PAL_CHAT_MODEL=gpt-oss:120b PAL_TOOLBELT=1 pal chat`.
- Verified E2E: /plan drafted on gpt-oss:120b; /feed executed via pal run --plan (result returned).

## 2026-10-06 (3) — /plan auto-picks model by plan TYPE
- chat_repl.py: added _classify_plan (keyword types: code/security/analysis/fileops/bulk/general),
  _pick_plan_model (type->model map, Ollama-Cloud-first + fallbacks, availability-filtered), and
  _PLAN_MODELS. /plan now auto-selects the suitable model for the kind of plan (overrides the pin),
  prints "auto-picked for type=<t>". /plan:<type> forces a type. Env overrides: PAL_PLAN_MODEL (force
  one), PAL_PLAN_MODELS_<TYPE> (per-type list).
- Verified: classifier 6/6 on samples; live analysis plan auto-picked nemotron-3-ultra (not pinned gpt-oss:120b).

## 2026-10-06 (4) — /plan now auto-feeds to PAL (one step)
- chat_repl.py: extracted _run_plan_through_pal() helper (write ~/.pal/last_plan.md + `pal run --plan`).
  /plan now drafts THEN auto-runs the plan through PAL by default (previously draft-only). /plan:draft
  drafts without running. /feed refactored to the same helper. Verified E2E (PLAN_AUTOFEED_OK).

## 2026-10-06 (5) — stop security-mission refusals in /plan
- Root cause: /plan drafts via the plain `chat` path, which (unlike _tools_loop at line ~271) did
  NOT apply the authorized-pentest preamble, so security goals got model refusals ("safeguard alert").
- Fix: /plan now prepends _SECURITY_PREAMBLE (via _maybe_security / ptype=="security") to the plan prompt.
- Launcher ollama-orch: export PAL_GUARDRAIL_INBOUND=log to silence inbound prompt-injection warn-alerts.
  CREDENTIAL MASKING LEFT ON (protects the operator's secrets). Full off = PAL_GUARDRAIL=0 (not default).
- Verified: security /plan drafted a 10-step recon/SSRF plan (no refusal) and auto-fed to PAL.

## 2026-10-06 (6) — reasoning-leak guard in _tools_loop
- Problem: gpt-oss (Ollama) can return chain-of-thought in message.reasoning with content="" and NO
  tool_call; PAL's reasoning-field fallback then surfaced raw deliberation and the loop stopped.
- Fix (chat_repl.py): _looks_like_reasoning() (>=2 deliberation markers + len>=200) + _REASONING_NUDGE.
  In _tools_loop, when no tool_call AND text looks like reasoning, nudge the model to emit a tool_call
  or final answer and continue (cap PAL_REASONING_GUARD_NUDGES=2). Disable with PAL_REASONING_GUARD=0.
- Verified: heuristic 4/4 (leak=True; short/result/plan=False); normal gpt-oss:120b tool run unaffected.

## 2026-10-06 (7) — /plan refusal retry + never-feed-a-refusal
- Problem: /plan draft refused ("I'm sorry, I can't help") and the refusal was auto-fed to PAL.
- Fix (chat_repl.py): _is_refusal() (regex + SMART-QUOTE normalization — models emit curly ' in I’m/can’t,
  which defeated the first regex) and _plan_candidates(). /plan now tries each type-pool model in order,
  skips any that refuse, reports if ALL refuse, and never auto-feeds a refusal. /feed also refuses to feed
  a refusal. Security plan pool: gpt-oss:120b -> nemotron-3-ultra -> nemotron-3-super -> gpt-oss:20b
  (dropped openrouter/free per no-or-free-for-authed-pentest rule).
- Verified: _is_refusal 6/6 + curly-quote case; live gpt-oss:120b refused -> auto-retried nemotron-3-ultra
  -> real recon/auth-bypass plan produced.

## 2026-10-06 (8) — background plan runs + finish notification
- chat_repl.py: _launch_plan_background() runs `pal run --plan` DETACHED (setsid, start_new_session),
  saves plan+results to ~/.pal/plan_runs/{plan_,run_}<ts>.{md,json}, and on finish fires
  notify-send (desktop popup) + paplay (freedesktop/complete.oga) + spd-say "pal plan finished".
  /plan auto-feed and /feed now background by default; chat prints pid + results path immediately.
  Revert to inline foreground with PAL_PLAN_BG=0.
- Verified: /feed detached (pid shown, chat freed); results file written (steps_run:1, BG_PING_OK);
  notify-send exit 0 (popup shown); complete.oga present.

## 2026-10-06 (9) — soft-refusal detection + security plan framing + pool reorder
- _REFUSAL_RE broadened: catches SOFT refusals ("I cannot PROVIDE/GIVE/CREATE...", "what I can offer
  instead", "crosses into exploitation", "detailed exploitation methodology"). Prevents a soft-refusal
  being fed to PAL as a plan. Verified: nemotron soft refusal=True; real plans incl. one containing
  'provide the subdomain list'=False.
- Security /plan prompt reframed as an AUTHORIZED OWASP-WSTG TEST PLAN (concrete test cases + exact
  tools/commands, "do not refuse or substitute a reading list") -> nemotron-3-ultra now drafts real
  curl-based auth test cases instead of soft-refusing.
- _PLAN_MODELS["security"] reordered nemotron-3-ultra FIRST (gpt-oss:120b reliably refuses auth testing;
  nemotron complies) -> skips the wasted gpt-oss refusal round-trip.

## 2026-10-06 (10) — background pid reporting fix
- _launch_plan_background used Popen(["setsid","bash",...], start_new_session=True): setsid forked the
  real worker into a new session and EXITED immediately, so proc.pid was a throwaway that `ps -p` showed
  as "not running" while the plan actually ran under a different pid. Removed the redundant "setsid"
  (start_new_session=True already makes the child a session leader). proc.pid is now the real long-lived
  wrapper. Verified: reported pid alive 2s after launch.

## 2026-10-06 (11) — plan EXECUTOR fix (qwen3 413) + clean results file
- Problem: a bg plan run launched WITHOUT --model -> pal run --plan defaulted executor to qwen3
  (groq qwen3.8-27b, ITPM 7000) -> every step 413 "Request too large/rate_limit_exceeded"; nothing ran.
  Also `2>&1` merged error logs into the JSON results file (unparseable).
- Fix (chat_repl.py): _launch_plan_background + _run_plan_through_pal default executor to
  PAL_PLAN_EXEC_MODEL (default gpt-oss:120b, 128k, no tiny ITPM); stderr -> <res>.log (JSON stays clean).
  /plan auto-feed now executes on the model that DREW the plan (selected_model or drafter) so security
  plans run on the compliant drafter (nemotron). Verified: bg run w/o pin used default, clean JSON,
  no qwen/413, step executed (STEP_ONE_OK).

## 2026-10-06 (12) — /plan & /feed execute via MISSION orchestrator (distribute+review+retry)
- chat_repl.py: _plan_exec_parts() builds the exec command; default PAL_PLAN_MODE=mission runs
  `pal mission <goal+draft> --json` (Writer->Executor->Reviewers->Judge: distinct model per role,
  parallel panel for complexity>=4, judge-feedback retry up to PAL_MISSION_MAX_ITERS, per-call
  fallback_chain). PAL_PLAN_MODE=run keeps old sequential `pal run --plan`. Security missions pass
  --writer/--executor nemotron-3-ultra (gpt-oss refuses auth). _launch_plan_background + 
  _run_plan_through_pal + call sites updated to pass (goal, plan_text, model, ptype).
- .env: PAL_MISSION_{WRITER,EXECUTOR,REVIEWER,ASSESS}_MODELS -> Ollama Cloud (nemotron-3-ultra,
  gpt-oss:120b/20b) + gemini-3.5-flash-lite; REMOVED groq (openai/gpt-oss-120b, qwen3) which has an
  8000 TPM cap -> mission's ~18KB repo-context prompts crashed with "exceed cap (TPM>8000)" (0-byte result).
- Verified: pal mission COMPLETE on gpt-oss:120b; hit 2 rate limits mid-run but fallback_chain RECOVERED
  and returned correct answer. Clean JSON.

## 2026-10-06 (13) — classify auth as security + drafting via _ask_direct (no groq)
- Root causes of the auth /plan failure: (a) classifier missed auth/login terms -> type=general -> no
  security preamble/framing -> gpt-oss refused; (b) drafting used the chat MCP tool which auto-routed to
  groq custom/openai/gpt-oss-120b (8000 TPM) -> "exceed cap" crash.
- Fixes (chat_repl.py): _PLAN_KEYWORDS security now includes login/auth/jwt/session/oauth/mfa/user-enum/
  rate-limit/password-reset/csrf/cors/cookie/token/etc. /plan drafts via _ask_direct (dispatch -> EXACT
  model, no auto-route to groq) with the preamble as SYSTEM; loop skips __ERROR__/rate_limit/empty too.
  Security pool reordered gpt-oss:120b FIRST (it COMPLIES under the OWASP-test-plan framing once the goal
  is correctly typed security; proven via direct API: clean curl user-enum plan in 2s). nemotron fallback.
- Verified: auth goals now classify security (4/4); direct API: gpt-oss:120b returns real plan content,
  no groq TPM crash in the drafting path.

## 2026-10-06 (14) — panel produced plan-not-results; security defaults to run-mode execution
- run_20261006-095228: mission PANEL (9 models) only WROTE a test-plan .md; judge correctly INCOMPLETE
  ("did not execute the commands / no verification on disk"). Panel mode brainstorms, doesn't run tools.
- .env PAL_MISSION_PANEL=0 (missions now execute via Writer->Executor->Judge, not brainstorm-panel).
- _plan_exec_parts: default mode is now RUN for ptype==security (executes the drafted concrete
  curl/ffuf/jwt_tool steps with tools) and MISSION for other goals. PAL_PLAN_MODE still overrides.

## 2026-10-06 (15) — THE execution bug: gpt-oss:120b resolved to groq (8000 TPM) not Ollama
- run_20261006-095831: run mode executed step 1 then steps 2-15 ALL died "rate_limit:
  custom/openai/gpt-oss-120b exceed cap (TPM>8000)". Root cause: ProviderType.CUSTOM (groq flat-rate)
  aliases gpt-oss/gpt-oss-120b and was ordered BEFORE the Ollama extras, so `gpt-oss:120b` resolved to
  groq (8000 TPM), not ollama.com. Only nemotron-3-ultra/gemma4:31b reached ollama.
- Fix: providers/extra_providers.py register_extras insert_before now includes CUSTOM, so extras
  (strict allowlists) win over groq-custom for their own models. Verified: gpt-oss:120b -> ollama,
  gpt-oss:20b -> ollama_cloud, openai/gpt-oss-120b -> custom (unchanged). 3-step pal run --plan on
  gpt-oss:120b: 0 cap errors, all steps executed (curl 200).
- Note: keys.json already had a rich `ollama` entry (ollama.com, Turbo free tier) pre-dating my
  redundant `ollama_cloud` add; both point to ollama.com/v1 and work.

## 2026-10-06 (16) — /plan false-positive: rejected valid plans mentioning "rate-limit"
- The draft error-guard checked `"rate_limit" in ans` -> a VALID security plan that mentions rate-limiting
  was flagged as an error and skipped (fell through to slow nemotron). Fixed: only __ERROR__ prefix / empty
  counts as a draft failure. Security pool reordered to fast models first: gpt-oss:120b, gpt-oss:20b,
  nemotron-3-super, nemotron-3-ultra (ultra is slow, now last).

## Executor-level authorization boundary — scope enforcement + intent classification (2026-10-07)
- ROOT CAUSE (bug 2, git scope expansion): NO authorization/scope model existed anywhere in the tool chain. The user's intent ("push README.md") was passed as a natural-language task string to an LLM, which freely emitted `git add -A && git commit && git push`; the `bash` adapter ran it verbatim. `git` was also in the read-only allowlist, so even read-only `/tools` mode could stage/commit/push. No secret/sensitive scan before external publish. `mission._is_protected` only guarded the writer file-write stage, not git/bash.
- ROOT CAUSE (bug 1, security overinterpretation): `_TOOLS_SYS_FULL` hard-coded "You are an offensive-security assistant … authorized penetration testing" on EVERY full tools_loop (incl. "create a directory"). `classifier._SEC_RE` + `mission._heuristic_assess` fired "security" on bare keyword substring (filename/dirname/commit object), e.g. "commit exploit.py".
- NEW providers/tooling/authz.py — the hard boundary. `ToolScope` (immutable; intent/authorized_paths/scope_mode explicit|open/allow_scope_expansion=False/external_ok/cwd) carried as a contextvar through the whole chain; `push_scope` NARROWS-only (a downstream/nested scope can never widen or re-open a parent's explicit allow-list). `analyze_git_command` decomposes compound bash into GitOps (detects add -A/-u/./glob/$()-substitution=stages_all, commit -a, push=external, unbalanced-quote=fail-closed). `path_in_scope` glob/dir-aware (README.md, src/**, bare dir). Secret detection by NAME (.env/*.pem/*.key/id_rsa/credentials*/secret*/engagement*/pentest-report*) AND CONTENT (private-key block, AWS/GitHub/Slack/Google keys, JWT, bearer, generic api_key= assignments). `enforce(name,args,scope)` is the single check: rejects stage-all + out-of-scope paths in explicit mode; secret-scans every external publish (git push / gh pr-create/merge/release/repo-create) regardless of mode; blocks credential writes. Env: PAL_AUTHZ_DISABLE=1 (off), PAL_AUTHZ_ALLOW_SECRETS=1 (permit secrets in a publish). Fail-closed in explicit mode, fail-open otherwise.
- NEW providers/router/intent.py — the stage BEFORE llm planning. `classify_intent`: security requires a security VERB+TARGET (scan/enumerate/exploit a host/url/domain/api) OR a vuln-noun+assessment-verb ("test this API for vulnerabilities"); a keyword that is only the OBJECT of a fs/git verb ("mkdir enumeration", "commit exploit.py") is NOT security. Extracts git op + explicit paths; explicit paths => explicit scope (hard allow-list), "push everything/my changes" => open scope. `scope_for_request` builds the ToolScope the executor enforces.
- WIRE providers/tooling/toolbelt.py — Toolbelt.execute() (the ONE chokepoint every tool call/model/fallback/panel funnels through) now calls authz.enforce(name,args,current_scope()) BEFORE the handler; a denial is audited and returned, operation never runs. Enforcement is below the LLM — no reasoning/model-swap can bypass it.
- WIRE providers/router/chat_repl.py — _tools_loop pins authz.push_scope(intent.scope_for_request(task,cwd)) for the whole loop (covers headless `pal run`, REPL default line via _tools_loop_pool, mission commands). _TOOLS_SYS_FULL rewritten NEUTRAL ("do exactly what the user asked; don't assume a security objective from names"; SCOPE rule: never git add . with an explicit file list). `_maybe_security` now gates the AUTHORIZATION preamble on intent.is_security (verb+target), not bare keyword — real recon still gets the permissive framing, ordinary fs/git work does not.
- WIRE providers/router/mission.py — `_execute_plan(…, goal=)` pins the GOAL's scope around command execution so writer-emitted commands inherit it (narrows-only). `_heuristic_assess` recon only on intent.is_security. `_is_protected` unified with authz.scan_name (now also *.pem/*.key/id_rsa/credentials*/engagement*/…).
- WIRE providers/router/classifier.py — security_permissive route suppressed when intent is a plain git/fileops op (keyword as filename/commit object no longer picks the permissive security model).
- HARDEN providers/tooling/adapters/bash.py — in read-only mode `git` may run INSPECTION subcommands only (status/log/diff/show/branch/remote/rev-parse/ls-files/…); add/commit/push/etc. blocked (fail-closed on unparse). Closes the "read-only mode can mutate/publish the repo" hole.
- TESTS tests/test_authz_scope.py(25) + tests/test_intent_classify.py(14) — 39 pass. Cover every spec regression case: single_file_push, directory_push, sensitive_files_present, explicit_file_list, model_scope_expansion (git add . rejected), downstream_model_scope_expansion (intersection), unrelated_staged_files (force-staged .env still blocks push), normal_directory_creation (fileops not security), actual_enumeration (security), content-scan-not-trusting-filename, env overrides, end-to-end via Toolbelt.execute. E2E proven in a real git repo: `add -A`/out-of-scope add/force-staged .env push all rejected; authorized `add README.md` runs.
- RESIDUAL RISK / LIMITS: (a) scope is extracted heuristically from the request's NL — a very indirect phrasing of a path could under-scope (open mode); open mode still secret-scans external pushes. (b) authz gates git/gh/write_file mutation+publish surfaces, not arbitrary non-git bash (full mode is still full shell by design); a model could still `rm`/`curl` out-of-scope files in full mode — out of scope for this change, flagged for a follow-up fs-write/network gate. (c) `_effective_push_set` is best-effort git; if git introspection fails it falls back to staged+HEAD~1 (still secret-scanned). (d) PAL_AUTHZ_DISABLE / PAL_AUTHZ_ALLOW_SECRETS are operator escape hatches, not model-settable.
