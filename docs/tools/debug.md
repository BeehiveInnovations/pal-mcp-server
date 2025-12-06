# Debug Tool - Systematic Investigation & Expert Analysis

**Step-by-step investigation followed by expert debugging assistance**

The `debug` workflow guides Claude through a systematic investigation process where Claude performs methodical code 
examination, evidence collection, and hypothesis formation across multiple steps. Once the investigation is complete, 
the tool provides expert analysis from the selected AI model (optionally) based on all gathered findings.

## Example Prompts

```
Get gemini to debug why my API returns 400 errors randomly with the full stack trace: [paste traceback]
```

You can also ask it to debug on its own, no external model required (**recommended in most cases**).
```
Use debug tool to find out why the app is crashing, here are some app logs [paste app logs] and a crash trace: [paste crash trace]
```

## How It Works 

The debug tool implements a **systematic investigation methodology** where Claude is guided through structured debugging steps:

**Investigation Phase:**
1. **Step 1**: Claude describes the issue and begins thinking deeply about possible underlying causes, side-effects, and contributing factors
2. **Step 2+**: Claude examines relevant code, traces errors, tests hypotheses, and gathers evidence
3. **Throughout**: Claude tracks findings, relevant files, methods, and evolving hypotheses with confidence levels
4. **Backtracking**: Claude can revise previous steps when new insights emerge
5. **Completion**: Once investigation is thorough, Claude signals completion

**Expert Analysis Phase:**
After Claude completes the investigation, it automatically calls the selected AI model with (unless confidence is **certain**, 
in which case expert analysis is bypassed):
- Complete investigation summary with all steps and findings
- Relevant files and methods identified during investigation  
- Final hypothesis and confidence assessment
- Error context and supporting evidence
- Visual debugging materials if provided

This structured approach ensures Claude performs methodical groundwork before expert analysis, resulting in significantly better debugging outcomes and more efficient token usage.

**Special Note**: If you want Claude to perform the entire debugging investigation without calling another model, you can include "don't use any other model" in your prompt, and Claude will complete the full workflow independently.

## Key Features

- **Multi-step investigation process** with evidence collection and hypothesis evolution
- **Systematic code examination** with file and method tracking throughout investigation
- **Confidence assessment and revision** capabilities for investigative steps
- **Backtracking support** to revise previous steps when new insights emerge
- **Expert analysis integration** that provides final debugging recommendations based on complete investigation
- **Error context support**: Stack traces, logs, and runtime information
- **Visual debugging**: Include error screenshots, stack traces, console output
- **Conversation threading**: Continue investigations across multiple sessions
- **Large context analysis**: Handle extensive log files and multiple related code files
- **Multi-language support**: Debug issues across Python, JavaScript, Java, C#, Swift, and more
- **Web search integration**: Identifies when additional research would help solve problems

## Tool Parameters

**Investigation Step Parameters:**
- `step`: Current investigation step description (required)
- `step_number`: Current step number in investigation sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable as process evolves)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries and evidence collected in this step (required)
- `files_checked`: All files examined during investigation (tracks exploration path)
- `relevant_files`: Files directly tied to the root cause or its effects
- `relevant_methods`: Specific methods/functions involved in the issue
- `hypothesis`: Current best guess about the underlying cause
- `confidence`: Confidence level in current hypothesis (exploring/low/medium/high/certain)
- `continuation_id`: Thread ID for continuing investigations across sessions
- `images`: Visual debugging materials (error screenshots, logs, etc.)

**Model Selection:**
- `model`: auto|pro|flash|flash-2.0|flashlite|o3|o3-mini|o4-mini|gpt4.1|gpt5.1|gpt5.1-codex|gpt5.1-codex-mini|gpt5|gpt5-mini|gpt5-nano (default: server default)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_assistant_model`: Whether to use expert analysis phase (default: true, set to false to use Claude only)

## Usage Examples

**Error Debugging:**
```
Debug this TypeError: 'NoneType' object has no attribute 'split' in my parser.py
```

**With Stack Trace:**
```
Use gemini to debug why my API returns 500 errors with this stack trace: [paste full traceback]
```

**With File Context:**
```
Debug without using external model, the authentication failure in auth.py and user_model.py
```

**Performance Debugging:**
```
Debug without using external model to find out why the app is consuming excessive memory during bulk edit operations
```

**Runtime Environment Issues:**
```
Debug deployment issues with server startup failures, here's the runtime info: [environment details]
```

## Investigation Methodology

The debug tool enforces a thorough, structured investigation process:

**Step-by-Step Investigation (Claude-Led):**
1. **Initial Problem Description:** Claude describes the issue and begins thinking about possible causes, side-effects, and contributing factors
2. **Code Examination:** Claude systematically examines relevant files, traces execution paths, and identifies suspicious patterns
3. **Evidence Collection:** Claude gathers findings, tracks files checked, and identifies methods/functions involved
4. **Hypothesis Formation:** Claude develops working theories about the root cause with confidence assessments
5. **Iterative Refinement:** Claude can backtrack and revise previous steps as understanding evolves
6. **Investigation Completion:** Claude signals when sufficient evidence has been gathered

**Expert Analysis Phase (Another AI Model When Used):**
Once investigation is complete, the selected AI model performs:
- **Root Cause Analysis:** Deep analysis of all investigation findings and evidence
- **Solution Recommendations:** Specific fixes with implementation guidance
- **Prevention Strategies:** Measures to avoid similar issues in the future
- **Testing Approaches:** Validation methods for proposed solutions

**Key Benefits:**
- **Methodical Evidence Collection:** Ensures no critical information is missed
- **Progressive Understanding:** Hypotheses evolve as investigation deepens
- **Complete Context:** Expert analysis receives full investigation history
- **Efficient Token Usage:** Structured approach prevents redundant back-and-forth

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

**For Investigation Steps:**
- **Be thorough in step descriptions**: Explain what you're examining and why
- **Track all files examined**: Include even files that don't contain the bug (tracks investigation path)
- **Document findings clearly**: Summarize discoveries, suspicious patterns, and evidence
- **Evolve hypotheses**: Update theories as investigation progresses
- **Use backtracking wisely**: Revise previous steps when new insights emerge
- **Include visual evidence**: Screenshots, error dialogs, console output

**For Initial Problem Description:**
- **Provide complete error context**: Full stack traces, error messages, and logs
- **Describe expected vs actual behavior**: Clear symptom description
- **Include environment details**: Runtime versions, configuration, deployment context
- **Mention previous attempts**: What debugging steps have already been tried
- **Be specific about occurrence**: When, where, and how the issue manifests

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

- **Use `debug`** for: Specific runtime errors, exceptions, crashes, performance issues requiring systematic investigation
- **Use `codereview`** for: Finding potential bugs in code without specific errors or symptoms
- **Use `analyze`** for: Understanding code structure and flow without troubleshooting specific issues
- **Use `precommit`** for: Validating changes before commit to prevent introducing bugs

## Investigation Example

**Step 1:** "The user authentication fails intermittently with no error logs. I need to investigate the auth flow and identify where failures might occur silently."

**Step 2:** "Examined auth.py and found three potential failure points: token validation, database connectivity, and session management. No obvious bugs yet but need to trace execution flow."

**Step 3:** "Found suspicious async/await pattern in session_manager.py lines 45-67. The await might be missing exception handling. This could explain silent failures."

**Completion:** Investigation reveals likely root cause in exception handling, ready for expert analysis with full context.
