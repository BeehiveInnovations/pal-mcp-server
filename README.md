# Zen MCP: Many Workflows. One Context.

[zen_web.webm](https://github.com/user-attachments/assets/851e3911-7f06-47c0-a4ab-a2601236697c)

<div align="center">
  <b>🤖 <a href="https://www.anthropic.com/claude-code">Claude Code</a> OR <a href="https://github.com/google-gemini/gemini-cli">Gemini CLI</a> + [Gemini / OpenAI / Grok / OpenRouter / DIAL / Ollama / Anthropic / Any Model] = Your Ultimate AI Development Team</b>
</div>

<br/>

**AI orchestration for Claude Code** - A Model Context Protocol server that gives your CLI of choice (e.g. [Claude Code](https://www.anthropic.com/claude-code)) access to multiple AI models for enhanced code analysis, problem-solving, and collaborative development.

**True AI collaboration with conversation continuity** - Claude stays in control but gets perspectives from the best AI for each subtask. Context carries forward seamlessly across tools and models, enabling complex workflows like: code reviews with multiple models → automated planning → implementation → pre-commit validation.

> **You're in control.** Claude orchestrates the AI team, but you decide the workflow. Craft powerful prompts that bring in Gemini Pro, GPT 5, Flash, or local offline models exactly when needed.

<details>
<summary><b>Reasons to Use Zen MCP</b></summary>

1. **Multi-Model Orchestration** - Claude coordinates with Gemini Pro, O3, GPT-5, and 50+ other models to get the best analysis for each task

2. **Context Revival Magic** - Even after Claude's context resets, continue conversations seamlessly by having other models "remind" Claude of the discussion

3. **Guided Workflows** - Enforces systematic investigation phases that prevent rushed analysis and ensure thorough code examination

4. **Extended Context Windows** - Break Claude's limits by delegating to Gemini (1M tokens) or O3 (200K tokens) for massive codebases

5. **True Conversation Continuity** - Full context flows across tools and models - Gemini remembers what O3 said 10 steps ago

6. **Model-Specific Strengths** - Extended thinking with Gemini Pro, blazing speed with Flash, strong reasoning with O3, privacy with local Ollama

7. **Professional Code Reviews** - Multi-pass analysis with severity levels, actionable feedback, and consensus from multiple AI experts

8. **Smart Debugging Assistant** - Systematic root cause analysis with hypothesis tracking and confidence levels

9. **Automatic Model Selection** - Claude intelligently picks the right model for each subtask (or you can specify)

10. **Vision Capabilities** - Analyze screenshots, diagrams, and visual content with vision-enabled models

11. **Local Model Support** - Run Llama, Mistral, or other models locally for complete privacy and zero API costs

12. **Bypass MCP Token Limits** - Automatically works around MCP's 25K limit for large prompts and responses

**The Killer Feature:** When Claude's context resets, just ask to "continue with O3" - the other model's response magically revives Claude's understanding without re-ingesting documents!

#### Example: Multi-Model Code Review Workflow

1. `Perform a codereview using gemini pro and o3 and use planner to generate a detailed plan, implement the fixes and do a final precommit check by continuing from the previous codereview`
2. This triggers a [`codereview`](docs/tools/codereview.md) workflow where Claude walks the code, looking for all kinds of issues
3. After multiple passes, collects relevant code and makes note of issues along the way
4. Maintains a `confidence` level between `exploring`, `low`, `medium`, `high` and `certain` to track how confidently it's been able to find and identify issues
5. Generates a detailed list of critical -> low issues
6. Shares the relevant files, findings, etc with **Gemini Pro** to perform a deep dive for a second [`codereview`](docs/tools/codereview.md)
7. Comes back with a response and next does the same with o3, adding to the prompt if a new discovery comes to light
8. When done, Claude takes in all the feedback and combines a single list of all critical -> low issues, including good patterns in your code. The final list includes new findings or revisions in case Claude misunderstood or missed something crucial and one of the other models pointed this out
9. It then uses the [`planner`](docs/tools/planner.md) workflow to break the work down into simpler steps if a major refactor is required
10. Claude then performs the actual work of fixing highlighted issues
11. When done, Claude returns to Gemini Pro for a [`precommit`](docs/tools/precommit.md) review

All within a single conversation thread! Gemini Pro in step 11 _knows_ what was recommended by O3 in step 7! Taking that context
and review into consideration to aid with its final pre-commit review.

**Think of it as Claude Code _for_ Claude Code.** This MCP isn't magic. It's just **super-glue**.

> **Remember:** Claude stays in full control — but **YOU** call the shots.
> Zen is designed to have Claude engage other models only when needed — and to follow through with meaningful back-and-forth.
> **You're** the one who crafts the powerful prompt that makes Claude bring in Gemini, Flash, O3 — or fly solo.
> You're the guide. The prompter. The puppeteer.
> #### You are the AI - **Actually Intelligent**.

#### Recommended AI Stack

For best results, use Claude Code with:
- **Opus 4.1** - All agentic work and orchestration
- **Gemini 2.5 Pro** - Deep thinking, code reviews, debugging, pre-commit analysis

</details>

## Quick Start (5 minutes)

**Prerequisites:** Python 3.10+, Git, [uv installed](https://docs.astral.sh/uv/getting-started/installation/)

**1. Get API Keys** (choose one or more):
- **[OpenRouter](https://openrouter.ai/)** - Access multiple models with one API
- **[Gemini](https://makersuite.google.com/app/apikey)** - Google's latest models
- **[OpenAI](https://platform.openai.com/api-keys)** - O3, GPT-5 series
- **[X.AI](https://console.x.ai/)** - Grok models
- **[DIAL](https://dialx.ai/)** - Vendor-agnostic model access
- **[Ollama](https://ollama.ai/)** - Local models (free)

**2. Install** (choose one):

**Option A: Instant Setup with uvx** (recommended)
```json
// Add to ~/.claude/settings.json or .mcp.json
{
  "mcpServers": {
    "zen": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/BeehiveInnovations/zen-mcp-server.git", "zen-mcp-server"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "GEMINI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**Option B: Clone and Setup**
```bash
git clone https://github.com/BeehiveInnovations/zen-mcp-server.git
cd zen-mcp-server
./run-server.sh  # Handles everything: setup, config, API keys
```

**3. Start Using!**
```
"Use zen to analyze this code for security issues with gemini pro"
"Debug this error with o3 and then get flash to suggest optimizations"
"Plan the migration strategy with zen, get consensus from multiple models"
```

👉 **[Complete Setup Guide](docs/getting-started.md)** with detailed installation, configuration, and troubleshooting

## Core Tools

> **Note:** Each tool comes with its own multi-step workflow, parameters, and descriptions that consume valuable context window space even when not in use. To optimize performance, some tools are disabled by default. See [Tool Configuration](#tool-configuration) below to enable them.

**Collaboration & Planning** *(Enabled by default)*
- **[`chat`](docs/tools/chat.md)** - Brainstorm ideas, get second opinions, validate approaches
- **[`thinkdeep`](docs/tools/thinkdeep.md)** - Extended reasoning, edge case analysis, alternative perspectives
- **[`planner`](docs/tools/planner.md)** - Break down complex projects into structured, actionable plans
- **[`consensus`](docs/tools/consensus.md)** - Get expert opinions from multiple AI models with stance steering

**Code Analysis & Quality**
- **[`debug`](docs/tools/debug.md)** - Systematic investigation and root cause analysis
- **[`precommit`](docs/tools/precommit.md)** - Validate changes before committing, prevent regressions
- **[`codereview`](docs/tools/codereview.md)** - Professional reviews with severity levels and actionable feedback
- **[`analyze`](docs/tools/analyze.md)** *(disabled by default - [enable](#tool-configuration))* - Understand architecture, patterns, dependencies across entire codebases

**Development Tools** *(Disabled by default - [enable](#tool-configuration))*
- **[`refactor`](docs/tools/refactor.md)** - Intelligent code refactoring with decomposition focus
- **[`testgen`](docs/tools/testgen.md)** - Comprehensive test generation with edge cases
- **[`secaudit`](docs/tools/secaudit.md)** - Security audits with OWASP Top 10 analysis
- **[`docgen`](docs/tools/docgen.md)** - Generate documentation with complexity analysis

**Utilities**
- **[`challenge`](docs/tools/challenge.md)** - Prevent "You're absolutely right!" responses with critical analysis
- **[`tracer`](docs/tools/tracer.md)** *(disabled by default - [enable](#tool-configuration))* - Static analysis prompts for call-flow mapping

<details>
<summary><b id="tool-configuration">👉 Tool Configuration</b></summary>

### Default Configuration

To optimize context window usage, only essential tools are enabled by default:

**Enabled by default:**
- `chat`, `thinkdeep`, `planner`, `consensus` - Core collaboration tools
- `codereview`, `precommit`, `debug` - Essential code quality tools
- `challenge` - Critical thinking utility

**Disabled by default:**
- `analyze`, `refactor`, `testgen`, `secaudit`, `docgen`, `tracer`

### Enabling Additional Tools

To enable additional tools, remove them from the `DISABLED_TOOLS` list:

**Option 1: Edit your .env file**
```bash
# Default configuration (from .env.example)
DISABLED_TOOLS=analyze,refactor,testgen,secaudit,docgen,tracer

# To enable specific tools, remove them from the list
# Example: Enable analyze tool
DISABLED_TOOLS=refactor,testgen,secaudit,docgen,tracer

# To enable ALL tools
DISABLED_TOOLS=
```

**Option 2: Configure in MCP settings**
```json
// In ~/.claude/settings.json or .mcp.json
{
  "mcpServers": {
    "zen": {
      "env": {
        // Enable analyze by removing it from disabled list
        "DISABLED_TOOLS": "refactor,testgen,secaudit,docgen,tracer"
      }
    }
  }
}
```

**Option 3: Enable all tools**
```json
// Remove or empty the DISABLED_TOOLS to enable everything
{
  "mcpServers": {
    "zen": {
      "env": {
        "DISABLED_TOOLS": ""
      }
    }
  }
}
```

**Note:** 
- Essential tools (`version`, `listmodels`) cannot be disabled
- After changing tool configuration, restart your Claude session for changes to take effect
- Each tool adds to context window usage, so only enable what you need

</details>

## Key Features

**AI Orchestration**
- **Auto model selection** - Claude picks the right AI for each task
- **Multi-model workflows** - Chain different models in single conversations
- **Conversation continuity** - Context preserved across tools and models
- **[Context revival](docs/context-revival.md)** - Continue conversations even after context resets

**Model Support**
- **Multiple providers** - Gemini, OpenAI, X.AI, OpenRouter, DIAL, Ollama
- **Latest models** - GPT-5, Gemini 2.5 Pro, O3, Grok-4, local Llama
- **[Thinking modes](docs/advanced-usage.md#thinking-modes)** - Control reasoning depth vs cost
- **Vision support** - Analyze images, diagrams, screenshots

**Developer Experience**
- **Guided workflows** - Systematic investigation prevents rushed analysis
- **Smart file handling** - Auto-expand directories, manage token limits
- **Web search integration** - Access current documentation and best practices
- **[Large prompt support](docs/advanced-usage.md#working-with-large-prompts)** - Bypass MCP's 25K token limit

## Example Workflows

**Multi-model Code Review:**
```
"Perform a codereview using gemini pro and o3, then use planner to create a fix strategy"
```
→ Claude reviews code systematically → Consults Gemini Pro → Gets O3's perspective → Creates unified action plan

**Collaborative Debugging:**
```
"Debug this race condition with max thinking mode, then validate the fix with precommit"
```
→ Deep investigation → Expert analysis → Solution implementation → Pre-commit validation

**Architecture Planning:**
```
"Plan our microservices migration, get consensus from pro and o3 on the approach"
```
→ Structured planning → Multiple expert opinions → Consensus building → Implementation roadmap

👉 **[Advanced Usage Guide](docs/advanced-usage.md)** for complex workflows, model configuration, and power-user features

## Quick Links

**📖 Documentation**
- [Getting Started](docs/getting-started.md) - Complete setup guide
- [Tools Reference](docs/tools/) - All tools with examples
- [Advanced Usage](docs/advanced-usage.md) - Power user features
- [Configuration](docs/configuration.md) - Environment variables, restrictions

**🔧 Setup & Support**
- [WSL Setup](docs/wsl-setup.md) - Windows users
- [Troubleshooting](docs/troubleshooting.md) - Common issues
- [Contributing](docs/contributions.md) - Code standards, PR process

## License

Apache 2.0 License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with the power of **Multi-Model AI** collaboration 🤝
- **A**ctual **I**ntelligence by real Humans
- [MCP (Model Context Protocol)](https://modelcontextprotocol.com) by Anthropic
- [Claude Code](https://claude.ai/code) - Your AI coding orchestrator
- [Gemini 2.5 Pro & Flash](https://ai.google.dev/) - Extended thinking & fast analysis
- [OpenAI O3 & GPT-5](https://openai.com/) - Strong reasoning & latest capabilities

### Star History

[![Star History Chart](https://api.star-history.com/svg?repos=BeehiveInnovations/zen-mcp-server&type=Date)](https://www.star-history.com/#BeehiveInnovations/zen-mcp-server&Date)
