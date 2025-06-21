# PreCommit Tool - Pre-Commit Validation

**Comprehensive review of staged/unstaged git changes across multiple repositories through workflow-driven investigation**

The `precommit` tool provides thorough validation of git changes before committing, ensuring code quality, requirement compliance, and preventing regressions across multiple repositories. This workflow tool guides Claude through systematic investigation of git changes, repository status, and file modifications across multiple steps before providing expert validation.

## Thinking Mode

**Default is `medium` (8,192 tokens).** Use `high` or `max` for critical releases when thorough validation justifies the token cost.

## How the Workflow Works

The precommit tool implements a **structured workflow** for comprehensive change validation:

**Investigation Phase (Claude-Led):**
1. **Step 1**: Claude describes the validation plan and begins analyzing git status across repositories
2. **Step 2+**: Claude examines changes, diffs, dependencies, and potential impacts
3. **Throughout**: Claude tracks findings, relevant files, issues, and confidence levels
4. **Completion**: Once investigation is thorough, Claude signals completion

**Expert Validation Phase:**
After Claude completes the investigation (unless confidence is **certain**):
- Complete summary of all changes and their context
- Potential issues and regressions identified
- Requirement compliance assessment
- Final recommendations for safe commit

**Special Note**: If you want Claude to perform the entire pre-commit validation without calling another model, you can include "don't use any other model" in your prompt, and Claude will complete the full workflow independently.

## Model Recommendation

Pre-commit validation benefits significantly from models with extended context windows like Gemini Pro, which can analyze extensive changesets across multiple files and repositories simultaneously. This comprehensive view enables detection of cross-file dependencies, architectural inconsistencies, and integration issues that might be missed when reviewing changes in isolation due to context constraints.

## Visual Example

<div align="center">
  <img src="https://github.com/user-attachments/assets/584adfa6-d252-49b4-b5b0-0cd6e97fb2c6" width="950">
</div>

**Prompt Used:**
```
Now use gemini and perform a review and precommit and ensure original requirements are met, no duplication of code or
logic, everything should work as expected
```

How beautiful is that? Claude used `precommit` twice and `codereview` once and actually found and fixed two critical errors before commit!

### Real-world Example

Here's an example where Claude was made to go through changes *it* was asked to make. Its recommendation 
to **Publish all Changes** was made after a rigorous set of prompts where it examined the small set of changes 
from different angles (performance, bugs, anti-patterns etc). After confirming that unit tests were 
passing, it went ahead with an initial review with O3; came back clean - all good to go. O3 was happy, everything looked great.

Then it shared the changes and relevant code with Gemini 2.5 Pro - the following is the outcome:

```
⏺ zen:precommit (MCP)(step: "FINAL VALIDATION COMPLETE. All changes have been thoroughly analyzed and are ready for
                     commit. The modifications successfully fix 4 GitHub CI test failures with high-quality, defensive
                     implementations that maintain architectural integrity and coding standards. No issues or regressions
                      detected.", step_number: 4, total_steps: 4, next_step_required: false, findings: "COMMIT
                     RECOMMENDATION: ✅ APPROVED\n\nSUMMARY OF CHANGES:\n✅ Fixed 4 GitHub CI test failures:\n   -
                     test_openrouter_with_restrictions (Mock iteration issue)  \n   - test_execute_with_branching
                     (Missing metadata)\n   - test_execute_with_revision (Missing metadata)\n   - test_metadata_preserved
                      (Provider type AttributeError)\n\n✅ IMPLEMENTATION QUALITY VERIFIED:\n   - Defensive programming
                     with proper type checking\n   - Error handling with meaningful fallbacks\n   - Backward
                     compatibility maintained\n   - Coding standards followed (no hasattr/getattr in changes)\n   -
                     Architectural patterns preserved\n\n✅ COMPREHENSIVE TESTING:\n   - All originally failing tests
                     pass\n   - Affected functionality: 37/37 tests pass\n   - Provider systems: 16/16 tests pass  \n   -
                      Module imports work correctly\n   - No regressions detected\n\n✅ CHANGE IMPACT ASSESSMENT:\n   -
                     Minimal, targeted changes\n   - No security or performance concerns\n   - Maintains API
                     compatibility\n   - Changes are well-documented with clear comments\n\nRECOMMENDATION: These changes
                      are safe to commit and will resolve the GitHub CI failures without any negative impact.",
  ⎿  {
       "status": "calling_expert_analysis",
       "step_number": 4,
     … +169 lines (ctrl+r to expand)

⏺ 🔍 Pre-Commit Validation Complete

  Based on comprehensive analysis using both O3 and Gemini 2.5 Pro models, I can provide the following assessment:

  ✅ APPROVED WITH CRITICAL FIX REQUIRED

  The changes successfully fix all 4 GitHub CI test failures and are well-implemented with defensive programming
  patterns. However, the expert analysis identified one critical issue that must be addressed before commit:

  🚨 [HIGH PRIORITY] Critical Issue Found

  Inconsistent Provider Handling in tools/base.py
  - Location: tools/base.py line ~1833 in _create_continuation_offer_response method
  - Problem: The defensive provider handling pattern was applied in 2 locations but missed a 3rd location
  - Impact: Risk of AttributeError: 'str' object has no attribute 'get_provider_type' in continuation scenarios
  - Fix Required: Apply the same defensive pattern to the missed location
```

