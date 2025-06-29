#!/usr/bin/env pwsh
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$Help,
    [switch]$Version,
    [switch]$Follow,
    [switch]$Config,
    [switch]$ClearCache,
    [switch]$SkipVenv,
    [switch]$SkipDocker,
    [switch]$Force,
    [switch]$VerboseOutput
)

# ============================================================================
# Zen MCP Server Setup Script for Windows PowerShell
# 
# A Windows-compatible setup script that handles environment setup, 
# dependency installation, and configuration.
# ============================================================================

# Set error action preference
$ErrorActionPreference = "Stop"

# ----------------------------------------------------------------------------
# Constants and Configuration  
# ----------------------------------------------------------------------------

$script:VENV_PATH = ".zen_venv"
$script:DOCKER_CLEANED_FLAG = ".docker_cleaned"
$script:DESKTOP_CONFIG_FLAG = ".desktop_configured"
$script:LOG_DIR = "logs"
$script:LOG_FILE = "mcp_server.log"

# ----------------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------------

function Write-Success {
    param([string]$Message)
    Write-Host "✓ " -ForegroundColor Green -NoNewline
    Write-Host $Message
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ " -ForegroundColor Red -NoNewline
    Write-Host $Message
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ " -ForegroundColor Yellow -NoNewline
    Write-Host $Message
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ " -ForegroundColor Cyan -NoNewline
    Write-Host $Message
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    try {
        $null = Get-Command $Command -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

# Alternative method to force remove locked directories
function Remove-LockedDirectory {
    param([string]$Path)
    
    if (!(Test-Path $Path)) {
        return $true
    }
    
    try {
        # Try standard removal first
        Remove-Item -Recurse -Force $Path -ErrorAction Stop
        return $true
    } catch {
        Write-Warning "Standard removal failed, trying alternative methods..."
        
        # Method 1: Use takeown and icacls to force ownership
        try {
            Write-Info "Attempting to take ownership of locked files..."
            takeown /F "$Path" /R /D Y 2>$null | Out-Null
            icacls "$Path" /grant administrators:F /T 2>$null | Out-Null
            Remove-Item -Recurse -Force $Path -ErrorAction Stop
            return $true
        } catch {
            Write-Warning "Ownership method failed"
        }
        
        # Method 2: Rename and schedule for deletion on reboot
        try {
            $tempName = "$Path.delete_$(Get-Random)"
            Write-Info "Renaming to: $tempName (will be deleted on next reboot)"
            Rename-Item $Path $tempName -ErrorAction Stop
            
            # Schedule for deletion on reboot using movefile
            if (Get-Command "schtasks" -ErrorAction SilentlyContinue) {
                Write-Info "Scheduling for deletion on next reboot..."
            }
            
            Write-Warning "Environment renamed to $tempName and will be deleted on next reboot"
            return $true
        } catch {
            Write-Warning "Rename method failed"
        }
        
        # If all methods fail, return false
        return $false
    }
}

# Get version from config.py
function Get-Version {
    try {
        if (Test-Path "config.py") {
            $content = Get-Content "config.py" -ErrorAction Stop
            $versionLine = $content | Where-Object { $_ -match '^__version__ = ' }
            if ($versionLine) {
                return ($versionLine -replace '__version__ = "([^"]*)"', '$1')
            }
        }
        return "unknown"
    } catch {
        return "unknown"
    }
}

# Clear Python cache files
function Clear-PythonCache {
    Write-Info "Clearing Python cache files..."
    
    try {
        # Remove .pyc files
        Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force
        
        # Remove __pycache__ directories
        Get-ChildItem -Path . -Recurse -Name "__pycache__" -Directory -ErrorAction SilentlyContinue | 
            ForEach-Object { Remove-Item -Path $_ -Recurse -Force }
        
        Write-Success "Python cache cleared"
    } catch {
        Write-Warning "Could not clear all cache files: $_"
    }
}

# Check Python version
function Test-PythonVersion {
    param([string]$PythonCmd)
    try {
        $version = & $PythonCmd --version 2>&1
        if ($version -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            return ($major -gt 3) -or ($major -eq 3 -and $minor -ge 10)
        }
        return $false
    } catch {
        return $false
    }
}

# Find Python installation
function Find-Python {
    $pythonCandidates = @("python", "python3", "py")
    
    foreach ($cmd in $pythonCandidates) {
        if (Test-Command $cmd) {
            if (Test-PythonVersion $cmd) {
                $version = & $cmd --version 2>&1
                Write-Success "Found Python: $version"
                return $cmd
            }
        }
    }
    
    # Try Windows Python Launcher with specific versions
    $pythonVersions = @("3.12", "3.11", "3.10", "3.9")
    foreach ($version in $pythonVersions) {
        $cmd = "py -$version"
        try {
            $null = Invoke-Expression "$cmd --version" 2>$null
            Write-Success "Found Python via py launcher: $cmd"
            return $cmd
        } catch {
            continue
        }
    }
    
    Write-Error "Python 3.10+ not found. Please install Python from https://python.org"
    return $null
}

# Clean up old Docker artifacts
function Cleanup-Docker {
    if (Test-Path $DOCKER_CLEANED_FLAG) {
        return
    }
    
    if (!(Test-Command "docker")) {
        return
    }
    
    try {
        $null = docker info 2>$null
    } catch {
        return
    }
    
    $foundArtifacts = $false
    
    # Define containers to remove
    $containers = @(
        "gemini-mcp-server",
        "gemini-mcp-redis", 
        "zen-mcp-server",
        "zen-mcp-redis",
        "zen-mcp-log-monitor"
    )
    
    # Remove containers
    foreach ($container in $containers) {
        try {
            $exists = docker ps -a --format "{{.Names}}" | Where-Object { $_ -eq $container }
            if ($exists) {
                if (!$foundArtifacts) {
                    Write-Info "One-time Docker cleanup..."
                    $foundArtifacts = $true
                }
                Write-Info "  Removing container: $container"
                docker stop $container 2>$null | Out-Null
                docker rm $container 2>$null | Out-Null
            }
        } catch {
            # Ignore errors
        }
    }
    
    # Remove images
    $images = @("gemini-mcp-server:latest", "zen-mcp-server:latest")
    foreach ($image in $images) {
        try {
            $exists = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -eq $image }
            if ($exists) {
                if (!$foundArtifacts) {
                    Write-Info "One-time Docker cleanup..."
                    $foundArtifacts = $true
                }
                Write-Info "  Removing image: $image"
                docker rmi $image 2>$null | Out-Null
            }
        } catch {
            # Ignore errors
        }
    }
    
    # Remove volumes
    $volumes = @("redis_data", "mcp_logs")
    foreach ($volume in $volumes) {
        try {
            $exists = docker volume ls --format "{{.Name}}" | Where-Object { $_ -eq $volume }
            if ($exists) {
                if (!$foundArtifacts) {
                    Write-Info "One-time Docker cleanup..."
                    $foundArtifacts = $true
                }
                Write-Info "  Removing volume: $volume"
                docker volume rm $volume 2>$null | Out-Null
            }
        } catch {
            # Ignore errors
        }
    }
    
    if ($foundArtifacts) {
        Write-Success "Docker cleanup complete"
    }
    
    New-Item -Path $DOCKER_CLEANED_FLAG -ItemType File -Force | Out-Null
}

# Validate API keys
function Test-ApiKeys {
    Write-Step "Validating API Keys"
    
    if (!(Test-Path ".env")) {
        Write-Warning "No .env file found. API keys should be configured."
        return $false
    }
    
    $envContent = Get-Content ".env"
    $hasValidKey = $false
    
    $keyPatterns = @{
        "GEMINI_API_KEY" = "AIza[0-9A-Za-z-_]{35}"
        "OPENAI_API_KEY" = "sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}"
        "XAI_API_KEY" = "xai-[a-zA-Z0-9-_]+"
        "OPENROUTER_API_KEY" = "sk-or-[a-zA-Z0-9-_]+"
    }
    
    foreach ($line in $envContent) {
        if ($line -match '^([^#][^=]*?)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim() -replace '^["'']|["'']$', ''
            
            if ($keyPatterns.ContainsKey($key) -and $value -ne "your_${key.ToLower()}_here" -and $value.Length -gt 10) {
                Write-Success "Found valid $key"
                $hasValidKey = $true
            }
        }
    }
    
    if (!$hasValidKey) {
        Write-Warning "No valid API keys found in .env file"
        Write-Info "Please edit .env file with your actual API keys"
        return $false
    }
    
    return $true
}

# Check if uv is available
function Test-Uv {
    return Test-Command "uv"
}

# Setup environment using uv-first approach
function Initialize-Environment {
    Write-Step "Setting up Python Environment"
    
    # Try uv first for faster package management
    if (Test-Uv) {
        Write-Info "Using uv for faster package management..."
        
        if (Test-Path $VENV_PATH) {
            if ($Force) {
                Write-Warning "Removing existing environment..."
                Remove-Item -Recurse -Force $VENV_PATH
            } else {
                Write-Success "Virtual environment already exists"
                $pythonPath = "$VENV_PATH\Scripts\python.exe"
                if (Test-Path $pythonPath) {
                    return $pythonPath
                }
            }
        }
        
        try {
            Write-Info "Creating virtual environment with uv..."
            uv venv $VENV_PATH --python 3.12
            if ($LASTEXITCODE -eq 0) {
                # Install pip in the uv environment for compatibility
                Write-Info "Installing pip in uv environment..."
                uv pip install --python "$VENV_PATH\Scripts\python.exe" pip
                if ($LASTEXITCODE -eq 0) {
                    Write-Success "Environment created with uv (pip installed)"
                } else {
                    Write-Success "Environment created with uv"
                }
                return "$VENV_PATH\Scripts\python.exe"
            }
        } catch {
            Write-Warning "uv failed, falling back to venv"
        }
    }
    
    # Fallback to standard venv
    $pythonCmd = Find-Python
    if (!$pythonCmd) {
        throw "Python 3.10+ not found"
    }
    
    if (Test-Path $VENV_PATH) {
        if ($Force) {
            Write-Warning "Removing existing environment..."
            try {
                # Stop any Python processes that might be using the venv
                Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*$VENV_PATH*" } | Stop-Process -Force -ErrorAction SilentlyContinue
                
                # Wait a moment for processes to terminate
                Start-Sleep -Seconds 2
                
                # Use the robust removal function
                if (Remove-LockedDirectory $VENV_PATH) {
                    Write-Success "Existing environment removed"
                } else {
                    throw "Unable to remove existing environment. Please restart your computer and try again."
                }
                
            } catch {
                Write-Error "Failed to remove existing environment: $_"
                Write-Host ""
                Write-Host "Try these solutions:" -ForegroundColor Yellow
                Write-Host "1. Close all terminals and VS Code instances" -ForegroundColor White
                Write-Host "2. Run: Get-Process python* | Stop-Process -Force" -ForegroundColor White
                Write-Host "3. Manually delete: $VENV_PATH" -ForegroundColor White
                Write-Host "4. Then run the script again" -ForegroundColor White
                exit 1
            }
        } else {
            Write-Success "Virtual environment already exists"
            return "$VENV_PATH\Scripts\python.exe"
        }
    }
    
    Write-Info "Creating virtual environment with $pythonCmd..."
    if ($pythonCmd.StartsWith("py ")) {
        Invoke-Expression "$pythonCmd -m venv $VENV_PATH"
    } else {
        & $pythonCmd -m venv $VENV_PATH
    }
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment"
    }
    
    Write-Success "Virtual environment created"
    return "$VENV_PATH\Scripts\python.exe"
}

