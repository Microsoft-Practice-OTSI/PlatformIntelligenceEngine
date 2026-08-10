# ADPIE - Platform Intelligence Engine

## Quick Start

Run the one-shot setup script after every fresh clone (Windows/PowerShell):

```powershell
cd d:\Gravity\ADPIE
.\setup.ps1        # creates .venv, installs backend deps + `pip install -e .`, runs `npm install`
```

On Linux/macOS/Git Bash: `./setup.sh`

This installs **both** sides — backend (venv + requirements + the `pie` package in
editable mode) and frontend (`node_modules`). Without it you'll hit
`No module named 'pie'` (backend) or `'vite' is not recognized` (frontend).

### Run everything with one command

Launch the backend **and** frontend together:

```powershell
.\start.ps1        # Windows / PowerShell
```

```bash
./start.sh         # Linux / macOS / Git Bash
```

```
Backend : http://localhost:8000   (API docs: http://localhost:8000/docs)
Frontend: http://localhost:5173
```

Press `Ctrl+C` to stop both servers.

### Backend (FastAPI)

```powershell
cd d:\Gravity\ADPIE

# Start the backend
uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000
```

> **Important:** Always activate the virtual environment (`.venv\Scripts\Activate.ps1`) before running `pip install` or `uvicorn`.
> The project uses a **src layout**: `pie` lives in `src/`, so it is NOT importable until the package is installed.
> Run `.venv\Scripts\python.exe -m pip install -e .` (or the `setup.ps1` script) to fix `No module named 'pie'`.
> - If you get `uvicorn: The term 'uvicorn' is not recognized`, the venv is not active (or packages were installed into the global Python instead of the venv).
> - If you get `ModuleNotFoundError: No module named 'pie'`, the project itself is not installed — run `pip install -e .`.
> - If you see `Error creating LLM provider ... No module named 'openai'. Falling back to Mock Provider`, the venv is missing the `openai` SDK (NVIDIA NIM / OpenAI providers need it) — run `pip install -r requirements.txt` (now includes `openai`).
> If activation is not desired, run directly via the venv Python instead:
> ```powershell
> .venv\Scripts\python.exe -m uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000
> ```

The API will be available at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

### Frontend (React + Vite)

```bash
cd d:\Gravity\ADPIE\frontend
npm install        # first time only (or use setup.ps1)
npm run dev
```

The frontend will be available at `http://localhost:5173` (default Vite port)

## Project Structure

```
ADPIE/
├── setup.ps1 / setup.sh  # One-shot bootstrap: venv + deps + editable install + npm install
├── start.ps1 / start.sh  # Launch backend + frontend together (Ctrl+C to stop)
├── src/pie/           # Backend source code
│   ├── api/           # FastAPI application
│   ├── auth/          # Authentication modules
│   ├── teams/         # Teams integration
│   └── ...
├── frontend/          # React frontend
│   ├── src/
│   └── ...
├── tests/             # Test suite
├── Documentation/     # Project documentation
└── spikes/            # Experimental spikes
```

## Requirements

- Python 3.11+
- Node.js 18+
- uv or pip for Python dependencies
- npm for Node dependencies

## Install Dependencies

### Backend
```powershell
cd d:\Gravity\ADPIE

# Create the virtual environment (first time only)
python -m venv .venv

# Activate it (PowerShell). On the venv working, run uvicorn from here.
.venv\Scripts\Activate.ps1

# Install dependencies (with the venv active)
pip install -r requirements.txt
# or with uv
uv pip install -r requirements.txt

# Install the project itself in editable mode (src layout - required for `import pie`)
pip install -e .
```

### Frontend
```bash
cd d:\Gravity\ADPIE\frontend
npm install
```