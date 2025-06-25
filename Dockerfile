# ===========================================
# STAGE 1: Build dependencies
# ===========================================
FROM python:3.11-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ===========================================
# STAGE 2: Runtime image
# ===========================================
FROM python:3.11-slim AS runtime

# Add metadata labels for traceability
LABEL maintainer="Zen MCP Server Team"
LABEL version="1.0.0"
LABEL description="Zen MCP Server - AI-powered Model Context Protocol server"
LABEL org.opencontainers.image.title="zen-mcp-server"
LABEL org.opencontainers.image.description="AI-powered Model Context Protocol server with multi-provider support"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/BeehiveInnovations/zen-mcp-server"
LABEL org.opencontainers.image.documentation="https://github.com/BeehiveInnovations/zen-mcp-server/blob/main/README.md"
LABEL org.opencontainers.image.licenses="Apache 2.0 License"

# Create non-root user for security
RUN groupadd -r zenuser && useradd -r -g zenuser zenuser

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=zenuser:zenuser . .

# Create logs directory with proper permissions
RUN mkdir -p logs && chown -R zenuser:zenuser logs

# Create tmp directory for container operations
RUN mkdir -p tmp && chown -R zenuser:zenuser tmp

# Copy health check script
COPY --chown=zenuser:zenuser docker/scripts/healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod +x /usr/local/bin/healthcheck.py

# Switch to non-root user
USER zenuser

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python /usr/local/bin/healthcheck.py

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Default command
CMD ["python", "server.py"]
