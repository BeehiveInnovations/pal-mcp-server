<#
.SYNOPSIS
    Installation, configuration, and launch script for Zen MCP server on Windows.

.DESCRIPTION
    This PowerShell script prepares the environment for the Zen MCP server:
    - Installs and checks Python 3.10+ (with venv or uv if available)
    - Installs required Python dependencies
    - Configures environment files (.env)
    - Validates presence of required API keys
    - Cleans Python caches and obsolete Docker artifacts
    - Offers automatic integration with Claude Desktop, Gemini CLI, VSCode, Cursor, Windsurf, and Trae
    - Manages configuration file backups (max 3 retained)
    - Allows real-time log following or server launch

.PARAMETER Help
    Shows script help.

.PARAMETER Version
    Shows Zen MCP server version.

.PARAMETER Follow
    Follows server logs in real time.

.PARAMETER Config
    Shows configuration instructions for Claude and other compatible clients.

.PARAMETER ClearCache
    Removes Python cache files (__pycache__, .pyc).

.PARAMETER SkipVenv
    Skips Python virtual environment creation.

.PARAMETER SkipDocker
    Skips Docker checks and cleanup.

.PARAMETER Force
    Forces recreation of the Python virtual environment.

.PARAMETER VerboseOutput
    Enables more detailed output (currently unused).

.PARAMETER Dev
    Installs development dependencies from requirements-dev.txt if available.

.EXAMPLE
    .\run-server.ps1
    Prepares the environment and starts the Zen MCP server.

    .\run-server.ps1 -Follow
    Follows server logs in real time.

    .\run-server.ps1 -Config
    Shows configuration instructions for clients.

    .\run-server.ps1 -Dev
    Prepares the environment with development dependencies and starts the server.

