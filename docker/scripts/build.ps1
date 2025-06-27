#!/usr/bin/env pwsh
#Requires -Version 5.1
[CmdletBinding()]
param()

# Set error action preference
$ErrorActionPreference = "Stop"

# Colors for output (using Write-Host with colors)
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

Write-ColorText "=== Building Zen MCP Server Docker Image ===" -Color Green

# Check if .env file exists
if (!(Test-Path ".env")) {
    Write-ColorText "Warning: .env file not found. Copying from .env.example" -Color Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-ColorText "Please edit .env file with your API keys before running the server" -Color Yellow
    } else {
        Write-ColorText "Error: .env.example not found" -Color Red
        exit 1
    }
}

# Build the Docker image
Write-ColorText "Building Docker image..." -Color Green
try {
    docker-compose build --no-cache
    if ($LASTEXITCODE -ne 0) {
        throw "Docker build failed"
    }
} catch {
    Write-ColorText "Error: Failed to build Docker image" -Color Red
    exit 1
}

# Verify the build
Write-ColorText "Verifying build..." -Color Green
$images = docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}" | Select-String "zen-mcp-server"

if ($images) {
    Write-ColorText "✓ Docker image built successfully" -Color Green
    Write-ColorText "Image details:" -Color Green
    $images | ForEach-Object { Write-Host $_.Line }
} else {
    Write-ColorText "✗ Failed to build Docker image" -Color Red
    exit 1
}

Write-ColorText "=== Build Complete ===" -Color Green
Write-ColorText "Next steps:" -Color Yellow
Write-Host "  1. Edit .env file with your API keys"
Write-ColorText "  2. Run: " -Color White -NoNewline
Write-ColorText "docker-compose up -d" -Color Green

Write-ColorText "Or use the deploy script: " -Color White -NoNewline
Write-ColorText ".\deploy.ps1" -Color Green