A subtle but critical issue spotted by Gemini that both Claude + O3 missed. This is the power of running these workflows with Zen.

## Example Prompts

```
Use zen and perform a thorough precommit ensuring there aren't any new regressions or bugs introduced
```

## Key Features

- **Recursive repository discovery** - finds all git repos including nested ones
- **Validates changes against requirements** - ensures implementation matches intent
- **Detects incomplete changes** - finds added functions never called, missing tests, etc.
- **Multi-repo support** - reviews changes across multiple repositories in one go
- **Configurable scope** - review staged, unstaged, or compare against branches
- **Security focused** - catches exposed secrets, vulnerabilities in new code
- **Smart truncation** - handles large diffs without exceeding context limits
- **Cross-file dependency analysis** - identifies breaking changes across modules
- **Test coverage validation** - ensures new code has appropriate test coverage
- **Regression detection** - compares against requirements to prevent scope creep

## Tool Parameters

**Workflow Investigation Parameters (used during step-by-step process):**
- `step`: Current investigation step description (required for each step)
- `step_number`: Current step number in validation sequence (required)
- `total_steps`: Estimated total investigation steps (adjustable)
- `next_step_required`: Whether another investigation step is needed
- `findings`: Discoveries and evidence collected in this step (required)
- `files_checked`: All files examined during investigation
- `relevant_files`: Files directly relevant to the changes
- `relevant_context`: Methods/functions/classes affected by changes
- `issues_found`: Issues identified with severity levels
- `confidence`: Confidence level in validation completeness (exploring/low/medium/high/certain)
- `backtrack_from_step`: Step number to backtrack from (for revisions)
- `hypothesis`: Current assessment of change safety and completeness
- `images`: Screenshots of requirements, design mockups for validation

**Initial Configuration (used in step 1):**
- `path`: Starting directory to search for repos (default: current directory, absolute path required)
- `prompt`: The original user request description for the changes (required for context)
- `model`: auto|pro|flash|o3|o3-mini|o4-mini|o4-mini-high|gpt4.1 (default: server default)
- `compare_to`: Compare against a branch/tag instead of local changes (optional)
- `severity_filter`: critical|high|medium|low|all (default: all)
- `include_staged`: Include staged changes in the review (default: true)
- `include_unstaged`: Include uncommitted changes in the review (default: true)
- `focus_on`: Specific aspects to focus on
- `temperature`: Temperature for response (default: 0.2)
- `thinking_mode`: minimal|low|medium|high|max (default: medium, Gemini only)
- `use_websearch`: Enable web search for best practices (default: true)
- `use_assistant_model`: Whether to use expert validation phase (default: true, set to false to use Claude only)
- `continuation_id`: Continue previous validation discussions

## Usage Examples

**Basic Pre-commit Validation:**
```
"Use zen precommit to validate my changes before committing"
```

**Security-Focused Validation:**
```
"Perform precommit security review with gemini pro on the authentication changes"
```

**Multi-Repository Validation:**
```
"Validate changes across all repositories in this workspace with o3"
```

**Against Specific Branch:**
```
"Compare current changes against main branch with precommit using gemini pro"
```

**With Requirements Context:**
```
"Precommit validation ensuring the new payment feature meets requirements in FEATURE_SPEC.md"
```

## Validation Scope

The tool automatically discovers and validates:

**Repository Discovery:**
- Searches recursively for all `.git` directories
- Handles nested repositories and submodules
- Configurable search depth to prevent excessive recursion

**Change Analysis:**
- Staged changes (`git diff --cached`)
- Unstaged changes (`git diff`)
- Untracked files that should be added
- Deleted files and their impact

**Cross-Repository Impact:**
- Shared dependencies between repositories
- API contract changes that affect other repos
- Configuration changes with system-wide impact

## Validation Categories

**Completeness Checks:**
- New functions/classes have corresponding tests
- Documentation updated for API changes
- Configuration files updated as needed
- Migration scripts for database changes

**Quality Assurance:**
- Code follows project standards
- No obvious bugs or logical errors
- Performance implications considered
- Security vulnerabilities addressed

**Requirement Compliance:**
- Implementation matches original requirements
- No scope creep or unauthorized changes
- All acceptance criteria met
- Edge cases properly handled

**Integration Safety:**
- Breaking changes properly documented
- Backward compatibility maintained where required
- Dependencies correctly updated
- Environment-specific changes validated

## Best Practices

- **Provide clear context**: Include the original requirements or feature description
- **Use for significant changes**: Most valuable for features, refactoring, or security updates
- **Review before final commit**: Catch issues before they enter the main branch
- **Include visual context**: Screenshots of requirements or expected behavior
- **Focus validation scope**: Use `focus_on` parameter for specific concerns
- **Multi-stage validation**: Use continuation for iterative improvement

## Output Format

Validation results include:
- **Change Summary**: Overview of what was modified across repositories
- **Requirement Compliance**: How well changes match original intent
- **Completeness Assessment**: Missing tests, documentation, or related changes
- **Security Review**: Potential vulnerabilities or exposed secrets
- **Integration Impact**: Cross-repository and cross-module effects
- **Recommendations**: Specific actions before committing

## When to Use PreCommit vs Other Tools

- **Use `precommit`** for: Validating changes before git commit, ensuring requirement compliance
- **Use `codereview`** for: General code quality assessment without git context
- **Use `debug`** for: Diagnosing specific runtime issues
- **Use `analyze`** for: Understanding existing code without validation context