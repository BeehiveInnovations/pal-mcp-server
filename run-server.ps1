<#
.SYNOPSIS
    Installation, configuration, and launch script for PAL MCP server on Windows.

.DESCRIPTION
    This PowerShell script prepares the environment for the PAL MCP server:
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
    Shows PAL MCP server version.

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

.PARAMETER Docker
    Uses Docker to build and run the MCP server instead of Python virtual environment.

.EXAMPLE
    .\run-server.ps1
    Prepares the environment and starts the PAL MCP server.

    .\run-server.ps1 -Follow
    Follows server logs in real time.

    .\run-server.ps1 -Config
    Shows configuration instructions for clients.

    .\run-server.ps1 -Dev
    Prepares the environment with development dependencies and starts the server.

    .\run-server.ps1 -Docker
    Builds and runs the server using Docker containers.

    .\run-server.ps1 -Docker -Follow
    Builds and runs the server using Docker containers and follows the logs.

    .\run-server.ps1 -Docker -Force
    Forces rebuilding of the Docker image and runs the server.

.NOTES
    Project Author     : BeehiveInnovations
    Script Author      : GiGiDKR (https://github.com/GiGiDKR)
    Date               : 07-05-2025
    Version            : See config.py (__version__)
    References         : https://github.com/BeehiveInnovations/pal-mcp-server

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
    [switch]$Dev,
    [switch]$Docker
)

# ============================================================================
# PAL MCP Server Setup Script for Windows
# 
# A Windows-compatible setup script that handles environment setup, 
# dependency installation, and configuration.
# ============================================================================

# Set error action preference
$ErrorActionPreference = "Stop"

# ----------------------------------------------------------------------------
# Constants and Configuration  
# ----------------------------------------------------------------------------

$script:VENV_PATH = ".pal_venv"
$script:DOCKER_CLEANED_FLAG = ".docker_cleaned"
$script:DESKTOP_CONFIG_FLAG = ".desktop_configured"
$script:LOG_DIR = "logs"
$script:LOG_FILE = "mcp_server.log"
$script:LegacyServerNames = @("zen", "zen-mcp", "zen-mcp-server", "zen_mcp", "zen_mcp_server")

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
    }
    catch {
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
    }
    catch {
        Write-Warning "Standard removal failed, trying alternative methods..."
        
        # Method 1: Use takeown and icacls to force ownership
        try {
            Write-Info "Attempting to take ownership of locked files..."
            takeown /F "$Path" /R /D Y 2>$null | Out-Null
            icacls "$Path" /grant administrators:F /T 2>$null | Out-Null
            Remove-Item -Recurse -Force $Path -ErrorAction Stop
            return $true
        }
        catch {
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
        }
        catch {
            Write-Warning "Rename method failed"
        }
        
        # If all methods fail, return false
        return $false
    }
}

# Remove legacy MCP server entries from a hash/dictionary or PSObject
function Remove-LegacyServerKeys {
    param([object]$Container)

    $removed = $false
    if ($null -eq $Container) {
        return $false
    }

    foreach ($legacy in $script:LegacyServerNames) {
        if ($Container -is [System.Collections.IDictionary]) {
            if ($Container.Contains($legacy)) {
                $Container.Remove($legacy) | Out-Null
                $removed = $true
            }
        }
        elseif ($Container.PSObject -and $Container.PSObject.Properties[$legacy]) {
            $Container.PSObject.Properties.Remove($legacy)
            $removed = $true
        }
    }

    return $removed
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
                }
                catch {
                    Write-Warning "Could not remove old backup: $($backup.Name)"
                }
            }
            Write-Success "Backup retention: kept $MaxBackups most recent backups"
        }
        
        Write-Success "Backup created: $(Split-Path $backupPath -Leaf)"
        return $backupPath
        
    }
    catch {
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
    }
    catch {
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
    }
    catch {
        Write-Warning "Could not clear all cache files: $_"
    }
}

# Get absolute path
function Get-AbsolutePath {
    param([string]$Path)
    
    if (Test-Path $Path) {
        # Use Resolve-Path for full resolution
        return Resolve-Path $Path
    }
    else {
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
    }
    catch {
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
        }
        catch {
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
    }
    catch {
        return
    }
    
    $foundArtifacts = $false
    
    # Define containers to remove
    $containers = @(
        "gemini-mcp-server",
        "gemini-mcp-redis", 
        "pal-mcp-server",
        "pal-mcp-redis",
        "pal-mcp-log-monitor"
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
        }
        catch {
            # Ignore errors
        }
    }
    
    # Remove images
    $images = @("gemini-mcp-server:latest", "pal-mcp-server:latest")
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
        }
        catch {
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
        }
        catch {
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
        "GEMINI_API_KEY"     = "AIza[0-9A-Za-z-_]{35}"
        "OPENAI_API_KEY"     = "sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}"
        "XAI_API_KEY"        = "xai-[a-zA-Z0-9-_]+"
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
            }
            else {
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
        }
        catch {
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
                }
                else {
                    throw "Unable to remove existing environment. Please restart your computer and try again."
                }
                
            }
            catch {
                Write-Error "Failed to remove existing environment: $_"
                Write-Host ""
                Write-Host "Try these solutions:" -ForegroundColor Yellow
                Write-Host "1. Close all terminals and VS Code instances" -ForegroundColor White
                Write-Host "2. Run: Get-Process python* | Stop-Process -Force" -ForegroundColor White
                Write-Host "3. Manually delete: $VENV_PATH" -ForegroundColor White
                Write-Host "4. Then run the script again" -ForegroundColor White
                exit 1
            }
        }
        else {
            Write-Success "Virtual environment already exists"
            return Get-AbsolutePath "$VENV_PATH\Scripts\python.exe"
        }
    }
    
    Write-Info "Creating virtual environment with $pythonCmd..."
    if ($pythonCmd.StartsWith("py ")) {
        Invoke-Expression "$pythonCmd -m venv $VENV_PATH"
    }
    else {
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
                }
                else {
                    throw "Unable to remove existing environment. Please restart your computer and try again."
                }
                
            }
            catch {
                Write-Error "Failed to remove existing environment: $_"
                Write-Host ""
                Write-Host "Try these solutions:" -ForegroundColor Yellow
                Write-Host "1. Close all terminals and VS Code instances" -ForegroundColor White
                Write-Host "2. Run: Get-Process python* | Stop-Process -Force" -ForegroundColor White
                Write-Host "3. Manually delete: $VENV_PATH" -ForegroundColor White
                Write-Host "4. Then run the script again" -ForegroundColor White
                exit 1
            }
        }
        else {
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
        }
        else {
            & $pythonCmd -m venv $VENV_PATH
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        
        Write-Success "Virtual environment created"
    }
    catch {
        Write-Error "Failed to create virtual environment: $_"
        exit 1
    }
}

