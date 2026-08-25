# ==============================================================================
# Autonomous GitHub-to-LinkedIn Spotlight Agent - Docker Container
# ==============================================================================

FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH="data/history.db" \
    SERVER_HOST="0.0.0.0" \
    SERVER_PORT=8000

# Install system dependencies (curl for container healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching efficiency
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy application source code and files
COPY src/ /app/src/
COPY main.py /app/main.py

# Ensure persistent data storage directory exists
RUN mkdir -p /app/data

# Expose FastAPI server port
EXPOSE 8000

# Default command starts the FastAPI server
CMD ["python", "main.py"]
