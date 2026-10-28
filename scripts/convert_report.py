import json
import os

json_path = "/home/kali/.pal/plan_runs/run_20261006-190821.json"
md_path = "/home/kali/Desktop/BEON_COMPREHENSIVE_AUTH_REPORT.md"

if not os.path.exists(json_path):
    print(f"Error: {json_path} not found.")
    exit(1)

with open(json_path, "r") as f:
    data = json.load(f)

plan_file = data.get("plan", "N/A")
steps_run = data.get("steps_run", 0)
steps = data.get("steps", [])

md_lines = [
    "# Comprehensive Authentication Security Assessment Report",
    f"**Target:** `https://stage.app.beon.chat/login`",
    f"**Plan Source:** `{plan_file}`",
    f"**Total Steps Executed:** {steps_run}",
    f"**Date:** October 6, 2026",
    "",
    "---",
    "",
    "## Executive Summary",
    "This report consolidates the findings from PAL's orchestrated, multi-step autonomous security assessment (utilizing native `secsuite` MCP tool capabilities instead of desktop binaries) against the Beon Chat staging authentication portal. The assessment covered endpoint reconnaissance, API route discovery via SPA assets, session token analysis, and rate-limiting evaluation.",
    "",
    "---",
    "",
    "## Detailed Step-by-Step Execution & Findings",
    ""
]

for s in steps:
    step_num = s.get("step", "N/A")
    task_desc = s.get("task", "N/A")
    result = s.get("result", "N/A")
    tools_used = s.get("tools_used", [])

    md_lines.append(f"### Step {step_num}: {task_desc}")
    md_lines.append("")
    md_lines.append(f"**Result / Analysis:**")
    md_lines.append(f"{result}")
    md_lines.append("")
    if tools_used:
        md_lines.append(f"**Tools / Commands Executed:**")
        for t in tools_used:
            tool_name = t.get("tool", "unknown")
            args = t.get("args", {})
            md_lines.append(f"- `{tool_name}`: `{args}`")
        md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

md_lines.append("## Recommendations for Manual Testing")
md_lines.append("1. **API Endpoint Enumeration**: Trace all network calls in proxy history during login flow to identify API base paths (e.g., `/api/v1/auth`).")
md_lines.append("2. **JWT & Cookie Security**: Use PAL's native `secsuite` tool (`jwt_decode`, `jwt_forge`) to audit token integrity and verify session cookie flags (`HttpOnly`, `Secure`, `SameSite`).")
md_lines.append("3. **Rate Limiting & Brute Force**: Test account lockout thresholds using parallel requests (`secsuite` send_parallel).")
md_lines.append("4. **CSRF & Header Validation**: Verify if custom headers are strictly enforced by the backend.")

with open(md_path, "w") as f:
    f.write("\n".join(md_lines))

print(f"Successfully generated markdown report at {md_path}")
