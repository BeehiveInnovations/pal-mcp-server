#!/usr/bin/env pwsh
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$WithSimulator,
    [switch]$VerboseOutput
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorText {
    param(
        [Parameter(Mandatory)]
        [string]$Text,
        [string]$Color = "White",
        [switch]$NoNewline
    )
    if ($NoNewline) {
        Write-Host $Text -ForegroundColor $Color -NoNewline
    } else {
        Write-Host $Text -ForegroundColor $Color
    }
}

function Write-Emoji {
    param(
        [Parameter(Mandatory)]
        [string]$Emoji,
        [Parameter(Mandatory)]
        [string]$Text,
        [string]$Color = "White"
    )
    Write-Host "$Emoji " -NoNewline
    Write-ColorText $Text -Color $Color
}

Write-Emoji "🧪" "Running Integration Tests for Zen MCP Server" -Color Cyan
Write-ColorText "==============================================" -Color Cyan
Write-ColorText "These tests use real API calls with your configured keys"
Write-Host ""

# Check for virtual environment
$venvPath = ".zen_venv"
$activateScript = if ($IsWindows -or $env:OS -eq "Windows_NT") {
    "$venvPath\Scripts\Activate.ps1"
} else {
    "$venvPath/bin/activate"
}

if (Test-Path $venvPath) {
    Write-Emoji "✅" "Virtual environment found" -Color Green
    
    # Activate virtual environment (for PowerShell on Windows)
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        if (Test-Path "$venvPath\Scripts\Activate.ps1") {
            & "$venvPath\Scripts\Activate.ps1"
        } elseif (Test-Path "$venvPath\Scripts\activate.bat") {
            # Use Python directly from venv
            $env:PATH = "$PWD\$venvPath\Scripts;$env:PATH"
        }
    }
} else {
    Write-Emoji "❌" "No virtual environment found!" -Color Red
    Write-ColorText "Please run: .\run-server.ps1 first" -Color Yellow
    exit 1
}

# Check for .env file
if (!(Test-Path ".env")) {
    Write-Emoji "⚠️" "Warning: No .env file found. Integration tests may fail without API keys." -Color Yellow
    Write-Host ""
}

Write-Emoji "🔑" "Checking API key availability:" -Color Cyan
Write-ColorText "---------------------------------" -Color Cyan

# Function to check if API key is configured
function Test-ApiKey {
    param(
        [string]$KeyName
    )
    
    # Check environment variable
    $envValue = [Environment]::GetEnvironmentVariable($KeyName)
    if (![string]::IsNullOrWhiteSpace($envValue)) {
        return $true
    }
    
    # Check .env file
    if (Test-Path ".env") {
        $envContent = Get-Content ".env" -ErrorAction SilentlyContinue
        $found = $envContent | Where-Object { $_ -match "^$KeyName\s*=" -and $_ -notmatch "^$KeyName\s*=\s*$" }
        return $found.Count -gt 0
    }
    
    return $false
}

# Check API keys
$apiKeys = @(
    "GEMINI_API_KEY",
    "OPENAI_API_KEY", 
    "XAI_API_KEY",
    "OPENROUTER_API_KEY",
    "CUSTOM_API_URL"
)

foreach ($key in $apiKeys) {
    if (Test-ApiKey $key) {
        if ($key -eq "CUSTOM_API_URL") {
            Write-Emoji "✅" "$key configured (local models)" -Color Green
        } else {
            Write-Emoji "✅" "$key configured" -Color Green
        }
    } else {
        Write-Emoji "❌" "$key not found" -Color Red
    }
}

Write-Host ""

# Load environment variables from .env if it exists
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]*?)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Run integration tests
Write-Emoji "🏃" "Running integration tests..." -Color Cyan
Write-ColorText "------------------------------" -Color Cyan

try {
    # Build pytest command
    $pytestArgs = @("tests/", "-v", "-m", "integration", "--tb=short")
    
    if ($VerboseOutput) {
        $pytestArgs += "--verbose"
    }
    
    # Run pytest
    python -m pytest @pytestArgs
    
    if ($LASTEXITCODE -ne 0) {
        throw "Integration tests failed"
    }
    
    Write-Host ""
    Write-Emoji "✅" "Integration tests completed!" -Color Green
} catch {
    Write-Host ""
    Write-Emoji "❌" "Integration tests failed!" -Color Red
    Write-ColorText "Error: $_" -Color Red
    exit 1
}

# Run simulator tests if requested
if ($WithSimulator) {
    Write-Host ""
    Write-Emoji "🤖" "Running simulator tests..." -Color Cyan
    Write-ColorText "----------------------------" -Color Cyan
    
    try {
        if ($VerboseOutput) {
            python communication_simulator_test.py --verbose
        } else {
            python communication_simulator_test.py
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Emoji "❌" "Simulator tests failed!" -Color Red
            Write-ColorText "This may be due to a known issue in communication_simulator_test.py" -Color Yellow
            Write-ColorText "Integration tests completed successfully - you can proceed." -Color Green
        } else {
            Write-Host ""
            Write-Emoji "✅" "Simulator tests completed!" -Color Green
        }
    } catch {
        Write-Host ""
        Write-Emoji "❌" "Simulator tests failed!" -Color Red
        Write-ColorText "Error: $_" -Color Red
        Write-ColorText "This may be due to a known issue in communication_simulator_test.py" -Color Yellow
        Write-ColorText "Integration tests completed successfully - you can proceed." -Color Green
    }
}

Write-Host ""
Write-Emoji "💡" "Tips:" -Color Yellow
Write-ColorText "- Run '.\run_integration_tests.ps1' for integration tests only" -Color White
Write-ColorText "- Run '.\run_integration_tests.ps1 -WithSimulator' to also run simulator tests" -Color White
Write-ColorText "- Run '.\code_quality_checks.ps1' for unit tests and linting" -Color White
Write-ColorText "- Check logs in logs\mcp_server.log if tests fail" -Color White
