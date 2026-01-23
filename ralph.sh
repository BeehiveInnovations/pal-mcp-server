#!/bin/bash

# =============================================================================
# Ralph Loop - Zero-Cost Automated Coding Loop
# =============================================================================
#
# This script implements a Ralph Loop that:
# 1. Reads tasks from prd.json
# 2. Uses CLI tools (claude, gemini, codex) for zero-cost AI execution
# 3. Runs code quality checks as the "back-pressure" gate
# 4. Iterates until all tasks pass or max iterations reached
#
# Usage:
#   ./ralph.sh              # Run the loop
#   ./ralph.sh --init       # Initialize with a new PRD
#   ./ralph.sh --status     # Check current status
#   ./ralph.sh --consensus  # Use consensus mode (multi-model)
#
# =============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD_FILE="${SCRIPT_DIR}/prd.json"
PROGRESS_FILE="${SCRIPT_DIR}/progress.txt"
PROMPT_TEMPLATE="${SCRIPT_DIR}/ralph_prompt.md"
RALPH_UTILS="${SCRIPT_DIR}/ralph_utils.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default settings
CLI_TOOL="claude"  # Options: claude, gemini, codex
USE_CONSENSUS=false
MAX_RETRIES=3
SLEEP_BETWEEN_ITERATIONS=2

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Get Python command (prefer venv)
get_python() {
    if [[ -f "${SCRIPT_DIR}/.pal_venv/bin/python" ]]; then
        echo "${SCRIPT_DIR}/.pal_venv/bin/python"
    elif [[ -n "$VIRTUAL_ENV" ]]; then
        echo "python"
    else
        echo "python3"
    fi
}

PYTHON_CMD=$(get_python)

# Check if required tools exist
check_requirements() {
    log_info "Checking requirements..."

    # Check Python utils
    if [[ ! -f "$RALPH_UTILS" ]]; then
        log_error "ralph_utils.py not found at $RALPH_UTILS"
        exit 1
    fi

    # Check for at least one CLI tool
    local has_cli=false
    if command -v claude &> /dev/null; then
        has_cli=true
        log_info "Found: claude CLI"
    fi
    if command -v gemini &> /dev/null; then
        has_cli=true
        log_info "Found: gemini CLI"
    fi
    if command -v codex &> /dev/null; then
        has_cli=true
        log_info "Found: codex CLI"
    fi

    if [[ "$has_cli" == "false" ]]; then
        log_error "No CLI tool found. Install at least one of: claude, gemini, codex"
        exit 1
    fi

    log_success "Requirements check passed"
}

# Initialize a new PRD
init_prd() {
    local project_name="$1"
    local description="$2"
    local tasks_file="$3"

    if [[ -z "$project_name" ]]; then
        echo "Usage: ./ralph.sh --init --name 'Project Name' --description 'Description' [--tasks tasks.json]"
        exit 1
    fi

    log_info "Initializing new PRD: $project_name"

    local cmd="$PYTHON_CMD $RALPH_UTILS init --name '$project_name' --description '$description'"
    if [[ -n "$tasks_file" ]]; then
        cmd="$cmd --tasks-file '$tasks_file'"
    fi

    eval "$cmd"
    log_success "PRD initialized at $PRD_FILE"
}

# Show current status
show_status() {
    log_info "Current Ralph Loop Status"
    echo "=========================================="
    $PYTHON_CMD "$RALPH_UTILS" status
    echo "=========================================="
}

# Get the next task
get_next_task() {
    $PYTHON_CMD "$RALPH_UTILS" next 2>/dev/null
}

# Get context for AI
get_context() {
    $PYTHON_CMD "$RALPH_UTILS" context
}

# Mark task as done
mark_done() {
    local task_id="$1"
    local notes="$2"
    $PYTHON_CMD "$RALPH_UTILS" done "$task_id" --notes "$notes"
}

# Mark task as failed
mark_failed() {
    local task_id="$1"
    local error="$2"
    $PYTHON_CMD "$RALPH_UTILS" fail "$task_id" --error "$error"
}

# Mark task as in progress
mark_in_progress() {
    local task_id="$1"
    $PYTHON_CMD "$RALPH_UTILS" start "$task_id"
}

# Record a learning
record_learning() {
    local message="$1"
    $PYTHON_CMD "$RALPH_UTILS" learn "$message"
}

# Check if should continue
should_continue() {
    $PYTHON_CMD "$RALPH_UTILS" check 2>/dev/null
    return $?
}

