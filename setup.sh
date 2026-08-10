#!/usr/bin/env bash
# One-shot project bootstrap (Linux / macOS / Git Bash)
# Creates the venv, installs backend deps, registers the `pie` package
# (editable install), and installs frontend deps. Safe to re-run.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---- Backend ---------------------------------------------------------------
if [ ! -d ".venv" ]; then
    echo "==> Creating virtual environment (.venv)"
    python -m venv .venv
fi
PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
    echo "ERROR: Python venv not found at $PYTHON" >&2
    exit 1
fi

echo "==> Installing backend dependencies (requirements.txt)"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

# Registers src layout package so `import pie` works (uvicorn, CLI, tests)
echo "==> Installing pie package (editable install: pip install -e .)"
"$PYTHON" -m pip install -e .

# ---- Frontend --------------------------------------------------------------
if [ -f "frontend/package.json" ]; then
    echo "==> Installing frontend dependencies (npm install)"
    (cd frontend && npm install)
fi

echo ""
echo "Setup complete. Start the app:"
echo "  Backend:  .venv/bin/python -m uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000"
echo "  Frontend: cd frontend && npm run dev"
