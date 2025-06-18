# Contributing to Zen MCP Server

Thank you for your interest in contributing to Zen MCP Server! This guide will help you understand our development process, coding standards, and how to submit high-quality contributions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
3. **Set up the development environment**:
   ```bash
   ./run-server.sh
   ```
4. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

## Development Process

### 1. Code Quality Standards

We maintain high code quality standards. **All contributions must pass our automated checks**.

#### Required Code Quality Checks

Before submitting any PR, run our automated quality check script:

```bash
# Run the comprehensive quality checks script
./code_quality_checks.sh
```

This script automatically runs:
- Ruff linting with auto-fix
- Black code formatting 
- Import sorting with isort
- Complete unit test suite (361 tests)
- Verification that all checks pass 100%

**Manual commands** (if you prefer to run individually):
```bash
# Run all linting checks (MUST pass 100%)
ruff check .
black --check .
isort --check-only .

# Auto-fix issues if needed
ruff check . --fix
black .
isort .

# Run complete unit test suite (MUST pass 100%)
python -m pytest -xvs

# Run simulator tests for tool changes
python communication_simulator_test.py
```

**Important**: 
- **Every single test must pass** - we have zero tolerance for failing tests in CI
- All linting must pass cleanly (ruff, black, isort)
- Import sorting must be correct
- Tests failing in GitHub Actions will result in PR rejection

### 2. Testing Requirements

#### When to Add Tests

1. **New features MUST include tests**:
   - Add unit tests in `tests/` for new functions or classes
   - Test both success and error cases
   
2. **Tool changes require simulator tests**:
   - Add simulator tests in `simulator_tests/` for new or modified tools
   - Use realistic prompts that demonstrate the feature
   - Validate output through server logs
   
3. **Bug fixes require regression tests**:
   - Add a test that would have caught the bug
   - Ensure the bug cannot reoccur

#### Test Naming Conventions
- Unit tests: `test_<feature>_<scenario>.py`
- Simulator tests: `test_<tool>_<behavior>.py`

### 3. Pull Request Process

#### PR Title Format

Your PR title MUST follow one of these formats:

**Version Bumping Prefixes** (trigger version bump):
- `feat: <description>` - New features (MINOR version bump)
- `fix: <description>` - Bug fixes (PATCH version bump)
- `breaking: <description>` or `BREAKING CHANGE: <description>` - Breaking changes (MAJOR version bump)
- `perf: <description>` - Performance improvements (PATCH version bump)
- `refactor: <description>` - Code refactoring (PATCH version bump)

**Non-Version Prefixes** (no version bump):
- `docs: <description>` - Documentation only
- `chore: <description>` - Maintenance tasks
- `test: <description>` - Test additions/changes
- `ci: <description>` - CI/CD changes
- `style: <description>` - Code style changes

**Other Options**:
- `docs: <description>` - Documentation changes only
- `chore: <description>` - Maintenance tasks

#### PR Checklist

Use our [PR template](../.github/pull_request_template.md) and ensure:

- [ ] PR title follows the format guidelines above
- [ ] Activated venv and ran `./code_quality_checks.sh` (all checks passed 100%)
- [ ] Self-review completed
- [ ] Tests added for ALL changes
- [ ] Documentation updated as needed
- [ ] All unit tests passing
- [ ] Relevant simulator tests passing (if tool changes)
- [ ] Ready for review

### 4. Code Style Guidelines

#### Python Code Style
- Follow PEP 8 with Black formatting
- Use type hints for function parameters and returns
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines when possible
- Use descriptive variable names

#### Example:
```python
def process_model_response(
    response: ModelResponse,
    max_tokens: Optional[int] = None
) -> ProcessedResult:
    """Process and validate model response.
    
    Args:
        response: Raw response from the model provider
        max_tokens: Optional token limit for truncation
        
    Returns:
        ProcessedResult with validated and formatted content
        
    Raises:
        ValueError: If response is invalid or exceeds limits
    """
    # Implementation here
```

#### Import Organization
Imports must be organized by isort into these groups:
1. Standard library imports
2. Third-party imports
3. Local application imports

### 5. Specific Contribution Types

#### Adding a New Provider
See our detailed guide: [Adding a New Provider](./adding_providers.md)

#### Adding a New Tool
See our detailed guide: [Adding a New Tool](./adding_tools.md)

#### Modifying Existing Tools
1. Ensure backward compatibility unless explicitly breaking
2. Update all affected tests
3. Update documentation if behavior changes
4. Add simulator tests for new functionality

### 6. Documentation Standards

- Update README.md for user-facing changes
- Add docstrings to all new code
- Update relevant docs/ files
- Include examples for new features
- Keep documentation concise and clear

### 7. Commit Message Guidelines

Write clear, descriptive commit messages:
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed explanation if needed
- Reference issues: "Fixes #123"

Example:
```
feat: Add retry logic to Gemini provider

Implements exponential backoff for transient errors
in Gemini API calls. Retries up to 2 times with
configurable delays.

Fixes #45
```

## Common Issues and Solutions

### Linting Failures
```bash
# Auto-fix most issues
ruff check . --fix
black .
isort .
```

### Test Failures
- Check test output for specific errors
- Run individual tests for debugging: `pytest tests/test_specific.py -xvs`
- Ensure server environment is set up for simulator tests

### Import Errors
- Verify virtual environment is activated
- Check all dependencies are installed: `pip install -r requirements.txt`

## Getting Help

- **Questions**: Open a GitHub issue with the "question" label
- **Bug Reports**: Use the bug report template
- **Feature Requests**: Use the feature request template
- **Discussions**: Use GitHub Discussions for general topics

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Assume good intentions

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes for significant contributions
- Special mentions for exceptional work

Thank you for contributing to Zen MCP Server! Your efforts help make this tool better for everyone.