# Increment iteration
increment_iteration() {
    $PYTHON_CMD "$RALPH_UTILS" iterate
}

# Build the prompt for the AI
build_prompt() {
    local context
    context=$(get_context)

    # Read the template and substitute context
    if [[ -f "$PROMPT_TEMPLATE" ]]; then
        sed "s|{context}|$context|g" "$PROMPT_TEMPLATE"
    else
        # Fallback if template doesn't exist
        echo "$context"
        echo ""
        echo "Complete this task. Run ./code_quality_checks.sh after making changes."
    fi
}

# Run code quality checks (back-pressure gate)
run_quality_checks() {
    log_step "Running code quality checks..."

    if [[ -f "${SCRIPT_DIR}/code_quality_checks.sh" ]]; then
        if "${SCRIPT_DIR}/code_quality_checks.sh"; then
            log_success "All quality checks passed"
            return 0
        else
            log_error "Quality checks failed"
            return 1
        fi
    else
        log_warning "code_quality_checks.sh not found, skipping"
        return 0
    fi
}

# Execute task with Claude CLI
execute_with_claude() {
    local prompt="$1"
    local task_id="$2"

    log_step "Executing task #$task_id with Claude CLI..."

    # Use claude with --print for non-interactive mode
    # The prompt is passed via stdin
    echo "$prompt" | claude --print 2>&1

    return $?
}

# Execute task with Gemini CLI
execute_with_gemini() {
    local prompt="$1"
    local task_id="$2"

    log_step "Executing task #$task_id with Gemini CLI..."

    # Use gemini CLI
    echo "$prompt" | gemini 2>&1

    return $?
}

# Execute task with Codex CLI
execute_with_codex() {
    local prompt="$1"
    local task_id="$2"

    log_step "Executing task #$task_id with Codex CLI..."

    # Use codex CLI
    codex "$prompt" 2>&1

    return $?
}

# Execute task with the selected CLI tool
execute_task() {
    local prompt="$1"
    local task_id="$2"

    case "$CLI_TOOL" in
        claude)
            execute_with_claude "$prompt" "$task_id"
            ;;
        gemini)
            execute_with_gemini "$prompt" "$task_id"
            ;;
        codex)
            execute_with_codex "$prompt" "$task_id"
            ;;
        *)
            log_error "Unknown CLI tool: $CLI_TOOL"
            return 1
            ;;
    esac
}

# Execute with consensus (multiple models)
execute_with_consensus() {
    local task_id="$1"

    log_step "Executing task #$task_id with Consensus (multi-model)..."

    # Get the consensus prompt
    local consensus_prompt
    consensus_prompt=$($PYTHON_CMD "$RALPH_UTILS" consensus-prompt)

    # Use the PAL MCP consensus tool via the CLI
    # This calls multiple models concurrently for zero-cost decision making
    log_info "Consulting models: cli:gemini, cli:claude for consensus..."

    # For now, we use claude CLI with a consensus-style prompt
    # In a full implementation, this would call the MCP server's consensus tool
    local full_prompt="You are participating in a consensus decision. Multiple models are being consulted.

$consensus_prompt

Provide your analysis and recommendation. Be specific about:
1. Recommended approach
2. Key implementation steps
3. Potential risks
4. Success criteria verification method"

    echo "$full_prompt" | claude --print 2>&1

    return $?
}