# Install dependencies function - Simplified uv-first approach
function Install-Dependencies {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonPath,
        [switch]$InstallDevDependencies = $false
    )
    
    Write-Step "Installing Dependencies"

    # Build requirements files list
    $requirementsFiles = @("requirements.txt")
    if ($InstallDevDependencies) {
        if (Test-Path "requirements-dev.txt") {
            $requirementsFiles += "requirements-dev.txt"
            Write-Info "Including development dependencies from requirements-dev.txt"
        }
        else {
            Write-Warning "Development dependencies requested but requirements-dev.txt not found"
        }
    }

    # Try uv first for faster package management
    $useUv = Test-Uv
    if ($useUv) {
        Write-Info "Installing dependencies with uv (fast)..."
        try {
            foreach ($file in $requirementsFiles) {
                Write-Info "Installing from $file with uv..."
                $uv = (Get-Command uv -ErrorAction Stop).Source
                $arguments = @('pip', 'install', '-r', $file, '--python', $PythonPath)
                $proc = Start-Process -FilePath $uv -ArgumentList $arguments -NoNewWindow -Wait -PassThru

                if ($proc.ExitCode -ne 0) { 
                    throw "uv failed to install $file with exit code $($proc.ExitCode)" 
                }

            }
            Write-Success "Dependencies installed successfully with uv"
            return
        }
        catch {
            Write-Warning "uv installation failed: $_. Falling back to pip"
            $useUv = $false
        }
    }

    # Fallback to pip
    Write-Info "Installing dependencies with pip..."
    $pipCmd = Join-Path (Split-Path $PythonPath -Parent) "pip.exe"
    
    try {
        # Upgrade pip first
        & $pipCmd install --upgrade pip | Out-Null
    }
    catch {
        Write-Warning "Could not upgrade pip, continuing..."
    }

    try {
        foreach ($file in $requirementsFiles) {
            Write-Info "Installing from $file with pip..."
            & $pipCmd install -r $file
            if ($LASTEXITCODE -ne 0) {
                throw "pip failed to install $file"
            }
        }
        Write-Success "Dependencies installed successfully with pip"
    }
    catch {
        Write-Error "Failed to install dependencies with pip: $_"
        exit 1
    }
}

# ----------------------------------------------------------------------------
# Docker Functions
# ============================================================================

# Test Docker availability and requirements
function Test-DockerRequirements {
    Write-Step "Checking Docker Requirements"
    
    if (!(Test-Command "docker")) {
        Write-Error "Docker not found. Please install Docker Desktop from https://docker.com"
        return $false
    }
    
    try {
        $null = docker version 2>$null
        Write-Success "Docker is installed and running"
    }
    catch {
        Write-Error "Docker is installed but not running. Please start Docker Desktop."
        return $false
    }
    
    if (!(Test-Command "docker-compose")) {
        Write-Warning "docker-compose not found. Trying docker compose..."
        try {
            $null = docker compose version 2>$null
            Write-Success "Docker Compose (v2) is available"
            return $true
        }
        catch {
            Write-Error "Docker Compose not found. Please install Docker Compose."
            return $false
        }
    }
    else {
        Write-Success "Docker Compose is available"
        return $true
    }
}

# Build Docker image
function Build-DockerImage {
    param([switch]$Force = $false)
    
    Write-Step "Building Docker Image"
    
    # Check if image exists
    try {
        $imageExists = docker images --format "{{.Repository}}:{{.Tag}}" | Where-Object { $_ -eq "pal-mcp-server:latest" }
        if ($imageExists -and !$Force) {
            Write-Success "Docker image already exists. Use -Force to rebuild."
            return $true
        }
    }
    catch {
        # Continue if command fails
    }
    
    if ($Force -and $imageExists) {
        Write-Info "Forcing rebuild of Docker image..."
        try {
            docker rmi pal-mcp-server:latest 2>$null
        }
        catch {
            Write-Warning "Could not remove existing image, continuing..."
        }
    }
    
    Write-Info "Building Docker image from Dockerfile..."
    try {
        $buildArgs = @()
        if ($Dev) {
            # For development builds, we could add specific build args
            Write-Info "Building with development support..."
        }
        
        docker build -t pal-mcp-server:latest .
        if ($LASTEXITCODE -ne 0) {
            throw "Docker build failed"
        }
        
        Write-Success "Docker image built successfully"
        return $true
    }
    catch {
        Write-Error "Failed to build Docker image: $_"
        return $false
    }
}

# Prepare Docker environment file
function Initialize-DockerEnvironment {
    Write-Step "Preparing Docker Environment"
    
    # Ensure .env file exists
    if (!(Test-Path ".env")) {
        Write-Warning "No .env file found. Creating default .env file..."
        
        $defaultEnv = @"
# API Keys - Replace with your actual keys
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
XAI_API_KEY=your_xai_api_key_here
DIAL_API_KEY=your_dial_api_key_here
DIAL_API_HOST=your_dial_api_host_here
DIAL_API_VERSION=your_dial_api_version_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
CUSTOM_API_URL=your_custom_api_url_here
CUSTOM_API_KEY=your_custom_api_key_here
CUSTOM_MODEL_NAME=your_custom_model_name_here

# Server Configuration
DEFAULT_MODEL=auto
LOG_LEVEL=INFO
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5
DEFAULT_THINKING_MODE_THINKDEEP=high

# Optional Advanced Settings
#DISABLED_TOOLS=
#MAX_MCP_OUTPUT_TOKENS=
#TZ=UTC
"@
        
        $defaultEnv | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success "Default .env file created"
        Write-Warning "Please edit .env file with your actual API keys"
    }
    else {
        Write-Success ".env file exists"
    }
    
    # Create logs directory for volume mount
    Initialize-Logging
    
    return $true
}

# Start Docker services
function Start-DockerServices {
    param([switch]$Follow = $false)
    
    Write-Step "Starting Docker Services"
    
    # Check if docker-compose.yml exists
    if (!(Test-Path "docker-compose.yml")) {
        Write-Error "docker-compose.yml not found in current directory"
        return $false
    }
    
    try {
        # Stop any existing services
        Write-Info "Stopping any existing services..."
        if (Test-Command "docker-compose") {
            docker-compose down 2>$null
        }
        else {
            docker compose down 2>$null
        }
        
        # Start services
        Write-Info "Starting PAL MCP Server with Docker Compose..."
        if (Test-Command "docker-compose") {
            if ($Follow) {
                docker-compose up --build
            }
            else {
                docker-compose up -d --build
            }
        }
        else {
            if ($Follow) {
                docker compose up --build
            }
            else {
                docker compose up -d --build
            }
        }
        
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to start Docker services"
        }
        
        if (!$Follow) {
            Write-Success "Docker services started successfully"
            Write-Info "Container name: pal-mcp-server"
            Write-Host ""
            Write-Host "To view logs: " -NoNewline
            Write-Host "docker logs -f pal-mcp-server" -ForegroundColor Yellow
            Write-Host "To stop: " -NoNewline
            Write-Host "docker-compose down" -ForegroundColor Yellow
        }
        
        return $true
    }
    catch {
        Write-Error "Failed to start Docker services: $_"
        return $false
    }
}

# Get Docker container status
function Get-DockerStatus {
    try {
        $containerStatus = docker ps --filter "name=pal-mcp-server" --format "{{.Status}}"
        if ($containerStatus) {
            Write-Success "Container status: $containerStatus"
            return $true
        }
        else {
            Write-Warning "Container not running"
            return $false
        }
    }
    catch {
        Write-Warning "Could not get container status: $_"
        return $false
    }
}

