# LibreChatMCP Dockerfile
FROM python:3.10-slim

# Set workdir
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install dependencies using pip and requirements.txt
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Set default environment variables for FastMCP compatibility
ENV PORT=3002
ENV HOST=0.0.0.0

# Start
EXPOSE 3002
CMD ["python", "main.py"]
