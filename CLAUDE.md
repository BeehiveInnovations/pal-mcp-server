# Claude Development Guide for Zen MCP Server

This file contains essential commands and workflows for developing and maintaining the Zen MCP Server when working with Claude. Use these instructions to efficiently run quality checks, manage the server, check logs, and run tests.

## Quick Reference Commands

### Code Quality Checks

Before making any changes or submitting PRs, always run the comprehensive quality checks:

```bash
# Activate virtual environment first
source venv/bin/activate

# Run all quality checks (linting, formatting, tests)
./code_quality_checks.sh
```

This script automatically runs:
- Ruff linting with auto-fix
- Black code formatting 
- Import sorting with isort
- Complete unit test suite
- Verification that all checks pass 100%

### Server Management

#### Setup/Update the Server
```bash
# Run setup script (handles everything)
./run-server.sh
```

This script will:
- Set up Python virtual environment
- Install all dependencies
- Create/update .env file
- Configure MCP with Claude
- Verify API keys

#### View Logs
```bash
# Follow logs in real-time
./run-server.sh -f

# Or manually view logs
tail -f logs/mcp_server.log
```

### Log Management

#### View Server Logs
```bash
# View last 500 lines of server logs
tail -n 500 logs/mcp_server.log

# Follow logs in real-time
tail -f logs/mcp_server.log

# View specific number of lines
tail -n 100 logs/mcp_server.log

# Search logs for specific patterns
grep "ERROR" logs/mcp_server.log
grep "tool_name" logs/mcp_activity.log
```

#### Monitor Tool Executions Only
```bash
# View tool activity log (focused on tool calls and completions)
tail -n 100 logs/mcp_activity.log

# Follow tool activity in real-time
tail -f logs/mcp_activity.log

# Use the dedicated log monitor (shows tool calls, completions, errors)
python log_monitor.py
```

The `log_monitor.py` script provides a real-time view of:
- Tool calls and completions
- Conversation resumptions and context
- Errors and warnings from all log files
- File rotation handling

#### All Available Log Files
```bash
# Main server log (all activity)
tail -f logs/mcp_server.log

# Tool activity only (TOOL_CALL, TOOL_COMPLETED, etc.)
tail -f logs/mcp_activity.log

# Debug information (if configured)
tail -f logs/debug.log
```

### Testing

Simulation tests are available to test the MCP server in a 'live' scenario, using your configured
API keys to ensure the models are working and the server is able to communicate back and forth. 

**IMPORTANT**: After any code changes, restart your Claude session for the changes to take effect.

#### Run All Simulator Tests
```bash
# Run the complete test suite
python communication_simulator_test.py

# Run tests with verbose output
python communication_simulator_test.py --verbose
```

#### Run Individual Simulator Tests (Recommended)
```bash
# List all available tests
python communication_simulator_test.py --list-tests

# RECOMMENDED: Run tests individually for better isolation and debugging
python communication_simulator_test.py --individual basic_conversation
python communication_simulator_test.py --individual content_validation
python communication_simulator_test.py --individual cross_tool_continuation
python communication_simulator_test.py --individual memory_validation

# Run multiple specific tests
python communication_simulator_test.py --tests basic_conversation content_validation

# Run individual test with verbose output for debugging
python communication_simulator_test.py --individual memory_validation --verbose
```

Available simulator tests include:
- `basic_conversation` - Basic conversation flow with chat tool
- `content_validation` - Content validation and duplicate detection
- `per_tool_deduplication` - File deduplication for individual tools
- `cross_tool_continuation` - Cross-tool conversation continuation scenarios
- `cross_tool_comprehensive` - Comprehensive cross-tool file deduplication and continuation
- `line_number_validation` - Line number handling validation across tools
- `memory_validation` - Conversation memory validation
- `model_thinking_config` - Model-specific thinking configuration behavior
- `o3_model_selection` - O3 model selection and usage validation
- `ollama_custom_url` - Ollama custom URL endpoint functionality
- `openrouter_fallback` - OpenRouter fallback behavior when only provider
- `openrouter_models` - OpenRouter model functionality and alias mapping
- `token_allocation_validation` - Token allocation and conversation history validation
- `testgen_validation` - TestGen tool validation with specific test function
- `refactor_validation` - Refactor tool validation with codesmells
- `conversation_chain_validation` - Conversation chain and threading validation
- `consensus_stance` - Consensus tool validation with stance steering (for/against/neutral)

**Note**: All simulator tests should be run individually for optimal testing and better error isolation.

#### Run Unit Tests Only
```bash
# Run all unit tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_refactor.py -v

# Run specific test function
python -m pytest tests/test_refactor.py::TestRefactorTool::test_format_response -v

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

### Development Workflow

#### Before Making Changes
1. Ensure virtual environment is activated: `source venv/bin/activate`
2. Run quality checks: `./code_quality_checks.sh`
3. Check logs to ensure server is healthy: `tail -n 50 logs/mcp_server.log`

#### After Making Changes
1. Run quality checks again: `./code_quality_checks.sh`
2. Run relevant simulator tests: `python communication_simulator_test.py --individual <test_name>`
3. Check logs for any issues: `tail -n 100 logs/mcp_server.log`
4. Restart Claude session to use updated code

#### Before Committing/PR
1. Final quality check: `./code_quality_checks.sh`
2. Run full simulator test suite: `python communication_simulator_test.py`
3. Verify all tests pass 100%

### Common Troubleshooting

#### Server Issues
```bash
# Check if Python environment is set up correctly
./run-server.sh

# View recent errors
grep "ERROR" logs/mcp_server.log | tail -20

# Check virtual environment
which python
# Should show: .../zen-mcp-server/.zen_venv/bin/python
```

#### Test Failures
```bash
# Run individual failing test with verbose output
python communication_simulator_test.py --individual <test_name> --verbose

# Check server logs during test execution
tail -f logs/mcp_server.log

# Run tests with debug output
LOG_LEVEL=DEBUG python communication_simulator_test.py --individual <test_name>
```

#### Linting Issues
```bash
# Auto-fix most linting issues
ruff check . --fix
black .
isort .

# Check what would be changed without applying
ruff check .
black --check .
isort --check-only .
```

### File Structure Context

- `./code_quality_checks.sh` - Comprehensive quality check script
- `./run-server.sh` - Server setup and management
- `communication_simulator_test.py` - End-to-end testing framework
- `simulator_tests/` - Individual test modules
- `tests/` - Unit test suite
- `tools/` - MCP tool implementations
- `providers/` - AI provider implementations
- `systemprompts/` - System prompt definitions
- `logs/` - Server log files

### Environment Requirements

- Python 3.9+ with virtual environment
- All dependencies from `requirements.txt` installed
- Proper API keys configured in `.env` file

This guide provides everything needed to efficiently work with the Zen MCP Server codebase using Claude. Always run quality checks before and after making changes to ensure code integrity.