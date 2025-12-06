# Docker Deployment Guide

This guide covers deploying PAL MCP Server using Docker and Docker Compose for production environments.

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/BeehiveInnovations/pal-mcp-server.git
   cd pal-mcp-server
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Deploy with Docker Compose**:
   ```bash
   # Linux/macOS
   ./docker/scripts/deploy.sh
   
   # Windows PowerShell
   .\docker\scripts\deploy.ps1
   ```

## Environment Configuration

### Required API Keys

At least one API key must be configured in your `.env` file:

```env
# Google Gemini (Recommended)
GEMINI_API_KEY=your_gemini_api_key_here

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here

# X.AI GROK
XAI_API_KEY=your_xai_api_key_here

# OpenRouter (unified access)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Additional providers
DIAL_API_KEY=your_dial_api_key_here
DIAL_API_HOST=your_dial_host
```

### Optional Configuration

```env
# Default model selection
DEFAULT_MODEL=auto

# Logging
LOG_LEVEL=INFO
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5

# Advanced settings
DEFAULT_THINKING_MODE_THINKDEEP=high
DISABLED_TOOLS=
MAX_MCP_OUTPUT_TOKENS=

# Timezone
TZ=UTC
```

## Deployment Scripts

### Linux/macOS Deployment

Use the provided bash script for robust deployment:

```bash
./docker/scripts/deploy.sh
```

**Features:**
- ✅ Environment validation
- ✅ Exponential backoff health checks
- ✅ Automatic log management
- ✅ Service status monitoring

### Windows PowerShell Deployment

Use the PowerShell script for Windows environments:

```powershell
.\docker\scripts\deploy.ps1
```

**Additional Options:**
```powershell
# Skip health check
.\docker\scripts\deploy.ps1 -SkipHealthCheck

# Custom timeout
.\docker\scripts\deploy.ps1 -HealthCheckTimeout 120
```

## Docker Architecture

### Multi-Stage Build

The Dockerfile uses a multi-stage build for optimal image size:

1. **Builder Stage**: Installs dependencies and creates virtual environment
2. **Runtime Stage**: Copies only necessary files for minimal footprint

### Security Features

- **Non-root user**: Runs as `paluser` (UID/GID 1000)
- **Read-only filesystem**: Container filesystem is immutable
- **No new privileges**: Prevents privilege escalation
- **Secure tmpfs**: Temporary directories with strict permissions

### Resource Management

Default resource limits:
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

## Service Management

### Starting the Service

```bash
# Start in background
docker-compose up -d

# Start with logs
docker-compose up
```

### Monitoring

```bash
# View service status
docker-compose ps

# Follow logs
docker-compose logs -f pal-mcp

# View health status
docker inspect pal-mcp-server --format='{{.State.Health.Status}}'
```

### Stopping the Service

```bash
# Graceful stop
docker-compose down

# Force stop
docker-compose down --timeout 10
```

## Health Checks

The container includes comprehensive health checks:

- **Process check**: Verifies server.py is running
- **Import check**: Validates critical Python modules
- **Directory check**: Ensures log directory is writable
- **API check**: Tests provider connectivity

Health check configuration:
```yaml
healthcheck:
  test: ["CMD", "python", "/usr/local/bin/healthcheck.py"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

## Persistent Data

### Volumes

- **Logs**: `./logs:/app/logs` - Application logs
- **Config**: `pal-mcp-config:/app/conf` - Configuration persistence
- **Time sync**: `/etc/localtime:/etc/localtime:ro` - Host timezone sync

**Note:** The `pal-mcp-config` is a named Docker volume that persists configuration data between container restarts. All data placed in `/app/conf` inside the container is preserved thanks to this persistent volume. This applies to both `docker-compose run` and `docker-compose up` commands.

### Log Management

Logs are automatically rotated with configurable retention:

```env
LOG_MAX_SIZE=10MB      # Maximum log file size
LOG_BACKUP_COUNT=5     # Number of backup files to keep
```

## Networking

### Default Configuration

- **Network**: `pal-network` (bridge)
- **Subnet**: `172.20.0.0/16`
- **Isolation**: Container runs in isolated network

### Port Exposure

By default, no ports are exposed. The MCP server communicates via stdio when used with Claude Desktop or other MCP clients.

For external access (advanced users):
```yaml
ports:
  - "3000:3000"  # Add to service configuration if needed
```

## Troubleshooting

### Common Issues

**1. Health check failures:**
```bash
# Check logs
docker-compose logs pal-mcp