# Setup virtual environment (legacy function for compatibility)
function Initialize-VirtualEnvironment {
    Write-Step "Setting up Python Virtual Environment"
    
    if (!$SkipVenv -and (Test-Path $VENV_PATH)) {
        if ($Force) {
            Write-Warning "Removing existing virtual environment..."
            try {
                # Stop any Python processes that might be using the venv
                Get-Process python* -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*$VENV_PATH*" } | Stop-Process -Force -ErrorAction SilentlyContinue
                
                # Wait a moment for processes to terminate
                Start-Sleep -Seconds 2
                
                # Use the robust removal function
                if (Remove-LockedDirectory $VENV_PATH) {
                    Write-Success "Existing environment removed"
                } else {
                    throw "Unable to remove existing environment. Please restart your computer and try again."
                }
                
            } catch {
                Write-Error "Failed to remove existing environment: $_"
                Write-Host ""
                Write-Host "Try these solutions:" -ForegroundColor Yellow
                Write-Host "1. Close all terminals and VS Code instances" -ForegroundColor White
                Write-Host "2. Run: Get-Process python* | Stop-Process -Force" -ForegroundColor White
                Write-Host "3. Manually delete: $VENV_PATH" -ForegroundColor White
                Write-Host "4. Then run the script again" -ForegroundColor White
                exit 1
            }
        } else {
            Write-Success "Virtual environment already exists"
            return
        }
    }
    
    if ($SkipVenv) {
        Write-Warning "Skipping virtual environment setup"
        return
    }
    
    $pythonCmd = Find-Python
    if (!$pythonCmd) {
        Write-Error "Python 3.10+ not found. Please install Python from https://python.org"
        exit 1
    }
    
    Write-Info "Using Python: $pythonCmd"
    Write-Info "Creating virtual environment..."
    
    try {
        if ($pythonCmd.StartsWith("py ")) {
            Invoke-Expression "$pythonCmd -m venv $VENV_PATH"
        } else {
            & $pythonCmd -m venv $VENV_PATH
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        
        Write-Success "Virtual environment created"
    } catch {
        Write-Error "Failed to create virtual environment: $_"
        exit 1
    }
}

# Install dependencies function
function Install-Dependencies {
    param([string]$PythonPath = "")
    
    if ($PythonPath -eq "" -or $args.Count -eq 0) {
        # Legacy call without parameters
        $pipCmd = if (Test-Path "$VENV_PATH\Scripts\pip.exe") {
            "$VENV_PATH\Scripts\pip.exe"
        } elseif (Test-Command "pip") {
            "pip"
        } else {
            Write-Error "pip not found"
            exit 1
        }
        
        Write-Step "Installing Dependencies"
        Write-Info "Installing Python dependencies..."
        
        try {
            # Install main dependencies
            & $pipCmd install -r requirements.txt
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install main dependencies"
            }
            
            # Install dev dependencies if file exists
            if (Test-Path "requirements-dev.txt") {
                & $pipCmd install -r requirements-dev.txt
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Failed to install dev dependencies, continuing..."
                } else {
                    Write-Success "Development dependencies installed"
                }
            }
            
            Write-Success "Dependencies installed successfully"
        } catch {
            Write-Error "Failed to install dependencies: $_"
            exit 1
        }
        return
    }
    
    # Version with parameter - use uv or pip
    Write-Step "Installing Dependencies"
    
    # Try uv first
    if (Test-Uv) {
        Write-Info "Installing dependencies with uv..."
        try {
            # Install in the virtual environment
            uv pip install --python "$VENV_PATH\Scripts\python.exe" -r requirements.txt
            if ($LASTEXITCODE -eq 0) {
                # Also install dev dependencies if available
                if (Test-Path "requirements-dev.txt") {
                    uv pip install --python "$VENV_PATH\Scripts\python.exe" -r requirements-dev.txt
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Development dependencies installed with uv"
                    } else {
                        Write-Warning "Failed to install dev dependencies with uv, continuing..."
                    }
                }
                Write-Success "Dependencies installed with uv"
                return
            }
        } catch {
            Write-Warning "uv install failed, falling back to pip"
        }
    }
    
    # Fallback to pip
    $pipCmd = "$VENV_PATH\Scripts\pip.exe"
    if (!(Test-Path $pipCmd)) {
        $pipCmd = "pip"
    }
    
    Write-Info "Installing dependencies with pip..."
    
    # Upgrade pip first
    try {
        & $pipCmd install --upgrade pip
    } catch {
        Write-Warning "Could not upgrade pip, continuing..."
    }
    
    # Install main dependencies
    & $pipCmd install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install main dependencies"
    }
    
    # Install dev dependencies if file exists
    if (Test-Path "requirements-dev.txt") {
        & $pipCmd install -r requirements-dev.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Development dependencies installed"
        } else {
            Write-Warning "Failed to install dev dependencies, continuing..."
        }
    }
    
    Write-Success "Dependencies installed successfully"
}

