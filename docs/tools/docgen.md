# DocGen Tool - Comprehensive Documentation Generation

**Generates comprehensive documentation with complexity analysis through workflow-driven investigation**

The `docgen` tool creates thorough documentation by analyzing your code structure, understanding function complexity, and documenting gotchas and unexpected behaviors that developers need to know. This workflow tool guides Claude through systematic investigation of code functionality, architectural patterns, and documentation needs across multiple steps before generating comprehensive documentation with complexity analysis and call flow information.

## Thinking Mode

**Default is `medium` (8,192 tokens) for extended thinking models.** Use `high` for complex systems with intricate architectures or `max` for comprehensive documentation projects requiring exhaustive analysis.

## How the Workflow Works

The docgen tool implements a **structured workflow** for comprehensive documentation generation:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Claude describes the documentation plan and begins analyzing code structure
2. **Step 2+**: Claude examines functions, methods, complexity patterns, and documentation gaps
3. **Throughout**: Claude tracks findings, documentation opportunities, and architectural insights
4. **Completion**: Once investigation is thorough, Claude signals completion

**Documentation Generation Phase:**
After Claude completes the investigation:
- Complete documentation strategy with style consistency
- Function/method documentation with complexity analysis
- Call flow and dependency documentation
- Gotchas and unexpected behavior documentation
- Final polished documentation following project standards

This workflow ensures methodical analysis before documentation generation, resulting in more comprehensive and valuable documentation.

## Model Recommendation

Documentation generation excels with analytical models like Gemini Pro or O3, which can understand complex code relationships, identify non-obvious behaviors, and generate thorough documentation that covers gotchas and edge cases. The combination of large context windows and analytical reasoning enables generation of documentation that helps prevent integration issues and developer confusion.

## Example Prompts

**Basic Usage:**
```
"Use zen to generate documentation for the UserManager class"
"Document the authentication module with complexity analysis using gemini pro"
"Add comprehensive documentation to all methods in src/payment_processor.py"
```

## Key Features

- **Incremental documentation approach** - Documents methods AS YOU ANALYZE them for immediate value
- **Complexity analysis** - Big O notation for algorithms and performance characteristics
- **Call flow documentation** - Dependencies and method relationships
- **Gotchas and edge case documentation** - Hidden behaviors and unexpected parameter interactions
- **Multi-agent workflow** analyzing code structure and identifying documentation needs
- **Follows existing project documentation style** and conventions
- **Supports multiple programming languages** with appropriate documentation formats
- **Updates existing documentation** when found to be incorrect or incomplete
- **Inline comments for complex logic** within functions and methods

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current investigation step description (required for each step)
- `step_number`: Current step number in documentation sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries about code structure and documentation needs (required)
- `files_checked`: All files examined during investigation
- `relevant_files`: Files containing code requiring documentation (required in step 1)
- `relevant_context`: Methods/functions/classes needing documentation

**Initial Configuration (used in step 1):**
- `prompt`: Description of what to document and specific focus areas (required)
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|o4-mini-high|gpt4.1 (default: server default)
- `document_complexity`: Include Big O complexity analysis (default: true)
- `document_flow`: Include call flow and dependency information (default: true)
- `update_existing`: Update existing documentation when incorrect/incomplete (default: true)
- `comments_on_complex_logic`: Add inline comments for complex algorithmic steps (default: true)

## Usage Examples

**Class Documentation:**
```
"Generate comprehensive documentation for the PaymentProcessor class including complexity analysis"
```

**Module Documentation:**
```
"Document all functions in the authentication module with call flow information"
```

**API Documentation:**
```
"Create documentation for the REST API endpoints in api/users.py with parameter gotchas"
```

**Algorithm Documentation:**
```
"Document the sorting algorithm in utils/sort.py with Big O analysis and edge cases"
```

**Library Documentation:**
```
"Add comprehensive documentation to the utility library with usage examples and warnings"
```

## Documentation Standards

**Function/Method Documentation:**
- Parameter types and descriptions
- Return value documentation with types
- Algorithmic complexity analysis (Big O notation)
- Call flow and dependency information
- Purpose and behavior explanation
- Exception types and conditions

**Gotchas and Edge Cases:**
- Parameter combinations that produce unexpected results
- Hidden dependencies on global state or environment
- Order-dependent operations where sequence matters
- Performance implications and bottlenecks
- Thread safety considerations
- Platform-specific behavior differences

**Code Quality Documentation:**
- Inline comments for complex logic
- Design pattern explanations
- Architectural decision rationale
- Usage examples and best practices

## Documentation Features Generated

**Complexity Analysis:**
- Time complexity (Big O notation)
- Space complexity when relevant
- Worst-case, average-case, and best-case scenarios
- Performance characteristics and bottlenecks

**Call Flow Documentation:**
- Which methods/functions this code calls
- Which methods/functions call this code
- Key dependencies and interactions
- Side effects and state modifications
- Data flow through functions

**Gotchas Documentation:**
- Non-obvious parameter interactions
- Hidden state dependencies
- Silent failure conditions
- Resource management requirements
- Version compatibility issues
- Platform-specific behaviors

## Incremental Documentation Approach

**Key Benefits:**
- **Immediate value delivery** - Code becomes more maintainable right away
- **Iterative improvement** - Pattern recognition across multiple analysis rounds
- **Quality validation** - Testing documentation effectiveness during workflow
- **Reduced cognitive load** - Focus on one function/method at a time

**Workflow Process:**
1. **Analyze and Document**: Examine each function and immediately add documentation
2. **Continue Analyzing**: Move to next function while building understanding
3. **Refine and Standardize**: Review and improve previously added documentation

## Language Support

**Automatic Detection and Formatting:**
- **Python**: Docstrings, type hints, Sphinx compatibility
- **JavaScript**: JSDoc, TypeScript documentation
- **Java**: Javadoc, annotation support
- **C#**: XML documentation comments
- **Swift**: Documentation comments, Swift-DocC
- **Go**: Go doc conventions
- **C/C++**: Doxygen-style documentation
- **And more**: Adapts to language conventions

## Documentation Quality Features

**Comprehensive Coverage:**
- All public methods and functions
- Complex private methods requiring explanation
- Class and module-level documentation
- Configuration and setup requirements

**Developer-Focused:**
- Clear explanations of non-obvious behavior
- Usage examples for complex APIs
- Warning about common pitfalls
- Integration guidance and best practices

**Maintainable Format:**
- Consistent documentation style
- Appropriate level of detail
- Cross-references and links
- Version and compatibility notes

## Best Practices

- **Be specific about scope**: Target specific classes/modules rather than entire codebases
- **Focus on complexity**: Prioritize documenting complex algorithms and non-obvious behaviors
- **Include context**: Provide architectural overview for better documentation strategy
- **Document incrementally**: Let the tool document functions as it analyzes them
- **Emphasize gotchas**: Request focus on edge cases and unexpected behaviors
- **Follow project style**: Maintain consistency with existing documentation patterns

## When to Use DocGen vs Other Tools

- **Use `docgen`** for: Creating comprehensive documentation, adding missing docs, improving existing documentation
- **Use `analyze`** for: Understanding code structure without generating documentation
- **Use `codereview`** for: Reviewing code quality including documentation completeness
- **Use `refactor`** for: Restructuring code before documentation (cleaner code = better docs)