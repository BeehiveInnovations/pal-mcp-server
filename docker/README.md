# Zen MCP Server - Docker Setup

## Quick Start

### 1. Prerequisites

- Docker installed (Docker Compose optional)
- At least one API key (Gemini, OpenAI, xAI, etc.)

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit with your API keys (at least one required)
# Required: GEMINI_API_KEY or OPENAI_API_KEY or XAI_API_KEY
nano .env
```

### 3. Build Image

```bash
# Build the Docker image
docker build -t zen-mcp-server:latest .

# Or use the build script (Bash)
chmod +x docker/scripts/build.sh
./docker/scripts/build.sh

# Build with PowerShell
docker/scripts/build.ps1

```

### 4. Usage Options

#### A. Direct Docker Run (Recommended for MCP)

```bash
# Run with environment file
docker run --rm -i --env-file .env \
  -v $(pwd)/logs:/app/logs \
  zen-mcp-server:latest

# Run with inline environment variables
docker run --rm -i \
  -e GEMINI_API_KEY="your_key_here" \
  -e LOG_LEVEL=INFO \
  -v $(pwd)/logs:/app/logs \
  zen-mcp-server:latest
```

#### B. Docker Compose (For Development/Monitoring)

```bash
# Deploy with Docker Compose
chmod +x docker/scripts/deploy.sh
./docker/scripts/deploy.sh

# Or use PowerShell script
docker/scripts/deploy.ps1

# Interactive stdio mode
docker-compose exec zen-mcp python server.py
```

## Service Management

### Docker Commands

```bash
# View running containers
docker ps

# View logs from container
docker logs <container_id>

# Stop all zen-mcp containers
docker stop $(docker ps -q --filter "ancestor=zen-mcp-server:latest")

# Remove old containers and images
docker container prune
docker image prune
```

### Docker Compose Management (Optional)

```bash
# View logs
docker-compose logs -f zen-mcp

# Check status
docker-compose ps

# Restart service
docker-compose restart zen-mcp

# Stop services
docker-compose down

# Rebuild and update
docker-compose build --no-cache zen-mcp
docker-compose up -d zen-mcp
```

## Health Monitoring

The container includes health checks that verify:
- Server process is running
- Python modules can be imported
- Log directory is writable  
- API keys are configured

## Volumes

- `./logs:/app/logs` - Persistent log storage
- `zen-mcp-config:/app/conf` - Configuration persistence

## Security

- Runs as non-root user `zenuser`
- Read-only filesystem with tmpfs for temporary files
- No network ports exposed (stdio communication only)
- Secrets managed via environment variables

## Troubleshooting

### Container won't start

```bash
# Check if image exists
docker images zen-mcp-server

# Test container interactively
docker run --rm -it --env-file .env zen-mcp-server:latest bash

# Check environment variables
docker run --rm --env-file .env zen-mcp-server:latest env | grep API

# Test with minimal configuration
docker run --rm -i -e GEMINI_API_KEY="test" zen-mcp-server:latest python server.py
```

### MCP Connection Issues

```bash
# Test Docker connectivity
docker run --rm hello-world

# Verify container stdio
echo '{"jsonrpc": "2.0", "method": "ping"}' | docker run --rm -i --env-file .env zen-mcp-server:latest python server.py

# Check Claude Desktop logs for connection errors
```

### API Key Problems

```bash
# Verify API keys are loaded
docker run --rm --env-file .env zen-mcp-server:latest python -c "import os; print('GEMINI_API_KEY:', bool(os.getenv('GEMINI_API_KEY')))"

# Test API connectivity
docker run --rm --env-file .env zen-mcp-server:latest python /usr/local/bin/healthcheck.py
```

### Permission Issues

```bash
# Fix log directory permissions (Linux/macOS)
sudo chown -R $USER:$USER logs/
chmod 755 logs/

# Windows: Run Docker Desktop as Administrator if needed
```

### Memory/Performance Issues

```bash
# Check container resource usage
docker stats

# Run with memory limits
docker run --rm -i --memory="512m" --env-file .env zen-mcp-server:latest

# Monitor Docker logs
docker run --rm -i --env-file .env zen-mcp-server:latest 2>&1 | tee docker.log
```

## MCP Integration (Claude Desktop)

### Configuration File Setup

Add to your Claude Desktop MCP configuration:

```json
{
  "servers": {
    "zen-docker": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/absolute/path/to/zen-mcp-server/.env",
        "-v",
        "/absolute/path/to/zen-mcp-server/logs:/app/logs",
        "zen-mcp-server:latest",
        "python",
        "server.py"
      ],
      "env": {
        "DOCKER_BUILDKIT": "1"
      }
    }
  }
}
```

### Windows MCP Configuration

For Windows users, use forward slashes in paths:

```json
{
  "servers": {
    "zen-docker": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "C:/Users/YourName/path/to/zen-mcp-server/.env",
        "-v",
        "C:/Users/YourName/path/to/zen-mcp-server/logs:/app/logs",
        "zen-mcp-server:latest",
        "python",
        "server.py"
      ],
      "env": {
        "DOCKER_BUILDKIT": "1"
      }
    }
  }
}
```

### Environment File Template

Create `.env` file with at least one API key:

```bash
# Required: At least one API key
GEMINI_API_KEY=your_gemini_key_here
OPENAI_API_KEY=your_openai_key_here

# Optional configuration
LOG_LEVEL=INFO
DEFAULT_MODEL=auto
DEFAULT_THINKING_MODE_THINKDEEP=high

# Optional API keys (leave empty if not used)
ANTHROPIC_API_KEY=
XAI_API_KEY=
DIAL_API_KEY=
OPENROUTER_API_KEY=
CUSTOM_API_URL=
```

## Quick Test & Validation

### 1. Test Docker Image

```bash
# Test container starts correctly
docker run --rm zen-mcp-server:latest python --version

# Test health check
docker run --rm -e GEMINI_API_KEY="test" zen-mcp-server:latest python /usr/local/bin/healthcheck.py
```

### 2. Test MCP Protocol

```bash
# Test basic MCP communication
echo '{"jsonrpc": "2.0", "method": "initialize", "params": {}}' | \
  docker run --rm -i --env-file .env zen-mcp-server:latest python server.py
```

### 3. Validate Configuration

```bash
# Run validation script
python test_mcp_config.py

# Or validate JSON manually
python -m json.tool .vscode/mcp.json
```

## Available Tools

The Zen MCP Server provides these tools when properly configured:

- **chat** - General AI conversation and collaboration
- **thinkdeep** - Multi-stage investigation and reasoning  
- **planner** - Interactive sequential planning
- **consensus** - Multi-model consensus workflow
- **codereview** - Comprehensive code review
- **debug** - Root cause analysis and debugging
- **analyze** - Code analysis and assessment
- **refactor** - Refactoring analysis and suggestions
- **secaudit** - Security audit workflow
- **testgen** - Test generation with edge cases
- **docgen** - Documentation generation
- **tracer** - Code tracing and dependency mapping
- **precommit** - Pre-commit validation workflow
- **listmodels** - Available AI models information
- **version** - Server version and configuration

## Performance Notes

- **Image size**: ~293MB optimized multi-stage build
- **Memory usage**: ~256MB base + model overhead
- **Startup time**: ~2-3 seconds for container initialization
- **API response**: Varies by model and complexity (1-30 seconds)

For production use, consider:
- Using specific API keys for rate limiting
- Monitoring container resource usage
- Setting up log rotation for persistent logs
- Using Docker health checks for reliability
