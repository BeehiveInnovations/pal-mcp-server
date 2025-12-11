# PAL MCP: Many Workflows. One Context.

<div align="center">

  <em>Your AI's PAL – a Provider Abstraction Layer</em><br />
  <sub><a href="docs/name-change.md">Formerly known as Zen MCP</a></sub>

  [PAL in action](https://github.com/user-attachments/assets/0d26061e-5f21-4ab1-b7d0-f883ddc2c3da)

👉 **[Watch more examples](#-watch-tools-in-action)**

### Your CLI + Multiple Models = Your AI Dev Team

**Use the 🤖 CLI you love:**  
[Claude Code](https://www.anthropic.com/claude-code) · [Gemini CLI](https://github.com/google-gemini/gemini-cli) · [Codex CLI](https://github.com/openai/codex) · [Qwen Code CLI](https://qwenlm.github.io/qwen-code-docs/) · [Cursor](https://cursor.com) · _and more_

**With multiple models within a single prompt:**  
Gemini · OpenAI · Anthropic · Grok · Azure · Ollama · OpenRouter · DIAL · On-Device Model

</div>

---

## 🆕 Now with CLI-to-CLI Bridge

The new **[`clink`](docs/tools/clink.md)** (CLI + Link) tool connects external AI CLIs directly into your workflow:

- **Connect external CLIs** like [Gemini CLI](https://github.com/google-gemini/gemini-cli), [Codex CLI](https://github.com/openai/codex), and [Claude Code](https://www.anthropic.com/claude-code) directly into your workflow
- **CLI Subagents** - Launch isolated CLI instances from _within_ your current CLI! Claude Code can spawn Codex subagents, Codex can spawn Gemini CLI subagents, etc. Offload heavy tasks (code reviews, bug hunting) to fresh contexts while your main session's context window remains unpolluted. Each subagent returns only final results.
- **Context Isolation** - Run separate investigations without polluting your primary workspace
- **Role Specialization** - Spawn `planner`, `codereviewer`, or custom role agents with specialized system prompts
- **Full CLI Capabilities** - Web search, file inspection, MCP tool access, latest documentation lookups
- **Seamless Continuity** - Sub-CLIs participate as first-class members with full conversation context between tools

```bash
# Codex spawns Codex subagent for isolated code review in fresh context
clink with codex codereviewer to audit auth module for security issues
# Subagent reviews in isolation, returns final report without cluttering your context as codex reads each file and walks the directory structure

# Consensus from different AI models → Implementation handoff with full context preservation between tools
Use consensus with gpt-5 and gemini-pro to decide: dark mode or offline support next
Continue with clink gemini - implement the recommended feature
# Gemini receives full debate context and starts coding immediately
```

👉 **[Learn more about clink](docs/tools/clink.md)**

---

## Why PAL MCP?

**Why rely on one AI model when you can orchestrate them all?**

A Model Context Protocol server that supercharges tools like [Claude Code](https://www.anthropic.com/claude-code), [Codex CLI](https://developers.openai.com/codex/cli), and IDE clients such
as [Cursor](https://cursor.com) or the [Claude Dev VS Code extension](https://marketplace.visualstudio.com/items?itemName=Anthropic.claude-vscode). **PAL MCP connects your favorite AI tool
to multiple AI models** for enhanced code analysis, problem-solving, and collaborative development.

### True AI Collaboration with Conversation Continuity

PAL supports **conversation threading** so your CLI can **discuss ideas with multiple AI models, exchange reasoning, get second opinions, and even run collaborative debates between models** to help you reach deeper insights and better solutions.

Your CLI always stays in control but gets perspectives from the best AI for each subtask. Context carries forward seamlessly across tools and models, enabling complex workflows like: code reviews with multiple models → automated planning → implementation → pre-commit validation.

> **You're in control.** Your CLI of choice orchestrates the AI team, but you decide the workflow. Craft powerful prompts that bring in Gemini Pro, GPT 5, Flash, or local offline models exactly when needed.

<details>
<summary><b>Reasons to Use PAL MCP</b></summary>

A typical workflow with Claude Code as an example:

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
> PAL is designed to have Claude engage other models only when needed — and to follow through with meaningful back-and-forth.
> **You're** the one who crafts the powerful prompt that makes Claude bring in Gemini, Flash, O3 — or fly solo.
> You're the guide. The prompter. The puppeteer.
> #### You are the AI - **Actually Intelligent**.
</details>

#### Recommended AI Stack

<details>
<summary>For Claude Code Users</summary>

For best results when using [Claude Code](https://claude.ai/code):  

- **Sonnet 4.5** - All agentic work and orchestration
- **Gemini 3.0 Pro** OR **GPT-5.2 / Pro** - Deep thinking, additional code reviews, debugging and validations, pre-commit analysis
</details>

<details>
<summary>For Codex Users</summary>

For best results when using [Codex CLI](https://developers.openai.com/codex/cli):  

- **GPT-5.2 Codex Medium** - All agentic work and orchestration
- **Gemini 3.0 Pro** OR **GPT-5.2-Pro** - Deep thinking, additional code reviews, debugging and validations, pre-commit analysis
</details>

## Quick Start (5 minutes)

**Prerequisites:** Python 3.10+, Git, [uv installed](https://docs.astral.sh/uv/getting-started/installation/)

**1. Get API Keys** (choose one or more):
- **[OpenRouter](https://openrouter.ai/)** - Access multiple models with one API
- **[Gemini](https://makersuite.google.com/app/apikey)** - Google's latest models
- **[OpenAI](https://platform.openai.com/api-keys)** - O3, GPT-5 series
- **[Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/)** - Enterprise deployments of GPT-4o, GPT-4.1, GPT-5 family
- **[X.AI](https://console.x.ai/)** - Grok models
- **[DIAL](https://dialx.ai/)** - Vendor-agnostic model access
- **[Ollama](https://ollama.ai/)** - Local models (free)

**2. Install** (choose one):

**Option A: Clone and Automatic Setup** (recommended)
```bash
git clone https://github.com/BeehiveInnovations/pal-mcp-server.git
cd pal-mcp-server

# Handles everything: setup, config, API keys from system environment. 
# Auto-configures Claude Desktop, Claude Code, Gemini CLI, Codex CLI, Qwen CLI
# Enable / disable additional settings in .env
./run-server.sh  
```

**Option B: Instant Setup with [uvx](https://docs.astral.sh/uv/getting-started/installation/)**
```json
// Add to ~/.claude/settings.json or .mcp.json
// Don't forget to add your API keys under env
{
  "mcpServers": {
    "pal": {
      "command": "bash",
      "args": ["-c", "for p in $(which uvx 2>/dev/null) $HOME/.local/bin/uvx /opt/homebrew/bin/uvx /usr/local/bin/uvx uvx; do [ -x \"$p\" ] && exec \"$p\" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server; done; echo 'uvx not found' >&2; exit 1"],
      "env": {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:~/.local/bin",
        "GEMINI_API_KEY": "your-key-here",
        "DISABLED_TOOLS": "analyze,refactor,testgen,secaudit,docgen,tracer",
        "DEFAULT_MODEL": "auto"
      }
    }
  }
}
```

**3. Start Using!**
```
"Use pal to analyze this code for security issues with gemini pro"
"Debug this error with o3 and then get flash to suggest optimizations"
"Plan the migration strategy with pal, get consensus from multiple models"
"clink with cli_name=\"gemini\" role=\"planner\" to draft a phased rollout plan"
```

👉 **[Complete Setup Guide](docs/getting-started.md)** with detailed installation, configuration for Gemini / Codex / Qwen, and troubleshooting
👉 **[Cursor & VS Code Setup](docs/getting-started.md#ide-clients)** for IDE integration instructions
📺 **[Watch tools in action](#-watch-tools-in-action)** to see real-world examples

## Provider Configuration

PAL activates any provider that has credentials in your `.env`. See `.env.example` for deeper customization.

## Core Tools

> **Note:** Each tool comes with its own multi-step workflow, parameters, and descriptions that consume valuable context window space even when not in use. To optimize performance, some tools are disabled by default. See [Tool Configuration](#tool-configuration) below to enable them.

**Collaboration & Planning** *(Enabled by default)*
- **[`clink`](docs/tools/clink.md)** - Bridge requests to external AI CLIs (Gemini planner, codereviewer, etc.)
- **[`chat`](docs/tools/chat.md)** - Brainstorm ideas, get second opinions, validate approaches. With capable models (GPT-5.2 Pro, Gemini 3.0 Pro), generates complete code / implementation
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
- **[`apilookup`](docs/tools/apilookup.md)** - Forces current-year API/SDK documentation lookups in a sub-process (saves tokens within the current context window), prevents outdated training data responses
- **[`challenge`](docs/tools/challenge.md)** - Prevent "You're absolutely right!" responses with critical analysis
- **[`tracer`](docs/tools/tracer.md)** *(disabled by default - [enable](#tool-configuration))* - Static analysis prompts for call-flow mapping

<details>
<summary><b id="tool-configuration">👉 Tool Configuration</b></summary>

### Default Configuration

To optimize context window usage, only essential tools are enabled by default:

**Enabled by default:**
- `chat`, `thinkdeep`, `planner`, `consensus` - Core collaboration tools
- `codereview`, `precommit`, `debug` - Essential code quality tools
- `apilookup` - Rapid API/SDK information lookup
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
    "pal": {
      "env": {
        // Tool configuration
        "DISABLED_TOOLS": "refactor,testgen,secaudit,docgen,tracer",
        "DEFAULT_MODEL": "pro",
        "DEFAULT_THINKING_MODE_THINKDEEP": "high",
        
        // API configuration
        "GEMINI_API_KEY": "your-gemini-key",
        "OPENAI_API_KEY": "your-openai-key",
        "OPENROUTER_API_KEY": "your-openrouter-key",
        
        // Logging and performance
        "LOG_LEVEL": "INFO",
        "CONVERSATION_TIMEOUT_HOURS": "6",
        "MAX_CONVERSATION_TURNS": "50"
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
    "pal": {
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

## 📺 Watch Tools In Action

<details>
<summary><b>Chat Tool</b> - Collaborative decision making and multi-turn conversations</summary>

**Picking Redis vs Memcached:**

[Chat Redis or Memcached_web.webm](https://github.com/user-attachments/assets/41076cfe-dd49-4dfc-82f5-d7461b34705d)

**Multi-turn conversation with continuation:**

[Chat With Gemini_web.webm](https://github.com/user-attachments/assets/37bd57ca-e8a6-42f7-b5fb-11de271e95db)

</details>

<details>
<summary><b>Consensus Tool</b> - Multi-model debate and decision making</summary>

**Multi-model consensus debate:**

[PAL Consensus Debate](https://github.com/user-attachments/assets/76a23dd5-887a-4382-9cf0-642f5cf6219e)

</details>

<details>
<summary><b>PreCommit Tool</b> - Comprehensive change validation</summary>

**Pre-commit validation workflow:**

<div align="center">
  <img src="https://github.com/user-attachments/assets/584adfa6-d252-49b4-b5b0-0cd6e97fb2c6" width="950">
</div>

</details>

<details>
<summary><b>API Lookup Tool</b> - Current vs outdated API documentation</summary>

**Without PAL - outdated APIs:**

[API without PAL](https://github.com/user-attachments/assets/01a79dc9-ad16-4264-9ce1-76a56c3580ee)

**With PAL - current APIs:**

[API with PAL](https://github.com/user-attachments/assets/5c847326-4b66-41f7-8f30-f380453dce22)

</details>

<details>
<summary><b>Challenge Tool</b> - Critical thinking vs reflexive agreement</summary>

**Without PAL:**

![without_pal@2x](https://github.com/user-attachments/assets/64f3c9fb-7ca9-4876-b687-25e847edfd87)

**With PAL:**

![with_pal@2x](https://github.com/user-attachments/assets/9d72f444-ba53-4ab1-83e5-250062c6ee70)

</details>

## Key Features

**AI Orchestration**
- **Auto model selection** - Claude picks the right AI for each task
- **Multi-model workflows** - Chain different models in single conversations
- **Conversation continuity** - Context preserved across tools and models
- **[Context revival](docs/context-revival.md)** - Continue conversations even after context resets

**Model Support**
- **Multiple providers** - Gemini, OpenAI, Azure, X.AI, OpenRouter, DIAL, Ollama
- **Latest models** - GPT-5, Gemini 3.0 Pro, O3, Grok-4, local Llama
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
- [Docs Overview](docs/index.md) - High-level map of major guides
- [Getting Started](docs/getting-started.md) - Complete setup guide
- [Tools Reference](docs/tools/) - All tools with examples
- [Advanced Usage](docs/advanced-usage.md) - Power user features
- [Configuration](docs/configuration.md) - Environment variables, restrictions
- [Adding Providers](docs/adding_providers.md) - Provider-specific setup (OpenAI, Azure, custom gateways)
- [Model Ranking Guide](docs/model_ranking.md) - How intelligence scores drive auto-mode suggestions

**🔧 Setup & Support**
- [WSL Setup](docs/wsl-setup.md) - Windows users
- [Troubleshooting](docs/troubleshooting.md) - Common issues
- [Contributing](docs/contributions.md) - Code standards, PR process

## License

Apache 2.0 License - see [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with the power of **Multi-Model AI** collaboration 🤝
- **A**ctual **I**ntelligence by real Humans
- [MCP (Model Context Protocol)](https://modelcontextprotocol.com)
- [Codex CLI](https://developers.openai.com/codex/cli)
- [Claude Code](https://claude.ai/code)
- [Gemini](https://ai.google.dev/)
- [OpenAI](https://openai.com/)
- [Azure OpenAI](https://learn.microsoft.com/azure/ai-services/openai/)

### Star History

[![Star History Chart](https://api.star-history.com/svg?repos=BeehiveInnovations/pal-mcp-server&type=Date)](https://www.star-history.com/#BeehiveInnovations/pal-mcp-server&Date)
