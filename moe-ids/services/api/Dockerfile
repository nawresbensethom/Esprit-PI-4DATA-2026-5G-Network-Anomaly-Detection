# ── Stage 1: build dependencies ──────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools for compiled packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY moe_ids/ moe_ids/
COPY mlops/ mlops/
COPY services/ services/
COPY scripts/ scripts/

# If a local wheel cache exists (populated by `make wheels`), install from disk
# so Docker never hits PyPI for the large packages. Falls back to PyPI otherwise.
COPY wheels/ wheels/
RUN pip install --no-cache-dir --no-index --find-links=wheels/ \
    --prefix=/install \
    tensorflow xgboost scikit-learn scipy numpy pandas \
    fastapi "uvicorn[standard]" prometheus-client psycopg2-binary \
    pydantic-settings python-multipart structlog

# mlflow-skinny is pure Python (~2 MB) — install from PyPI directly
RUN pip install --no-cache-dir --timeout 120 --prefix=/install \
    "mlflow-skinny>=2.8"

# ── Stage 2: runtime image ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy only the application code needed at runtime
COPY --from=builder /build/moe_ids/ moe_ids/
COPY --from=builder /build/mlops/ mlops/
COPY --from=builder /build/services/ services/
COPY --from=builder /build/scripts/ scripts/
COPY --from=builder /build/pyproject.toml pyproject.toml

# Artefacts are mounted at runtime — create the mount point
RUN mkdir -p /app/artefacts /app/logs/predictions && \
    chown -R appuser:appuser /app

USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ARTEFACTS_DIR=/app/artefacts \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"

CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]