#!/usr/bin/env pwsh
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipLinting,
    [switch]$VerboseOutput
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorText {
    param(
        [Parameter(Mandatory)]
        [string]$Text,
        [string]$Color = "White"
    )
    Write-Host $Text -ForegroundColor $Color
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

Write-Emoji "🔍" "Running Code Quality Checks for Zen MCP Server" -Color Cyan
Write-ColorText "=================================================" -Color Cyan

# Determine Python command
$pythonCmd = $null
$pipCmd = $null

if (Test-Path ".zen_venv") {
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        if (Test-Path ".zen_venv\Scripts\python.exe") {
            $pythonCmd = ".zen_venv\Scripts\python.exe"
            $pipCmd = ".zen_venv\Scripts\pip.exe"
        }
    } else {
        if (Test-Path ".zen_venv/bin/python") {
            $pythonCmd = ".zen_venv/bin/python"
            $pipCmd = ".zen_venv/bin/pip"
        }
    }
    
    if ($pythonCmd) {
        Write-Emoji "✅" "Using venv" -Color Green
    }
} elseif ($env:VIRTUAL_ENV) {
    $pythonCmd = "python"
    $pipCmd = "pip"
    Write-Emoji "✅" "Using activated virtual environment: $env:VIRTUAL_ENV" -Color Green
} else {
    Write-Emoji "❌" "No virtual environment found!" -Color Red
    Write-ColorText "Please run: .\run-server.ps1 first to set up the environment" -Color Yellow
    exit 1
}

Write-Host ""

# Check and install dev dependencies if needed
Write-Emoji "🔍" "Checking development dependencies..." -Color Cyan
$devDepsNeeded = $false

# List of dev tools to check
$devTools = @("ruff", "black", "isort", "pytest")

foreach ($tool in $devTools) {
    $toolFound = $false
    
    # Check in venv
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        if (Test-Path ".zen_venv\Scripts\$tool.exe") {
            $toolFound = $true
        }
    } else {
        if (Test-Path ".zen_venv/bin/$tool") {
            $toolFound = $true
        }
    }
    
    # Check in PATH
    if (!$toolFound) {
        try {
            $null = Get-Command $tool -ErrorAction Stop
            $toolFound = $true
        } catch {
            # Tool not found
        }
    }
    
    if (!$toolFound) {
        $devDepsNeeded = $true
        break
    }
}

if ($devDepsNeeded) {
    Write-Emoji "📦" "Installing development dependencies..." -Color Yellow
    try {
        & $pipCmd install -q -r requirements-dev.txt
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install dev dependencies"
        }
        Write-Emoji "✅" "Development dependencies installed" -Color Green
    } catch {
        Write-Emoji "❌" "Failed to install development dependencies" -Color Red
        Write-ColorText "Error: $_" -Color Red
        exit 1
    }
} else {
    Write-Emoji "✅" "Development dependencies already installed" -Color Green
}

# Set tool paths
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $ruffCmd = if (Test-Path ".zen_venv\Scripts\ruff.exe") { ".zen_venv\Scripts\ruff.exe" } else { "ruff" }
    $blackCmd = if (Test-Path ".zen_venv\Scripts\black.exe") { ".zen_venv\Scripts\black.exe" } else { "black" }
    $isortCmd = if (Test-Path ".zen_venv\Scripts\isort.exe") { ".zen_venv\Scripts\isort.exe" } else { "isort" }
    $pytestCmd = if (Test-Path ".zen_venv\Scripts\pytest.exe") { ".zen_venv\Scripts\pytest.exe" } else { "pytest" }
} else {
    $ruffCmd = if (Test-Path ".zen_venv/bin/ruff") { ".zen_venv/bin/ruff" } else { "ruff" }
    $blackCmd = if (Test-Path ".zen_venv/bin/black") { ".zen_venv/bin/black" } else { "black" }
    $isortCmd = if (Test-Path ".zen_venv/bin/isort") { ".zen_venv/bin/isort" } else { "isort" }
    $pytestCmd = if (Test-Path ".zen_venv/bin/pytest") { ".zen_venv/bin/pytest" } else { "pytest" }
}

