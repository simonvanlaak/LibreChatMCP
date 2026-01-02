# LibreChat-MCP Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies in a single layer
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    jq && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies with cache mount for faster rebuilds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create storage directory for user files
RUN mkdir -p /storage

# Copy application code (this layer changes most frequently)
COPY . .

# Set default environment variables for FastMCP compatibility
ENV PORT=3002 \
    HOST=0.0.0.0 \
    STORAGE_ROOT=/storage

# Expose port
EXPOSE 3002

# Start
CMD ["python", "main.py"]
