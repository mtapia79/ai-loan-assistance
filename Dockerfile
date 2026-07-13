# ── Stage 1: Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec first for layer caching
COPY pyproject.toml poetry.lock* .
COPY README.md .
COPY app/ ./app/

# Install dependencies using Poetry
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-root && \
    pip install -e .

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --system appgroup && useradd --system --gid appgroup appuser

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy application source
COPY app/ ./app
COPY pyproject.toml poetry.lock* .

# Ensure we own our working directory
RUN chown -R appuser:appgroup /app

USER appuser

# Metadata
LABEL org.opencontainers.image.title="AI Loan Assistance"
LABEL org.opencontainers.image.description="Enterprise AI Loan Decision Assistant"
LABEL org.opencontainers.image.version="0.1.0"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
