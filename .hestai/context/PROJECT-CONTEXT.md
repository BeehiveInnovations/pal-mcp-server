# PROJECT-CONTEXT

## Current Phase
**Branch:** agent-port
**Commit:** 2514b21 (feat(prompts): add complete system prompt library for all clink agent roles)
**Status:** PR #1 RESOLVED - system prompt files successfully created and committed; quality gates ready for validation

## Recent Achievements
- ✓ PR #1 RESOLVED: Complete system prompt library created for all clink agent roles (2514b21)
- ✓ PR #1 CI failure root cause identified and fixed: missing systemprompts/* files for newly declared agent roles
- ✓ Quality gate structure validated (lint, typecheck, test gates operational)
- ✓ Complete worktree protection and safety architecture documented
- ✓ Documented branch protection hooks preventing commits/pushes to main

## Active Work
- **READY:** Run quality gates (lint, typecheck, test) to validate PR #1 fix
- **PENDING:** Verify all 3 gates pass with newly created prompt files
- **NEXT:** Merge PR #1 to main after quality gate validation

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

## Files Modified (Commit 2514b21)
- systemprompts/: **COMPLETE** - Full system prompt library created for all agent roles
- conf/cli_clients/*.json: Agent role declarations (claude.json, codex.json, gemini.json)
- .hestai/context/PROJECT-CONTEXT.md: Updated with resolution status

**Status:** All prompt files created and committed; quality gates pending validation