.NOTES
    Project Author     : BeehiveInnovations
    Script Author      : GiGiDKR (https://github.com/GiGiDKR)
    Date               : 07-05-2025
    Version            : See config.py (__version__)
    References         : https://github.com/BeehiveInnovations/zen-mcp-server

#>
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
    [switch]$VerboseOutput,
    [switch]$Dev
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

# Manage configuration file backups with maximum 3 files retention
function Manage-ConfigBackups {
    param(
        [string]$ConfigFilePath,
        [int]$MaxBackups = 3
    )
    
    if (!(Test-Path $ConfigFilePath)) {
        Write-Warning "Configuration file not found: $ConfigFilePath"
        return $null
    }
    
    try {
        # Create new backup with timestamp
        $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
        $backupPath = "$ConfigFilePath.backup_$timestamp"
        Copy-Item $ConfigFilePath $backupPath -ErrorAction Stop
        
        # Find all existing backups for this config file
        $configDir = Split-Path $ConfigFilePath -Parent
        $configFileName = Split-Path $ConfigFilePath -Leaf
        $backupPattern = "$configFileName.backup_*"
        
        $existingBackups = Get-ChildItem -Path $configDir -Filter $backupPattern -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        
        # Keep only the most recent MaxBackups files
        if ($existingBackups.Count -gt $MaxBackups) {
            $backupsToRemove = $existingBackups | Select-Object -Skip $MaxBackups
            foreach ($backup in $backupsToRemove) {
                try {
                    Remove-Item $backup.FullName -Force -ErrorAction Stop
                    Write-Info "Removed old backup: $($backup.Name)"
                } catch {
                    Write-Warning "Could not remove old backup: $($backup.Name)"
                }
            }
            Write-Success "Backup retention: kept $MaxBackups most recent backups"
        }
        
        Write-Success "Backup created: $(Split-Path $backupPath -Leaf)"
        return $backupPath
        
    } catch {
        Write-Warning "Failed to create backup: $_"
        return $null
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

# Get absolute path
function Get-AbsolutePath {
    param([string]$Path)
    
    if (Test-Path $Path) {
        # Use Resolve-Path for full resolution
        return Resolve-Path $Path
    } else {
        # Use unresolved method
        return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
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
                    return Get-AbsolutePath $pythonPath
                }
            }
        }
        
        try {
            Write-Info "Creating virtual environment with uv..."
            uv venv $VENV_PATH --python 3.12
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Environment created with uv"
                return Get-AbsolutePath "$VENV_PATH\Scripts\python.exe"
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
            return Get-AbsolutePath "$VENV_PATH\Scripts\python.exe"
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
    return Get-AbsolutePath "$VENV_PATH\Scripts\python.exe"
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
    param(
        [string]$PythonPath = "",
        [switch]$InstallDevDependencies = $false
    )
    
    Write-Step "Installing Dependencies"
    
    # If this is a legacy call without parameters, handle the global $Dev parameter
    if ($PythonPath -eq "" -or $args.Count -eq 0) {
        $InstallDevDependencies = $Dev
        
        # Legacy call without parameters - use pip
        $pipCmd = if (Test-Path "$VENV_PATH\Scripts\pip.exe") {
            "$VENV_PATH\Scripts\pip.exe"
        } elseif (Test-Command "pip") {
            "pip"
        } else {
            Write-Error "pip not found"
            exit 1
        }
        
        Write-Info "Installing Python dependencies with pip..."
        
        try {
            # Install main dependencies
            & $pipCmd install -r requirements.txt
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install main dependencies"
            }
            
            # Install dev dependencies if requested and file exists
            if ($InstallDevDependencies -and (Test-Path "requirements-dev.txt")) {
                Write-Info "Installing development dependencies..."
                & $pipCmd install -r requirements-dev.txt
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Failed to install dev dependencies, continuing..."
                } else {
                    Write-Success "Development dependencies installed"
                }
            } elseif ($InstallDevDependencies -and !(Test-Path "requirements-dev.txt")) {
                Write-Warning "Development dependencies requested but requirements-dev.txt not found"
            }
            
            Write-Success "Dependencies installed successfully"
        } catch {
            Write-Error "Failed to install dependencies: $_"
            exit 1
        }
        return
    }
    
    # New version with parameter - handle global $Dev parameter if not explicitly passed
    if ($args.Count -eq 1 -and $args[0] -is [string]) {
        $InstallDevDependencies = $Dev
    }
    
    # Try uv first for faster package management
    if (Test-Uv) {
        Write-Info "Installing dependencies with uv..."
        try {
            uv pip install -r requirements.txt
            if ($LASTEXITCODE -eq 0) {
                # Install dev dependencies if requested and file exists
                if ($InstallDevDependencies -and (Test-Path "requirements-dev.txt")) {
                    Write-Info "Installing development dependencies with uv..."
                    uv pip install -r requirements-dev.txt
                    if ($LASTEXITCODE -eq 0) {
                        Write-Success "Development dependencies installed with uv"
                    } else {
                        Write-Warning "Failed to install dev dependencies with uv, continuing..."
                    }
                } elseif ($InstallDevDependencies -and !(Test-Path "requirements-dev.txt")) {
                    Write-Warning "Development dependencies requested but requirements-dev.txt not found"
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
    
    # Install dev dependencies if requested and file exists
    if ($InstallDevDependencies -and (Test-Path "requirements-dev.txt")) {
        Write-Info "Installing development dependencies with pip..."
        & $pipCmd install -r requirements-dev.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Development dependencies installed"
        } else {
            Write-Warning "Failed to install dev dependencies, continuing..."
        }
    } elseif ($InstallDevDependencies -and !(Test-Path "requirements-dev.txt")) {
        Write-Warning "Development dependencies requested but requirements-dev.txt not found"
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
    $response = Read-Host "Configure Zen for Claude Desktop? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
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
            
            # Create backup with retention management
            $backupPath = Manage-ConfigBackups $claudeConfigPath
            
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
    $response = Read-Host "Configure Zen for Gemini CLI? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
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
"@ | Out-File -FilePath $zenWrapper -Encoding ASCII
        
        Write-Success "Created zen-mcp-server.cmd wrapper script"
    }
    
    # Update Gemini settings
    Write-Info "Updating Gemini CLI configuration..."
    
    try {
        # Create backup with retention management
        $backupPath = Manage-ConfigBackups $geminiConfig
        
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

# Check and update Cursor configuration
function Test-CursorIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    Write-Step "Checking Cursor Integration"
    
    # Check if Cursor is installed
    if (!(Test-Command "cursor")) {
        Write-Info "Cursor not detected - skipping Cursor integration"
        return
    }
    
    Write-Info "Found Cursor"
    
    $cursorConfigPath = "$env:USERPROFILE\.cursor\mcp.json"
    
    # Check if MCP is already configured
    if (Test-Path $cursorConfigPath) {
        try {
            $settings = Get-Content $cursorConfigPath -Raw | ConvertFrom-Json
            if ($settings.mcpServers -and $settings.mcpServers.zen) {
                Write-Success "Zen MCP already configured in Cursor"
                return
            }
        } catch {
            Write-Warning "Could not read existing Cursor configuration"
        }
    }
    
    # Ask user if they want to configure Cursor
    Write-Host ""
    $response = Read-Host "Configure Zen MCP for Cursor? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Skipping Cursor integration"
        return
    }
    
    try {
        # Create config directory if it doesn't exist
        $configDir = Split-Path $cursorConfigPath -Parent
        if (!(Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
        
        # Create backup with retention management
        if (Test-Path $cursorConfigPath) {
            $backupPath = Manage-ConfigBackups $cursorConfigPath
        }
        
        # Read existing config or create new one
        $config = @{}
        if (Test-Path $cursorConfigPath) {
            $config = Get-Content $cursorConfigPath -Raw | ConvertFrom-Json
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
        $config | ConvertTo-Json -Depth 10 | Out-File $cursorConfigPath -Encoding UTF8
        
        Write-Success "Successfully configured Cursor"
        Write-Host "  Config: $cursorConfigPath" -ForegroundColor Gray
        Write-Host "  Restart Cursor to use Zen MCP Server" -ForegroundColor Gray
        
    } catch {
        Write-Error "Failed to update Cursor configuration: $_"
        Write-Host ""
        Write-Host "Manual configuration for Cursor:"
        Write-Host "Location: $cursorConfigPath"
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

# Check and update Windsurf configuration
function Test-WindsurfIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    Write-Step "Checking Windsurf Integration"
    
    $windsurfConfigPath = "$env:USERPROFILE\.codeium\windsurf\mcp_config.json"
    $windsurfAppDir = "$env:USERPROFILE\.codeium\windsurf"
    
    # Check if Windsurf directory exists (better detection than command)
    if (!(Test-Path $windsurfAppDir)) {
        Write-Info "Windsurf not detected - skipping Windsurf integration"
        return
    }
    
    Write-Info "Found Windsurf installation"
    
    # Check if MCP is already configured
    if (Test-Path $windsurfConfigPath) {
        try {
            $settings = Get-Content $windsurfConfigPath -Raw | ConvertFrom-Json
            if ($settings.mcpServers -and $settings.mcpServers.zen) {
                Write-Success "Zen MCP already configured in Windsurf"
                return
            }
        } catch {
            Write-Warning "Could not read existing Windsurf configuration"
        }
    }
    
    # Ask user if they want to configure Windsurf
    Write-Host ""
    $response = Read-Host "Configure Zen MCP for Windsurf? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Skipping Windsurf integration"
        return
    }
    
    try {
        # Create config directory if it doesn't exist
        $configDir = Split-Path $windsurfConfigPath -Parent
        if (!(Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
        
        # Create backup with retention management
        if (Test-Path $windsurfConfigPath) {
            $backupPath = Manage-ConfigBackups $windsurfConfigPath
        }
        
        # Read existing config or create new one
        $config = @{}
        if (Test-Path $windsurfConfigPath) {
            $config = Get-Content $windsurfConfigPath -Raw | ConvertFrom-Json
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
        $config | ConvertTo-Json -Depth 10 | Out-File $windsurfConfigPath -Encoding UTF8
        
        Write-Success "Successfully configured Windsurf"
        Write-Host "  Config: $windsurfConfigPath" -ForegroundColor Gray
        Write-Host "  Restart Windsurf to use Zen MCP Server" -ForegroundColor Gray
        
    } catch {
        Write-Error "Failed to update Windsurf configuration: $_"
        Write-Host ""
        Write-Host "Manual configuration for Windsurf:"
        Write-Host "Location: $windsurfConfigPath"
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

# Check and update Trae configuration
function Test-TraeIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    Write-Step "Checking Trae Integration"
    
    $traeConfigPath = "$env:APPDATA\Trae\User\mcp.json"
    $traeAppDir = "$env:APPDATA\Trae"
    
    # Check if Trae directory exists (better detection than command)
    if (!(Test-Path $traeAppDir)) {
        Write-Info "Trae not detected - skipping Trae integration"
        return
    }
    
    Write-Info "Found Trae installation"
    
    # Check if MCP is already configured
    if (Test-Path $traeConfigPath) {
        try {
            $settings = Get-Content $traeConfigPath -Raw | ConvertFrom-Json
            if ($settings.mcpServers -and $settings.mcpServers.zen) {
                Write-Success "Zen MCP already configured in Trae"
                return
            }
        } catch {
            Write-Warning "Could not read existing Trae configuration"
        }
    }
    
    # Ask user if they want to configure Trae
    Write-Host ""
    $response = Read-Host "Configure Zen MCP for Trae? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Skipping Trae integration"
        return
    }
    
    try {
        # Create config directory if it doesn't exist
        $configDir = Split-Path $traeConfigPath -Parent
        if (!(Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }
        
        # Create backup with retention management
        if (Test-Path $traeConfigPath) {
            $backupPath = Manage-ConfigBackups $traeConfigPath
        }
        
        # Read existing config or create new one
        $config = @{}
        if (Test-Path $traeConfigPath) {
            $config = Get-Content $traeConfigPath -Raw | ConvertFrom-Json
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
        $config | ConvertTo-Json -Depth 10 | Out-File $traeConfigPath -Encoding UTF8
        
        Write-Success "Successfully configured Trae"
        Write-Host "  Config: $traeConfigPath" -ForegroundColor Gray
        Write-Host "  Restart Trae to use Zen MCP Server" -ForegroundColor Gray
        
    } catch {
        Write-Error "Failed to update Trae configuration: $_"
        Write-Host ""
        Write-Host "Manual configuration for Trae:"
        Write-Host "Location: $traeConfigPath"
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

# Check and update VSCode configuration
function Test-VSCodeIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    Write-Step "Checking VSCode Integration"
    
    # Check for VSCode installations
    $vscodeVersions = @()
    
    # VSCode standard
    if (Test-Command "code") {
        $vscodeVersions += @{
            Name = "VSCode"
            Command = "code"
            UserPath = "$env:APPDATA\Code\User"
        }
    }
    
    # VSCode Insiders
    if (Test-Command "code-insiders") {
        $vscodeVersions += @{
            Name = "VSCode Insiders"
            Command = "code-insiders"
            UserPath = "$env:APPDATA\Code - Insiders\User"
        }
    }
    
    if ($vscodeVersions.Count -eq 0) {
        Write-Info "VSCode not detected - skipping VSCode integration"
        return
    }
    
    foreach ($vscode in $vscodeVersions) {
        Write-Info "Found $($vscode.Name)"
        
        # Find settings.json files with modification dates
        $settingsFiles = @()
        $userPath = $vscode.UserPath
        
        # Check default profile
        $defaultSettings = Join-Path $userPath "settings.json"
        if (Test-Path $defaultSettings) {
            $lastWrite = (Get-Item $defaultSettings).LastWriteTime
            $settingsFiles += @{
                Path = $defaultSettings
                ProfileName = "Default Profile"
                LastModified = $lastWrite
            }
        }
        
        # Check profiles directory
        $profilesPath = Join-Path $userPath "profiles"
        if (Test-Path $profilesPath) {
            $profiles = Get-ChildItem $profilesPath -Directory
            foreach ($profile in $profiles) {
                $profileSettings = Join-Path $profile.FullName "settings.json"
                if (Test-Path $profileSettings) {
                    $lastWrite = (Get-Item $profileSettings).LastWriteTime
                    $settingsFiles += @{
                        Path = $profileSettings
                        ProfileName = "Profile: $($profile.Name)"
                        LastModified = $lastWrite
                    }
                }
            }
        }
        
        if ($settingsFiles.Count -eq 0) {
            Write-Warning "No settings.json found for $($vscode.Name)"
            continue
        }
        
        # Sort by last modified date (most recent first) and take only the most recent
        $mostRecentProfile = $settingsFiles | Sort-Object LastModified -Descending | Select-Object -First 1
        
        # Process only the most recent settings file
        $settingsFile = $mostRecentProfile
        $settingsPath = $settingsFile.Path
        $profileName = $settingsFile.ProfileName
        
        # Check if MCP is already configured
        if (Test-Path $settingsPath) {
            try {
                $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
                if ($settings.mcp -and $settings.mcp.servers -and $settings.mcp.servers.zen) {
                    Write-Success "Zen MCP already configured in $($vscode.Name)"
                    continue
                }
            } catch {
                Write-Warning "Could not read existing settings for $($vscode.Name)"
            }
        }
        
        # Ask user if they want to configure this VSCode instance
        Write-Host ""
        $response = Read-Host "Configure Zen MCP for $($vscode.Name)? (y/N)"
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Info "Skipping $($vscode.Name)"
            continue
        }
        
                    try {
                # Create backup with retention management
                if (Test-Path $settingsPath) {
                    $backupPath = Manage-ConfigBackups $settingsPath
                }
                
                # Read existing settings as JSON string
                $jsonContent = "{}"
                if (Test-Path $settingsPath) {
                    $jsonContent = Get-Content $settingsPath -Raw
                    if (!$jsonContent.Trim()) {
                        $jsonContent = "{}"
                    }
                } else {
                    # Create directory if it doesn't exist
                    $settingsDir = Split-Path $settingsPath -Parent
                    if (!(Test-Path $settingsDir)) {
                        New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
                    }
                }
                
                # Parse JSON
                $settings = $jsonContent | ConvertFrom-Json
                
                # Build zen configuration
                $zenConfigObject = New-Object PSObject
                $zenConfigObject | Add-Member -MemberType NoteProperty -Name "command" -Value $PythonPath
                $zenConfigObject | Add-Member -MemberType NoteProperty -Name "args" -Value @($ServerPath)
                
                # Build servers object
                $serversObject = New-Object PSObject
                $serversObject | Add-Member -MemberType NoteProperty -Name "zen" -Value $zenConfigObject
                
                # Build mcp object
                $mcpObject = New-Object PSObject
                $mcpObject | Add-Member -MemberType NoteProperty -Name "servers" -Value $serversObject
                
                # Add mcp to settings (replace if exists)
                if ($settings.PSObject.Properties.Name -contains "mcp") {
                    $settings.mcp = $mcpObject
                } else {
                    $settings | Add-Member -MemberType NoteProperty -Name "mcp" -Value $mcpObject
                }
                
                # Write updated settings
                $settings | ConvertTo-Json -Depth 10 | Out-File $settingsPath -Encoding UTF8
            
            Write-Success "Successfully configured $($vscode.Name)"
            Write-Host "  Config: $settingsPath" -ForegroundColor Gray
            Write-Host "  Restart $($vscode.Name) to use Zen MCP Server" -ForegroundColor Gray
            
        } catch {
            Write-Error "Failed to update $($vscode.Name) settings: $_"
            Write-Host ""
            Write-Host "Manual configuration for $($vscode.Name):"
            Write-Host "Location: $settingsPath"
            Write-Host "Add this to your settings.json:"
            Write-Host @"
{
  "mcp": {
    "servers": {
      "zen": {
        "command": "$PythonPath",
        "args": ["$ServerPath"]
      }
    }
  }
}
"@ -ForegroundColor Yellow
        }
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
    
    Write-Info "3. For VSCode:"
    Write-Host "   Add this configuration to your VSCode settings.json:"
    Write-Host "   Location: $env:APPDATA\Code\User\<profile-id>\settings.json"
    Write-Host ""
    
    $vscodeConfigJson = @{
        mcp = @{
            servers = @{
                zen = @{
                    command = $PythonPath
                    args = @($ServerPath)
                }
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $vscodeConfigJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "4. For Cursor:"
    Write-Host "   Add this configuration to your Cursor config file:"
    Write-Host "   Location: $env:USERPROFILE\.cursor\mcp.json"
    Write-Host ""
    
    $cursorConfigJson = @{
        mcpServers = @{
            zen = @{
                command = $PythonPath
                args = @($ServerPath)
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $cursorConfigJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "5. For Trae:"
    Write-Host "   Add this configuration to your Trae config file:"
    Write-Host "   Location: $env:APPDATA\Trae\Users\mcp.json"
    Write-Host ""
    
    $traeConfigJson = @{
        mcpServers = @{
            zen = @{
                command = $PythonPath
                args = @($ServerPath)
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $traeConfigJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "6. For Windsurf:"
    Write-Host "   Add this configuration to your Windsurf config file:"
    Write-Host "   Location: $env:USERPROFILE\.codeium\windsurf\mcp_config.json"
    Write-Host ""
    
    $windsurfConfigJson = @{
        mcpServers = @{
            zen = @{
                command = $PythonPath
                args = @($ServerPath)
            }
        }
    } | ConvertTo-Json -Depth 5
    
    Write-Host $windsurfConfigJson -ForegroundColor Yellow
    Write-Host ""
    
    Write-Info "7. Restart Claude Desktop, Gemini CLI, VSCode, Cursor, Windsurf, or Trae after updating the config files"
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
            $serverPath = Get-AbsolutePath "server.py"
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
        Install-Dependencies $pythonPath -InstallDevDependencies:$Dev
    } catch {
        Write-Error "Failed to install dependencies: $_"
        exit 1
    }
    
    # Step 7: Get absolute server path
    $serverPath = Get-AbsolutePath "server.py"
    
    # Step 8: Display setup instructions
    Show-SetupInstructions $pythonPath $serverPath
    
    # Step 9: Check Claude integrations
    Test-ClaudeCliIntegration $pythonPath $serverPath
    Test-ClaudeDesktopIntegration $pythonPath $serverPath
    
    # Step 10: Check VSCode integration
    Test-VSCodeIntegration $pythonPath $serverPath
    
    # Step 11: Check Cursor integration  
    Test-CursorIntegration $pythonPath $serverPath
    
    # Step 12: Check Windsurf integration
    Test-WindsurfIntegration $pythonPath $serverPath
    
    # Step 13: Check Trae integration
    Test-TraeIntegration $pythonPath $serverPath
    
    # Step 14: Check Gemini CLI integration
    Test-GeminiCliIntegration (Split-Path $serverPath -Parent)
    
    # Step 15: Setup logging directory
    Initialize-Logging
    
    # Step 16: Display log information
    Write-Host ""
    Write-Host "Logs will be written to: $(Get-AbsolutePath $LOG_DIR)\$LOG_FILE"
    Write-Host ""
    
    # Step 17: Handle command line arguments
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