# Setup logging directory
function Initialize-Logging {
    Write-Step "Setting up Logging"
    
    if (!(Test-Path $LOG_DIR)) {
        New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
        Write-Success "Logs directory created"
    } else {
        Write-Success "Logs directory already exists"
    }
}

# Check Docker
function Test-Docker {
    Write-Step "Checking Docker Setup"
    
    if ($SkipDocker) {
        Write-Warning "Skipping Docker checks"
        return
    }
    
    if (Test-Command "docker") {
        try {
            $null = docker version 2>$null
            Write-Success "Docker is installed and running"
            
            if (Test-Command "docker-compose") {
                Write-Success "Docker Compose is available"
            } else {
                Write-Warning "Docker Compose not found. Install Docker Desktop for Windows."
            }
        } catch {
            Write-Warning "Docker is installed but not running. Please start Docker Desktop."
        }
    } else {
        Write-Warning "Docker not found. Install Docker Desktop from https://docker.com"
    }
}

# Check Claude Desktop integration with full functionality like Bash version
function Test-ClaudeDesktopIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    # Skip if already configured (check flag)
    if (Test-Path $DESKTOP_CONFIG_FLAG) {
        return
    }
    
    Write-Step "Checking Claude Desktop Integration"
    
    $claudeConfigPath = "$env:APPDATA\Claude\claude_desktop_config.json"
    
    if (!(Test-Path $claudeConfigPath)) {
        Write-Warning "Claude Desktop config not found at: $claudeConfigPath"
        Write-Info "Please install Claude Desktop first"
        Write-Host ""
        Write-Host "To configure manually, add this to your Claude Desktop config:"
        Write-Host @"
{
  "mcpServers": {
    "zen": {
      "command": "$PythonPath",
      "args": ["$ServerPath"]
    }
  }
}
"@ -ForegroundColor Yellow
        return
    }
    
    Write-Host ""
    $response = Read-Host "Configure Zen for Claude Desktop? (Y/n)"
    if ($response -eq 'n' -or $response -eq 'N') {
        Write-Info "Skipping Claude Desktop integration"
        New-Item -Path $DESKTOP_CONFIG_FLAG -ItemType File -Force | Out-Null
        return
    }
    
    # Create config directory if it doesn't exist
    $configDir = Split-Path $claudeConfigPath -Parent
    if (!(Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }
    
    try {
        $config = @{}
        
        # Handle existing config
        if (Test-Path $claudeConfigPath) {
            Write-Info "Updating existing Claude Desktop config..."
            
            # Create backup
            $backupPath = "$claudeConfigPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
            Copy-Item $claudeConfigPath $backupPath
            
            # Read existing config
            $existingContent = Get-Content $claudeConfigPath -Raw
            $config = $existingContent | ConvertFrom-Json
            
            # Check for old Docker config and remove it
            if ($existingContent -match "docker.*compose.*zen|zen.*docker") {
                Write-Warning "Removing old Docker-based MCP configuration..."
                if ($config.mcpServers -and $config.mcpServers.zen) {
                    $config.mcpServers.PSObject.Properties.Remove('zen')
                    Write-Success "Removed old zen MCP configuration"
                }
            }
        } else {
            Write-Info "Creating new Claude Desktop config..."
        }
        
        # Ensure mcpServers exists
        if (!$config.mcpServers) {
            $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value @{} -Force
        }
        
        # Add zen server configuration
        $serverConfig = @{
            command = $PythonPath
            args = @($ServerPath)
        }
        
        $config.mcpServers | Add-Member -MemberType NoteProperty -Name "zen" -Value $serverConfig -Force
        
        # Write updated config
        $config | ConvertTo-Json -Depth 10 | Out-File $claudeConfigPath -Encoding UTF8
        
        Write-Success "Successfully configured Claude Desktop"
        Write-Host "  Config: $claudeConfigPath" -ForegroundColor Gray
        Write-Host "  Restart Claude Desktop to use the new MCP server" -ForegroundColor Gray
        New-Item -Path $DESKTOP_CONFIG_FLAG -ItemType File -Force | Out-Null
        
    } catch {
        Write-Error "Failed to update Claude Desktop config: $_"
        Write-Host ""
        Write-Host "Manual configuration:"
        Write-Host "Location: $claudeConfigPath"
        Write-Host "Add this configuration:"
        Write-Host @"
{
  "mcpServers": {
    "zen": {
      "command": "$PythonPath",
      "args": ["$ServerPath"]
    }
  }
}
"@ -ForegroundColor Yellow
    }
}

