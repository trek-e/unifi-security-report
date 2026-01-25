# Stage 1: Build dependencies
FROM python:3.14-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Stage 2: Production image
FROM python:3.14-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/

# Environment defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UNIFI_LOG_FORMAT=json

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /app/reports && \
    chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD test -f /tmp/unifi-scanner-health && \
        python -c "import json; d=json.load(open('/tmp/unifi-scanner-health')); exit(0 if d.get('status')=='healthy' else 1)" \
    || exit 1

ENTRYPOINT ["unifi-scanner"]
