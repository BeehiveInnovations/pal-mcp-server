# Chat Tool - General Development Chat & Collaborative Thinking

**Your thinking partner - bounce ideas, get second opinions, brainstorm collaboratively**

The `chat` tool is your collaborative thinking partner for development conversations. It's designed to help you brainstorm, validate ideas, get second opinions, and explore alternatives in a conversational format.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `low` for quick questions to save tokens, or `high` for complex discussions when thoroughness matters.

## Example Prompt

```
I need to pick between Redis and Memcached for session storage and I need an expert opinion for the project
I'm working on. Take a look at the code and get an idea of what this project does, pick one of the two options
and then chat with gemini pro and continue discussing pros and cons to come to a final conclusion. I need a one
word verdict in the end.
```
<div style="center">
  
  [Chat Redis or Memcached_web.webm](https://github.com/user-attachments/assets/41076cfe-dd49-4dfc-82f5-d7461b34705d)
  
</div>

**Another Example**:

* We ask Claude code to pick one of two frameworks, then `chat` with `gemini` to make a final decision
* Gemini responds, confirming choice. We use `continuation` to ask another question using the same conversation thread
* Gemini responds with explanation. We use continuation again, using `/zen:continue (MCP)` command the second time

<div style="center">
  
[Chat With Gemini_web.webm](https://github.com/user-attachments/assets/37bd57ca-e8a6-42f7-b5fb-11de271e95db)

</div>

## Key Features

- **Collaborative thinking partner** for your analysis and planning
- **Get second opinions** on your designs and approaches
- **Brainstorm solutions** and explore alternatives together
- **Structured code generation**: When using GPT-5 Pro or Gemini 2.5 Pro, get complete, production-ready implementations saved to `zen_generated.code` for your CLI to review and apply
- **Validate your checklists** and implementation plans
- **General development questions** and explanations
- **Technology comparisons** and best practices
- **Architecture and design discussions**
- **File reference support**: `"Use gemini to explain this algorithm with context from algorithm.py"`
- **Image support**: Include screenshots, diagrams, UI mockups for visual analysis: `"Chat with gemini about this error dialog screenshot to understand the user experience issue"`
- **Dynamic collaboration**: Models can request additional files or context during the conversation if needed for a more thorough response
- **Web search awareness**: Automatically identifies when online research would help and instructs Claude to perform targeted searches using continuation IDs

## Tool Parameters

- `prompt`: Your question or discussion topic (required)
- `model`: auto|pro|flash|flash-2.0|flashlite|o3|o3-mini|o4-mini|gpt4.1|gpt5|gpt5-mini|gpt5-nano (default: server default)
- `absolute_file_paths`: Optional absolute file or directory paths for additional context
- `images`: Optional images for visual context (absolute paths)
- `working_directory_absolute_path`: **Required** - Absolute path to an existing directory where generated code artifacts will be saved
- `temperature`: Response creativity (0-1, default 0.5)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `continuation_id`: Continue previous conversations

## Structured Code Generation

When using advanced reasoning models like **GPT-5 Pro** or **Gemini 2.5 Pro**, the chat tool can generate complete, production-ready code implementations in a structured format.

### How It Works

1. You ask your AI agent to implement a complex new feature using `chat` with a higher-reasoning model such as **GPT-5 Pro** or **Gemini 2.5 Pro**
2. The model generates structured implementation and shares the complete implementation with Zen
3. Zen saves the code to `zen_generated.code` and asks AI agent to implement the plan
4. AI agent continues from the previous context, reads the file, applies the implementation

### When Code Generation Activates

The structured format activates for **substantial implementation work**:
- Creating new features from scratch with multiple files or significant code
- Major refactoring across multiple files or large sections
- Implementing new modules, components, or subsystems
- Large-scale updates affecting substantial portions of the codebase
- Complete rewrites of functions, algorithms, or approaches

For minor changes (small tweaks, bug fixes, algorithm improvements), the model responds normally with inline code blocks.

### Example Usage

```
chat with gpt-5-pro and ask it to make me a standalone, classic version of the
Pacman game using pygame that I can run from the commandline. Give me a single
script to execute in the end with any / all dependencies setup for me. 
Do everything using pygame, we have no external resources / images / audio at
hand. Instead of ghosts, it'll be different geometric shapes moving around 
in the maze that Pacman can eat (so there are no baddies). Pacman gets to eat
everything including bread-crumbs and large geometric shapes but make me the
classic maze / walls that it navigates within using keyboard arrow keys.
```

See the [Configuration Guide](../configuration.md#code-generation-capability) for details on the `allow_code_generation` flag.

## Usage Examples

**Basic Development Chat:**
```
"Chat with zen about the best approach for user authentication in my React app"
```

**Technology Comparison:**
```
"Use flash to discuss whether PostgreSQL or MongoDB would be better for my e-commerce platform"
```

**Architecture Discussion:**
```
"Chat with pro about microservices vs monolith architecture for my project, consider scalability and team size"
```

**File Context Analysis:**
```
"Use gemini to chat about the current authentication implementation in auth.py and suggest improvements"
```

**Visual Analysis:**
```
"Chat with gemini about this UI mockup screenshot - is the user flow intuitive?"
```

## Best Practices

- **Be specific about context**: Include relevant files or describe your project scope
- **Ask for trade-offs**: Request pros/cons for better decision-making
- **Use conversation continuation**: Build on previous discussions with `continuation_id`
- **Leverage visual context**: Include diagrams, mockups, or screenshots when discussing UI/UX
- **Encourage research**: When you suspect documentation has changed, explicitly ask the assistant to confirm by requesting a web search

## When to Use Chat vs Other Tools

- **Use `chat`** for: Open-ended discussions, brainstorming, getting second opinions, technology comparisons
- **Use `thinkdeep`** for: Extending specific analysis, challenging assumptions, deeper reasoning
- **Use `analyze`** for: Understanding existing code structure and patterns
- **Use `debug`** for: Specific error diagnosis and troubleshooting