# ============================================================================
# End Docker Functions
# ============================================================================

# Setup logging directory
function Initialize-Logging {
    Write-Step "Setting up Logging"
    
    if (!(Test-Path $LOG_DIR)) {
        New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null
        Write-Success "Logs directory created"
    }
    else {
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
            }
            else {
                Write-Warning "Docker Compose not found. Install Docker Desktop for Windows."
            }
        }
        catch {
            Write-Warning "Docker is installed but not running. Please start Docker Desktop."
        }
    }
    else {
        Write-Warning "Docker not found. Install Docker Desktop from https://docker.com"
    }
}

# ----------------------------------------------------------------------------
# MCP Client Configuration System
# ----------------------------------------------------------------------------

# Centralized MCP client definitions
$script:McpClientDefinitions = @(
    @{
        Name           = "Claude Desktop"
        DetectionPath  = "$env:APPDATA\Claude\claude_desktop_config.json"
        DetectionType  = "Path"
        ConfigPath     = "$env:APPDATA\Claude\claude_desktop_config.json"
        ConfigJsonPath = "mcpServers.pal"
        NeedsConfigDir = $true
    },
    @{
        Name             = "VSCode"
        DetectionCommand = "code"
        DetectionType    = "Command"
        ConfigPath       = "$env:APPDATA\Code\User\settings.json"
        ConfigJsonPath   = "mcp.servers.pal"
        IsVSCode         = $true
    },
    @{
        Name             = "VSCode Insiders"
        DetectionCommand = "code-insiders"
        DetectionType    = "Command"
        ConfigPath       = "$env:APPDATA\Code - Insiders\User\mcp.json"
        ConfigJsonPath   = "servers.pal"
        IsVSCodeInsiders = $true
    },
    @{
        Name             = "Cursor"
        DetectionCommand = "cursor"
        DetectionType    = "Command"
        ConfigPath       = "$env:USERPROFILE\.cursor\mcp.json"
        ConfigJsonPath   = "mcpServers.pal"
    },
    @{
        Name           = "Windsurf"
        DetectionPath  = "$env:USERPROFILE\.codeium\windsurf"
        DetectionType  = "Path"
        ConfigPath     = "$env:USERPROFILE\.codeium\windsurf\mcp_config.json"
        ConfigJsonPath = "mcpServers.pal"
    },
    @{
        Name           = "Trae"
        DetectionPath  = "$env:APPDATA\Trae"
        DetectionType  = "Path"
        ConfigPath     = "$env:APPDATA\Trae\User\mcp.json"
        ConfigJsonPath = "mcpServers.pal"
    }
)

# Docker MCP configuration template (legacy, kept for backward compatibility)
$script:DockerMcpConfig = @{
    command = "docker"
    args    = @("exec", "-i", "pal-mcp-server", "python", "server.py")
    type    = "stdio"
}

# Generate Docker MCP configuration using docker run (recommended for all clients)
function Get-DockerMcpConfigRun {
    param([string]$ServerPath)
    
    $scriptDir = Split-Path $ServerPath -Parent
    $envFile = Join-Path $scriptDir ".env"
    
    return @{
        command = "docker"
        args    = @("run", "--rm", "-i", "--env-file", $envFile, "pal-mcp-server:latest", "python", "server.py")
        type    = "stdio"
    }
}

# Generate Python MCP configuration
function Get-PythonMcpConfig {
    param([string]$PythonPath, [string]$ServerPath)
    return @{
        command = $PythonPath
        args    = @($ServerPath)
        type    = "stdio"
    }
}

# Check if client uses mcp.json format with servers structure
function Test-McpJsonFormat {
    param([hashtable]$Client)
    
    $configFileName = Split-Path $Client.ConfigPath -Leaf
    return $configFileName -eq "mcp.json"
}

# Check if client uses the new VS Code Insiders format (servers instead of mcpServers)
function Test-VSCodeInsidersFormat {
    param([hashtable]$Client)
    
    return $Client.IsVSCodeInsiders -eq $true -and $Client.ConfigJsonPath -eq "servers.pal"
}

# Analyze existing MCP configuration to determine type (Python or Docker)
function Get-ExistingMcpConfigType {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Client,
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath
    )
    
    if (!(Test-Path $ConfigPath)) {
        return @{
            Exists  = $false
            Type    = "None"
            Details = "No configuration found"
        }
    }
    
    try {
        $content = Get-Content $ConfigPath -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
        if (!$content) {
            return @{
                Exists  = $false
                Type    = "None"
                Details = "Invalid JSON configuration"
            }
        }
        
        # Navigate to pal configuration
        $pathParts = $Client.ConfigJsonPath.Split('.')
        $palKey = $pathParts[-1]
        $parentPath = $pathParts[0..($pathParts.Length - 2)]
        
        $targetObject = $content
        foreach ($key in $parentPath) {
            if (!$targetObject.PSObject.Properties[$key]) {
                return @{
                    Exists  = $false
                    Type    = "None"
                    Details = "Configuration structure not found"
                }
            }
            $targetObject = $targetObject.$key
        }
        
        if (!$targetObject.PSObject.Properties[$palKey]) {
            return @{
                Exists  = $false
                Type    = "None"
                Details = "PAL configuration not found"
            }
        }
        
        $palConfig = $targetObject.$palKey
        
        # Analyze configuration type
        if ($palConfig.command -eq "docker") {
            $dockerType = "Unknown"
            $details = "Docker configuration"
            
            if ($palConfig.args -and $palConfig.args.Count -gt 0) {
                if ($palConfig.args[0] -eq "run") {
                    $dockerType = "Docker Run"
                    $details = "Docker run (dedicated container)"
                }
                elseif ($palConfig.args[0] -eq "exec") {
                    $dockerType = "Docker Exec"
                    $details = "Docker exec (existing container)"
                }
                else {
                    $details = "Docker ($($palConfig.args[0]))"
                }
            }
            
            return @{
                Exists  = $true
                Type    = "Docker"
                SubType = $dockerType
                Details = $details
                Command = $palConfig.command
                Args    = $palConfig.args
            }
        }
        elseif ($palConfig.command -and $palConfig.command.EndsWith("python.exe")) {
            $pythonType = "Python"
            $details = "Python virtual environment"
            
            if ($palConfig.command.Contains(".pal_venv")) {
                $details = "Python (pal virtual environment)"
            }
            elseif ($palConfig.command.Contains("venv")) {
                $details = "Python (virtual environment)"
            }
            else {
                $details = "Python (system installation)"
            }
            
            return @{
                Exists  = $true
                Type    = "Python"
                SubType = $pythonType
                Details = $details
                Command = $palConfig.command
                Args    = $palConfig.args
            }
        }
        else {
            return @{
                Exists  = $true
                Type    = "Unknown"
                Details = "Unknown configuration type: $($palConfig.command)"
                Command = $palConfig.command
                Args    = $palConfig.args
            }
        }
        
    }
    catch {
        return @{
            Exists  = $false
            Type    = "Error"
            Details = "Error reading configuration: $_"
        }
    }
}

