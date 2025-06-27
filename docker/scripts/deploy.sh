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
    # At least one of these API keys must be set
    local required_vars=("GEMINI_API_KEY" "GOOGLE_API_KEY" "OPENAI_API_KEY" "XAI_API_KEY" "DIAL_API_KEY" "OPENROUTER_API_KEY")
    
    local has_api_key=false
    for var in "${required_vars[@]}"; do
        if [[ -n "${!var:-}" ]]; then
            has_api_key=true
            break
        fi
    done

    if [[ "$has_api_key" == false ]]; then
        echo -e "${RED}Error: At least one API key must be set in your .env file${NC}"
        printf '  %s\n' "${required_vars[@]}"
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

# Exponential backoff health check function
wait_for_health() {
    local max_attempts=6
    local attempt=1
    local delay=2

    while (( attempt <= max_attempts )); do
        status=$(docker-compose ps -q zen-mcp | xargs docker inspect -f "{{.State.Health.Status}}" 2>/dev/null || echo "unavailable")
        if [[ "$status" == "healthy" ]]; then
            return 0
        fi
        echo -e "${YELLOW}Waiting for service to be healthy... (attempt $attempt/${max_attempts}, retrying in ${delay}s)${NC}"
        sleep $delay
        delay=$(( delay * 2 ))
        attempt=$(( attempt + 1 ))
    done

    echo -e "${RED}Service failed to become healthy after $max_attempts attempts${NC}"
    echo -e "${YELLOW}Checking logs:${NC}"
    docker-compose logs zen-mcp
    exit 1
}

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
