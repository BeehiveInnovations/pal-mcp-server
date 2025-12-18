# PROJECT-CONTEXT

## Current Phase
**Branch:** agent-port
**Commit:** c0adca8 (docs(setup): add comprehensive worktree configuration and protection guide)
**Status:** Worktree isolation and branch protection hooks fully documented; guardrails in place for safe multi-remote workflow

## Recent Achievements
- ✓ Documented branch protection hooks (prepare-commit-msg, pre-push) preventing commits/pushes to main
- ✓ Created WORKTREE-SETUP.md with comprehensive protection guide and configuration instructions
- ✓ Established remote configuration pattern: origin → fork, upstream → original repo
- ✓ Documented safe PR creation workflow with --repo flag and emergency bypass procedures
- ✓ Synchronized clink client configurations (claude, codex, gemini) between agent-port and hestai-mcp-server

## Active Work
- Quality gates pending: lint, typecheck, test (scheduled)
- Configuration verification across three client providers in progress

## Current Architecture
**Repository:** PAL MCP Server (pal-mcp-server)
**Worktree:** agent-port (isolated testing environment for infrastructure)
**Focus:** Multi-provider clink client configuration and HestAI agent role routing
**Tools:** clink client configuration, MCP server setup, multi-model delegation

## Key Context

### Worktree Protection & Isolation Pattern (c0adca8)
The agent-port worktree implements **multi-layer isolation** protecting main branch and safe multi-remote workflow:

**Branch Protection Hooks:**
- `prepare-commit-msg`: Prevents accidental commits on main branch
- `pre-push`: Blocks pushes to main/upstream branches, allows feature branch pushes

**Remote Configuration:**
- `origin` → fork (safe push destination, PR source)
- `upstream` → original repo (pull-only, automatic updates)
- Workflow: feature on agent-port → automatic upstream pulls → PR via --repo flag

**Why This Architecture:**
- Developers can't accidentally push to production (main)
- Automatic synchronization with upstream maintains context currency
- Safe multi-remote workflow scales across team
- Documentation in WORKTREE-SETUP.md enables new developers to replicate pattern

### Configuration Synchronization Pattern
Three CLI client configurations (claude, codex, gemini) provide consistent role-based model delegation:
- 50+ specialized HestAI agent roles mapped across providers
- Model-specific routing: opus (critical decisions), sonnet (tactical), haiku (routine)
- System prompt paths enable infrastructure-as-code configuration
- Synchronized between worktree testing and main branch distribution

## Files Modified
- conf/cli_clients/claude.json (3 → 391 lines)
- conf/cli_clients/codex.json (updated with 46+ roles)
- conf/cli_clients/gemini.json (updated with consistent structure)

Total: 3 files, 939 insertions, 17 deletions