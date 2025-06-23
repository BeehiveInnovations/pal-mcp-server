# TestGen Tool - Comprehensive Test Generation

**Generates thorough test suites with edge case coverage through workflow-driven investigation**

The `testgen` tool creates comprehensive test suites by analyzing your code paths, understanding intricate dependencies, and identifying realistic edge cases and failure scenarios that need test coverage. This workflow tool guides Claude through systematic investigation of code functionality, critical paths, edge cases, and integration points across multiple steps before generating comprehensive tests with realistic failure mode analysis.

## Thinking Mode

**Default is `medium` (8,192 tokens) for extended thinking models.** Use `high` for complex systems with many interactions or `max` for critical systems requiring exhaustive test coverage.

## How the Workflow Works

The testgen tool implements a **structured workflow** for comprehensive test generation:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Claude describes the test generation plan and begins analyzing code functionality
2. **Step 2+**: Claude examines critical paths, edge cases, error handling, and integration points
3. **Throughout**: Claude tracks findings, test scenarios, and coverage gaps
4. **Completion**: Once investigation is thorough, Claude signals completion

**Test Generation Phase:**
After Claude completes the investigation:
- Complete test scenario catalog with all edge cases
- Framework-specific test generation
- Realistic failure mode coverage
- Final test suite with comprehensive coverage

This workflow ensures methodical analysis before test generation, resulting in more thorough and valuable test suites.

## Model Recommendation

Test generation excels with extended reasoning models like Gemini Pro or O3, which can analyze complex code paths, understand intricate dependencies, and identify comprehensive edge cases. The combination of large context windows and advanced reasoning enables generation of thorough test suites that cover realistic failure scenarios and integration points that shorter-context models might overlook.

## Example Prompts

**Basic Usage:**
```
"Use zen to generate tests for User.login() method"
"Generate comprehensive tests for the sorting method in src/new_sort.py using o3"
"Create tests for edge cases not already covered in our tests using gemini pro"
```

## Key Features

- **Multi-agent workflow** analyzing code paths and identifying realistic failure modes
- **Generates framework-specific tests** following project conventions
- **Supports test pattern following** when examples are provided
- **Dynamic token allocation** (25% for test examples, 75% for main code)
- **Prioritizes smallest test files** for pattern detection
- **Can reference existing test files**: `"Generate tests following patterns from tests/unit/"`
- **Specific code coverage** - target specific functions/classes rather than testing everything
- **Image support**: Test UI components, analyze visual requirements: `"Generate tests for this login form using the UI mockup screenshot"`
- **Edge case identification**: Systematic discovery of boundary conditions and error states
- **Realistic failure mode analysis**: Understanding what can actually go wrong in production
- **Integration test support**: Tests that cover component interactions and system boundaries

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current investigation step description (required for each step)
- `step_number`: Current step number in test generation sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries about functionality and test scenarios (required)
- `files_checked`: All files examined during investigation
- `relevant_files`: Files directly needing tests (required in step 1)
- `relevant_context`: Methods/functions/classes requiring test coverage
- `confidence`: Confidence level in test plan completeness (exploring/low/medium/high/certain)
- `backtrack_from_step`: Step number to backtrack from (for revisions)

**Initial Configuration (used in step 1):**
- `prompt`: Description of what to test, testing objectives, and specific scope/focus areas (required)
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|gpt4.1 (default: server default)
- `test_examples`: Optional existing test files or directories to use as style/pattern reference (absolute paths)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_assistant_model`: Whether to use expert test generation phase (default: true, set to false to use Claude only)

## Usage Examples

**Method-Specific Tests:**
```
"Generate tests for User.login() method covering authentication success, failure, and edge cases"
```

**Class Testing:**
```
"Use pro to generate comprehensive tests for PaymentProcessor class with max thinking mode"
```

**Following Existing Patterns:**
```
"Generate tests for new authentication module following patterns from tests/unit/auth/"
```

**UI Component Testing:**
```
"Generate tests for this login form component using the UI mockup screenshot"
```

**Algorithm Testing:**
```
"Create thorough tests for the sorting algorithm in utils/sort.py, focus on edge cases and performance"
```

**Integration Testing:**
```
"Generate integration tests for the payment processing pipeline from order creation to completion"
```

## Test Generation Strategy

**Code Path Analysis:**
- Identifies all execution paths through the code
- Maps conditional branches and loops
- Discovers error handling paths
- Analyzes state transitions

**Edge Case Discovery:**
- Boundary value analysis (empty, null, max values)
- Invalid input scenarios
- Race conditions and timing issues
- Resource exhaustion cases

**Failure Mode Analysis:**
- External dependency failures
- Network and I/O errors
- Authentication and authorization failures
- Data corruption scenarios

**Framework Detection:**
The tool automatically detects and generates tests for:
- **Python**: pytest, unittest, nose2
- **JavaScript**: Jest, Mocha, Jasmine, Vitest
- **Java**: JUnit 4/5, TestNG, Mockito
- **C#**: NUnit, MSTest, xUnit
- **Swift**: XCTest
- **Go**: testing package
- **And more**: Adapts to project conventions

## Test Categories Generated

**Unit Tests:**
- Function/method behavior validation
- Input/output verification
- Error condition handling
- State change verification

**Integration Tests:**
- Component interaction testing
- API endpoint validation
- Database integration
- External service mocking

**Edge Case Tests:**
- Boundary conditions
- Invalid inputs
- Resource limits
- Concurrent access

**Performance Tests:**
- Response time validation
- Memory usage checks
- Load handling
- Scalability verification

## Best Practices

- **Be specific about scope**: Target specific functions/classes rather than requesting tests for everything
- **Provide test examples**: Include existing test files for pattern consistency
- **Focus on critical paths**: Prioritize testing of business-critical functionality
- **Include visual context**: Screenshots or mockups for UI component testing
- **Describe testing objectives**: Explain what aspects are most important to test
- **Consider test maintenance**: Request readable, maintainable test code

## Test Quality Features

**Realistic Test Data:**
- Generates meaningful test data that represents real-world scenarios
- Avoids trivial test cases that don't add value
- Creates data that exercises actual business logic

**Comprehensive Coverage:**
- Happy path scenarios
- Error conditions and exceptions
- Edge cases and boundary conditions
- Integration points and dependencies

**Maintainable Code:**
- Clear test names that describe what's being tested
- Well-organized test structure
- Appropriate use of setup/teardown
- Minimal test data and mocking

## Advanced Features

**Pattern Following:**
When test examples are provided, the tool analyzes:
- Naming conventions and structure
- Assertion patterns and style
- Mocking and setup approaches
- Test data organization

**Large Context Analysis:**
With models like Gemini Pro, the tool can:
- Analyze extensive codebases for comprehensive test coverage
- Understand complex interactions across multiple modules
- Generate integration tests that span multiple components

**Visual Testing:**
For UI components and visual elements:
- Generate tests based on visual requirements
- Create accessibility testing scenarios
- Test responsive design behaviors

## When to Use TestGen vs Other Tools

- **Use `testgen`** for: Creating comprehensive test suites, filling test coverage gaps, testing new features
- **Use `debug`** for: Diagnosing specific test failures or runtime issues
- **Use `codereview`** for: Reviewing existing test quality and coverage
- **Use `analyze`** for: Understanding existing test structure without generating new tests