# Main loop iteration
run_iteration() {
    local iteration
    iteration=$(increment_iteration)

    echo ""
    echo "=============================================="
    log_info "Ralph Loop - Iteration $iteration"
    echo "=============================================="

    # Get next task
    local task_json
    task_json=$(get_next_task) || {
        log_success "No more tasks to process!"
        return 1
    }

    local task_id
    task_id=$(echo "$task_json" | $PYTHON_CMD -c "import sys,json; print(json.load(sys.stdin)['id'])")
    local task_desc
    task_desc=$(echo "$task_json" | $PYTHON_CMD -c "import sys,json; print(json.load(sys.stdin)['description'])")

    log_info "Task #$task_id: $task_desc"

    # Mark task as in progress
    mark_in_progress "$task_id"

    # Build the prompt
    local prompt
    prompt=$(build_prompt)

    # Execute the task
    local output
    local exec_status

    if [[ "$USE_CONSENSUS" == "true" ]]; then
        output=$(execute_with_consensus "$task_id" 2>&1)
        exec_status=$?
    else
        output=$(execute_task "$prompt" "$task_id" 2>&1)
        exec_status=$?
    fi

    echo "$output"

    if [[ $exec_status -ne 0 ]]; then
        log_error "Task execution failed"
        mark_failed "$task_id" "CLI execution failed with status $exec_status"
        record_learning "Task #$task_id failed: CLI returned non-zero status"
        return 0  # Continue loop
    fi

    # Run quality checks (back-pressure gate)
    if run_quality_checks; then
        log_success "Task #$task_id completed successfully!"
        mark_done "$task_id" "Completed in iteration $iteration"
        record_learning "Task #$task_id succeeded on attempt"

        # Git commit the changes
        if command -v git &> /dev/null && [[ -d "${SCRIPT_DIR}/.git" ]]; then
            log_step "Committing changes..."
            cd "$SCRIPT_DIR"
            git add -A
            git commit -m "Ralph Loop: Completed task #$task_id - $task_desc" || true
        fi
    else
        log_warning "Task #$task_id: Quality checks failed, will retry"
        local error_msg="Quality checks failed in iteration $iteration"
        mark_failed "$task_id" "$error_msg"
        record_learning "Task #$task_id failed quality checks: needs fixes"

        # Reset task to pending for retry
        $PYTHON_CMD "$RALPH_UTILS" start "$task_id" 2>/dev/null || true
    fi

    return 0
}

# Main loop
run_loop() {
    check_requirements

    if [[ ! -f "$PRD_FILE" ]]; then
        log_error "No prd.json found. Initialize with: ./ralph.sh --init --name 'Project' --description 'Description'"
        exit 1
    fi

    log_info "Starting Ralph Loop..."
    show_status

    local iteration_count=0
    local max_iterations=100

    while should_continue; do
        ((iteration_count++))

        if [[ $iteration_count -gt $max_iterations ]]; then
            log_error "Max iterations ($max_iterations) reached. Stopping."
            break
        fi

        run_iteration || break

        # Small delay between iterations
        sleep "$SLEEP_BETWEEN_ITERATIONS"
    done

    echo ""
    echo "=============================================="
    log_success "Ralph Loop Complete!"
    echo "=============================================="
    show_status

    # Show final summary
    log_info "Progress log: $PROGRESS_FILE"
    if [[ -f "$PROGRESS_FILE" ]]; then
        echo ""
        echo "Recent progress:"
        tail -10 "$PROGRESS_FILE"
    fi
}

# =============================================================================
# CLI Argument Parsing
# =============================================================================

show_help() {
    cat << EOF
Ralph Loop - Zero-Cost Automated Coding Loop

Usage:
  ./ralph.sh                    Run the Ralph Loop
  ./ralph.sh --init             Initialize a new PRD
  ./ralph.sh --status           Show current status
  ./ralph.sh --consensus        Run with consensus mode (multi-model)
  ./ralph.sh --cli <tool>       Use specific CLI tool (claude|gemini|codex)
  ./ralph.sh --help             Show this help

Init Options:
  --name <name>                 Project name (required for --init)
  --description <desc>          Project description (required for --init)
  --tasks <file>                JSON file with tasks (optional)

Examples:
  # Initialize a new project
  ./ralph.sh --init --name "My Project" --description "Building feature X"

  # Run with default settings (claude)
  ./ralph.sh

  # Run with consensus mode
  ./ralph.sh --consensus

  # Run with specific CLI tool
  ./ralph.sh --cli gemini

EOF
}

# Parse arguments
INIT_MODE=false
PROJECT_NAME=""
PROJECT_DESC=""
TASKS_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --init)
            INIT_MODE=true
            shift
            ;;
        --name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --description)
            PROJECT_DESC="$2"
            shift 2
            ;;
        --tasks)
            TASKS_FILE="$2"
            shift 2
            ;;
        --status)
            show_status
            exit 0
            ;;
        --consensus)
            USE_CONSENSUS=true
            shift
            ;;
        --cli)
            CLI_TOOL="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
if [[ "$INIT_MODE" == "true" ]]; then
    if [[ -z "$PROJECT_NAME" ]] || [[ -z "$PROJECT_DESC" ]]; then
        log_error "Both --name and --description are required for --init"
        show_help
        exit 1
    fi
    init_prd "$PROJECT_NAME" "$PROJECT_DESC" "$TASKS_FILE"
else
    run_loop
fi