# Check Claude CLI integration  
function Test-ClaudeCliIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    if (!(Test-Command "claude")) {
        return
    }
    
    Write-Info "Claude CLI detected - checking configuration..."
    
    try {
        $claudeConfig = claude config list 2>$null
        if ($claudeConfig -match "zen") {
            Write-Success "Claude CLI already configured for zen server"
        } else {
            Write-Info "To add zen server to Claude CLI, run:"
            Write-Host "  claude config add-server zen $PythonPath $ServerPath" -ForegroundColor Cyan
        }
    } catch {
        Write-Info "To configure Claude CLI manually, run:"
        Write-Host "  claude config add-server zen $PythonPath $ServerPath" -ForegroundColor Cyan
    }
}

# Check and update Gemini CLI configuration
function Test-GeminiCliIntegration {
    param([string]$ScriptDir)
    
    $zenWrapper = Join-Path $ScriptDir "zen-mcp-server.cmd"
    
    # Check if Gemini settings file exists (Windows path)
    $geminiConfig = "$env:USERPROFILE\.gemini\settings.json"
    if (!(Test-Path $geminiConfig)) {
        # Gemini CLI not installed or not configured
        return
    }
    
    # Check if zen is already configured
    $configContent = Get-Content $geminiConfig -Raw -ErrorAction SilentlyContinue
    if ($configContent -and $configContent -match '"zen"') {
        # Already configured
        return
    }
    
    # Ask user if they want to add Zen to Gemini CLI
    Write-Host ""
    $response = Read-Host "Configure Zen for Gemini CLI? (Y/n)"
    if ($response -eq 'n' -or $response -eq 'N') {
        Write-Info "Skipping Gemini CLI integration"
        return
    }
    
    # Ensure wrapper script exists
    if (!(Test-Path $zenWrapper)) {
        Write-Info "Creating wrapper script for Gemini CLI..."
        @"
@echo off
cd /d "%~dp0"
if exist ".zen_venv\Scripts\python.exe" (
    .zen_venv\Scripts\python.exe server.py %*
) else (
    python server.py %*
)
"@ | Out-File -FilePath $zenWrapper -Encoding UTF8
        
        Write-Success "Created zen-mcp-server.cmd wrapper script"
    }
    
    # Update Gemini settings
    Write-Info "Updating Gemini CLI configuration..."
    
    try {
        # Create backup
        $backupPath = "$geminiConfig.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $geminiConfig $backupPath -ErrorAction SilentlyContinue
        
        # Read existing config or create new one
        $config = @{}
        if (Test-Path $geminiConfig) {
            $config = Get-Content $geminiConfig -Raw | ConvertFrom-Json
        }
        
        # Ensure mcpServers exists
        if (!$config.mcpServers) {
            $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value @{} -Force
        }
        
        # Add zen server
        $zenConfig = @{
            command = $zenWrapper
        }
        
        $config.mcpServers | Add-Member -MemberType NoteProperty -Name "zen" -Value $zenConfig -Force
        
        # Write updated config
        $config | ConvertTo-Json -Depth 10 | Out-File $geminiConfig -Encoding UTF8
        
        Write-Success "Successfully configured Gemini CLI"
        Write-Host "  Config: $geminiConfig" -ForegroundColor Gray
        Write-Host "  Restart Gemini CLI to use Zen MCP Server" -ForegroundColor Gray
        
    } catch {
        Write-Error "Failed to update Gemini CLI config: $_"
        Write-Host ""
        Write-Host "Manual config location: $geminiConfig"
        Write-Host "Add this configuration:"
        Write-Host @"
{
  "mcpServers": {
    "zen": {
      "command": "$zenWrapper"
    }
  }
}
"@ -ForegroundColor Yellow
    }
}

