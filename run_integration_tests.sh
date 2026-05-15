#!/bin/bash

# PAL MCP Server - Run Integration Tests
# This script runs integration tests that require API keys
# Run this locally on your Mac to ensure everything works end-to-end

set -e  # Exit on any error

echo "🧪 Running Integration Tests for PAL MCP Server"
echo "=============================================="
echo "These tests use real API calls with your configured keys"
echo ""

# Activate virtual environment
if [[ -f ".pal_venv/bin/activate" ]]; then
    source .pal_venv/bin/activate
    echo "✅ Using virtual environment"
else
    echo "❌ No virtual environment found!"
    echo "Please run: ./run-server.sh first"
    exit 1
fi

# Check for .env file
if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: No .env file found. Integration tests may fail without API keys."
    echo ""
fi

echo "🔑 Checking API key availability:"
echo "---------------------------------"

# Check which API keys are available
if [[ -n "$GEMINI_API_KEY" ]] || grep -q "GEMINI_API_KEY=" .env 2>/dev/null; then
    echo "✅ GEMINI_API_KEY configured"
else
    echo "❌ GEMINI_API_KEY not found"
fi

if [[ -n "$OPENAI_API_KEY" ]] || grep -q "OPENAI_API_KEY=" .env 2>/dev/null; then
    echo "✅ OPENAI_API_KEY configured"
else
    echo "❌ OPENAI_API_KEY not found"
fi

if [[ -n "$XAI_API_KEY" ]] || grep -q "XAI_API_KEY=" .env 2>/dev/null; then
    echo "✅ XAI_API_KEY configured"
else
    echo "❌ XAI_API_KEY not found"
fi

if [[ -n "$ZAI_API_KEY" ]] || grep -q "ZAI_API_KEY=" .env 2>/dev/null; then
    echo "✅ ZAI_API_KEY configured"
else
    echo "❌ ZAI_API_KEY not found"
fi

if [[ -n "$OPENROUTER_API_KEY" ]] || grep -q "OPENROUTER_API_KEY=" .env 2>/dev/null; then
    echo "✅ OPENROUTER_API_KEY configured"
else
    echo "❌ OPENROUTER_API_KEY not found"
fi

if [[ -n "$CUSTOM_API_URL" ]] || grep -q "CUSTOM_API_URL=" .env 2>/dev/null; then
    echo "✅ CUSTOM_API_URL configured (local models)"
else
    echo "❌ CUSTOM_API_URL not found"
fi

echo ""

# Run integration tests
echo "🏃 Running integration tests..."
echo "------------------------------"

# Run only integration tests (marked with @pytest.mark.integration)
python -m pytest tests/ -v -m "integration" --tb=short

echo ""
echo "✅ Integration tests completed!"
echo ""

# Also run simulator tests if requested
if [[ "$1" == "--with-simulator" ]]; then
    echo "🤖 Running simulator tests..."
    echo "----------------------------"
    python communication_simulator_test.py --verbose
    echo ""
    echo "✅ Simulator tests completed!"
fi

echo "💡 Tips:"
echo "- Run './run_integration_tests.sh' for integration tests only"
echo "- Run './run_integration_tests.sh --with-simulator' to also run simulator tests"
echo "- Run './code_quality_checks.sh' for unit tests and linting"
echo "- Check logs in logs/mcp_server.log if tests fail"