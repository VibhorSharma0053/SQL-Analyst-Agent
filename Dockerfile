# file: Dockerfile
FROM python:3.12-slim

# Install system utilities (curl for healthchecks)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optimize layer caching: copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure data directory exists
RUN mkdir -p /app/data

# Ensure Python outputs logs immediately
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production

EXPOSE 8000

# Docker healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1

# Start the FastAPI server binding to 0.0.0.0
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]