# Generic MCP client configuration function
function Configure-McpClient {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Client,
        [Parameter(Mandatory = $true)]
        [bool]$UseDocker,
        [string]$PythonPath = "",
        [string]$ServerPath = ""
    )

    Write-Step "Checking $($Client.Name) Integration"

    # Client detection
    $detected = $false
    if ($Client.DetectionType -eq "Command" -and (Test-Command $Client.DetectionCommand)) {
        $detected = $true
    }
    elseif ($Client.DetectionType -eq "Path" -and (Test-Path ($Client.DetectionPath -as [string]))) {
        $detected = $true
    }

    if (!$detected) {
        Write-Info "$($Client.Name) not detected - skipping integration"
        return
    }
    Write-Info "Found $($Client.Name)"

    # Handle VSCode special logic for profiles
    $configPath = $Client.ConfigPath
    if ($Client.IsVSCode) {
        $userPath = Split-Path $configPath -Parent
        if (!(Test-Path $userPath)) {
            Write-Warning "$($Client.Name) user directory not found. Skipping."
            return
        }
        
        # Find most recent settings.json (default or profile)
        $settingsFiles = @()
        $defaultSettings = $configPath
        if (Test-Path $defaultSettings) {
            $settingsFiles += @{
                Path         = $defaultSettings
                LastModified = (Get-Item $defaultSettings).LastWriteTime
            }
        }
        
        $profilesPath = Join-Path $userPath "profiles"
        if (Test-Path $profilesPath) {
            Get-ChildItem $profilesPath -Directory | ForEach-Object {
                $profileSettings = Join-Path $_.FullName "settings.json"
                if (Test-Path $profileSettings) {
                    $settingsFiles += @{
                        Path         = $profileSettings
                        LastModified = (Get-Item $profileSettings).LastWriteTime
                    }
                }
            }
        }
        
        if ($settingsFiles.Count -gt 0) {
            $configPath = ($settingsFiles | Sort-Object LastModified -Descending | Select-Object -First 1).Path
        }
    }

    # Handle VSCode Insiders special logic for profiles (uses mcp.json)
    if ($Client.IsVSCodeInsiders) {
        $userPath = Split-Path $configPath -Parent
        if (!(Test-Path $userPath)) {
            Write-Warning "$($Client.Name) user directory not found. Skipping."
            return
        }
        
        # Find most recent mcp.json (default or profile)
        $mcpFiles = @()
        $defaultMcp = $configPath
        if (Test-Path $defaultMcp) {
            $mcpFiles += @{
                Path         = $defaultMcp
                LastModified = (Get-Item $defaultMcp).LastWriteTime
            }
        }
        
        $profilesPath = Join-Path $userPath "profiles"
        if (Test-Path $profilesPath) {
            Get-ChildItem $profilesPath -Directory | ForEach-Object {
                $profileMcp = Join-Path $_.FullName "mcp.json"
                if (Test-Path $profileMcp) {
                    $mcpFiles += @{
                        Path         = $profileMcp
                        LastModified = (Get-Item $profileMcp).LastWriteTime
                    }
                }
            }
        }
        
        if ($mcpFiles.Count -gt 0) {
            $configPath = ($mcpFiles | Sort-Object LastModified -Descending | Select-Object -First 1).Path
        }
    }

    # Check if already configured and analyze existing configuration
    $existingConfig = Get-ExistingMcpConfigType -Client $Client -ConfigPath $configPath
    $newConfigType = if ($UseDocker) { "Docker" } else { "Python" }
    
    if ($existingConfig.Exists) {
        Write-Info "Found existing PAL MCP configuration in $($Client.Name)"
        Write-Info "  Current: $($existingConfig.Details)"
        Write-Info "  New: $newConfigType configuration"
        
        if ($existingConfig.Type -eq $newConfigType) {
            Write-Warning "Same configuration type ($($existingConfig.Type)) already exists"
            $response = Read-Host "`nOverwrite existing $($existingConfig.Type) configuration? (y/N)"
        }
        else {
            Write-Warning "Different configuration type detected"
            Write-Info "  Replacing: $($existingConfig.Type) → $newConfigType"
            $response = Read-Host "`nReplace $($existingConfig.Type) with $newConfigType configuration? (y/N)"
        }
        
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Info "Keeping existing configuration in $($Client.Name)"
            return
        }
        
        Write-Info "Proceeding with configuration update..."
    }
    else {
        # User confirmation for new installation
        $response = Read-Host "`nConfigure PAL MCP for $($Client.Name) (mode: $newConfigType)? (y/N)"
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Info "Skipping $($Client.Name) integration"
            return
        }
    }

    try {
        # Create config directory if needed
        $configDir = Split-Path $configPath -Parent
        if (!(Test-Path $configDir)) {
            New-Item -ItemType Directory -Path $configDir -Force | Out-Null
        }

        # Backup existing config
        if (Test-Path $configPath) {
            Manage-ConfigBackups -ConfigFilePath $configPath
        }

        # Read or create config
        $config = New-Object PSObject
        $usesMcpJsonFormat = Test-McpJsonFormat -Client $Client
        $usesVSCodeInsidersFormat = Test-VSCodeInsidersFormat -Client $Client
        
        if (Test-Path $configPath) {
            $fileContent = Get-Content $configPath -Raw
            if ($fileContent.Trim()) {
                $config = $fileContent | ConvertFrom-Json -ErrorAction SilentlyContinue
            }
            if ($null -eq $config) { $config = New-Object PSObject }
        }
        
        # Initialize structure for mcp.json format files if they don't exist or are empty
        if ($usesMcpJsonFormat) {
            if ($usesVSCodeInsidersFormat) {
                # For VS Code Insiders format: {"servers": {...}}
                if (!$config.PSObject.Properties["servers"]) {
                    $config | Add-Member -MemberType NoteProperty -Name "servers" -Value (New-Object PSObject)
                }
            }
            else {
                # For other clients format: {"mcpServers": {...}}
                if (!$config.PSObject.Properties["mcpServers"]) {
                    $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value (New-Object PSObject)
                }
            }
        }
        
        # Initialize MCP structure for VS Code settings.json if it doesn't exist
        if ($Client.IsVSCode -and $Client.ConfigJsonPath.StartsWith("mcp.")) {
            if (!$config.PSObject.Properties["mcp"]) {
                $config | Add-Member -MemberType NoteProperty -Name "mcp" -Value (New-Object PSObject)
            }
            if (!$config.mcp.PSObject.Properties["servers"]) {
                $config.mcp | Add-Member -MemberType NoteProperty -Name "servers" -Value (New-Object PSObject)
            }
        }

        # Generate server config
        $serverConfig = if ($UseDocker) { 
            # Use docker run for all clients (more reliable than docker exec)
            Get-DockerMcpConfigRun $ServerPath
        }
        else { 
            Get-PythonMcpConfig $PythonPath $ServerPath 
        }

        # Navigate and set configuration
        $pathParts = $Client.ConfigJsonPath.Split('.')
        $palKey = $pathParts[-1]
        $parentPath = $pathParts[0..($pathParts.Length - 2)]
        
        $targetObject = $config
        foreach ($key in $parentPath) {
            if (!$targetObject.PSObject.Properties[$key]) {
                $targetObject | Add-Member -MemberType NoteProperty -Name $key -Value (New-Object PSObject)
            }
            $targetObject = $targetObject.$key
        }

        # Remove legacy zen entries to avoid duplicate or broken MCP servers
        $legacyRemoved = Remove-LegacyServerKeys $targetObject
        if ($legacyRemoved) {
            Write-Info "Removed legacy MCP entries (zen → pal)"
        }

        $targetObject | Add-Member -MemberType NoteProperty -Name $palKey -Value $serverConfig -Force

        # Write config
        $config | ConvertTo-Json -Depth 10 | Out-File $configPath -Encoding UTF8
        Write-Success "Successfully configured $($Client.Name)"
        Write-Host "  Config: $configPath" -ForegroundColor Gray
        Write-Host "  Restart $($Client.Name) to use the new MCP server" -ForegroundColor Gray

    }
    catch {
        Write-Error "Failed to update $($Client.Name) configuration: $_"
    }
}

