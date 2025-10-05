# Clink Tool - CLI-to-CLI Bridge

**Bring other AI CLIs into your workflow - Gemini (for now), Qwen (soon), Codex (soon), and more work alongside Claude without context switching**

The `clink` tool lets you leverage external AI CLIs (like Gemini CLI, etc.) directly within your current conversation. Instead of switching between terminal windows or losing context, you can ask Gemini to plan a complex migration, review code with specialized prompts, or answer questions - all while staying in your primary Claude Code workflow.

## Why Use Clink (CLI + Link)?

**Scenario 1**: You're working in Claude Code and want Gemini's 1M context window to analyze a massive codebase, or you need Gemini's latest web search to validate documentation.

**Without clink**: Open a new terminal, run `gemini`, lose your conversation context, manually copy/paste findings back.

**With clink**: Just say `"clink with gemini to review this entire codebase for architectural issues"` - Gemini launches separately, processes request and returns results, and the conversation continues seamlessly.

**Scenario 2**: Use [`consensus`](consensus.md) to debate which feature to implement next with multiple models, then seamlessly hand off to Gemini for implementation.

```
"Use consensus with pro and gpt5 to decide whether to add dark mode or offline support next"
[consensus runs, models deliberate, recommendation emerges]

"Continue with clink - implement the recommended feature"
```

Gemini receives the full conversation context from `consensus` including the consensus prompt + replies, understands the chosen feature, technical constraints discussed, and can start implementation immediately. No re-explaining, no context loss - true conversation continuity across tools and models.

## Key Features

- **Stay in one CLI**: No switching between terminal sessions or losing context
- **Full conversation continuity**: Gemini's responses participate in the same conversation thread
- **Role-based prompts**: Pre-configured roles for planning, code review, or general questions
- **Full CLI capabilities**: Gemini can use its own web search, file tools, and latest features
- **Token efficiency**: File references (not full content) to conserve tokens
- **Cross-tool collaboration**: Combine with other Zen tools like `planner` → `clink` → `codereview`
- **Free tier available**: Gemini offers 1,000 requests/day free with a personal Google account - great for cost savings across tools

## Available Roles

**Default Role** - General questions, summaries, quick answers
```
"Use clink to ask gemini about the latest React 19 features"
```

**Planner Role** - Strategic planning with multi-phase approach
```
"Clink with gemini role='planner' to map out our microservices migration strategy"
```

**Code Reviewer Role** - Focused code analysis with severity levels
```
"Use clink role='codereviewer' to review auth.py for security issues"
```

You can make your own custom roles in `conf/cli_clients/gemini.json` or tweak existing ones.

## Tool Parameters

- `prompt`: Your question or task for the external CLI (required)
- `cli_name`: Which CLI to use - `gemini` (default), or add your own in `conf/cli_clients/`
- `role`: Preset role - `default`, `planner`, `codereviewer` (default: `default`)
- `files`: Optional file paths for context (references only, CLI opens files itself)
- `images`: Optional image paths for visual context
- `continuation_id`: Continue previous clink conversations

## Usage Examples

**Architecture Planning:**
```
"Use clink with gemini planner to design a 3-phase rollout plan for our feature flags system"
```

**Code Review with Context:**
```
"Clink to gemini codereviewer: Review payment_service.py for race conditions and concurrency issues"
```

**Quick Research Question:**
```
"Ask gemini via clink: What are the breaking changes in TypeScript 5.5?"
```

**Multi-Tool Workflow:**
```
"Use planner to outline the refactor, then clink gemini planner for validation,
then codereview to verify the implementation"
```

**Leveraging Gemini's Web Search:**
```
"Clink gemini to research current best practices for Kubernetes autoscaling in 2025"
```

## How Clink Works

1. **Your request** - You ask your current CLI to use `clink` with a specific CLI and role
2. **Background execution** - Zen spawns the configured CLI (e.g., `gemini --output-format json`)
3. **Context forwarding** - Your prompt, files (as references), and conversation history are sent as part of the prompt
4. **CLI processing** - Gemini (or other CLI) uses its own tools: web search, file access, thinking modes
5. **Seamless return** - Results flow back into your conversation with full context preserved
6. **Continuation support** - Future tools and models can reference Gemini's findings via [continuation support](../context-revival.md) within Zen. 

## Best Practices

- **Pre-authenticate CLIs**: Install and configure Gemini CLI first (`npm install -g @google/gemini-cli`)
- **Choose appropriate roles**: Use `planner` for strategy, `codereviewer` for code, `default` for general questions
- **Leverage CLI strengths**: Gemini's 1M context for large codebases, web search for current docs
- **Combine with Zen tools**: Chain `clink` with `planner`, `codereview`, `debug` for powerful workflows
- **File efficiency**: Pass file paths, let the CLI decide what to read (saves tokens)

## Configuration

Clink configurations live in `conf/cli_clients/`. The default `gemini.json` includes:

```json
{
  "name": "gemini",
  "command": "gemini",
  "additional_args": ["--telemetry", "false"],
  "roles": {
    "planner": {
      "prompt_path": "systemprompts/clink/gemini_planner.txt",
      "role_args": ["--experimental-acp"]
    }
  }
}
```

**Adding new CLIs**: Drop a JSON config into `conf/cli_clients/` and create role prompts in `systemprompts/clink/`.

## When to Use Clink vs Other Tools

- **Use `clink`** for: Leveraging external CLI capabilities (Gemini's web search, 1M context), specialized CLI features, cross-CLI collaboration
- **Use `chat`** for: Direct model-to-model conversations within Zen
- **Use `planner`** for: Zen's native planning workflows with step validation
- **Use `codereview`** for: Zen's structured code review with severity levels

**CAUTION**: `clink` opens additional doors but not without additional risk. Configuration arguments like `--approval-mode yolo` in `conf/cli_clients/gemini.json` bypass safety
prompts and should only be used when you're certain the operations are safe.
Review your role configurations carefully before enabling automated execution modes. You can add safeguards and guardrails within role-specific system prompts (in `systemprompts/clink/`) to restrict or guide the external CLI's behavior.

## Setup Requirements

Ensure [gemini](https://github.com/google-gemini/gemini-cli) is installed and configured. 

## Related Guides

- [Chat Tool](chat.md) - Direct model conversations
- [Planner Tool](planner.md) - Zen's native planning workflows
- [CodeReview Tool](codereview.md) - Structured code reviews
- [Context Revival](../context-revival.md) - Continuing conversations across tools
- [Advanced Usage](../advanced-usage.md) - Complex multi-tool workflows
