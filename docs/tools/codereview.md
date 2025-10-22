# CodeReview Tool - Professional Code Review

**Comprehensive code analysis with prioritized feedback through workflow-driven investigation**

The `codereview` tool provides professional code review capabilities with actionable feedback, severity-based issue prioritization, and support for various review types from quick style checks to comprehensive security audits. This workflow tool guides Claude through systematic investigation steps with forced pauses between each step to ensure thorough code examination, issue identification, and quality assessment before providing expert analysis.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `high` for security-critical code (worth the extra tokens) or `low` for quick style checks (saves ~6k tokens).

## How the Workflow Works

The codereview tool implements a **structured workflow** that ensures thorough code examination:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Claude describes the review plan and begins systematic analysis of code structure
2. **Step 2+**: Claude examines code quality, security implications, performance concerns, and architectural patterns
3. **Throughout**: Claude tracks findings, relevant files, issues, and confidence levels
4. **Completion**: Once review is comprehensive, Claude signals completion

**Expert Analysis Phase:**
After Claude completes the investigation (unless confidence is **certain**):
- Complete review summary with all findings and evidence
- Relevant files and code patterns identified
- Issues categorized by severity levels
- Final recommendations based on investigation

**Special Note**: If you want Claude to perform the entire review without calling another model, you can include "don't use any other model" in your prompt, and Claude will complete the full workflow independently.

## Model Recommendation

This tool particularly benefits from Gemini Pro or Flash models due to their 1M context window, which allows comprehensive analysis of large codebases. Claude's context limitations make it challenging to see the "big picture" in complex projects - this is a concrete example where utilizing a secondary model with larger context provides significant value beyond just experimenting with different AI capabilities.

## Example Prompts

```
Perform a codereview with gemini pro and review auth.py for security issues and potential vulnerabilities.
I need an actionable plan but break it down into smaller quick-wins that we can implement and test rapidly 
```

## Pro Tip: Multiple Parallel Reviews

**You can start more than one codereview session with Claude:**

```
Start separate sub-tasks for codereview one with o3 finding critical issues and one with flash finding low priority issues
and quick-wins and give me the final single combined review highlighting only the critical issues 
```

The above prompt will simultaneously run two separate `codereview` tools with two separate models and combine the output into a single summary for you to consume.

## Key Features

- **Issues prioritized by severity** (🔴 CRITICAL → 🟢 LOW)
- **Supports specialized reviews**: security, performance, quick
- **Coding standards enforcement**: `"Use gemini to review src/ against PEP8 standards"`
- **Severity filtering**: `"Get gemini to review auth/ - only report critical vulnerabilities"`
- **Image support**: Review code from screenshots, error dialogs, or visual bug reports: `"Review this error screenshot and the related auth.py file for potential security issues"`
- **Multi-file analysis**: Comprehensive review of entire directories or codebases
- **Actionable feedback**: Specific recommendations with line numbers and code examples
- **Language-specific expertise**: Tailored analysis for Python, JavaScript, Java, C#, Swift, and more
- **Integration issue detection**: Identifies cross-file dependencies and architectural problems
- **Security vulnerability scanning**: Focused on common security patterns and anti-patterns

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current investigation step description (required for each step)
- `step_number`: Current step number in review sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries and evidence collected in this step (required)
- `files_checked`: All files examined during investigation
- `relevant_files`: Files directly relevant to the review (required in step 1)
- `relevant_context`: Methods/functions/classes central to review findings
- `issues_found`: Issues identified with severity levels
- `confidence`: Confidence level in review completeness (exploring/low/medium/high/certain)
- `images`: Visual references for review context

**Initial Review Configuration (used in step 1):**
- `prompt`: User's summary of what the code does, expected behavior, constraints, and review objectives (required)
- `model`: auto|pro|flash|flash-2.0|flashlite|o3|o3-mini|o4-mini|gpt4.1|gpt5|gpt5-mini|gpt5-nano (default: server default)
- `review_type`: full|security|performance|quick (default: full)
- `focus_on`: Specific aspects to focus on (e.g., "security vulnerabilities", "performance bottlenecks")
- `standards`: Coding standards to enforce (e.g., "PEP8", "ESLint", "Google Style Guide")
- `severity_filter`: critical|high|medium|low|all (default: all)
- `temperature`: Temperature for consistency (0-1, default 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_assistant_model`: Whether to use expert analysis phase (default: true, set to false to use Claude only)
- `continuation_id`: Continue previous review discussions

## Review Types

**Full Review (default):**
- Comprehensive analysis including bugs, security, performance, maintainability
- Best for new features or significant code changes

**Security Review:**
- Focused on security vulnerabilities and attack vectors
- Checks for common security anti-patterns
- Best for authentication, authorization, data handling code

**Performance Review:**
- Analyzes performance bottlenecks and optimization opportunities
- Memory usage, algorithmic complexity, resource management
- Best for performance-critical code paths

**Quick Review:**
- Fast style and basic issue check
- Lower token usage for rapid feedback
- Best for code formatting and simple validation

## Severity Levels

Issues are categorized and prioritized:

- **🔴 CRITICAL**: Security vulnerabilities, crashes, data corruption
- **🟠 HIGH**: Logic errors, performance issues, reliability problems  
- **🟡 MEDIUM**: Code smells, maintainability issues, minor bugs
- **🟢 LOW**: Style issues, documentation, minor improvements

## Usage Examples

**Basic Security Review:**
```
"Review the authentication module in auth/ for security vulnerabilities with gemini pro"
```

**Performance-Focused Review:**
```
"Use o3 to review backend/api.py for performance issues, focus on database queries and caching"
```

**Quick Style Check:**
```
"Quick review of utils.py with flash, only report critical and high severity issues"
```

**Standards Enforcement:**
```
"Review src/ directory against PEP8 standards with gemini, focus on code formatting and structure"
```

**Visual Context Review:**
```
"Review this authentication code along with the error dialog screenshot to understand the security implications"
```

## Best Practices

- **Provide context**: Describe what the code is supposed to do and any constraints
- **Use appropriate review types**: Security for auth code, performance for critical paths
- **Set severity filters**: Focus on critical issues for quick wins
- **Include relevant files**: Review related modules together for better context
- **Use parallel reviews**: Run multiple reviews with different models for comprehensive coverage
- **Follow up on findings**: Use the continuation feature to discuss specific issues in detail

## Output Format

Reviews include:
- **Executive Summary**: Overview of code quality and main concerns
- **Detailed Findings**: Specific issues with severity levels, line numbers, and recommendations
- **Quick Wins**: Easy-to-implement improvements with high impact
- **Long-term Improvements**: Structural changes for better maintainability
- **Security Considerations**: Specific security recommendations when relevant

## When to Use CodeReview vs Other Tools

- **Use `codereview`** for: Finding bugs, security issues, performance problems, code quality assessment
- **Use `analyze`** for: Understanding code structure without finding issues
- **Use `debug`** for: Diagnosing specific runtime errors or exceptions
- **Use `refactor`** for: Identifying structural improvements and modernization opportunities
