#!/usr/bin/env bash
# Helper for Preview MCP: launches the arq worker from inside backend/
# so `app.workers.arq_worker` resolves on import path.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec .venv/bin/arq app.workers.arq_worker.WorkerSettings