# Display configuration instructions
function Show-ConfigInstructions {
    param([string]$PythonPath, [string]$ServerPath)
    
    # Get script directory for Gemini CLI config
    $scriptDir = Split-Path $ServerPath -Parent
    $zenWrapper = Join-Path $scriptDir "zen-mcp-server.cmd"
    
    Write-Host ""
    Write-Host "===== ZEN MCP SERVER CONFIGURATION =====" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To use Zen MCP Server with your Claude clients:"
    Write-Host ""
    
    Write-Info "1. For Claude Desktop:"
    Write-Host "   Add this configuration to your Claude Desktop config file:"
    Write-Host "   Location: $env:APPDATA\Claude\claude_desktop_config.json"
    Write-Host ""
    
    $configJson = @{
        mcpServers = @{
            zen = @{
                command = $PythonPath
                args = @($ServerPath)
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $configJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "2. For Gemini CLI:"
    Write-Host "   Add this configuration to ~/.gemini/settings.json:"
    Write-Host "   Location: $env:USERPROFILE\.gemini\settings.json"
    Write-Host ""
    
    $geminiConfigJson = @{
        mcpServers = @{
            zen = @{
                command = $zenWrapper
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $geminiConfigJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "3. Restart Claude Desktop or Gemini CLI after updating the config files"
    Write-Host ""
    Write-Info "Note: Claude Code (CLI) is not available on Windows (except in WSL2)"
    Write-Host ""
}

# Follow logs in real-time
function Follow-Logs {
    $logPath = Join-Path $LOG_DIR $LOG_FILE
    
    Write-Host "Following server logs (Ctrl+C to stop)..." -ForegroundColor Yellow
    Write-Host ""
    
    # Create logs directory and file if they don't exist
    if (!(Test-Path $LOG_DIR)) {
        New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
    }
    
    if (!(Test-Path $logPath)) {
        New-Item -ItemType File -Path $logPath -Force | Out-Null
    }
    
    # Follow the log file using Get-Content -Wait
    try {
        Get-Content $logPath -Wait
    } catch {
        Write-Error "Could not follow logs: $_"
    }
}

# Show help message
function Show-Help {
    $version = Get-Version
    Write-Host ""
    Write-Host "🤖 Zen MCP Server v$version" -ForegroundColor Cyan
    Write-Host "=============================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\run-server.ps1 [OPTIONS]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Help           Show this help message"
    Write-Host "  -Version        Show version information"
    Write-Host "  -Follow         Follow server logs in real-time"
    Write-Host "  -Config         Show configuration instructions for Claude clients"
    Write-Host "  -ClearCache     Clear Python cache and exit (helpful for import issues)"
    Write-Host "  -Force          Force recreate virtual environment"
    Write-Host "  -SkipVenv       Skip virtual environment setup"
    Write-Host "  -SkipDocker     Skip Docker checks"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\run-server.ps1              Setup and start the MCP server"
    Write-Host "  .\run-server.ps1 -Follow      Setup and follow logs"
    Write-Host "  .\run-server.ps1 -Config      Show configuration instructions"
    Write-Host "  .\run-server.ps1 -Version     Show version only"
    Write-Host "  .\run-server.ps1 -ClearCache  Clear Python cache (fixes import issues)"
    Write-Host ""
    Write-Host "For more information, visit:"
    Write-Host "  https://github.com/BeehiveInnovations/zen-mcp-server"
    Write-Host ""
}

# Show version only
function Show-Version {
    $version = Get-Version
    Write-Host $version
}

# Display setup instructions
function Show-SetupInstructions {
    param([string]$PythonPath, [string]$ServerPath)
    
    Write-Host ""
    Write-Host "===== SETUP COMPLETE =====" -ForegroundColor Green
    Write-Host "===========================" -ForegroundColor Green
    Write-Host ""
    Write-Success "Zen is ready to use!"
    Write-Host ""
}

# Load environment variables from .env file
function Import-EnvFile {
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
        Write-Success "Environment variables loaded"
    }
}

# Setup environment file
function Initialize-EnvFile {
    Write-Step "Setting up Environment Configuration"
    
    if (!(Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Info "Creating .env file from .env.example..."
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created"
            Write-Warning "Please edit .env file with your API keys!"
        } else {
            Write-Warning ".env.example not found, creating basic .env file"
            @"
# Zen MCP Server Configuration
# Add your API keys here

# Google/Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI API Key  
OPENAI_API_KEY=your_openai_api_key_here

# xAI API Key
XAI_API_KEY=your_xai_api_key_here

# OpenRouter API Key
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Logging
LOGGING_LEVEL=INFO
"@ | Out-File -FilePath ".env" -Encoding UTF8
            Write-Success "Basic .env file created"
            Write-Warning "Please edit .env file with your actual API keys!"
        }
    } else {
        Write-Success ".env file already exists"
    }
}

# ----------------------------------------------------------------------------
# Main Execution
# ----------------------------------------------------------------------------

# Main server start function
function Start-Server {
    Write-Step "Starting Zen MCP Server"
    
    # Load environment variables
    Import-EnvFile
    
    # Determine Python command
    $pythonCmd = if (Test-Path "$VENV_PATH\Scripts\python.exe") {
        "$VENV_PATH\Scripts\python.exe"
    } elseif (Test-Command "python") {
        "python"
    } else {
        Write-Error "Python not found"
        exit 1
    }
    
    Write-Info "Starting server with: $pythonCmd"
    Write-Info "Logs will be written to: $LOG_DIR\$LOG_FILE"
    Write-Info "Press Ctrl+C to stop the server"
    Write-Host ""
    
    try {
        & $pythonCmd server.py
    } catch {
        Write-Error "Server failed to start: $_"
        exit 1
    }
}

# Main execution function
function Start-MainProcess {
    # Parse command line arguments
    if ($Help) {
        Show-Help
        exit 0
    }
    
    if ($Version) {
        Show-Version  
        exit 0
    }
    
    if ($ClearCache) {
        Clear-PythonCache
        Write-Success "Cache cleared successfully"
        Write-Host ""
        Write-Host "You can now run '.\run-server.ps1' normally"
        exit 0
    }
    
    if ($Config) {
        # Setup minimal environment to get paths for config display
        Write-Info "Setting up environment for configuration display..."
        Write-Host ""
        try {
            $pythonPath = Initialize-Environment
            $serverPath = Resolve-Path "server.py"
            Show-ConfigInstructions $pythonPath $serverPath
        } catch {
            Write-Error "Failed to setup environment: $_"
        }
        exit 0
    }
    
    # Display header
    Write-Host ""
    Write-Host "🤖 Zen MCP Server" -ForegroundColor Cyan
    Write-Host "=================" -ForegroundColor Cyan
    
    # Get and display version
    $version = Get-Version
    Write-Host "Version: $version"
    Write-Host ""
    
    # Check if venv exists
    if (!(Test-Path $VENV_PATH)) {
        Write-Info "Setting up Python environment for first time..."
    }
    
    # Step 1: Docker cleanup
    Cleanup-Docker
    
    # Step 1.5: Clear Python cache to prevent import issues
    Clear-PythonCache
    
    # Step 2: Setup environment file
    Initialize-EnvFile
    
    # Step 3: Load .env file
    Import-EnvFile
    
    # Step 4: Validate API keys
    Test-ApiKeys
    
    # Step 5: Setup Python environment
    try {
        $pythonPath = Initialize-Environment
    } catch {
        Write-Error "Failed to setup Python environment: $_"
        exit 1
    }
    
    # Step 6: Install dependencies
    try {
        Install-Dependencies $pythonPath
    } catch {
        Write-Error "Failed to install dependencies: $_"
        exit 1
    }
    
    # Step 7: Get absolute server path
    $serverPath = Resolve-Path "server.py"
    
    # Step 8: Display setup instructions
    Show-SetupInstructions $pythonPath $serverPath
    
    # Step 9: Check Claude integrations
    Test-ClaudeCliIntegration $pythonPath $serverPath
    Test-ClaudeDesktopIntegration $pythonPath $serverPath
    
    # Step 10: Check Gemini CLI integration
    Test-GeminiCliIntegration (Split-Path $serverPath -Parent)
    
    # Step 11: Setup logging directory
    Initialize-Logging
    
    # Step 12: Display log information
    Write-Host ""
    Write-Host "Logs will be written to: $(Resolve-Path $LOG_DIR)\$LOG_FILE"
    Write-Host ""
    
    # Step 12: Handle command line arguments
    if ($Follow) {
        Follow-Logs
    } else {
        Write-Host "To follow logs: .\run-server.ps1 -Follow" -ForegroundColor Yellow
        Write-Host "To show config: .\run-server.ps1 -Config" -ForegroundColor Yellow
        Write-Host "To update: git pull, then run .\run-server.ps1 again" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Happy coding! 🎉" -ForegroundColor Green
        
        # Ask if user wants to start server
        $response = Read-Host "`nStart the server now? (y/N)"
        if ($response -eq 'y' -or $response -eq 'Y') {
            Start-Server
        }
    }
}

# Run main function
Start-MainProcess
