# Root-level Dockerfile.
# Purpose: zero-config Railway deploy from the repo root — no Root
# Directory setting required. Builds the FastAPI backend (the default
# API service). This is the entry point Railway sees first.
#
# The Worker is the SAME image with the start command overridden in the
# Railway dashboard to `arq app.workers.arq_worker.WorkerSettings`.
#
# The Frontend is a SEPARATE Railway service that points at `frontend/`
# as its Root Directory and uses `frontend/Dockerfile`.
#
# For multi-service Railway projects where each service sets its own
# Root Directory, the per-directory Dockerfiles (`backend/Dockerfile`,
# `frontend/Dockerfile`) are equivalent and the recommended path.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
  && rm -rf /var/lib/apt/lists/*

# Install Python deps from the backend pyproject.
COPY backend/pyproject.toml ./pyproject.toml
RUN pip install --upgrade pip && pip install -e .

# App code + brand YAMLs.
COPY backend/app ./app
COPY backend/data ./data

EXPOSE 8000

# Default = API. Worker overrides via Railway dashboard:
#   arq app.workers.arq_worker.WorkerSettings
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