Write-Host ""

# Step 1: Linting and Formatting
if (!$SkipLinting) {
    Write-Emoji "📋" "Step 1: Running Linting and Formatting Checks" -Color Cyan
    Write-ColorText "--------------------------------------------------" -Color Cyan

    try {
        Write-Emoji "🔧" "Running ruff linting with auto-fix..." -Color Yellow
        & $ruffCmd check --fix --exclude test_simulation_files --exclude .zen_venv
        if ($LASTEXITCODE -ne 0) {
            throw "Ruff linting failed"
        }

        Write-Emoji "🎨" "Running black code formatting..." -Color Yellow
        & $blackCmd . --exclude="test_simulation_files/" --exclude=".zen_venv/"
        if ($LASTEXITCODE -ne 0) {
            throw "Black formatting failed"
        }

        Write-Emoji "📦" "Running import sorting with isort..." -Color Yellow
        & $isortCmd . --skip-glob=".zen_venv/*" --skip-glob="test_simulation_files/*"
        if ($LASTEXITCODE -ne 0) {
            throw "Import sorting failed"
        }

        Write-Emoji "✅" "Verifying all linting passes..." -Color Yellow
        & $ruffCmd check --exclude test_simulation_files --exclude .zen_venv
        if ($LASTEXITCODE -ne 0) {
            throw "Final linting verification failed"
        }

        Write-Emoji "✅" "Step 1 Complete: All linting and formatting checks passed!" -Color Green
    } catch {
        Write-Emoji "❌" "Step 1 Failed: Linting and formatting checks failed" -Color Red
        Write-ColorText "Error: $_" -Color Red
        exit 1
    }
} else {
    Write-Emoji "⏭️" "Skipping linting and formatting checks" -Color Yellow
}

Write-Host ""

# Step 2: Unit Tests
if (!$SkipTests) {
    Write-Emoji "🧪" "Step 2: Running Complete Unit Test Suite" -Color Cyan
    Write-ColorText "---------------------------------------------" -Color Cyan

    try {
        Write-Emoji "🏃" "Running unit tests (excluding integration tests)..." -Color Yellow
        
        $pytestArgs = @("tests/", "-v", "-x", "-m", "not integration")
        if ($VerboseOutput) {
            $pytestArgs += "--verbose"
        }
        
        & $pythonCmd -m pytest @pytestArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Unit tests failed"
        }

        Write-Emoji "✅" "Step 2 Complete: All unit tests passed!" -Color Green
    } catch {
        Write-Emoji "❌" "Step 2 Failed: Unit tests failed" -Color Red
        Write-ColorText "Error: $_" -Color Red
        exit 1
    }
} else {
    Write-Emoji "⏭️" "Skipping unit tests" -Color Yellow
}

Write-Host ""

# Step 3: Final Summary
Write-Emoji "🎉" "All Code Quality Checks Passed!" -Color Green
Write-ColorText "==================================" -Color Green

if (!$SkipLinting) {
    Write-Emoji "✅" "Linting (ruff): PASSED" -Color Green
    Write-Emoji "✅" "Formatting (black): PASSED" -Color Green
    Write-Emoji "✅" "Import sorting (isort): PASSED" -Color Green
} else {
    Write-Emoji "⏭️" "Linting: SKIPPED" -Color Yellow
}

if (!$SkipTests) {
    Write-Emoji "✅" "Unit tests: PASSED" -Color Green
} else {
    Write-Emoji "⏭️" "Unit tests: SKIPPED" -Color Yellow
}

Write-Host ""
Write-Emoji "🚀" "Your code is ready for commit and GitHub Actions!" -Color Green
Write-Emoji "💡" "Remember to add simulator tests if you modified tools" -Color Yellow
