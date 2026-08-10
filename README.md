# ADPIE - Platform Intelligence Engine

## Quick Start

### Backend (FastAPI)

```powershell
cd d:\Gravity\ADPIE

# Create and activate a virtual environment (first time only)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies (first time only)
pip install -r requirements.txt

# Install the project itself in editable mode (first time only)
# Required: the package lives under src/ (src layout), so `pie` is not
# importable until installed. Without this you'll get "No module named 'pie'".
pip install -e .

# Start the backend
uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000
```

> **Important:** Always activate the virtual environment (`.venv\Scripts\Activate.ps1`) before running `pip install` or `uvicorn`.
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
npm run dev
```

The frontend will be available at `http://localhost:5173` (default Vite port)

## Project Structure

```
ADPIE/
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