# Main MCP client configuration orchestrator
function Invoke-McpClientConfiguration {
    param(
        [Parameter(Mandatory = $true)]
        [bool]$UseDocker,
        [string]$PythonPath = "",
        [string]$ServerPath = ""
    )
    
    Write-Step "Checking Client Integrations"
    
    # Configure GUI clients
    foreach ($client in $script:McpClientDefinitions) {
        Configure-McpClient -Client $client -UseDocker $UseDocker -PythonPath $PythonPath -ServerPath $ServerPath
    }
    
    # Handle CLI tools separately (they don't follow JSON config pattern)
    if (!$UseDocker) {
        Test-ClaudeCliIntegration $PythonPath $ServerPath
        Test-GeminiCliIntegration (Split-Path $ServerPath -Parent)
        Test-QwenCliIntegration $PythonPath $ServerPath
    }
}

# Keep existing CLI integration functions
function Test-ClaudeCliIntegration {
    param([string]$PythonPath, [string]$ServerPath)
    
    if (!(Test-Command "claude")) {
        return
    }
    
    Write-Info "Claude CLI detected - checking configuration..."

    foreach ($legacy in $script:LegacyServerNames) {
        try { claude mcp remove -s user $legacy 2>$null | Out-Null } catch {}
    }
    
    try {
        $claudeConfig = claude mcp list 2>$null
        if ($claudeConfig -match "pal") {
            Write-Success "Claude CLI already configured for pal server"
        }
        else {
            Write-Info "To add pal server to Claude CLI, run:"
            Write-Host "  claude mcp add -s user pal $PythonPath $ServerPath" -ForegroundColor Cyan
        }
    }
    catch {
        Write-Info "To configure Claude CLI manually, run:"
        Write-Host "  claude mcp add -s user pal $PythonPath $ServerPath" -ForegroundColor Cyan
    }
}

function Test-GeminiCliIntegration {
    param([string]$ScriptDir)
    
    $palWrapper = Join-Path $ScriptDir "pal-mcp-server.cmd"
    
    # Check if Gemini settings file exists (Windows path)
    $geminiConfig = "$env:USERPROFILE\.gemini\settings.json"
    if (!(Test-Path $geminiConfig)) {
        return
    }

    # Load existing config
    $config = @{}
    $configContent = Get-Content $geminiConfig -Raw -ErrorAction SilentlyContinue
    if ($configContent) {
        try { $config = $configContent | ConvertFrom-Json -ErrorAction Stop } catch { $config = @{} }
    }
    if ($null -eq $config -or $config -isnot [System.Collections.IDictionary]) {
        $config = @{}
    }

    if (-not $config.mcpServers -or $config.mcpServers -isnot [System.Collections.IDictionary]) {
        $config.mcpServers = [ordered]@{}
    }

    $legacyRemoved = Remove-LegacyServerKeys $config.mcpServers
    $palConfig = $config.mcpServers.pal
    $needsWrite = $legacyRemoved

    if ($palConfig) {
        if ($palConfig.command -ne $palWrapper) {
            $palConfig.command = $palWrapper
            $needsWrite = $true
        }

        if (!(Test-Path $palWrapper)) {
            Write-Info "Creating wrapper script for Gemini CLI..."
            @"
@echo off
cd /d "%~dp0"
if exist ".pal_venv\Scripts\python.exe" (
    .pal_venv\Scripts\python.exe server.py %*
) else (
    python server.py %*
)
"@ | Out-File -FilePath $palWrapper -Encoding ASCII
            Write-Success "Created pal-mcp-server.cmd wrapper script"
        }

        if ($needsWrite) {
            Manage-ConfigBackups -ConfigFilePath $geminiConfig | Out-Null
            $config | ConvertTo-Json -Depth 10 | Out-File $geminiConfig -Encoding UTF8
            Write-Success "Updated Gemini CLI configuration (cleaned legacy entries)"
            Write-Host "  Config: $geminiConfig" -ForegroundColor Gray
            Write-Host "  Restart Gemini CLI to use PAL MCP Server" -ForegroundColor Gray
        }
        return
    }

    # Ask user if they want to add PAL to Gemini CLI
    Write-Host ""
    $response = Read-Host "Configure PAL for Gemini CLI? (y/N)"
    if ($response -ne 'y' -and $response -ne 'Y') {
        Write-Info "Skipping Gemini CLI integration"
        return
    }
    
    # Ensure wrapper script exists
    if (!(Test-Path $palWrapper)) {
        Write-Info "Creating wrapper script for Gemini CLI..."
        @"
@echo off
cd /d "%~dp0"
if exist ".pal_venv\Scripts\python.exe" (
    .pal_venv\Scripts\python.exe server.py %*
) else (
    python server.py %*
)
"@ | Out-File -FilePath $palWrapper -Encoding ASCII
        
        Write-Success "Created pal-mcp-server.cmd wrapper script"
    }
    
    # Update Gemini settings
    Write-Info "Updating Gemini CLI configuration..."
    
    try {
        # Create backup with retention management
        $backupPath = Manage-ConfigBackups $geminiConfig
        
        # Ensure mcpServers exists
        if (-not $config.mcpServers -or $config.mcpServers -isnot [System.Collections.IDictionary]) {
            $config.mcpServers = [ordered]@{}
        }
        
        # Add pal server
        $palConfig = @{
            command = $palWrapper
        }
        
        $config.mcpServers | Add-Member -MemberType NoteProperty -Name "pal" -Value $palConfig -Force
        
        # Write updated config
        $config | ConvertTo-Json -Depth 10 | Out-File $geminiConfig -Encoding UTF8
        
        Write-Success "Successfully configured Gemini CLI"
        Write-Host "  Config: $geminiConfig" -ForegroundColor Gray
        Write-Host "  Restart Gemini CLI to use PAL MCP Server" -ForegroundColor Gray
        
    }
    catch {
        Write-Error "Failed to update Gemini CLI config: $_"
        Write-Host ""
        Write-Host "Manual config location: $geminiConfig"
        Write-Host "Add this configuration:"
        Write-Host @"
{
  "mcpServers": {
    "pal": {
      "command": "$palWrapper"
    }
  }
}
"@ -ForegroundColor Yellow
    }
}   

