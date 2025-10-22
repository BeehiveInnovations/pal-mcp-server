# Analyze Tool - Smart File Analysis

**General-purpose code understanding and exploration through workflow-driven investigation**

The `analyze` tool provides comprehensive code analysis and understanding capabilities, helping you explore codebases, understand architecture, and identify patterns across files and directories. This workflow tool guides Claude through systematic investigation of code structure, patterns, and architectural decisions across multiple steps, gathering comprehensive insights before providing expert analysis.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `high` for architecture analysis (comprehensive insights worth the cost) or `low` for quick file overviews (save ~6k tokens).

## How the Workflow Works

The analyze tool implements a **structured workflow** for thorough code understanding:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Claude describes the analysis plan and begins examining code structure
2. **Step 2+**: Claude investigates architecture, patterns, dependencies, and design decisions
3. **Throughout**: Claude tracks findings, relevant files, insights, and confidence levels
4. **Completion**: Once analysis is comprehensive, Claude signals completion

**Expert Analysis Phase:**
After Claude completes the investigation (unless confidence is **certain**):
- Complete analysis summary with all findings
- Architectural insights and pattern identification
- Strategic improvement recommendations
- Final expert assessment based on investigation

This workflow ensures methodical analysis before expert insights, resulting in deeper understanding and more valuable recommendations.

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
- **Web search capability**: Automatically requests Claude to perform web searches when fresh documentation, patterns, or best practices are needed, ensuring the analysis stays current

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current investigation step description (required for each step)
- `step_number`: Current step number in analysis sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries and insights collected in this step (required)
- `files_checked`: All files examined during investigation
- `relevant_files`: Files directly relevant to the analysis (required in step 1)
- `relevant_context`: Methods/functions/classes central to analysis findings
- `issues_found`: Issues or concerns identified with severity levels
- `confidence`: Confidence level in analysis completeness (exploring/low/medium/high/certain)
- `images`: Visual references for analysis context

**Initial Configuration (used in step 1):**
- `prompt`: What to analyze or look for (required)
- `model`: auto|pro|flash|flash-2.0|flashlite|o3|o3-mini|o4-mini|gpt4.1|gpt5|gpt5-mini|gpt5-nano (default: server default)
- `analysis_type`: architecture|performance|security|quality|general (default: general)
- `output_format`: summary|detailed|actionable (default: detailed)
- `temperature`: Temperature for analysis (0-1, default 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_assistant_model`: Whether to use expert analysis phase (default: true, set to false to use Claude only)
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
