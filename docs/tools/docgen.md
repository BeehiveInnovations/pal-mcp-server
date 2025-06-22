# DocGen Tool - Comprehensive Documentation Generation

**Generates comprehensive documentation with complexity analysis through workflow-driven investigation**

The `docgen` tool creates thorough documentation by analyzing your code structure, understanding function complexity, and documenting gotchas and unexpected behaviors that developers need to know. This workflow tool guides Claude through systematic investigation of code functionality, architectural patterns, and documentation needs across multiple steps before generating comprehensive documentation with complexity analysis and call flow information.

## How the Workflow Works

The docgen tool implements a **structured workflow** for comprehensive documentation generation:

**Investigation Phase (Claude-Led):**
1. **Step 1 (Discovery)**: Claude discovers ALL files needing documentation and reports exact count
2. **Step 2+ (Documentation)**: Claude documents files one-by-one with complete coverage validation
3. **Throughout**: Claude tracks progress with counters and enforces modern documentation styles
4. **Completion**: Only when all files are documented (num_files_documented = total_files_to_document)

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

- **Systematic file-by-file approach** - Complete documentation with progress tracking and validation
- **Modern documentation styles** - Enforces /// for Objective-C/Swift, /** */ for Java/JavaScript, etc.
- **Complexity analysis** - Big O notation for algorithms and performance characteristics
- **Call flow documentation** - Dependencies and method relationships
- **Counter-based completion** - Prevents stopping until all files are documented
- **Large file handling** - Systematic portion-by-portion documentation for comprehensive coverage
- **Final verification scan** - Mandatory check to ensure no functions are missed
- **Bug tracking** - Surfaces code issues without altering logic
- **Configuration parameters** - Control complexity analysis, call flow, and inline comments

## Tool Parameters

**Workflow Parameters (used during step-by-step process):**
- `step`: Current step description - discovery phase (step 1) or documentation phase (step 2+)
- `step_number`: Current step number in documentation sequence (required)
- `total_steps`: Dynamically calculated as 1 + total_files_to_document
- `next_step_required`: Whether another step is needed
- `findings`: Discoveries about code structure and documentation needs (required)
- `relevant_files`: Files being actively documented in current step
- `num_files_documented`: Counter tracking completed files (required)
- `total_files_to_document`: Total count of files needing documentation (required)

**Configuration Parameters (required fields):**
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

**Modern Documentation Style Enforcement:**
- **Python**: Triple-quote docstrings with type hints
- **Objective-C**: /// comments
- **Swift**: /// comments
- **JavaScript/TypeScript**: /** */ JSDoc style
- **Java**: /** */ Javadoc style  
- **C#**: /// XML documentation comments
- **C/C++**: /// for documentation comments
- **Go**: // comments above functions/types
- **Rust**: /// for documentation comments

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

- **Use systematic approach**: Tool now documents all files with progress tracking and validation
- **Trust the counters**: Tool prevents premature completion until all files are documented
- **Large files handled**: Tool automatically processes large files in systematic portions
- **Modern styles enforced**: Tool ensures correct documentation style per language
- **Configuration matters**: Enable complexity analysis and call flow for comprehensive docs
- **Bug tracking**: Tool surfaces issues without altering code - review findings after completion

## When to Use DocGen vs Other Tools

- **Use `docgen`** for: Creating comprehensive documentation, adding missing docs, improving existing documentation
- **Use `analyze`** for: Understanding code structure without generating documentation
- **Use `codereview`** for: Reviewing code quality including documentation completeness
- **Use `refactor`** for: Restructuring code before documentation (cleaner code = better docs)