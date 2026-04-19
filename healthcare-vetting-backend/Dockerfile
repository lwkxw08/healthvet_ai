# ── HealthVet AI Backend ─────────────────────────────────────────────
# Multi-stage build for production deployment
# Base: Python 3.11 slim (Debian Bookworm)

FROM python:3.11-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies (libpq for psycopg2, curl for healthcheck)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r healthvet && useradd -r -g healthvet -d /app -s /sbin/nologin healthvet

WORKDIR /app

# ── Dependencies stage ───────────────────────────────────────────────
FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application stage ────────────────────────────────────────────────
FROM dependencies AS app

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Copy frontend static build (served by FastAPI)
COPY static/ ./static/

# Create data directory for SQLite (if used)
RUN mkdir -p /data && chown healthvet:healthvet /data

# Switch to non-root user
USER healthvet

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Run with gunicorn + uvicorn workers for production
CMD ["python", "-m", "gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
