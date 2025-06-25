#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Building Zen MCP Server Docker Image ===${NC}"

# Check if .env file exists
if [[ ! -f .env ]]; then
    echo -e "${YELLOW}Warning: .env file not found. Copying from .env.example${NC}"
    if [[ -f .env.example ]]; then
        cp .env.example .env
        echo -e "${YELLOW}Please edit .env file with your API keys before running the server${NC}"
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
fi

# Build the Docker image
echo -e "${GREEN}Building Docker image...${NC}"
docker-compose build --no-cache

# Verify the build
if docker images | grep -q "zen-mcp-server"; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
    echo -e "${GREEN}Image details:${NC}"
    docker images | grep zen-mcp-server
else
    echo -e "${RED}✗ Failed to build Docker image${NC}"
    exit 1
fi

echo -e "${GREEN}=== Build Complete ===${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Edit .env file with your API keys"
echo -e "  2. Run: ${GREEN}docker-compose up -d${NC}"