# Manual health check
docker exec pal-mcp-server python /usr/local/bin/healthcheck.py
```

**2. Permission errors:**
```bash
# Fix log directory permissions
sudo chown -R 1000:1000 ./logs
```

**3. Environment variables not loaded:**
```bash
# Verify .env file exists and is readable
ls -la .env
cat .env
```

**4. API key validation errors:**
```bash
# Check environment variables in container
docker exec pal-mcp-server env | grep -E "(GEMINI|OPENAI|XAI)"
```

### Debug Mode

Enable verbose logging for troubleshooting:

```env
LOG_LEVEL=DEBUG
```

## Production Considerations

### Security

1. **Use Docker secrets** for API keys in production:
   ```yaml
   secrets:
     gemini_api_key:
       external: true
   ```

2. **Enable AppArmor/SELinux** if available

3. **Regular security updates**:
   ```bash
   docker-compose pull
   docker-compose up -d
   ```

### Monitoring

Consider integrating with monitoring solutions:

- **Prometheus**: Health check metrics
- **Grafana**: Log visualization
- **AlertManager**: Health status alerts

### Backup

Backup persistent volumes:
```bash
# Backup configuration
docker run --rm -v pal-mcp-config:/data -v $(pwd):/backup alpine tar czf /backup/config-backup.tar.gz -C /data .

# Restore configuration
docker run --rm -v pal-mcp-config:/data -v $(pwd):/backup alpine tar xzf /backup/config-backup.tar.gz -C /data
```

## Performance Tuning

### Resource Optimization

Adjust limits based on your workload:

```yaml
deploy:
  resources:
    limits:
      memory: 1G        # Increase for heavy workloads
      cpus: '1.0'       # More CPU for concurrent requests
```

### Memory Management

Monitor memory usage:
```bash
docker stats pal-mcp-server
```

Adjust Python memory settings if needed:
```env
PYTHONMALLOC=pymalloc
MALLOC_ARENA_MAX=2
```

## Integration with Claude Desktop

Configure Claude Desktop to use the containerized server. **Choose one of the configurations below based on your needs:**

### Option 1: Direct Docker Run (Recommended)

**The simplest and most reliable option for most users.**

```json
{
  "mcpServers": {
    "pal-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/absolute/path/to/pal-mcp-server/.env",
        "-v",
        "/absolute/path/to/pal-mcp-server/logs:/app/logs",
        "pal-mcp-server:latest"
      ]
    }
  }
}
```

**Exemple Windows** :
```json
{
  "mcpServers": {
    "pal-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "C:/path/to/pal-mcp-server/.env",
        "-v",
        "C:/path/to/pal-mcp-server/logs:/app/logs",
        "pal-mcp-server:latest"
      ]
    }
  }
}
```

### Option 2: Docker Compose Run (one-shot, uses docker-compose.yml)

**To use the advanced configuration from docker-compose.yml without a persistent container.**

```json
{
  "mcpServers": {
    "pal-mcp": {
      "command": "docker-compose",
      "args": [
        "-f", "/absolute/path/to/pal-mcp-server/docker-compose.yml",
        "run", "--rm", "pal-mcp"
      ]
    }
  }
}
```

### Option 3: Inline Environment Variables (Advanced)

**For highly customized needs.**

```json
{
  "mcpServers": {
    "pal-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "GEMINI_API_KEY=your_key_here",
        "-e", "LOG_LEVEL=INFO",
        "-e", "DEFAULT_MODEL=auto",
        "-v", "/path/to/logs:/app/logs",
        "pal-mcp-server:latest"
      ]
    }
  }
}
```

### Configuration Notes

**Important notes:**
- Replace `/absolute/path/to/pal-mcp-server` with the actual path to your project.
- Always use forward slashes `/` for Docker volumes, even on Windows.
- Ensure the `.env` file exists and contains your API keys.
- **Persistent volumes**: Docker Compose options (Options 2) automatically use the `pal-mcp-config` named volume for persistent configuration storage.

**Environment file requirements:**
```env
# At least one API key is required
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
# ... other keys
```

**Troubleshooting:**
- If Option 1 fails: check that the Docker image exists (`docker images pal-mcp-server`).
- If Option 2 fails: verify the compose file path and ensure the service is not already in use.
- Permission issues: make sure the `logs` folder is writable.

## Advanced Configuration

### Custom Networks

For complex deployments:
```yaml
networks:
  pal-network:
    driver: bridge
      ipam:
        config:
          - subnet: 172.20.0.0/16
            gateway: 172.20.0.1
```

### Multiple Instances

Run multiple instances with different configurations:
```bash
# Copy compose file
cp docker-compose.yml docker-compose.dev.yml

# Modify service names and ports
# Deploy with custom compose file
docker-compose -f docker-compose.dev.yml up -d
```

## Migration and Updates

### Updating the Server

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
./docker/scripts/deploy.sh
```

### Data Migration

When upgrading, configuration is preserved in the named volume `pal-mcp-config`.

For major version upgrades, check the [CHANGELOG](../CHANGELOG.md) for breaking changes.

## Support

For any questions, open an issue on GitHub or consult the official documentation.


---

**Next Steps:**
- Review the [Configuration Guide](configuration.md) for detailed environment variable options
- Check [Advanced Usage](advanced-usage.md) for custom model configurations
- See [Troubleshooting](troubleshooting.md) for common issues and solutions
