# Backend service Dockerfile.
# Build context = ./backend (whether via Railway Root Directory or compose).
# Used by BOTH services:
#   - the API (uvicorn …)
#   - the arq worker (arq …)
# Each Railway service overrides `startCommand`; locally, docker-compose
# overrides via `command:`. The default CMD below is for ad-hoc `docker run`.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY app ./app
COPY data ./data

EXPOSE 8000

# Default = API. Worker is the same image with a different start command.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
