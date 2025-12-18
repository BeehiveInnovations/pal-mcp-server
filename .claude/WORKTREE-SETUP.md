# Agent-Port Worktree Configuration

## Overview

This worktree is configured as an **isolated development environment** that:
- ✅ Can create branches and PRs for `origin/agent-port` (your fork)
- ✅ Can pull updates from `upstream/main` (the original repo)
- ❌ **Cannot** commit or push to `origin/main` (protected)
- ❌ **Cannot** push to `upstream` (original repo)

## Remote Configuration

```
origin   → https://github.com/elevanaltd/pal-mcp-server.git  (your fork)
upstream → https://github.com/BeehiveInnovations/pal-mcp-server.git (original)
```

## Branch Protection Hooks

Two Git hooks are installed to prevent accidental pushes to main:

### 1. **prepare-commit-msg** (blocks commits on main branch)
Prevents any commits when on the main branch.

```bash
# This will be BLOCKED:
git checkout main
git commit -m "something"

# Error output:
# ❌ BRANCH PROTECTION: Cannot commit to main
# This worktree is configured for agent-port development only
```

### 2. **pre-push** (blocks pushes to main branch)
Prevents any push that targets main branch.

```bash
# This will be BLOCKED:
git push origin main

# Error output:
# ❌ PUSH PROTECTION: Cannot push to main
# This worktree is configured for agent-port development only
```

## Workflow: Pull Upstream Updates

To get the latest changes from the original repository:

```bash
# 1. Fetch updates from upstream
git fetch upstream

# 2. Merge upstream/main into your current branch (usually agent-port)
git merge upstream/main

# 3. Push to your fork if desired
git push origin agent-port
```

**Or use one command:**
```bash
git pull upstream main
```

## Workflow: Create a Feature Branch & PR

```bash
# 1. Create feature branch from agent-port
git checkout agent-port
git pull origin agent-port
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add my feature"

# 3. Push to your fork
git push origin feature/my-feature

# 4. Create PR in GitHub (must explicitly specify your fork)
gh pr create --repo elevanaltd/pal-mcp-server \
  --title "feat: add my feature" \
  --body "Description of changes"
```

## Protected Workflows

### ✅ ALLOWED
- `git commit` on agent-port branch
- `git push origin agent-port`
- `git fetch upstream`
- `git merge upstream/main`
- `gh pr create --repo elevanaltd/pal-mcp-server`

### ❌ BLOCKED
- `git commit` on main branch (prepare-commit-msg hook)
- `git push origin main` (pre-push hook)
- `git push upstream main` (pre-push hook)
- `gh pr create` without `--repo` flag (defaults to upstream)

## Emergency: Bypass Hooks

**Only if absolutely necessary**, you can temporarily bypass hooks:

```bash
# Commit bypassing hook
git commit -m "msg" --no-verify

# Push bypassing hook
git push --no-verify
```

**⚠️ Use sparingly** - these protections exist for a reason.

## Branch Tracking

The agent-port branch is configured to track:
- **Local**: `agent-port`
- **Remote**: `origin/agent-port`

```bash
# Verify configuration
git config --local branch.agent-port.remote
# Output: origin

git config --local branch.agent-port.merge
# Output: refs/heads/agent-port
```

## Git Configuration

Key worktree-specific configs:

```bash
# Show all local config
git config --local --list

# Key values:
# branch.agent-port.remote=origin
# branch.agent-port.merge=refs/heads/agent-port
```

## Troubleshooting

### "Cannot commit to main"

```
❌ BRANCH PROTECTION: Cannot commit to main
```

**Solution**: Switch to agent-port branch
```bash
git checkout agent-port
```

### "Cannot push to main"

```
❌ PUSH PROTECTION: Cannot push to main
```

**Solution**: Ensure you're pushing to agent-port, not main
```bash
git push origin agent-port
```

### PR went to wrong repository

**Cause**: Used `gh pr create` without `--repo` flag

**Solution**: Always specify your fork
```bash
gh pr create --repo elevanaltd/pal-mcp-server [options]
```

## Summary

This worktree setup ensures:
1. **Isolation**: No accidental commits/pushes to main
2. **Flexibility**: Easy upstream synchronization
3. **Safety**: Branch protection hooks prevent common mistakes
4. **Clarity**: Explicit remote specification prevents confusion

The hooks are **non-destructive** and can be bypassed with `--no-verify` if truly needed, but they exist to guide correct workflow patterns.
