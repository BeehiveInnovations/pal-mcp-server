# Analyze Tool - Smart File Analysis

**General-purpose code understanding and exploration**

The `analyze` tool provides comprehensive code analysis and understanding capabilities, helping you explore codebases, understand architecture, and identify patterns across files and directories.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `high` for architecture analysis (comprehensive insights worth the cost) or `low` for quick file overviews (save ~6k tokens).

## Example Prompts

**Basic Usage:**
```
"Use gemini to analyze main.py to understand how it works"
"Get gemini to do an architecture analysis of the src/ directory"
```

## Key Features

- **Analyzes single files or entire directories** with intelligent file filtering
- **Supports specialized analysis types**: architecture, performance, security, quality, general
- **Uses file paths (not content) for clean terminal output** while processing full content
- **Can identify patterns, anti-patterns, and refactoring opportunities**
- **Large codebase support**: Handle massive codebases with 1M token context models
- **Cross-file relationship mapping**: Understand dependencies and interactions
- **Architecture visualization**: Describe system structure and component relationships
- **Image support**: Analyze architecture diagrams, UML charts, flowcharts: `"Analyze this system diagram with gemini to understand the data flow and identify bottlenecks"`
- **Web search capability**: When enabled with `use_websearch` (default: true), the model can request Claude to perform web searches and share results back to enhance analysis with current documentation, design patterns, and best practices

## Tool Parameters

- `files`: Files or directories to analyze (required, absolute paths)
- `prompt`: What to analyze or look for (required)
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|o4-mini-high|gpt4.1 (default: server default)
- `analysis_type`: architecture|performance|security|quality|general (default: general)
- `output_format`: summary|detailed|actionable (default: detailed)
- `temperature`: Temperature for analysis (0-1, default 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_websearch`: Enable web search for documentation and best practices (default: true)
- `continuation_id`: Continue previous analysis sessions

## Analysis Types

**General Analysis (default):**
- Overall code structure and organization
- Key components and their responsibilities
- Data flow and control flow
- Design patterns and architectural decisions

**Architecture Analysis:**
- System-level design and component relationships
- Module dependencies and coupling
- Separation of concerns and layering
- Scalability and maintainability considerations

**Performance Analysis:**
- Potential bottlenecks and optimization opportunities
- Algorithmic complexity assessment
- Memory usage patterns
- I/O and database interaction efficiency

**Security Analysis:**
- Security patterns and potential vulnerabilities
- Input validation and sanitization
- Authentication and authorization mechanisms
- Data protection and privacy considerations

**Quality Analysis:**
- Code quality metrics and maintainability
- Testing coverage and patterns
- Documentation completeness
- Best practices adherence

## Usage Examples

**Single File Analysis:**
```
"Analyze user_controller.py to understand the authentication flow with gemini"
```

**Directory Architecture Analysis:**
```
"Use pro to analyze the src/ directory architecture and identify the main components"
```

**Performance-Focused Analysis:**
```
"Analyze backend/api/ for performance bottlenecks with o3, focus on database queries"
```

**Security Assessment:**
```
"Use gemini pro to analyze the authentication module for security patterns and potential issues"
```

**Visual + Code Analysis:**
```
"Analyze this system architecture diagram along with the src/core/ implementation to understand the data flow"
```

**Large Codebase Analysis:**
```
"Analyze the entire project structure with gemini pro to understand how all components work together"
```

## Output Formats

**Summary Format:**
- High-level overview with key findings
- Main components and their purposes
- Critical insights and recommendations

**Detailed Format (default):**
- Comprehensive analysis with specific examples
- Code snippets and file references
- Detailed explanations of patterns and structures

**Actionable Format:**
- Specific recommendations and next steps
- Prioritized list of improvements
- Implementation guidance and examples

## Best Practices

- **Be specific about goals**: Clearly state what you want to understand or discover
- **Use appropriate analysis types**: Choose the type that matches your needs
- **Include related files**: Analyze modules together for better context understanding
- **Leverage large context models**: Use Gemini Pro for comprehensive codebase analysis
- **Combine with visual context**: Include architecture diagrams or documentation
- **Use continuation**: Build on previous analysis for deeper understanding

## Advanced Features

**Large Codebase Support:**
With models like Gemini Pro (1M context), you can analyze extensive codebases:
```
"Analyze the entire microservices architecture across all service directories"
```

**Cross-File Relationship Mapping:**
Understand how components interact across multiple files:
```
"Analyze the data processing pipeline across input/, processing/, and output/ directories"
```

**Pattern Recognition:**
Identify design patterns, anti-patterns, and architectural decisions:
```
"Analyze src/ to identify all design patterns used and assess their implementation quality"
```

**Web Search Enhancement:**
The tool can recommend searches for current best practices and documentation:
```
After analysis: "Recommended searches for Claude: 'FastAPI async best practices 2024', 'SQLAlchemy ORM performance optimization patterns'"
```

## When to Use Analyze vs Other Tools

- **Use `analyze`** for: Understanding code structure, exploring unfamiliar codebases, architecture assessment
- **Use `codereview`** for: Finding bugs and security issues with actionable fixes
- **Use `debug`** for: Diagnosing specific runtime errors or performance problems
- **Use `refactor`** for: Getting specific refactoring recommendations and implementation plans
- **Use `chat`** for: Open-ended discussions about code without structured analysis