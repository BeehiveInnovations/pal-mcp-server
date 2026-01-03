# CLI Consensus Implementation - Task Tracking

## Overview

将 CLI 工具（Gemini CLI、Claude Code、Codex CLI）封装为 `CLIProvider`，使 Consensus 工具可以直接使用 CLI 免费额度进行多模型共识。

## Architecture

```
Consensus Tool
    │
    ▼ models: [{model: "cli:gemini"}, {model: "cli:claude"}]
    │
Provider Registry
    │
    ▼ get_provider_for_model("cli:gemini")
    │
CLIProvider (新增)
    │
    ▼ generate_content() → agent.run()
    │
External CLI Process (免费)
```

## Progress Tracker

| Phase | Task | Status | Notes |
|-------|------|--------|-------|
| 1 | Add CLI ProviderType | [x] | `providers/shared/provider_type.py` |
| 1 | Create CLIProvider base | [x] | `providers/cli_provider.py` |
| 2 | Register CLIProvider | [x] | `providers/registry.py` |
| 2 | Update __init__.py exports | [x] | `providers/__init__.py` |
| 3 | Handle async execution | [x] | Thread pool for sync interface |
| 4 | Add stance injection | [x] | System prompt passed through |
| 5 | Schema discovery | [x] | listmodels integration via get_all_model_capabilities() |
| 6 | Unit tests | [x] | `tests/test_cli_provider.py` - 16/16 passed |
| 6 | Integration tests | [x] | End-to-end validation - PASSED |

## Implementation Details

### Phase 1: CLIProvider Base Framework

**Files to modify/create:**
- `providers/shared/provider_type.py` - Add `CLI` enum value
- `providers/cli_provider.py` - New file, CLIProvider implementation

**Model naming convention:**
- `cli:gemini` → Gemini CLI (default role)
- `cli:gemini:planner` → Gemini CLI (planner role)
- `cli:claude` → Claude Code CLI
- `cli:codex` → Codex CLI

### Phase 2: Registry Integration

**Files to modify:**
- `providers/registry.py` - Add CLI provider priority, initialization logic
- `providers/__init__.py` - Export CLIProvider

### Phase 3: Async Execution

**Challenge:** `ModelProvider.generate_content()` is sync, but `agent.run()` is async.

**Solution:** Use `concurrent.futures.ThreadPoolExecutor` to run async code in separate thread.

### Phase 4: Stance Injection

Consensus tool already handles stance via `system_prompt`. CLIProvider just needs to pass it correctly.

### Phase 5: Schema & Model Discovery

Ensure CLI models appear in `listmodels` output and Consensus schema.

### Phase 6: Testing

- Unit tests for model name parsing
- Integration tests for full consensus workflow

## Usage Example (Target)

```python
# All CLI (free)
consensus(
    models=[
        {"model": "cli:gemini", "stance": "for"},
        {"model": "cli:claude", "stance": "against"},
    ],
    step="Evaluate: Should we use microservices?",
    ...
)

# Mixed mode (CLI + API)
consensus(
    models=[
        {"model": "cli:gemini", "stance": "for"},      # Free
        {"model": "gpt-4o", "stance": "against"},      # Paid API
    ],
    ...
)
```

## CLI Configuration (Top-tier Models)

默认配置使用顶级模型：

| CLI | Model | Config File |
|-----|-------|-------------|
| `cli:claude` | **Claude Opus 4.5** | `conf/cli_clients/claude.json` |
| `cli:gemini` | **Gemini 3 Pro** | `conf/cli_clients/gemini.json` |
| `cli:codex` | **GPT-5.2 Codex** | `conf/cli_clients/codex.json` |

## Model Naming

支持两种格式（别名）：

| 格式 | 示例 | 说明 |
|------|------|------|
| 规范格式 | `cli:claude`, `cli:gemini:planner` | 推荐使用 |
| 别名格式 | `cli-claude`, `cli-gemini-planner` | 也可使用 |

## Changelog

### 2025-01-04 - Implementation Complete & Tested

**Core Implementation:**
- [x] Added `ProviderType.CLI` enum value
- [x] Created `CLIProvider` class implementing `ModelProvider` interface
- [x] Registered CLIProvider in `ModelProviderRegistry`
- [x] Added CLI provider priority (before GOOGLE for cli: models)
- [x] Implemented thread pool execution for async CLI calls
- [x] Stance injection supported via system_prompt passthrough
- [x] Schema discovery integrated via get_all_model_capabilities()

**Bug Fixes:**
- [x] Fixed alias validation (`cli-claude` now correctly resolves to `cli:claude`)
- [x] `validate_model_name()` now calls `_resolve_model_name()` first
- [x] `generate_content()` resolves aliases before parsing

**Testing:**
- [x] Unit tests: 16/16 passing
- [x] Integration tests: End-to-end consensus with CLI - PASSED

**Configuration:**
- [x] Updated CLI configs to use top-tier models (Opus 4.5, Gemini 3 Pro, GPT-5.2)

### Files Modified
- `providers/shared/provider_type.py` - Added CLI enum
- `providers/cli_provider.py` - New file (~360 lines)
- `providers/registry.py` - CLI provider initialization
- `providers/__init__.py` - Export CLIProvider
- `server.py` - CLI availability detection and registration
- `tests/test_cli_provider.py` - New test file (16 tests)
- `conf/cli_clients/*.json` - Updated to top-tier models
