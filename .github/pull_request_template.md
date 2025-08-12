## PR Title Format

**Please ensure your PR title follows [Conventional Commits](https://www.conventionalcommits.org/) format:**

### Version Bumping Types (trigger semantic release):
- `feat: <description>` - New features → **MINOR** version bump (1.1.0 → 1.2.0)
- `fix: <description>` - Bug fixes → **PATCH** version bump (1.1.0 → 1.1.1) 
- `perf: <description>` - Performance improvements → **PATCH** version bump (1.1.0 → 1.1.1)

### Breaking Changes (trigger MAJOR version bump):
For breaking changes, use any commit type above with `BREAKING CHANGE:` in the commit body or `!` after the type:
- `feat!: <description>` → **MAJOR** version bump (1.1.0 → 2.0.0)
- `fix!: <description>` → **MAJOR** version bump (1.1.0 → 2.0.0)

### Non-Versioning Types (no release):
- `build: <description>` - Build system changes
- `chore: <description>` - Maintenance tasks
- `ci: <description>` - CI/CD changes
- `docs: <description>` - Documentation only
- `refactor: <description>` - Code refactoring (no functional changes)
- `style: <description>` - Code style/formatting changes
- `test: <description>` - Test additions/changes

### Docker Build Triggering:

Docker builds are **independent** of versioning and trigger based on:

**Automatic**: When PRs modify relevant files:
- Python files (`*.py`), `requirements*.txt`, `pyproject.toml`
- Docker files (`Dockerfile`, `docker-compose.yml`, `.dockerignore`)

**Manual**: Add the `docker-build` label to force builds for any PR.

## Description

Please provide a clear and concise description of what this PR does.

## Changes Made

- [ ] List the specific changes made
- [ ] Include any breaking changes
- [ ] Note any dependencies added/removed

## Testing

**Please review our [Testing Guide](../docs/testing.md) before submitting.**

### Run all linting and tests (required):
```bash
# Activate virtual environment first
source venv/bin/activate

# Run comprehensive code quality checks (recommended)
./code_quality_checks.sh

# If you made tool changes, also run simulator tests
python communication_simulator_test.py
```

- [ ] All linting passes (ruff, black, isort)
- [ ] All unit tests pass
- [ ] **For new features**: Unit tests added in `tests/`
- [ ] **For tool changes**: Simulator tests added in `simulator_tests/`
- [ ] **For bug fixes**: Tests added to prevent regression
- [ ] Simulator tests pass (if applicable)
- [ ] Manual testing completed with realistic scenarios

## Related Issues

Fixes #(issue number)

## Checklist

- [ ] PR title follows the format guidelines above
- [ ] **Activated venv and ran code quality checks: `source venv/bin/activate && ./code_quality_checks.sh`**
- [ ] Self-review completed
- [ ] **Tests added for ALL changes** (see Testing section above)
- [ ] Documentation updated as needed
- [ ] All unit tests passing
- [ ] Relevant simulator tests passing (if tool changes)
- [ ] Ready for review

## Additional Notes

Any additional information that reviewers should know.