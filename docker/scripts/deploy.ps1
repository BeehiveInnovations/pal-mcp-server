#!/usr/bin/env pwsh
#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipHealthCheck,
    [int]$HealthCheckTimeout = 60
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

Write-ColorText "=== Deploying Zen MCP Server ===" -Color Green

# Function to check if required environment variables are set
function Test-EnvironmentVariables {
    # At least one of these API keys must be set
    $requiredVars = @(
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY", 
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "DIAL_API_KEY",
        "OPENROUTER_API_KEY"
    )
    
    $hasApiKey = $false
    foreach ($var in $requiredVars) {
        $value = [Environment]::GetEnvironmentVariable($var)
        if (![string]::IsNullOrWhiteSpace($value)) {
            $hasApiKey = $true
            break
        }
    }

    if (!$hasApiKey) {
        Write-ColorText "Error: At least one API key must be set in your .env file" -Color Red
        Write-ColorText "Required variables (at least one):" -Color Yellow
        $requiredVars | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
}

# Load environment variables from .env file
if (Test-Path ".env") {
    Write-ColorText "Loading environment variables from .env..." -Color Green
    
    # Read .env file and set environment variables
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^([^#][^=]*?)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-ColorText "✓ Environment variables loaded from .env" -Color Green
} else {
    Write-ColorText "Error: .env file not found" -Color Red
    Write-ColorText "Please copy .env.example to .env and configure your API keys" -Color Yellow
    exit 1
}

# Check required environment variables
Test-EnvironmentVariables

# Function to wait for service health with exponential backoff
function Wait-ForHealth {
    param(
        [int]$MaxAttempts = 6,
        [int]$InitialDelay = 2
    )
    
    $attempt = 1
    $delay = $InitialDelay

    while ($attempt -le $MaxAttempts) {
        try {
            # Get container ID for zen-mcp service
            $containerId = docker-compose ps -q zen-mcp
            if ([string]::IsNullOrWhiteSpace($containerId)) {
                $status = "unavailable"
            } else {
                $status = docker inspect -f "{{.State.Health.Status}}" $containerId 2>$null
                if ($LASTEXITCODE -ne 0) {
                    $status = "unavailable"
                }
            }
            
            if ($status -eq "healthy") {
                return $true
            }
            
            Write-ColorText "Waiting for service to be healthy... (attempt $attempt/$MaxAttempts, retrying in ${delay}s)" -Color Yellow
            Start-Sleep -Seconds $delay
            $delay = $delay * 2
            $attempt++
        } catch {
            Write-ColorText "Error checking health status: $_" -Color Red
            $attempt++
            Start-Sleep -Seconds $delay
        }
    }

    Write-ColorText "Service failed to become healthy after $MaxAttempts attempts" -Color Red
    Write-ColorText "Checking logs:" -Color Yellow
    docker-compose logs zen-mcp
    return $false
}

# Create logs directory if it doesn't exist
if (!(Test-Path "logs")) {
    Write-ColorText "Creating logs directory..." -Color Green
    New-Item -ItemType Directory -Path "logs" -Force | Out-Null
}

# Stop existing containers
Write-ColorText "Stopping existing containers..." -Color Green
try {
    docker-compose down
    if ($LASTEXITCODE -ne 0) {
        Write-ColorText "Warning: Failed to stop existing containers (they may not be running)" -Color Yellow
    }
} catch {
    Write-ColorText "Warning: Error stopping containers: $_" -Color Yellow
}

# Start the services
Write-ColorText "Starting Zen MCP Server..." -Color Green
try {
    docker-compose up -d
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start services"
    }
} catch {
    Write-ColorText "Error: Failed to start services" -Color Red
    Write-ColorText "Checking logs:" -Color Yellow
    docker-compose logs zen-mcp
    exit 1
}

# Wait for health check (unless skipped)
if (!$SkipHealthCheck) {
    Write-ColorText "Waiting for service to be healthy..." -Color Green
    
    # Simple timeout approach for health check
    $timeout = $HealthCheckTimeout
    $elapsed = 0
    $healthy = $false
    
    while ($elapsed -lt $timeout) {
        try {
            $containerId = docker-compose ps -q zen-mcp
            if (![string]::IsNullOrWhiteSpace($containerId)) {
                $status = docker inspect -f "{{.State.Health.Status}}" $containerId 2>$null
                if ($status -eq "healthy") {
                    $healthy = $true
                    break
                }
            }
        } catch {
            # Continue checking
        }
        
        Start-Sleep -Seconds 2
        $elapsed += 2
    }

    if (!$healthy) {
        Write-ColorText "Service failed to become healthy within timeout" -Color Red
        Write-ColorText "Checking logs:" -Color Yellow
        docker-compose logs zen-mcp
        exit 1
    }
}

Write-ColorText "✓ Zen MCP Server deployed successfully" -Color Green
Write-ColorText "Service Status:" -Color Green
docker-compose ps

Write-ColorText "=== Deployment Complete ===" -Color Green
Write-ColorText "Useful commands:" -Color Yellow
Write-ColorText "  View logs: " -Color White -NoNewline
Write-ColorText "docker-compose logs -f zen-mcp" -Color Green

Write-ColorText "  Stop service: " -Color White -NoNewline
Write-ColorText "docker-compose down" -Color Green

Write-ColorText "  Restart service: " -Color White -NoNewline
Write-ColorText "docker-compose restart zen-mcp" -Color Green

Write-ColorText "  PowerShell logs: " -Color White -NoNewline
Write-ColorText "Get-Content logs\mcp_server.log -Wait" -Color Green
