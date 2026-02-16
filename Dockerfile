# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt


# Final stage - slim runtime image
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser app.py .
COPY --chown=appuser:appuser cache_service.py .
COPY --chown=appuser:appuser config.py .
COPY --chown=appuser:appuser db_service.py .
COPY --chown=appuser:appuser rcon_service.py .
COPY --chown=appuser:appuser ssh_service.py .
COPY --chown=appuser:appuser stats_service.py .
COPY --chown=appuser:appuser static/ ./static/

# Create data directory for database (will be mounted as volume in K8s)
RUN mkdir -p /app/data && chown appuser:appuser /app/data

# Create .ssh directory for SSH key (will be mounted from K8s Secret)
RUN mkdir -p /home/appuser/.ssh && chown appuser:appuser /home/appuser/.ssh && chmod 700 /home/appuser/.ssh

# Switch to non-root user
USER appuser

# Add local packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Expose FastAPI port
EXPOSE 8000

# Health check (FastAPI /api/healthz endpoint)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/healthz')"

# Run the application
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
