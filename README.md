# Zen MCP: One Context. Many Minds.

https://github.com/user-attachments/assets/8097e18e-b926-4d8b-ba14-a979e4c58bda

<div align="center">  
  <b>🤖 Claude + [Gemini / O3 / GROK / OpenRouter / Ollama / Any Model] = Your Ultimate AI Development Team</b>
</div>

<br/>

The ultimate development partners for Claude - a Model Context Protocol server that gives Claude access to multiple AI models for enhanced code analysis, 
problem-solving, and collaborative development.

**Features true AI orchestration with conversations that continue across tasks** - Give Claude a complex
task and let it orchestrate between models automatically. Claude stays in control, performs the actual work, 
but gets perspectives from the best AI for each subtask. With tools like [`analyze`](#7-analyze---smart-file-analysis) for 
understanding codebases, [`codereview`](#4-codereview---professional-code-review) for audits, [`refactor`](#8-refactor---intelligent-code-refactoring) for 
improving code structure, [`debug`](#6-debug---expert-debugging-assistant) for solving complex problems, and [`precommit`](#5-precommit---pre-commit-validation) for 
validating changes, Claude can switch between different tools _and_ models mid-conversation, 
with context carrying forward seamlessly.

**Example Workflow - Claude Code:**
1. Performs its own reasoning
2. Uses Gemini Pro to deeply [`analyze`](#7-analyze---smart-file-analysis) the code in question for a second opinion
3. Switches to O3 to continue [`chatting`](#1-chat---general-development-chat--collaborative-thinking) about its findings 
4. Uses Flash to evaluate formatting suggestions from O3
5. Performs the actual work after taking in feedback from all three
6. Returns to Pro for a [`precommit`](#5-precommit---pre-commit-validation) review

All within a single conversation thread! Gemini Pro in step 6 _knows_ what was recommended by O3 in step 3! Taking that context
and review into consideration to aid with its pre-commit review.

**Think of it as Claude Code _for_ Claude Code.** This MCP isn't magic. It's just **super-glue**.

> **Remember:** Claude stays in full control — but **YOU** call the shots. 
> Zen is designed to have Claude engage other models only when needed — and to follow through with meaningful back-and-forth. 
> **You're** the one who crafts the powerful prompt that makes Claude bring in Gemini, Flash, O3 — or fly solo.  
> You're the guide. The prompter. The puppeteer. 
> ### You are the AI - **Actually Intelligent**.

## Quick Navigation

- **Getting Started**
  - [Quickstart](#quickstart-5-minutes) - Get running in 5 minutes with Docker
  - [Available Tools](#available-tools) - Overview of all tools
  - [AI-to-AI Conversations](#ai-to-ai-conversation-threading) - Multi-turn conversations

- **Tools Reference**
  - [`chat`](#1-chat---general-development-chat--collaborative-thinking) - Collaborative thinking
  - [`thinkdeep`](#2-thinkdeep---extended-reasoning-partner) - Extended reasoning
  - [`consensus`](#3-consensus---multi-model-perspective-gathering) - Multi-model consensus analysis
  - [`codereview`](#4-codereview---professional-code-review) - Code review
  - [`precommit`](#5-precommit---pre-commit-validation) - Pre-commit validation
  - [`debug`](#6-debug---expert-debugging-assistant) - Debugging help
  - [`analyze`](#7-analyze---smart-file-analysis) - File analysis
  - [`refactor`](#8-refactor---intelligent-code-refactoring) - Code refactoring with decomposition focus
  - [`tracer`](#9-tracer---static-code-analysis-prompt-generator) - Call-flow mapping and dependency tracing
  - [`testgen`](#10-testgen---comprehensive-test-generation) - Test generation with edge cases
  - [`your custom tool`](#add-your-own-tools) - Create custom tools for specialized workflows

- **Advanced Usage**
  - [Advanced Features](#advanced-features) - AI-to-AI conversations, large prompts, web search
  - [Complete Advanced Guide](docs/advanced-usage.md) - Model configuration, thinking modes, workflows, tool parameters

- **Setup & Support**
  - [Troubleshooting Guide](docs/troubleshooting.md) - Common issues and debugging steps
  - [License](#license) - Apache 2.0

## Why This Server?

Claude is brilliant, but sometimes you need:
- **Multiple AI perspectives** - Let Claude orchestrate between different models to get the best analysis
- **Automatic model selection** - Claude picks the right model for each task (or you can specify)
- **A senior developer partner** to validate and extend ideas ([`chat`](#1-chat---general-development-chat--collaborative-thinking))
- **A second opinion** on complex architectural decisions - augment Claude's thinking with perspectives from Gemini Pro, O3, or [dozens of other models via custom endpoints](docs/custom_models.md) ([`thinkdeep`](#2-thinkdeep---extended-reasoning-partner))
- **Get multiple expert opinions** - Have different AI models debate your ideas (some supporting, some critical) to help you make better decisions ([`consensus`](#3-consensus---multi-model-perspective-gathering))
- **Professional code reviews** with actionable feedback across entire repositories ([`codereview`](#4-codereview---professional-code-review))
- **Pre-commit validation** with deep analysis using the best model for the job ([`precommit`](#5-precommit---pre-commit-validation))
- **Expert debugging** - O3 for logical issues, Gemini for architectural problems ([`debug`](#6-debug---expert-debugging-assistant))
- **Extended context windows beyond Claude's limits** - Delegate analysis to Gemini (1M tokens) or O3 (200K tokens) for entire codebases, large datasets, or comprehensive documentation
- **Model-specific strengths** - Extended thinking with Gemini Pro, fast iteration with Flash, strong reasoning with O3, local privacy with Ollama
- **Local model support** - Run models like Llama 3.2 locally via Ollama, vLLM, or LM Studio for privacy and cost control
- **Dynamic collaboration** - Models can request additional context and follow-up replies from Claude mid-analysis
- **Smart file handling** - Automatically expands directories, manages token limits based on model capacity
- **Vision support** - Analyze images, diagrams, screenshots, and visual content with vision-capable models
- **[Bypass MCP's token limits](docs/advanced-usage.md#working-with-large-prompts)** - Work around MCP's 25K limit automatically
- **[Context revival across sessions](docs/context-revival.md)** - Continue conversations even after Claude's context resets, with other models maintaining full history

## Pro Tip: Context Revival

**This is an extremely powerful feature that cannot be highlighted enough**:

> The most amazing side-effect of this _conversation continuation_ system is that even AFTER Claude's context resets or
> compacts, since the continuation info is kept within MCP's memory, you can ask it to _continue_ discussing 
> the plan with `o3`, and it will suddenly revive Claude because O3 would know what was being talked about and 
> relay this back in a way that re-ignites Claude's understanding. All this without wasting context on asking Claude to
> ingest lengthy documents / code again and re-prompting it to communicate with another model. Zen manages that internally. The model's response
> revives Claude with better context around the discussion than an automatic summary ever can.   

**[📖 Read the complete technical deep-dive on how this revolutionary system works](docs/context-revival.md)**

This server orchestrates multiple AI models as your development team, with Claude automatically selecting the best model for each task or allowing you to choose specific models for different strengths.

<div align="center">
  <img src="https://github.com/user-attachments/assets/0f3c8e2d-a236-4068-a80e-46f37b0c9d35" width="600">
</div>

**Prompt Used:**
```
Study the code properly, think deeply about what this does and then see if there's any room for improvement in
terms of performance optimizations, brainstorm with gemini on this to get feedback and then confirm any change by
first adding a unit test with `measure` and measuring current code and then implementing the optimization and
measuring again to ensure it improved, then share results. Check with gemini in between as you make tweaks.
```

The final implementation resulted in a 26% improvement in JSON parsing performance for the selected library, reducing processing time through targeted, collaborative optimizations guided by Gemini’s analysis and Claude’s refinement.

## Quickstart (5 minutes)

### Prerequisites

- Docker Desktop installed ([Download here](https://www.docker.com/products/docker-desktop/))
- Git
- **Windows users**: WSL2 is required for Claude Code CLI

### 1. Get API Keys (at least one required)

**Option A: OpenRouter (Access multiple models with one API)**
- **OpenRouter**: Visit [OpenRouter](https://openrouter.ai/) for access to multiple models through one API. [Setup Guide](docs/custom_models.md)
  - Control model access and spending limits directly in your OpenRouter dashboard
  - Configure model aliases in [`conf/custom_models.json`](conf/custom_models.json)

**Option B: Native APIs**
- **Gemini**: Visit [Google AI Studio](https://makersuite.google.com/app/apikey) and generate an API key. For best results with Gemini 2.5 Pro, use a paid API key as the free tier has limited access to the latest models.
- **OpenAI**: Visit [OpenAI Platform](https://platform.openai.com/api-keys) to get an API key for O3 model access.
- **X.AI**: Visit [X.AI Console](https://console.x.ai/) to get an API key for GROK model access.

**Option C: Custom API Endpoints (Local models like Ollama, vLLM)**
[Please see the setup guide](docs/custom_models.md#option-2-custom-api-setup-ollama-vllm-etc). With a custom API you can use:
- **Ollama**: Run models like Llama 3.2 locally for free inference
- **vLLM**: Self-hosted inference server for high-throughput inference
- **LM Studio**: Local model hosting with OpenAI-compatible API interface
- **Text Generation WebUI**: Popular local interface for running models
- **Any OpenAI-compatible API**: Custom endpoints for your own infrastructure

> **Note:** Using all three options may create ambiguity about which provider / model to use if there is an overlap. 
> If all APIs are configured, native APIs will take priority when there is a clash in model name, such as for `gemini` and `o3`.
> Configure your model aliases and give them unique names in [`conf/custom_models.json`](conf/custom_models.json)

### 2. Clone and Set Up

```bash
# Clone to your preferred location
git clone https://github.com/BeehiveInnovations/zen-mcp-server.git
cd zen-mcp-server

# One-command setup (includes Redis for AI conversations)
./run-server.sh
```

**What this does:**
- **Builds Docker images** with all dependencies (including Redis for conversation threading)
- **Creates .env file** (automatically uses `$GEMINI_API_KEY` and `$OPENAI_API_KEY` if set in environment)
- **Starts Redis service** for AI-to-AI conversation memory
- **Starts MCP server** with providers based on available API keys
- **Adds Zen to Claude Code automatically**

### 3. Add Your API Keys

```bash
# Edit .env to add your API keys (if not already set in environment)
nano .env

# The file will contain, at least one should be set:
# GEMINI_API_KEY=your-gemini-api-key-here  # For Gemini models
# OPENAI_API_KEY=your-openai-api-key-here  # For O3 model
# OPENROUTER_API_KEY=your-openrouter-key  # For OpenRouter (see docs/custom_models.md)

# For local models (Ollama, vLLM, etc.) - Note: Use host.docker.internal for Docker networking:
# CUSTOM_API_URL=http://host.docker.internal:11434/v1  # Ollama example (NOT localhost!)
# CUSTOM_API_KEY=                                      # Empty for Ollama
# CUSTOM_MODEL_NAME=llama3.2                          # Default model

# WORKSPACE_ROOT=/Users/your-username  (automatically configured)

# Note: At least one API key OR custom URL is required

# After making changes to .env, restart the server:
# ./run-server.sh
```

**Restart MCP Server**: This step is important. You will need to `./run-server.sh` again for it to 
pick the changes made to `.env` otherwise the server will be unable to use your newly edited keys. Please also 
`./run-server.sh` any time in the future you modify the `.env` file. 

**Next**: Now run `claude` from your project folder using the terminal for it to connect to the newly added mcp server. 
If you were already running a `claude` code session, please exit and start a new session.

#### If Setting up for Claude Desktop

1. **Launch Claude Desktop**
- Open Claude Desktop
- Go to **Settings** → **Developer** → **Edit Config**

This will open a folder revealing `claude_desktop_config.json`.

2. **Update Docker Configuration**

The setup script shows you the exact configuration. It looks like this. When you ran `run-server.sh` it should
have produced a configuration for you to copy:

```json
{
  "mcpServers": {
    "zen": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "zen-mcp-server",
        "python",
        "server.py"
      ]
    }
  }
}
```

Paste the above into `claude_desktop_config.json`. If you have several other MCP servers listed, simply add this below the rest after a `,` comma:
```json
  ... other mcp servers ... ,

  "zen": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "zen-mcp-server",
        "python",
        "server.py"
      ]
  }
```

3. **Restart Claude Desktop**
Completely quit and restart Claude Desktop for the changes to take effect.

### 4. Start Using It!

Just ask Claude naturally:
- "Think deeper about this architecture design with zen" → Claude picks best model + `thinkdeep`
- "Using zen perform a code review of this code for security issues" → Claude might pick Gemini Pro + `codereview`
- "Use zen and debug why this test is failing, the bug might be in my_class.swift" → Claude might pick O3 + `debug`
- "With zen, analyze these files to understand the data flow" → Claude picks appropriate model + `analyze`
- "Use flash to suggest how to format this code based on the specs mentioned in policy.md" → Uses Gemini Flash specifically
- "Think deeply about this and get o3 to debug this logic error I found in the checkOrders() function" → Uses O3 specifically
- "Brainstorm scaling strategies with pro. Study the code, pick your preferred strategy and debate with pro to settle on two best approaches" → Uses Gemini Pro specifically
- "Use local-llama to localize and add missing translations to this project" → Uses local Llama 3.2 via custom URL
- "First use local-llama for a quick local analysis, then use opus for a thorough security review" → Uses both providers in sequence

## Available Tools

**Quick Tool Selection Guide:**
- **Need a thinking partner?** → `chat` (brainstorm ideas, get second opinions, validate approaches)
- **Need deeper thinking?** → `thinkdeep` (extends analysis, finds edge cases)
- **Need multiple perspectives?** → `consensus` (get diverse expert opinions on proposals and decisions)
- **Code needs review?** → `codereview` (bugs, security, performance issues)
- **Pre-commit validation?** → `precommit` (validate git changes before committing)
- **Something's broken?** → `debug` (root cause analysis, error tracing)
- **Want to understand code?** → `analyze` (architecture, patterns, dependencies)
- **Code needs refactoring?** → `refactor` (intelligent refactoring with decomposition focus)
- **Need call-flow analysis?** → `tracer` (generates prompts for execution tracing and dependency mapping)
- **Need comprehensive tests?** → `testgen` (generates test suites with edge cases)
- **Which models are available?** → `listmodels` (shows all configured providers and models)
- **Server info?** → `version` (version and configuration details)

**Auto Mode:** When `DEFAULT_MODEL=auto`, Claude automatically picks the best model for each task. You can override with: "Use flash for quick analysis" or "Use o3 to debug this".

**Model Selection Examples:**
- Complex architecture review → Claude picks Gemini Pro
- Quick formatting check → Claude picks Flash
- Logical debugging → Claude picks O3
- General explanations → Claude picks Flash for speed
- Local analysis → Claude picks your Ollama model

**Pro Tip:** Thinking modes (for Gemini models) control depth vs token cost. Use "minimal" or "low" for quick tasks, "high" or "max" for complex problems. [Learn more](docs/advanced-usage.md#thinking-modes)

**Tools Overview:**
1. [`chat`](docs/tools/chat.md) - Collaborative thinking and development conversations
2. [`thinkdeep`](docs/tools/thinkdeep.md) - Extended reasoning and problem-solving
3. [`consensus`](docs/tools/consensus.md) - Multi-model consensus analysis with stance steering
4. [`codereview`](docs/tools/codereview.md) - Professional code review with severity levels
5. [`precommit`](docs/tools/precommit.md) - Validate git changes before committing
6. [`debug`](docs/tools/debug.md) - Root cause analysis and debugging
7. [`analyze`](docs/tools/analyze.md) - General-purpose file and code analysis
8. [`refactor`](docs/tools/refactor.md) - Code refactoring with decomposition focus
9. [`tracer`](docs/tools/tracer.md) - Static code analysis prompt generator for call-flow mapping
10. [`testgen`](docs/tools/testgen.md) - Comprehensive test generation with edge case coverage
11. [`listmodels`](docs/tools/listmodels.md) - Display all available AI models organized by provider
12. [`version`](docs/tools/version.md) - Get server version and configuration

### 1. `chat` - General Development Chat & Collaborative Thinking
Your thinking partner for brainstorming, getting second opinions, and validating approaches. Perfect for technology comparisons, architecture discussions, and collaborative problem-solving.

```
Chat with zen about the best approach for user authentication in my React app
```

**[📖 Read More](docs/tools/chat.md)** - Detailed features, examples, and best practices

### 2. `thinkdeep` - Extended Reasoning Partner
Get a second opinion to augment Claude's own extended thinking. Uses specialized thinking models to challenge assumptions, identify edge cases, and provide alternative perspectives.

```
The button won't animate when clicked, it seems something else is intercepting the clicks. Use thinkdeep with gemini pro after gathering related code and handing it the files
and find out what the root cause is  
```

**[📖 Read More](docs/tools/thinkdeep.md)** - Enhanced analysis capabilities and critical evaluation process

### 3. `consensus` - Multi-Model Perspective Gathering
Get diverse expert opinions from multiple AI models on technical proposals and decisions. Supports stance steering (for/against/neutral) and structured decision-making.

```
Get a consensus with flash taking a supportive stance and gemini pro being critical to evaluate whether we should 
migrate from REST to GraphQL for our API. I need a definitive answer.
```

**[📖 Read More](docs/tools/consensus.md)** - Multi-model orchestration and decision analysis

### 4. `codereview` - Professional Code Review
Comprehensive code analysis with prioritized feedback and severity levels. Supports security reviews, performance analysis, and coding standards enforcement.

```
Perform a codereview with gemini pro especially the auth.py as I feel some of the code is bypassing security checks 
and there may be more potential vulnerabilities. Find and share related code."
```

**[📖 Read More](docs/tools/codereview.md)** - Professional review capabilities and parallel analysis

### 5. `precommit` - Pre-Commit Validation
Comprehensive review of staged/unstaged git changes across multiple repositories. Validates changes against requirements and detects potential regressions.

```
Perform a thorough precommit with o3, we want to only highlight critical issues, no blockers, no regressions. I need
100% confidence this covers all the edge cases listed in FIX_ISSUE_ABC.md
```

**[📖 Read More](docs/tools/precommit.md)** - Multi-repository validation and change analysis

### 6. `debug` - Expert Debugging Assistant
Root cause analysis for complex problems with systematic hypothesis generation. Supports error context, stack traces, and structured debugging approaches.

```
See logs under /Users/me/project/diagnostics.log and related code under the sync folder. Logs show that sync
works but sometimes it gets stuck and there are no errors displayed to the user. Using zen's debug tool with gemini pro, find out
why this is happening and what the root cause is and its fix 
```

**[📖 Read More](docs/tools/debug.md)** - Advanced debugging methodologies and troubleshooting

### 7. `analyze` - Smart File Analysis
General-purpose code understanding and exploration. Supports architecture analysis, pattern detection, and comprehensive codebase exploration.

```
Use gemini to analyze main.py to understand how it works
```

**[📖 Read More](docs/tools/analyze.md)** - Code analysis types and exploration capabilities

### 8. `refactor` - Intelligent Code Refactoring
Comprehensive refactoring analysis with top-down decomposition strategy. Prioritizes structural improvements and provides precise implementation guidance.

```
Use gemini pro to decompose my_crazy_big_class.m into smaller extensions
```

**[📖 Read More](docs/tools/refactor.md)** - Refactoring strategy and progressive analysis approach

### 9. `tracer` - Static Code Analysis Prompt Generator
Creates detailed analysis prompts for call-flow mapping and dependency tracing. Generates structured analysis requests for precision execution flow or dependency mapping.

```
Use zen tracer to analyze how UserAuthManager.authenticate is used and why
```

**[📖 Read More](docs/tools/tracer.md)** - Prompt generation and analysis modes

### 10. `testgen` - Comprehensive Test Generation
Generates thorough test suites with edge case coverage based on existing code and test framework. Uses multi-agent workflow for realistic failure mode analysis.

```
Use zen to generate tests for User.login() method
```

**[📖 Read More](docs/tools/testgen.md)** - Test generation strategy and framework support

### 11. `listmodels` - List Available Models
Display all available AI models organized by provider, showing capabilities, context windows, and configuration status.

```
Use zen to list available models
```

**[📖 Read More](docs/tools/listmodels.md)** - Model capabilities and configuration details

### 12. `version` - Server Information
Get server version, configuration details, and system status for debugging and troubleshooting.

```
What version of zen do I have
```

**[📖 Read More](docs/tools/version.md)** - Server diagnostics and configuration verification

For detailed tool parameters and configuration options, see the [Advanced Usage Guide](docs/advanced-usage.md).

### Prompt Support

Zen supports powerful structured prompts in Claude Code for quick access to tools and models:

#### Tool Prompts
- `/zen:chat ask local-llama what 2 + 2 is` - Use chat tool with auto-selected model
- `/zen:thinkdeep use o3 and tell me why the code isn't working in sorting.swift` - Use thinkdeep tool with auto-selected model
- `/zen:consensus use o3:for and flash:against and tell me if adding feature X is a good idea for the project. Pass them a summary of what it does.` - Use consensus tool with default configuration
- `/zen:codereview review for security module ABC` - Use codereview tool with auto-selected model
- `/zen:debug table view is not scrolling properly, very jittery, I suspect the code is in my_controller.m` - Use debug tool with auto-selected model
- `/zen:analyze examine these files and tell me what if I'm using the CoreAudio framework properly` - Use analyze tool with auto-selected model

#### Continuation Prompts
- `/zen:chat continue and ask gemini pro if framework B is better` - Continue previous conversation using chat tool

#### Advanced Examples
- `/zen:thinkdeeper check if the algorithm in @sort.py is performant and if there are alternatives we could explore`
- `/zen:consensus debate whether we should migrate to GraphQL for our API`
- `/zen:precommit confirm these changes match our requirements in COOL_FEATURE.md`
- `/zen:testgen write me tests for class ABC`
- `/zen:refactor propose a decomposition strategy, make a plan and save it in FIXES.md`

#### Syntax Format
The prompt format is: `/zen:[tool] [your_message]`

- `[tool]` - Any available tool name (chat, thinkdeep, codereview, debug, analyze, consensus, etc.)
- `[your_message]` - Your request, question, or instructions for the tool

**Note:** All prompts will show as "(MCP) [tool]" in Claude Code to indicate they're provided by the MCP server.

### Add Your Own Tools

**Want to create custom tools for your specific workflows?** 

The Zen MCP Server is designed to be extensible - you can easily add your own specialized
tools for domain-specific tasks, custom analysis workflows, or integration with your favorite 
services.

**[See Complete Tool Development Guide](docs/adding_tools.md)** - Step-by-step instructions for creating, testing, and integrating new tools

Your custom tools get the same benefits as built-in tools: multi-model support, conversation threading, token management, and automatic model selection.

## Advanced Features

### AI-to-AI Conversation Threading

This server enables **true AI collaboration** between Claude and multiple AI models, where they can coordinate and build on each other's insights across tools and conversations.

**[📖 Read More](docs/ai-collaboration.md)** - Multi-model coordination, conversation threading, and collaborative workflows


## Configuration

Configure the Zen MCP Server through environment variables in your `.env` file. Supports multiple AI providers, model restrictions, conversation settings, and advanced options.

```env
# Quick start - Auto mode (recommended)
DEFAULT_MODEL=auto
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
```

**Key Configuration Options:**
- **API Keys**: Native APIs (Gemini, OpenAI, X.AI), OpenRouter, or Custom endpoints (Ollama, vLLM)
- **Model Selection**: Auto mode or specific model defaults
- **Usage Restrictions**: Control which models can be used for cost control
- **Conversation Settings**: Timeout, turn limits, Redis configuration
- **Thinking Modes**: Token allocation for extended reasoning
- **Logging**: Debug levels and operational visibility

**[📖 Read More](docs/configuration.md)** - Complete configuration reference with examples

## Testing

For information on running tests, see the [Testing Guide](docs/testing.md).

## Contributing

We welcome contributions! Please see our comprehensive guides:
- [Contributing Guide](docs/contributions.md) - Code standards, PR process, and requirements
- [Adding a New Provider](docs/adding_providers.md) - Step-by-step guide for adding AI providers
- [Adding a New Tool](docs/adding_tools.md) - Step-by-step guide for creating new tools

## License

Apache 2.0 License - see LICENSE file for details.

## Acknowledgments

Built with the power of **Multi-Model AI** collaboration 🤝
- [MCP (Model Context Protocol)](https://modelcontextprotocol.com) by Anthropic
- [Claude Code](https://claude.ai/code) - Your AI coding assistant & orchestrator
- [Gemini 2.5 Pro & 2.0 Flash](https://ai.google.dev/) - Extended thinking & fast analysis
- [OpenAI O3](https://openai.com/) - Strong reasoning & general intelligence