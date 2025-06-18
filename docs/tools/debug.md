# Debug Tool - Expert Debugging Assistant

**Root cause analysis for complex problems**

The `debug` tool provides systematic debugging assistance with root cause analysis, hypothesis generation, and 
structured problem-solving approaches for complex technical issues.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `high` for tricky bugs (investment in finding root cause) or `low` for simple errors (save tokens).

## Example Prompts

**Basic Usage:**
```
Get gemini to debug why my API returns 400 errors randomly with the full stack trace: [paste traceback]
```

## How It Works 

Just because Claude gets to use a development partner doesn't mean it's off the hook! 
Claude does the initial groundwork of investigation and then passes this on to the other model - just as a developer 
would for a second opinion when involving another, with enough context. This results in a significant improvement in
bug hunting and reduces the chance of wasting precious tokens back and forth.

## Key Features

- **Generates multiple ranked hypotheses** for systematic debugging
- **Accepts error context**, stack traces, and logs
- **Can reference relevant files** for investigation
- **Supports runtime info** and previous attempts
- **Provides structured root cause analysis** with validation steps
- **Can request additional context** when needed for thorough analysis
- **Image support**: Include error screenshots, stack traces, console output: `"Debug this error using gemini with the stack trace screenshot and the failing test.py"`
- **Web search capability**: When enabled (default: true), identifies when searching for error messages, known issues, or documentation would help solve the problem and recommends specific searches for Claude
- **Large context analysis**: Can analyze extensive log files and multiple related code files simultaneously
- **Multi-language support**: Debug issues across Python, JavaScript, Java, C#, Swift, and more

## Tool Parameters

- `prompt`: Error message, symptoms, or issue description (required)
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|o4-mini-high|gpt4.1 (default: server default)
- `error_context`: Stack trace, logs, or additional error context
- `files`: Files or directories that might be related to the issue (absolute paths)
- `images`: Error screenshots, stack traces, console output (absolute paths)
- `runtime_info`: Environment, versions, or runtime information
- `previous_attempts`: What has been tried already
- `temperature`: Temperature for accuracy (0-1, default 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_websearch`: Enable web search for error messages and solutions (default: true)
- `continuation_id`: Continue previous debugging sessions

## Usage Examples

**Basic Error Debugging:**
```
"Debug this TypeError: 'NoneType' object has no attribute 'split' in my parser.py"
```

**With Stack Trace:**
```
"Use gemini to debug why my API returns 500 errors with this stack trace: [paste full traceback]"
```

**With File Context:**
```
"Debug the authentication failure in auth.py and user_model.py with o3"
```

**Performance Debugging:**
```
"Use pro to debug why my application is consuming excessive memory during bulk operations"
```

**With Visual Context:**
```
"Debug this crash using the error screenshot and the related crash_report.log"
```

**Runtime Environment Issues:**
```
"Debug deployment issues with server startup failures, here's the runtime info: [environment details]"
```

## Debugging Methodology

The debug tool follows a systematic approach:

**1. Problem Analysis:**
- Parse error messages and symptoms
- Identify affected components and subsystems
- Understand the expected vs actual behavior

**2. Hypothesis Generation:**
- Generate multiple potential root causes
- Rank hypotheses by likelihood and impact
- Consider both obvious and subtle possibilities

**3. Investigation Strategy:**
- Recommend specific files to examine
- Suggest logging or debugging steps
- Identify missing information needed

**4. Root Cause Analysis:**
- Analyze evidence from code, logs, and context
- Trace execution flow to identify failure points
- Consider environmental and configuration factors

**5. Solution Recommendations:**
- Provide specific fixes with code examples
- Suggest preventive measures
- Recommend testing strategies

## Debugging Categories

**Runtime Errors:**
- Exceptions and crashes
- Null pointer/reference errors
- Type errors and casting issues
- Memory leaks and resource exhaustion

**Logic Errors:**
- Incorrect algorithm implementation
- Off-by-one errors and boundary conditions
- State management issues
- Race conditions and concurrency bugs

**Integration Issues:**
- API communication failures
- Database connection problems
- Third-party service integration
- Configuration and environment issues

**Performance Problems:**
- Slow response times
- Memory usage spikes
- CPU-intensive operations
- I/O bottlenecks

## Best Practices

- **Provide complete error context**: Include full stack traces, error messages, and relevant logs
- **Share relevant code**: Include files mentioned in stack traces or related to the issue
- **Describe expected behavior**: Explain what should happen vs what's actually happening
- **Include environment details**: Runtime versions, configuration, deployment context
- **Mention previous attempts**: What debugging steps have already been tried
- **Use visual context**: Screenshots of error dialogs, console output, or debugging tools
- **Be specific about symptoms**: Describe when, where, and how the issue occurs

## Advanced Features

**Large Log Analysis:**
With models like Gemini Pro (1M context), you can include extensive log files for comprehensive analysis:
```
"Debug application crashes using these large log files: app.log, error.log, system.log"
```

**Multi-File Investigation:**
Analyze multiple related files simultaneously to understand complex issues:
```
"Debug the data processing pipeline issues across processor.py, validator.py, and output_handler.py"
```

**Web Search Integration:**
The tool can recommend specific searches for error messages, known issues, or documentation:
```
After analysis: "Recommended searches for Claude: 'Django 4.2 migration error specific_error_code', 'PostgreSQL connection pool exhaustion solutions'"
```

## When to Use Debug vs Other Tools

- **Use `debug`** for: Specific runtime errors, exceptions, crashes, performance issues
- **Use `codereview`** for: Finding potential bugs in code without specific errors
- **Use `analyze`** for: Understanding code structure and flow without troubleshooting
- **Use `precommit`** for: Validating changes before commit to prevent introducing bugs