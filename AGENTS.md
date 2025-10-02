# Repository Guidelines

## Project Structure & Module Organization
Zen MCP Server centers on `server.py`, which exposes MCP entrypoints and coordinates multi-model workflows. 
Feature-specific tools live in `tools/`, provider integrations in `providers/`, and shared helpers in `utils/`. 
Prompt and system context assets stay in `systemprompts/`, while configuration templates and automation scripts live under `conf/`, `scripts/`, and `docker/`. 
Unit tests sit in `tests/`; simulator-driven scenarios and log utilities are in `simulator_tests/` with the `communication_simulator_test.py` harness. 
Authoritative documentation and samples live in `docs/`, and runtime diagnostics are rotated in `logs/`.

## Build, Test, and Development Commands
- `source .zen_venv/bin/activate` – activate the managed Python environment.
- `./run-server.sh` – install dependencies, refresh `.env`, and launch the MCP server locally.
- `./code_quality_checks.sh` – run Ruff autofix, Black, isort, and the default pytest suite.
- `python communication_simulator_test.py --quick` – smoke-test orchestration across tools and providers.
- `./run_integration_tests.sh [--with-simulator]` – exercise provider-dependent flows against remote or Ollama models.

## Coding Style & Naming Conventions
Target Python 3.9+ with Black and isort using a 120-character line limit; Ruff enforces pycodestyle, pyflakes, bugbear, comprehension, and pyupgrade rules. Prefer explicit type hints, snake_case modules, and imperative commit-time docstrings. Extend workflows by defining hook or abstract methods instead of checking `hasattr()`/`getattr()`—inheritance-backed contracts keep behavior discoverable and testable.

## Testing Guidelines
Mirror production modules inside `tests/` and name tests `test_<behavior>` or `Test<Feature>` classes. Run `python -m pytest tests/ -v -m "not integration"` before every commit, adding `--cov=. --cov-report=html` for coverage-sensitive changes. Use `python communication_simulator_test.py --verbose` or `--individual <case>` to validate cross-agent flows, and reserve `./run_integration_tests.sh` for provider or transport modifications. Capture relevant excerpts from `logs/mcp_server.log` or `logs/mcp_activity.log` when documenting failures.

## Commit & Pull Request Guidelines
Follow Conventional Commits: `type(scope): summary`, where `type` is one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, or `chore`. Keep commits focused, referencing issues or simulator cases when helpful. Pull requests should outline intent, list validation commands executed, flag configuration or tool toggles, and attach screenshots or log snippets when user-visible behavior changes.

## Security & Configuration Tips
Store API keys and provider URLs in `.env` or your MCP client config; never commit secrets or generated log artifacts. Use `run-server.sh` to regenerate environments and verify connectivity after dependency changes. When adding providers or tools, sanitize prompts and responses, document required environment variables in `docs/`, and update `claude_config_example.json` if new capabilities ship by default.
