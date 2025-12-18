# PROJECT-CONTEXT

## Current Phase
**Branch:** agent-port
**Commit:** e73bc41 (docs(context): document complete worktree protection and safety architecture)
**Status:** PR #1 CI failure identified and root cause documented; missing prompt files for new agent roles blocking quality gates

## Recent Achievements
- ✓ PR #1 CI failure root cause identified: missing systemprompts/* files for newly declared agent roles
- ✓ Quality gate structure validated (lint, typecheck, test gates operational)
- ✓ Complete worktree protection and safety architecture documented
- ✓ Documented branch protection hooks preventing commits/pushes to main
- ✓ Multi-remote safe workflow (origin→fork, upstream→original) operational

## Active Work
- **BLOCKING:** Create missing prompt files for new agent roles (PR #1 fix)
- **PENDING:** Re-run quality gates after prompt files created
- **PENDING:** Validate all 3 quality gates pass before PR merge

## Current Architecture
**Repository:** PAL MCP Server (pal-mcp-server)
**Worktree:** agent-port (isolated testing environment for infrastructure)
**Focus:** Agent configuration, prompt file structure, quality gate validation
**Problem:** New agent roles declared without corresponding systemprompts/ files

## Key Context

### PR #1 CI Failure: Missing Prompt Files (e73bc41)
Root cause analysis complete: **Quality gates failing because new agent roles lack corresponding prompt files.**

**The Issue:**
- New agent roles added to configuration files (conf/cli_clients/*.json)
- System prompts NOT created in systemprompts/ directory
- CI quality gates detect undefined prompts → test failures

**Required Fix:**
→ Create systemprompts/[agent-role].txt files for each newly declared agent
→ Structure: agent-name matches conf/cli_clients role declarations
→ Format: OCTAVE-style system prompts defining agent constitutional identity

**Why This Matters:**
- Agent configuration → prompt files is 1:1 mapping requirement
- CI gates (lint, typecheck, test) validate structural coherence
- Missing files create broken references → gate failures cascade

**Architecture Pattern Preserved:**
- Three-location model (global ~/.claude/, HestAI hub, project .claude/) remains intact
- Configuration synchronization pattern (cfg-config-sync, hs-hooks-sync) unaffected
- Worktree isolation and branch protection hooks continue functioning

### Quality Gate Structure (CI Validation)
The pipeline enforces three sequential gates:
```
GATE_1: lint (ruff) → 0 errors required
GATE_2: typecheck (pytest/type validation) → 0 errors required
GATE_3: test (unit tests) → all passing required
```

Gates detect structural violations including missing prompt files, undefined references, and configuration inconsistencies. All three gates currently **PENDING** until prompt files created.

## Files Modified (Current Session)
- conf/cli_clients/*.json: Agent role declarations added
- systemprompts/: **MISSING** (requires creation)
- .hestai/context/PROJECT-CONTEXT.md: This file (PR #1 findings documented)

**Status:** 0 prompt files created; 3 quality gates pending resolution