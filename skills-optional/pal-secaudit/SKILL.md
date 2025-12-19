---
name: pal-secaudit
description: Performs security audit and vulnerability analysis, identifying security issues, OWASP risks, and secure coding violations.
allowed-tools: Bash, Read
---

# PAL SecAudit

## Overview

Security-focused code analysis identifying vulnerabilities, OWASP risks, and secure coding violations. Uses multi-step workflow for thorough security review.

## When to Use

- Security code reviews
- Vulnerability assessment
- OWASP compliance checking
- Pre-deployment security validation

## Workflow

Multi-step security audit:
1. Define audit strategy (OWASP Top 10, auth, validation)
2. Analyze authentication and authorization
3. Check input validation and injection risks
4. Review data handling and encryption
5. Final security assessment

## Parameters

### Required (Workflow Fields)
- `step` (string): Audit strategy and current findings
- `step_number` (integer): Current step number (starts at 1)
- `total_steps` (integer): Estimated total steps
- `next_step_required` (boolean): Whether more analysis needed
- `findings` (string): Vulnerabilities, auth issues, validation gaps

### Optional
- `files_checked` (string[]): Files inspected (absolute paths)
- `relevant_files` (string[]): Security-relevant files (absolute paths)
- `audit_focus` (string): owasp, compliance, infrastructure, dependencies
- `security_scope` (string): web, mobile, API, cloud
- `compliance_requirements` (string[]): SOC2, PCI DSS, HIPAA, etc.
- `threat_level` (string): low, medium, high
- `severity_filter` (string): Minimum severity to report
- `issues_found` (object[]): Vulnerabilities with severity
- `hypothesis` (string): Current theory about risks
- `confidence` (string): exploring, low, medium, high, very_high
- `model` (string): Specific model to use (default: auto-select)
- `continuation_id` (string): Continue previous audit
- `thinking_mode` (string): Reasoning depth
- `temperature` (number): 0 = deterministic, 1 = creative
- `use_assistant_model` (boolean): Use expert model for analysis
- `images` (string[]): Diagrams or threat models

## Output

JSON with vulnerabilities found, severity levels, and remediation steps.

## Invocation

```bash
# Start security audit (step 1)
pal-secaudit --step "Define audit strategy" --step_number 1 --total_steps 5 --next_step_required true --findings ""

# Continue audit (step 2+)
pal-secaudit --step "Check authentication" --step_number 2 --total_steps 5 --next_step_required true --findings "JWT implementation found" --continuation_id "abc-123"

# With specific focus
pal-secaudit --step "OWASP Top 10 review" --step_number 1 --total_steps 4 --next_step_required true --findings "" --audit_focus owasp --relevant_files '["./src/api.py"]'
```

## Model Selection

- Default: auto - System automatically selects the best available model
- Do NOT specify `--model` unless you have a specific reason - let the system choose
- If you must specify, use `pal-listmodels` to see available model names first
