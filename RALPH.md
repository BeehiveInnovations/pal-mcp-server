# Ralph Loop - Zero-Cost Automated Coding Loop

This implementation provides a Ralph Loop that leverages PAL MCP's CLI Provider for **zero API cost** automated coding workflows.

## What is Ralph Loop?

Ralph Loop is an automated coding methodology created by Geoffrey Huntley that:

1. **Iterates** through a task list until all tasks pass quality checks
2. **Persists memory** through files (not AI context)
3. **Uses back-pressure** (tests/linting) as quality gates
4. **Commits incrementally** after each successful task

Key insight: Each iteration starts fresh, avoiding context accumulation issues.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Zero-Cost Ralph Loop                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ralph.sh (Loop Controller)                                     │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  while [ passes != true ]; do                             │  │
│   │     1. Read prd.json → Get next task                      │  │
│   │     2. Build prompt → ralph_prompt.md + context           │  │
│   │     3. Execute → claude/gemini/codex CLI (FREE)           │  │
│   │     4. Validate → code_quality_checks.sh                  │  │
│   │     5. Update → prd.json + progress.txt + git commit      │  │
│   │  done                                                      │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   Files (Persistent Memory)                                      │
│   ├── prd.json         → Task list + status                     │
│   ├── progress.txt     → Learning log                           │
│   └── Git history      → Code changes                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Initialize a PRD (Product Requirements Document)

```bash
# Create a new PRD with project details
./ralph.sh --init \
  --name "My Feature" \
  --description "Implement user authentication"

# Or use a tasks file
./ralph.sh --init \
  --name "My Feature" \
  --description "Implement user authentication" \
  --tasks examples/prd_template.json
```

### 2. Add Tasks to prd.json

Edit `prd.json` to add your tasks:

```json
{
  "project_name": "My Feature",
  "description": "Implement user authentication",
  "tasks": [
    {
      "id": 1,
      "description": "Create User model with email and password fields",
      "success_criteria": "Model exists, migrations run, tests pass",
      "files_to_modify": ["models/user.py", "tests/test_user.py"],
      "status": "pending"
    },
    {
      "id": 2,
      "description": "Implement login endpoint",
      "success_criteria": "POST /login returns JWT token",
      "files_to_modify": ["routes/auth.py", "tests/test_auth.py"],
      "status": "pending"
    }
  ],
  "passes": false,
  "iteration": 0,
  "max_iterations": 50
}
```

### 3. Run the Loop

```bash
# Run with default CLI tool (claude)
./ralph.sh

# Run with specific CLI tool
./ralph.sh --cli gemini
./ralph.sh --cli codex

# Run with consensus mode (multiple models)
./ralph.sh --consensus

# Check status anytime
./ralph.sh --status
```

## CLI Tools (Zero Cost)

This implementation uses CLI tools that have free tiers:

| Tool | Free Tier | Command |
|------|-----------|---------|
| Claude Code | Included with Pro | `claude` |
| Gemini CLI | 1000 requests/day | `gemini` |
| Codex CLI | Varies | `codex` |

## File Reference

| File | Purpose |
|------|---------|
| `ralph.sh` | Main loop controller script |
| `ralph_utils.py` | Python utilities for PRD management |
| `ralph_prompt.md` | Prompt template for AI iterations |
| `prd.json` | Task list and progress state |
| `progress.txt` | Learning log across iterations |
| `examples/prd_template.json` | Example PRD structure |

## ralph_utils.py Commands

```bash
# Initialize a new PRD
python ralph_utils.py init --name "Project" --description "Description"

# Check current status
python ralph_utils.py status

# Get next task (JSON)
python ralph_utils.py next

# Get AI context (formatted for prompt)
python ralph_utils.py context

# Mark task as done
python ralph_utils.py done 1 --notes "Completed successfully"

# Mark task as failed
python ralph_utils.py fail 1 --error "Tests failing"

# Start working on a task
python ralph_utils.py start 1

# Record a learning
python ralph_utils.py learn "Discovered that X requires Y"

# Check if loop should continue
python ralph_utils.py check

# Increment iteration counter
python ralph_utils.py iterate

# Get consensus prompt for current task
python ralph_utils.py consensus-prompt
```

## Quality Gates (Back-Pressure)

The loop uses `code_quality_checks.sh` as the quality gate:

```bash
# Linting
ruff check --fix .

# Formatting
black .

# Import sorting
isort .

# Unit tests
python -m pytest tests/ -v -m "not integration"
```

Tasks are only marked complete when ALL checks pass.

## Task Design Principles

### Good Task (Right Size)

```json
{
  "description": "Add email validation to User.create() method",
  "success_criteria": "Invalid emails raise ValidationError, tests cover edge cases",
  "files_to_modify": ["models/user.py", "tests/test_user.py"]
}
```

### Bad Task (Too Large)

```json
{
  "description": "Build the entire authentication system",
  "success_criteria": "Users can log in"
}
```

### Guidelines

1. **One logical change per task** - Can be completed in a single AI context
2. **Clear success criteria** - AI can verify completion
3. **Specific files** - Helps AI focus
4. **Testable** - Must be verifiable by quality checks

## Consensus Mode

For complex decisions, use consensus mode which consults multiple models:

```bash
./ralph.sh --consensus
```

This leverages PAL MCP's Consensus tool to:
- Query multiple CLI models concurrently
- Gather different perspectives (for/against/neutral)
- Synthesize a unified recommendation

## Integration with PAL MCP

This Ralph Loop implementation integrates with PAL MCP Server's:

- **CLI Provider** (`providers/cli_provider.py`) - Zero-cost model access
- **Consensus Tool** (`tools/consensus.py`) - Multi-model decision making
- **code_quality_checks.sh** - Quality gates

## Monitoring Progress

```bash
# Watch progress in real-time
tail -f progress.txt

# Check PRD status
./ralph.sh --status

# View recent learnings
python ralph_utils.py status
```

## Troubleshooting

### "No CLI tool found"

Install at least one CLI tool:
```bash
# Claude Code
npm install -g @anthropic-ai/claude-code

# Gemini CLI
pip install google-generativeai

# Or use your preferred CLI
```

### "Quality checks failed"

The task will be retried. Check:
```bash
# Run checks manually
./code_quality_checks.sh

# See what's failing
ruff check .
python -m pytest tests/ -v
```

### "Max iterations reached"

Increase the limit in `prd.json`:
```json
{
  "max_iterations": 100
}
```

Or investigate why tasks keep failing:
```bash
cat progress.txt | grep "failed"
```

## References

- [Original Ralph Loop by Geoffrey Huntley](https://ghuntley.com/ralph/)
- [Everything is a Ralph Loop](https://ghuntley.com/loop/)
- [Ralph Playbook](https://claytonfarr.github.io/ralph-playbook/)
- [snarktank/ralph Implementation](https://github.com/snarktank/ralph)
