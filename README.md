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
1. [`chat`](#1-chat---general-development-chat--collaborative-thinking) - Collaborative thinking and development conversations
2. [`thinkdeep`](#2-thinkdeep---extended-reasoning-partner) - Extended reasoning and problem-solving
3. [`consensus`](#3-consensus---multi-model-perspective-gathering) - Multi-model consensus analysis with stance steering
4. [`codereview`](#4-codereview---professional-code-review) - Professional code review with severity levels
5. [`precommit`](#5-precommit---pre-commit-validation) - Validate git changes before committing
6. [`debug`](#6-debug---expert-debugging-assistant) - Root cause analysis and debugging
7. [`analyze`](#7-analyze---smart-file-analysis) - General-purpose file and code analysis
8. [`refactor`](#8-refactor---intelligent-code-refactoring) - Code refactoring with decomposition focus
9. [`tracer`](#9-tracer---static-code-analysis-prompt-generator) - Static code analysis prompt generator for call-flow mapping
10. [`testgen`](#10-testgen---comprehensive-test-generation) - Comprehensive test generation with edge case coverage
11. [`listmodels`](#11-listmodels---list-available-models) - Display all available AI models organized by provider
12. [`version`](#12-version---server-information) - Get server version and configuration

### 1. `chat` - General Development Chat & Collaborative Thinking
**Your thinking partner - bounce ideas, get second opinions, brainstorm collaboratively**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `low` for quick questions to save tokens, or `high` for complex discussions when thoroughness matters.

#### Example Prompt:

```
Chat with zen and pick the best model for this job. I need to pick between Redis and Memcached for session storage 
and I need an expert opinion for the project I'm working on. Get a good idea of what the project does, pick one of the two options
and then debate with the other models to give me a final verdict
```


**Key Features:**
- Collaborative thinking partner for your analysis and planning
- Get second opinions on your designs and approaches
- Brainstorm solutions and explore alternatives together
- Validate your checklists and implementation plans
- General development questions and explanations
- Technology comparisons and best practices
- Architecture and design discussions
- Can reference files for context: `"Use gemini to explain this algorithm with context from algorithm.py"`
- **Image support**: Include screenshots, diagrams, UI mockups for visual analysis: `"Chat with gemini about this error dialog screenshot to understand the user experience issue"`
- **Dynamic collaboration**: Gemini can request additional files or context during the conversation if needed for a more thorough response
- **Web search capability**: Analyzes when web searches would be helpful and recommends specific searches for Claude to perform, ensuring access to current documentation and best practices

### 2. `thinkdeep` - Extended Reasoning Partner

**Get a second opinion to augment Claude's own extended thinking**

**Thinking Mode:** Default is `high` (16,384 tokens) for deep analysis. Claude will automatically choose the best mode based on complexity - use `low` for quick validations, `medium` for standard problems, `high` for complex issues (default), or `max` for extremely complex challenges requiring deepest analysis.

#### Example Prompt:

```
Think deeper about my authentication design with pro using max thinking mode and brainstorm to come up 
with the best architecture for my project
```

**Key Features:**
- **Uses Gemini's specialized thinking models** for enhanced reasoning capabilities
- Provides a second opinion on Claude's analysis
- Challenges assumptions and identifies edge cases Claude might miss
- Offers alternative perspectives and approaches
- Validates architectural decisions and design patterns
- Can reference specific files for context: `"Use gemini to think deeper about my API design with reference to api/routes.py"`
- **Image support**: Analyze architectural diagrams, flowcharts, design mockups: `"Think deeper about this system architecture diagram with gemini pro using max thinking mode"`
- **Enhanced Critical Evaluation (v2.10.0)**: After Gemini's analysis, Claude is prompted to critically evaluate the suggestions, consider context and constraints, identify risks, and synthesize a final recommendation - ensuring a balanced, well-considered solution
- **Web search capability**: When enabled (default: true), identifies areas where current documentation or community solutions would strengthen the analysis and suggests specific searches for Claude

### 3. `consensus` - Multi-Model Perspective Gathering
**Get diverse expert opinions from multiple AI models on technical proposals and decisions**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` for complex architectural decisions or `max` for critical strategic choices requiring comprehensive analysis.

**Model Recommendation:** Consensus tool uses extended reasoning models by default, making it ideal for complex decision-making scenarios that benefit from multiple perspectives and deep analysis.

#### How It Works:
The consensus tool orchestrates multiple AI models to provide diverse perspectives on your proposals:
1. **Assign stances**: Each model can take a specific viewpoint (supportive, critical, or neutral)
2. **Gather opinions**: Models analyze your proposal from their assigned perspective with built-in common-sense guardrails
3. **Synthesize results**: Claude combines all perspectives into a balanced recommendation
4. **Natural language**: Use simple descriptions like "supportive", "critical", or "against" - the tool handles synonyms automatically

#### Example Prompts:

**For/Against Analysis:**
```
Use zen consensus with flash taking a supportive stance and pro being critical to evaluate whether 
we should migrate from REST to GraphQL for our API
```

**Multi-Model Technical Decision:**
```
Get consensus from o3, flash, and pro on our new authentication architecture. Have o3 focus on 
security implications, flash on implementation speed, and pro stay neutral for overall assessment
```

**Natural Language Stance Assignment:**
```
Use consensus tool with gemini being "for" the proposal and grok being "against" to debate 
whether we should adopt microservices architecture
```

**Key Features:**
- **Stance steering**: Assign specific perspectives (for/against/neutral) to each model with intelligent synonym handling
- **Custom stance prompts**: Provide specific instructions for how each model should approach the analysis
- **Ethical guardrails**: Models will refuse to support truly bad ideas regardless of assigned stance
- **Unknown stance handling**: Invalid stances automatically default to neutral with warning
- **Natural language support**: Use terms like "supportive", "critical", "oppose", "favor" - all handled intelligently
- **Sequential processing**: Reliable execution avoiding MCP protocol issues
- **Focus areas**: Specify particular aspects to emphasize (e.g., 'security', 'performance', 'user experience')
- **File context support**: Include relevant files for informed decision-making
- **Image support**: Analyze architectural diagrams, UI mockups, or design documents
- **Conversation continuation**: Build on previous consensus analysis with additional rounds
- **Web search capability**: Enhanced analysis with current best practices and documentation

**Parameters:**
- `prompt`: Detailed description of the proposal or decision to analyze
- `models`: List of model configurations with optional stance and custom instructions
- `files`: Context files for informed analysis (absolute paths)
- `images`: Visual references like diagrams or mockups
- `focus_areas`: Specific aspects to emphasize
- `temperature`: Control consistency (default: 0.2 for stable consensus)
- `thinking_mode`: Analysis depth (minimal/low/medium/high/max)
- `use_websearch`: Enable research for enhanced analysis (default: true)
- `continuation_id`: Continue previous consensus discussions

**Example Natural Language Model Specifications:**
```json
[
  {"model": "o3", "stance": "for", "stance_prompt": "Focus on technical benefits and implementation feasibility"},
  {"model": "flash", "stance": "against", "stance_prompt": "Identify risks, costs, and potential downsides"}, 
  {"model": "pro", "stance": "neutral"}
]
```

**Or simply use natural language:**
```
"Have gemini support the idea, grok oppose it, and flash stay neutral"
```

### 4. `codereview` - Professional Code Review  
**Comprehensive code analysis with prioritized feedback**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` for security-critical code (worth the extra tokens) or `low` for quick style checks (saves ~6k tokens).

**Model Recommendation:** This tool particularly benefits from Gemini Pro or Flash models due to their 1M context window, 
which allows comprehensive analysis of large codebases. Claude's context limitations make it challenging to see the
"big picture" in complex projects - this is a concrete example where utilizing a secondary model with larger context 
provides significant value beyond just experimenting with different AI capabilities.

#### Example Prompts:

```
Perform a codereview with gemini pro and review auth.py for security issues and potential vulnerabilities.
I need an actionable plan but break it down into smaller quick-wins that we can implement and test rapidly 
```

### Pro Tip

**You can start more than _one_ codereview sessions with Claude**:

```
Start separate sub-tasks for codereview one with o3 finding critical issues and one with flash finding low priority issues
and quick-wins and give me the final single combined review highlighting only the critical issues 
```

The above prompt will simultaneously run two separate `codereview` tools with two separate models and combine the output
into a single summary for you to consume.

**Key Features:**
- Issues prioritized by severity (🔴 CRITICAL → 🟢 LOW)
- Supports specialized reviews: security, performance, quick
- Can enforce coding standards: `"Use gemini to review src/ against PEP8 standards"`
- Filters by severity: `"Get gemini to review auth/ - only report critical vulnerabilities"`
- **Image support**: Review code from screenshots, error dialogs, or visual bug reports: `"Review this error screenshot and the related auth.py file for potential security issues"`

### 5. `precommit` - Pre-Commit Validation
**Comprehensive review of staged/unstaged git changes across multiple repositories**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` or `max` for critical releases when thorough validation justifies the token cost.

**Model Recommendation:** Pre-commit validation benefits significantly from models with
extended context windows like Gemini Pro, which can analyze extensive changesets across 
multiple files and repositories simultaneously. This comprehensive view enables detection of
cross-file dependencies, architectural inconsistencies, and integration issues that might be
missed when reviewing changes in isolation due to context constraints.

<div align="center">
  <img src="https://github.com/user-attachments/assets/584adfa6-d252-49b4-b5b0-0cd6e97fb2c6" width="950">
</div>

**Prompt Used:**
```
Now use gemini and perform a review and precommit and ensure original requirements are met, no duplication of code or
logic, everything should work as expected
```

How beautiful is that? Claude used `precommit` twice and `codereview` once and actually found and fixed two critical errors before commit!

#### Example Prompts:

```
Use zen and perform a thorough precommit ensuring there aren't any new regressions or bugs introduced
```

**Key Features:**
- **Recursive repository discovery** - finds all git repos including nested ones
- **Validates changes against requirements** - ensures implementation matches intent
- **Detects incomplete changes** - finds added functions never called, missing tests, etc.
- **Multi-repo support** - reviews changes across multiple repositories in one go
- **Configurable scope** - review staged, unstaged, or compare against branches
- **Security focused** - catches exposed secrets, vulnerabilities in new code
- **Smart truncation** - handles large diffs without exceeding context limits

**Parameters:**
- `path`: Starting directory to search for repos (default: current directory)
- `original_request`: The requirements for context
- `compare_to`: Compare against a branch/tag instead of local changes
- `review_type`: full|security|performance|quick
- `severity_filter`: Filter by issue severity
- `max_depth`: How deep to search for nested repos
- `images`: Screenshots of requirements, design mockups, or error states for validation context
### 6. `debug` - Expert Debugging Assistant
**Root cause analysis for complex problems**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` for tricky bugs (investment in finding root cause) or `low` for simple errors (save tokens).

#### Example Prompts:

**Basic Usage:**
```
"Use gemini to debug this TypeError: 'NoneType' object has no attribute 'split'"
"Get gemini to debug why my API returns 500 errors with the full stack trace: [paste traceback]"
```

**Key Features:**
- Generates multiple ranked hypotheses for systematic debugging
- Accepts error context, stack traces, and logs
- Can reference relevant files for investigation
- Supports runtime info and previous attempts
- Provides structured root cause analysis with validation steps
- Can request additional context when needed for thorough analysis
- **Image support**: Include error screenshots, stack traces, console output: `"Debug this error using gemini with the stack trace screenshot and the failing test.py"`
- **Web search capability**: When enabled (default: true), identifies when searching for error messages, known issues, or documentation would help solve the problem and recommends specific searches for Claude
### 7. `analyze` - Smart File Analysis
**General-purpose code understanding and exploration**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` for architecture analysis (comprehensive insights worth the cost) or `low` for quick file overviews (save ~6k tokens).

#### Example Prompts:

**Basic Usage:**
```
"Use gemini to analyze main.py to understand how it works"
"Get gemini to do an architecture analysis of the src/ directory"
```

**Key Features:**
- Analyzes single files or entire directories
- Supports specialized analysis types: architecture, performance, security, quality
- Uses file paths (not content) for clean terminal output
- Can identify patterns, anti-patterns, and refactoring opportunities
- **Image support**: Analyze architecture diagrams, UML charts, flowcharts: `"Analyze this system diagram with gemini to understand the data flow and identify bottlenecks"`
- **Web search capability**: When enabled with `use_websearch` (default: true), the model can request Claude to perform web searches and share results back to enhance analysis with current documentation, design patterns, and best practices

### 8. `refactor` - Intelligent Code Refactoring
**Comprehensive refactoring analysis with top-down decomposition strategy**

**Thinking Mode:** Default is `medium` (8,192 tokens). Use `high` for complex legacy systems (worth the investment for thorough refactoring plans) or `max` for extremely complex codebases requiring deep analysis.

**Model Recommendation:** The refactor tool excels with models that have large context windows like Gemini
Pro (1M tokens), which can analyze entire files and complex codebases simultaneously. 
This comprehensive view enables detection of cross-file dependencies, architectural patterns, 
and refactoring opportunities that might be missed when reviewing code in smaller chunks due to context
constraints.

#### Example Prompts:

```
"Use gemini pro to decompose my_crazy_big_class.m into smaller extensions"
"Using zen's refactor decompose the all_in_one_sync_code.swift into maintainable extensions"
```

💡Example of a **powerful prompt** to get the best out of both Claude + Flash's 1M Context: 
```
"First, think about how the authentication module works, find related classes and find
 any code smells, then using zen's refactor ask flash to confirm your findings but ask 
 it to find additional code smells and any other quick-wins and then fix these issues"
```

This results in Claude first performing its own expert analysis, encouraging it to think critically
and identify links within the project code. It then prompts `flash` to review the same code with a
hint—preventing it from duplicating Claude's findings and encouraging it to explore other areas that Claude
did *not* discover.

**Key Features:**
- **Intelligent prioritization** - Will refuse to work on low priority issues if code is unwieldy large and requires decomposition first, helps identify poorly managed classes and files that need structural improvements before detail work
- **Top-down decomposition strategy** - Analyzes file → class → function levels systematically
- **Four refactor types**: `codesmells` (detect anti-patterns), `decompose` (break down large components), `modernize` (update language features), `organization` (improve structure)
- **Precise line-number references** - Provides exact line numbers for Claude to implement changes
- **Language-specific guidance** - Tailored suggestions for Python, JavaScript, Java, C#, Swift, and more
- **Style guide integration** - Uses existing project files as pattern references
- **Conservative approach** - Careful dependency analysis to prevent breaking changes
- **Multi-file analysis** - Understands cross-file relationships and dependencies
- **Priority sequencing** - Recommends implementation order for refactoring changes
- **Image support**: Analyze code architecture diagrams, legacy system charts: `"Refactor this legacy module using gemini pro with the current architecture diagram"`

**Refactor Types (Progressive Priority System):**

**1. `decompose` (CRITICAL PRIORITY)** - Context-aware decomposition with adaptive thresholds:
- **AUTOMATIC decomposition** (CRITICAL severity - blocks all other refactoring):
  - Files >15,000 LOC, Classes >3,000 LOC, Functions >500 LOC
- **EVALUATE decomposition** (contextual severity - intelligent assessment):
  - Files >5,000 LOC, Classes >1,000 LOC, Functions >150 LOC
  - Only recommends if genuinely improves maintainability
  - Respects legacy stability, domain complexity, performance constraints
  - Considers legitimate cases where size is justified (algorithms, state machines, generated code)

**2. `codesmells`** - Applied only after decomposition is complete:
- Detect long methods, complex conditionals, duplicate code, magic numbers, poor naming

**3. `modernize`** - Applied only after decomposition is complete:
- Update to modern language features (f-strings, async/await, etc.)

**4. `organization`** - Applied only after decomposition is complete:
- Improve logical grouping, separation of concerns, module structure

**Progressive Analysis:** The tool performs a top-down check (worse → bad → better) and refuses to work on lower-priority issues if critical decomposition is needed first. It understands that massive files and classes create cognitive overload that must be addressed before detail work can be effective. Legacy code that cannot be safely decomposed is handled with higher tolerance thresholds and context-sensitive exemptions.

### 9. `tracer` - Static Code Analysis Prompt Generator
**Creates detailed analysis prompts for call-flow mapping and dependency tracing**

This is a specialized prompt-generation tool that creates structured analysis requests for Claude to perform comprehensive static code analysis. 
Rather than passing entire projects to another model, this tool generates focused prompts that 
Claude can use to efficiently trace execution flows and map dependencies within the codebase.

**Two Analysis Modes:**
- **`precision`**: For methods/functions - traces execution flow, call chains, and usage patterns with detailed branching analysis and side effects
- **`dependencies`**: For classes/modules/protocols - maps bidirectional dependencies and structural relationships

**Key Features:**
- Generates comprehensive analysis prompts instead of performing analysis directly
- Faster and more efficient than full project analysis by external models
- Creates structured instructions for call-flow graph generation
- Provides detailed formatting requirements for consistent output
- Supports any programming language with automatic convention detection
- Output can be used as an input into another tool, such as `chat` along with related code files to perform a logical call-flow analysis
- **Image support**: Analyze visual call flow diagrams, sequence diagrams: `"Generate tracer analysis for this payment flow using the sequence diagram"` 

#### Example Prompts:
```
"Use zen tracer to analyze how UserAuthManager.authenticate is used and why" -> uses `precision` mode 
"Use zen to generate a dependency trace for the PaymentProcessor class to understand its relationships" -> uses `dependencies` mode
```

### 10. `testgen` - Comprehensive Test Generation
**Generates thorough test suites with edge case coverage** based on existing code and test framework used.

**Thinking Mode (Extended thinking models):** Default is `medium` (8,192 tokens). Use `high` for complex systems with many interactions or `max` for critical systems requiring exhaustive test coverage.

**Model Recommendation:** Test generation excels with extended reasoning models like Gemini Pro or O3, 
which can analyze complex code paths, understand intricate dependencies, and identify comprehensive edge
cases. The combination of large context windows and advanced reasoning enables generation of thorough test
suites that cover realistic failure scenarios and integration points that shorter-context models might overlook.

#### Example Prompts:

**Basic Usage:**
```
"Use zen to generate tests for User.login() method"
"Generate comprehensive tests for the sorting method in src/new_sort.py using o3"
"Create tests for edge cases not already covered in our tests using gemini pro"
```

**Key Features:**
- Multi-agent workflow analyzing code paths and identifying realistic failure modes
- Generates framework-specific tests following project conventions
- Supports test pattern following when examples are provided
- Dynamic token allocation (25% for test examples, 75% for main code)
- Prioritizes smallest test files for pattern detection
- Can reference existing test files: `"Generate tests following patterns from tests/unit/"`
- Specific code coverage - target specific functions/classes rather than testing everything
- **Image support**: Test UI components, analyze visual requirements: `"Generate tests for this login form using the UI mockup screenshot"`

### 11. `listmodels` - List Available Models
```
"Use zen to list available models"
```
Shows all configured providers, available models with aliases, and context windows.

### 12. `version` - Server Information
```
"Get zen to show its version"
```

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

This server enables **true AI collaboration** between Claude and multiple AI models (Gemini, O3), where they can coordinate and question each other's approaches:

**How it works:**
- **Gemini can ask Claude follow-up questions** to clarify requirements or gather more context
- **Claude can respond** with additional information, files, or refined instructions
- **Claude can work independently** between exchanges - implementing solutions, gathering data, or performing analysis
- **Claude can return to Gemini** with progress updates and new context for further collaboration
- **Cross-tool continuation** - Start with one tool (e.g., `analyze`) and continue with another (e.g., `codereview`) using the same conversation thread
- **Both AIs coordinate their approaches** - questioning assumptions, validating solutions, and building on each other's insights
- Each conversation maintains full context while only sending incremental updates
- Conversations are automatically managed with Redis for persistence

**Example of Multi-Model AI Coordination:**
1. You: "Debate SwiftUI vs UIKit - which is better for iOS development?"
2. Claude (auto mode): "I'll orchestrate a debate between different models for diverse perspectives."
3. Gemini Pro: "From an architectural standpoint, SwiftUI's declarative paradigm and state management make it superior for maintainable, modern apps."
4. O3: "Logically analyzing the trade-offs: UIKit offers 15+ years of stability, complete control, and proven scalability. SwiftUI has <5 years maturity with ongoing breaking changes."
5. Claude: "Let me get Flash's quick take on developer experience..."
6. Gemini Flash: "SwiftUI = faster development, less code, better previews. UIKit = more control, better debugging, stable APIs."
7. **Claude's synthesis**: "Based on the multi-model analysis: Use SwiftUI for new projects prioritizing development speed, UIKit for apps requiring fine control or supporting older iOS versions."

**Asynchronous workflow example:**
- Claude can work independently between exchanges (analyzing code, implementing fixes, gathering data)
- Return to Gemini with progress updates and additional context  
- Each exchange shares only incremental information while maintaining full conversation history
- Automatically bypasses MCP's 25K token limits through incremental updates

**Enhanced collaboration features:**
- **Cross-questioning**: AIs can challenge each other's assumptions and approaches
- **Coordinated problem-solving**: Each AI contributes their strengths to complex problems
- **Context building**: Claude gathers information while Gemini provides deep analysis
- **Approach validation**: AIs can verify and improve each other's solutions
- **Cross-tool continuation**: Seamlessly continue conversations across different tools while preserving all context
- **Asynchronous workflow**: Conversations don't need to be sequential - Claude can work on tasks between exchanges, then return to Gemini with additional context and progress updates
- **Incremental updates**: Share only new information in each exchange while maintaining full conversation history
- **Automatic 25K limit bypass**: Each exchange sends only incremental context, allowing unlimited total conversation size
- Up to 10 exchanges per conversation (configurable via `MAX_CONVERSATION_TURNS`) with 3-hour expiry (configurable via `CONVERSATION_TIMEOUT_HOURS`)
- Thread-safe with Redis persistence across all tools
- **Image context preservation** - Images and visual references are maintained across conversation turns and tool switches

**Cross-tool & Cross-Model Continuation Example:**
```
1. Claude: "Analyze /src/auth.py for security issues"
   → Auto mode: Claude picks Gemini Pro for deep security analysis
   → Pro analyzes and finds vulnerabilities, provides continuation_id

2. Claude: "Review the authentication logic thoroughly"
   → Uses same continuation_id, but Claude picks O3 for logical analysis
   → O3 sees previous Pro analysis and provides logic-focused review

3. Claude: "Debug the auth test failures"
   → Same continuation_id, Claude keeps O3 for debugging
   → O3 provides targeted debugging with full context from both previous analyses

4. Claude: "Quick style check before committing"
   → Same thread, but Claude switches to Flash for speed
   → Flash quickly validates formatting with awareness of all previous fixes
```

For more advanced features like working with large prompts and dynamic context requests, see the [Advanced Usage Guide](docs/advanced-usage.md).


## Configuration

**Auto Mode (Recommended):** Set `DEFAULT_MODEL=auto` in your .env file and Claude will intelligently select the best model for each task.

```env
# .env file
DEFAULT_MODEL=auto  # Claude picks the best model automatically

# API Keys (at least one required)
GEMINI_API_KEY=your-gemini-key    # Enables Gemini Pro & Flash
OPENAI_API_KEY=your-openai-key    # Enables O3, O3mini, O4-mini, O4-mini-high, GPT-4.1
```

**Available Models:**
- **`pro`** (Gemini 2.5 Pro): Extended thinking, deep analysis
- **`flash`** (Gemini 2.0 Flash): Ultra-fast responses
- **`o3`**: Strong logical reasoning  
- **`o3mini`**: Balanced speed/quality
- **`o4-mini`**: Latest reasoning model, optimized for shorter contexts
- **`o4-mini-high`**: Enhanced O4 with higher reasoning effort
- **`gpt4.1`**: GPT-4.1 with 1M context window
- **Custom models**: via OpenRouter or local APIs (Ollama, vLLM, etc.)

For detailed configuration options, see the [Advanced Usage Guide](docs/advanced-usage.md).

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