#!/bin/bash
set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Deploying Zen MCP Server ===${NC}"

# Function to check if required environment variables are set
check_env_vars() {
    local required_vars=("GOOGLE_API_KEY" "OPENAI_API_KEY")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo -e "${RED}Error: Missing required environment variables:${NC}"
        printf '  %s\n' "${missing_vars[@]}"
        echo -e "${YELLOW}Please set these variables in your .env file${NC}"
        exit 1
    fi
}

# Load environment variables
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
    echo -e "${GREEN}✓ Environment variables loaded from .env${NC}"
else
    echo -e "${RED}Error: .env file not found${NC}"
    echo -e "${YELLOW}Please copy .env.example to .env and configure your API keys${NC}"
    exit 1
fi

# Check required environment variables
check_env_vars

# Create logs directory if it doesn't exist
mkdir -p logs

# Stop existing containers
echo -e "${GREEN}Stopping existing containers...${NC}"
docker-compose down

# Start the services
echo -e "${GREEN}Starting Zen MCP Server...${NC}"
docker-compose up -d

# Wait for health check
echo -e "${GREEN}Waiting for service to be healthy...${NC}"
timeout 60 bash -c 'while [[ "$(docker-compose ps -q zen-mcp | xargs docker inspect -f "{{.State.Health.Status}}")" != "healthy" ]]; do sleep 2; done' || {
    echo -e "${RED}Service failed to become healthy${NC}"
    echo -e "${YELLOW}Checking logs:${NC}"
    docker-compose logs zen-mcp
    exit 1
}

echo -e "${GREEN}✓ Zen MCP Server deployed successfully${NC}"
echo -e "${GREEN}Service Status:${NC}"
docker-compose ps

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  View logs: ${GREEN}docker-compose logs -f zen-mcp${NC}"
echo -e "  Stop service: ${GREEN}docker-compose down${NC}"
echo -e "  Restart service: ${GREEN}docker-compose restart zen-mcp${NC}"