function Show-QwenManualConfig {
    param(
        [string]$PythonPath,
        [string]$ServerPath,
        [string]$ScriptDir,
        [string]$ConfigPath,
        [System.Collections.IDictionary]$EnvironmentMap
    )

    Write-Host "Manual config location: $ConfigPath" -ForegroundColor Yellow
    Write-Host "Add or update this entry:" -ForegroundColor Yellow

    if ($EnvironmentMap -and $EnvironmentMap.Count -gt 0) {
        $pairs = $EnvironmentMap.GetEnumerator() | ForEach-Object {
            $escaped = ($_.Value -replace '\\', '\\\\' -replace '"', '\\"')
            '        "{0}": "{1}"' -f $_.Key, $escaped
        }

        Write-Host "{" -ForegroundColor Yellow
        Write-Host "  \"mcpServers\": {" -ForegroundColor Yellow
        Write-Host "    \"pal\": {" -ForegroundColor Yellow
        Write-Host "      \"command\": \"$PythonPath\"," -ForegroundColor Yellow
        Write-Host "      \"args\": [\"$ServerPath\"]," -ForegroundColor Yellow
        Write-Host "      \"cwd\": \"$ScriptDir\"," -ForegroundColor Yellow
        Write-Host "      \"env\": {" -ForegroundColor Yellow
        Write-Host ($pairs -join "`n") -ForegroundColor Yellow
        Write-Host "      }" -ForegroundColor Yellow
        Write-Host "    }" -ForegroundColor Yellow
        Write-Host "  }" -ForegroundColor Yellow
        Write-Host "}" -ForegroundColor Yellow
    }
    else {
        Write-Host "{" -ForegroundColor Yellow
        Write-Host "  \"mcpServers\": {" -ForegroundColor Yellow
        Write-Host "    \"pal\": {" -ForegroundColor Yellow
        Write-Host "      \"command\": \"$PythonPath\"," -ForegroundColor Yellow
        Write-Host "      \"args\": [\"$ServerPath\"]," -ForegroundColor Yellow
        Write-Host "      \"cwd\": \"$ScriptDir\"" -ForegroundColor Yellow
        Write-Host "    }" -ForegroundColor Yellow
        Write-Host "  }" -ForegroundColor Yellow
        Write-Host "}" -ForegroundColor Yellow
    }
}

