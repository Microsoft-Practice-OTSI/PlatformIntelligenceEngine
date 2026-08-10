#!/usr/bin/env bash
# One-command dev launcher (Linux / macOS / Git Bash)
# Starts the PIE backend (FastAPI/uvicorn) and frontend (Vite) together.
# Press Ctrl+C to stop both. Requires setup.sh to have been run once.

set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

if [ ! -x "$ROOT/.venv/bin/python" ]; then
    echo "ERROR: Backend venv missing. Run ./setup.sh first." >&2
    exit 1
fi
if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo "ERROR: Frontend deps missing. Run ./setup.sh first." >&2
    exit 1
fi

# Kill both servers on Ctrl+C / exit
trap 'kill 0' EXIT INT TERM

echo ""
echo "PIE is starting up..."
echo "  Backend : http://localhost:${BACKEND_PORT}   (API docs: http://localhost:${BACKEND_PORT}/docs)"
echo "  Frontend: http://localhost:${FRONTEND_PORT}"
echo "Press Ctrl+C to stop both servers."
echo ""

( cd "$ROOT" && .venv/bin/python -m uvicorn pie.api.app:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" ) &
( cd "$ROOT/frontend" && npm run dev ) &

wait