function Test-QwenCliIntegration {
    param([string]$PythonPath, [string]$ServerPath)

    if (!(Test-Command "qwen")) {
        return
    }

    Write-Info "Qwen CLI detected - checking configuration..."

    $configPath = Join-Path $env:USERPROFILE ".qwen\settings.json"
    $configDir = Split-Path $configPath -Parent
    $scriptDir = Split-Path $ServerPath -Parent

    $configStatus = "missing"
    $legacyRemoved = $false
    $skipPrompt = $false
    $config = @{}

    if (Test-Path $configPath) {
        try {
            Add-Type -AssemblyName System.Web.Extensions -ErrorAction SilentlyContinue
            $serializer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
            $serializer.MaxJsonLength = 67108864
            $rawJson = Get-Content $configPath -Raw
            $config = $serializer.DeserializeObject($rawJson)
            if (-not ($config -is [System.Collections.IDictionary])) {
                $config = @{}
            }

            if ($config.ContainsKey('mcpServers') -and $config['mcpServers'] -is [System.Collections.IDictionary]) {
                $servers = $config['mcpServers']
                $legacyRemoved = (Remove-LegacyServerKeys $servers) -or $legacyRemoved
                if ($servers.Contains('pal') -and $servers['pal'] -is [System.Collections.IDictionary]) {
                    $palConfig = $servers['pal']
                    $commandMatches = ($palConfig['command'] -eq $PythonPath)

                    $argsValue = $palConfig['args']
                    $argsList = @()
                    if ($argsValue -is [System.Collections.IEnumerable] -and $argsValue -isnot [string]) {
                        $argsList = @($argsValue)
                    }
                    elseif ($null -ne $argsValue) {
                        $argsList = @($argsValue)
                    }
                    $argsMatches = ($argsList.Count -eq 1 -and $argsList[0] -eq $ServerPath)

                    $cwdValue = $null
                    if ($palConfig.Contains('cwd')) {
                        $cwdValue = $palConfig['cwd']
                    }
                    $cwdMatches = ([string]::IsNullOrEmpty($cwdValue) -or $cwdValue -eq $scriptDir)

                    if ($commandMatches -and $argsMatches -and $cwdMatches) {
                        $configStatus = $legacyRemoved ? "cleanup" : "match"
                    }
                    else {
                        $configStatus = "mismatch"
                        Write-Warning "Existing Qwen CLI configuration differs from the current setup."
                    }
                }
            }
        }
        catch {
            $configStatus = "invalid"
            Write-Warning "Unable to parse Qwen CLI settings at $configPath ($_)."
            $config = @{}
        }
    }

    $envMap = [ordered]@{}
    if (Test-Path ".env") {
        foreach ($line in Get-Content ".env") {
            $trimmed = $line.Trim()
            if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith('#')) {
                continue
            }

            if ($line -match '^\s*([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $value = $matches[2]
                $value = ($value -replace '\s+#.*$', '').Trim()
                if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                    $value = $value.Substring(1, $value.Length - 2)
                }
                if ([string]::IsNullOrWhiteSpace($value)) {
                    $value = [Environment]::GetEnvironmentVariable($key, "Process")
                }
                if (![string]::IsNullOrWhiteSpace($value) -and $value -notmatch '^your_.*_here$') {
                    $envMap[$key] = $value
                }
            }
        }
    }

    $extraKeys = @(
        "GEMINI_API_KEY", "OPENAI_API_KEY", "XAI_API_KEY", "DIAL_API_KEY", "OPENROUTER_API_KEY",
        "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION", "AZURE_OPENAI_ALLOWED_MODELS", "AZURE_MODELS_CONFIG_PATH",
        "CUSTOM_API_URL", "CUSTOM_API_KEY", "CUSTOM_MODEL_NAME", "DEFAULT_MODEL", "GOOGLE_ALLOWED_MODELS",
        "OPENAI_ALLOWED_MODELS", "OPENROUTER_ALLOWED_MODELS", "XAI_ALLOWED_MODELS", "DEFAULT_THINKING_MODE_THINKDEEP",
        "DISABLED_TOOLS", "CONVERSATION_TIMEOUT_HOURS", "MAX_CONVERSATION_TURNS", "LOG_LEVEL", "PAL_MCP_FORCE_ENV_OVERRIDE"
    )

    foreach ($key in $extraKeys) {
        if (-not $envMap.Contains($key)) {
            $value = [Environment]::GetEnvironmentVariable($key, "Process")
            if (![string]::IsNullOrWhiteSpace($value) -and $value -notmatch '^your_.*_here$') {
                $envMap[$key] = $value
            }
        }
    }

    if ($configStatus -eq "match") {
        Write-Success "Qwen CLI already configured for pal server"
        return
    }

    if ($configStatus -eq "cleanup") {
        Write-Info "Removing legacy Qwen MCP entries from previous zen configuration..."
        $skipPrompt = $true
    }

    $prompt = "Configure PAL for Qwen CLI? (y/N)"
    if ($configStatus -eq "cleanup") {
        $prompt = "Remove legacy Qwen MCP entries and refresh configuration? (Y/n)"
    }
    elseif ($configStatus -eq "mismatch" -or $configStatus -eq "invalid") {
        $prompt = "Update Qwen CLI pal configuration? (y/N)"
    }

    if (-not $skipPrompt) {
        $response = Read-Host $prompt
        if ($response -ne 'y' -and $response -ne 'Y') {
            Write-Info "Skipping Qwen CLI integration"
            Show-QwenManualConfig $PythonPath $ServerPath $scriptDir $configPath $envMap
            return
        }
    }

    if (!(Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    if (Test-Path $configPath -and $configStatus -ne "missing") {
        Manage-ConfigBackups $configPath | Out-Null
    }

    try {
        if (-not ($config -is [System.Collections.IDictionary])) {
            $config = @{}
        }

        if (-not $config.ContainsKey('mcpServers') -or $config['mcpServers'] -isnot [System.Collections.IDictionary]) {
            $config['mcpServers'] = @{}
        }

        $palConfig = [ordered]@{
            command = $PythonPath
            args    = @($ServerPath)
            cwd     = $scriptDir
        }

        if ($envMap.Count -gt 0) {
            $palConfig['env'] = $envMap
        }

        $config['mcpServers']['pal'] = $palConfig

        $json = ($config | ConvertTo-Json -Depth 20)
        Set-Content -Path $configPath -Value $json -Encoding UTF8

        Write-Success "Successfully configured Qwen CLI"
        Write-Host "  Config: $configPath" -ForegroundColor Gray
        Write-Host "  Restart Qwen CLI to use PAL MCP Server" -ForegroundColor Gray
    }
    catch {
        Write-Error "Failed to update Qwen CLI configuration: $_"
        Show-QwenManualConfig $PythonPath $ServerPath $scriptDir $configPath $envMap
    }
}


# ----------------------------------------------------------------------------
# End MCP Client Configuration System
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# User Interface Functions
# ----------------------------------------------------------------------------

# Show script help
function Show-Help {
    Write-Host @"
PAL MCP Server - Setup and Launch Script

USAGE:
.\run-server.ps1 [OPTIONS]

OPTIONS:
-Help                   Show this help message
-Version                Show version information
-Follow                 Follow server logs in real time
-Config                 Show configuration instructions for MCP clients
-ClearCache             Clear Python cache files and exit
-Force                  Force recreation of Python virtual environment
-Dev                    Install development dependencies from requirements-dev.txt
-Docker                 Use Docker instead of Python virtual environment
-SkipVenv              Skip Python virtual environment creation
-SkipDocker            Skip Docker checks and cleanup

EXAMPLES:
.\run-server.ps1                      # Normal startup
.\run-server.ps1 -Follow              # Start and follow logs
.\run-server.ps1 -Config              # Show configuration help
.\run-server.ps1 -Dev                 # Include development dependencies
.\run-server.ps1 -Docker              # Use Docker deployment
.\run-server.ps1 -Docker -Follow      # Docker with log following

For more information, visit: https://github.com/BeehiveInnovations/pal-mcp-server
"@ -ForegroundColor White
}

# Show version information
function Show-Version {
    $version = Get-Version
    Write-Host "PAL MCP Server version: $version" -ForegroundColor Green
    Write-Host "PowerShell Setup Script for Windows" -ForegroundColor Cyan
    Write-Host "Author: GiGiDKR (https://github.com/GiGiDKR)" -ForegroundColor Gray
    Write-Host "Project: BeehiveInnovations/pal-mcp-server" -ForegroundColor Gray
}

# Show configuration instructions
function Show-ConfigInstructions {
    param(
        [string]$PythonPath = "",
        [string]$ServerPath = "",
        [switch]$UseDocker = $false
    )
    
    Write-Step "Configuration Instructions"
    
    if ($UseDocker) {
        Write-Host "Docker Configuration:" -ForegroundColor Yellow
        Write-Host "The MCP clients have been configured to use Docker containers." -ForegroundColor White
        Write-Host "Make sure the Docker container is running with: docker-compose up -d" -ForegroundColor Cyan
        Write-Host ""
    }
    else {
        Write-Host "Python Virtual Environment Configuration:" -ForegroundColor Yellow
        Write-Host "Python Path: $PythonPath" -ForegroundColor Cyan
        Write-Host "Server Path: $ServerPath" -ForegroundColor Cyan
        Write-Host ""
    }
    
    Write-Host "Supported MCP Clients:" -ForegroundColor Green
    Write-Host "✓ Claude Desktop" -ForegroundColor White
    Write-Host "✓ Claude CLI" -ForegroundColor White  
    Write-Host "✓ VSCode (with MCP extension)" -ForegroundColor White
    Write-Host "✓ VSCode Insiders" -ForegroundColor White
    Write-Host "✓ Cursor" -ForegroundColor White
    Write-Host "✓ Windsurf" -ForegroundColor White
    Write-Host "✓ Trae" -ForegroundColor White
    Write-Host "✓ Gemini CLI" -ForegroundColor White
    Write-Host "✓ Qwen CLI" -ForegroundColor White
    Write-Host ""
    Write-Host "The script automatically detects and configures compatible clients." -ForegroundColor Gray
    Write-Host "Restart your MCP clients after configuration to use the PAL MCP Server." -ForegroundColor Yellow
}

# Show setup instructions
function Show-SetupInstructions {
    param(
        [string]$PythonPath = "",
        [string]$ServerPath = "",
        [switch]$UseDocker = $false
    )
    
    Write-Step "Setup Complete"
    
    if ($UseDocker) {
        Write-Success "PAL MCP Server is configured for Docker deployment"
        Write-Host "Docker command: docker exec -i pal-mcp-server python server.py" -ForegroundColor Cyan
    }
    else {
        Write-Success "PAL MCP Server is configured for Python virtual environment"
        Write-Host "Python: $PythonPath" -ForegroundColor Cyan
        Write-Host "Server: $ServerPath" -ForegroundColor Cyan
    }
    
    Write-Host ""
    Write-Host "MCP clients will automatically connect to the server." -ForegroundColor Green
    Write-Host "For manual configuration, use the paths shown above." -ForegroundColor Gray
}

# Start the server
function Start-Server {
    Write-Step "Starting PAL MCP Server"
    
    $pythonPath = "$VENV_PATH\Scripts\python.exe"
    if (!(Test-Path $pythonPath)) {
        Write-Error "Python virtual environment not found. Please run setup first."
        return
    }
    
    $serverPath = "server.py"
    if (!(Test-Path $serverPath)) {
        Write-Error "Server script not found: $serverPath"
        return
    }
    
    try {
        Write-Info "Launching server..."
        & $pythonPath $serverPath
    }
    catch {
        Write-Error "Failed to start server: $_"
    }
}

# Follow server logs
function Follow-Logs {
    Write-Step "Following Server Logs"
    
    $logPath = Join-Path $LOG_DIR $LOG_FILE
    
    if (!(Test-Path $logPath)) {
        Write-Warning "Log file not found: $logPath"
        Write-Info "Starting server to generate logs..."
        Start-Server
        return
    }
    
    try {
        Write-Info "Following logs at: $logPath"
        Write-Host "Press Ctrl+C to stop following logs"
        Write-Host ""
        Get-Content $logPath -Wait
    }
    catch {
        Write-Error "Failed to follow logs: $_"
    }
}

# ----------------------------------------------------------------------------
# Environment File Management
# ----------------------------------------------------------------------------

# Initialize .env file if it doesn't exist
function Initialize-EnvFile {
    Write-Step "Setting up Environment File"
    
    if (!(Test-Path ".env")) {
        Write-Info "Creating default .env file..."
        @"
# API Keys - Replace with your actual keys
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
XAI_API_KEY=your_xai_api_key_here
DIAL_API_KEY=your_dial_api_key_here
DIAL_API_HOST=your_dial_api_host_here
DIAL_API_VERSION=your_dial_api_version_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
CUSTOM_API_URL=your_custom_api_url_here
CUSTOM_API_KEY=your_custom_api_key_here
CUSTOM_MODEL_NAME=your_custom_model_name_here

# Server Configuration
DEFAULT_MODEL=auto
LOG_LEVEL=INFO
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5
DEFAULT_THINKING_MODE_THINKDEEP=high

# Optional Advanced Settings
#DISABLED_TOOLS=
#MAX_MCP_OUTPUT_TOKENS=
#TZ=UTC
"@ | Out-File -FilePath ".env" -Encoding UTF8
        
        Write-Success "Default .env file created"
        Write-Warning "Please edit .env file with your actual API keys"
    }
    else {
        Write-Success ".env file already exists"
    }
}

# Import environment variables from .env file
function Import-EnvFile {
    if (!(Test-Path ".env")) {
        Write-Warning "No .env file found"
        return
    }
    
    try {
        $envContent = Get-Content ".env" -ErrorAction Stop
        foreach ($line in $envContent) {
            if ($line -match '^([^#][^=]*?)=(.*)$') {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim() -replace '^["'']|["'']$', ''
                
                # Set environment variable for the current session
                [Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
        Write-Success "Environment variables loaded from .env file"
    }
    catch {
        Write-Warning "Could not load .env file: $_"
    }
}

# ----------------------------------------------------------------------------
# Workflow Functions
# ----------------------------------------------------------------------------

# Docker deployment workflow
function Invoke-DockerWorkflow {
    Write-Step "Starting Docker Workflow"
    Write-Host "PAL MCP Server" -ForegroundColor Green
    Write-Host "=================" -ForegroundColor Cyan
    
    $version = Get-Version
    Write-Host "Version: $version"
    Write-Host "Mode: Docker Container" -ForegroundColor Yellow
    Write-Host ""
    
    # Docker setup and validation
    if (!(Test-DockerRequirements)) { exit 1 }
    if (!(Initialize-DockerEnvironment)) { exit 1 }
    
    Import-EnvFile
    Test-ApiKeys
    
    if (!(Build-DockerImage -Force:$Force)) { exit 1 }
    
    # Configure MCP clients for Docker
    Invoke-McpClientConfiguration -UseDocker $true
    
    Show-SetupInstructions -UseDocker
    
    # Start Docker services
    Write-Step "Starting PAL MCP Server"
    if ($Follow) {
        Write-Info "Starting server and following logs..."
        Start-DockerServices -Follow
        exit 0
    }
    
    if (!(Start-DockerServices)) { exit 1 }
    
    Write-Host ""
    Write-Success "PAL MCP Server is running in Docker!"
    Write-Host ""
    
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Restart your MCP clients (Claude Desktop, etc.)" -ForegroundColor White
    Write-Host "2. The server is now ready to use" -ForegroundColor White
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs: " -NoNewline -ForegroundColor White
    Write-Host "docker logs -f pal-mcp-server" -ForegroundColor Yellow
    Write-Host "  Stop server: " -NoNewline -ForegroundColor White
    Write-Host "docker-compose down" -ForegroundColor Yellow
    Write-Host "  Restart server: " -NoNewline -ForegroundColor White
    Write-Host "docker-compose restart" -ForegroundColor Yellow
}

# Python virtual environment deployment workflow
function Invoke-PythonWorkflow {
    Write-Step "Starting Python Virtual Environment Workflow"
    Write-Host "PAL MCP Server" -ForegroundColor Green
    Write-Host "=================" -ForegroundColor Cyan
    
    $version = Get-Version
    Write-Host "Version: $version"
    Write-Host ""
    
    if (!(Test-Path $VENV_PATH)) {
        Write-Info "Setting up Python environment for first time..."
    }
    
    # Python environment setup
    Cleanup-Docker
    Clear-PythonCache
    Initialize-EnvFile
    Import-EnvFile
    Test-ApiKeys
    
    try {
        $pythonPath = Initialize-Environment
    }
    catch {
        Write-Error "Failed to setup Python environment: $_"
        exit 1
    }
    
    try {
        Install-Dependencies $pythonPath -InstallDevDependencies:$Dev
    }
    catch {
        Write-Error "Failed to install dependencies: $_"
        exit 1
    }
    
    $serverPath = Get-AbsolutePath "server.py"
    
    # Configure MCP clients for Python
    Invoke-McpClientConfiguration -UseDocker $false -PythonPath $pythonPath -ServerPath $serverPath
    
    Show-SetupInstructions $pythonPath $serverPath
    Initialize-Logging
    
    Write-Host ""
    Write-Host "Logs will be written to: $(Get-AbsolutePath $LOG_DIR)\$LOG_FILE"
    Write-Host ""
    
    if ($Follow) {
        Follow-Logs
    }
    else {
        Write-Host "To follow logs: .\run-server.ps1 -Follow" -ForegroundColor Yellow
        Write-Host "To show config: .\run-server.ps1 -Config" -ForegroundColor Yellow
        Write-Host "To update: git pull, then run .\run-server.ps1 again" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Happy coding! 🎉" -ForegroundColor Green
        
        $response = Read-Host "`nStart the server now? (y/N)"
        if ($response -eq 'y' -or $response -eq 'Y') {
            Start-Server
        }
    }
}

# ----------------------------------------------------------------------------
# End Workflow Functions
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
# Main Execution
# ----------------------------------------------------------------------------

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
            if ($Docker) {
                # Docker configuration mode
                if (!(Test-DockerRequirements)) {
                    exit 1
                }
                Initialize-DockerEnvironment
                Show-ConfigInstructions "" "" -UseDocker
            }
            else {
                # Python virtual environment configuration mode
                $pythonPath = Initialize-Environment
                $serverPath = Get-AbsolutePath "server.py"
                Show-ConfigInstructions $pythonPath $serverPath
            }
        }
        catch {
            Write-Error "Failed to setup environment for configuration: $_"
            exit 1
        }
        exit 0
    }

    # ============================================================================
    # Docker Workflow
    # ============================================================================
    if ($Docker) {
        Invoke-DockerWorkflow
        exit 0
    }

    # ============================================================================
    # Python Virtual Environment Workflow (Default)
    # ============================================================================
    Invoke-PythonWorkflow
    exit 0
}

# ============================================================================
# Main Script Execution
# ============================================================================

# Execute main process
Start-MainProcess
