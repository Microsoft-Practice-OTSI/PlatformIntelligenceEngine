# One-shot project bootstrap (Windows / PowerShell)
# Creates the venv, installs backend deps, registers the `pie` package
# (editable install), and installs frontend deps. Safe to re-run.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# ---- Backend ---------------------------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment (.venv)"
    python -m venv .venv
}
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python venv not found at $Python"
}

Write-Host "==> Installing backend dependencies (requirements.txt)"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt

# Registers src layout package so `import pie` works (uvicorn, CLI, tests)
Write-Host "==> Installing pie package (editable install: pip install -e .)"
& $Python -m pip install -e .

# ---- Frontend --------------------------------------------------------------
if (Test-Path (Join-Path $Root "frontend\package.json")) {
    Write-Host "==> Installing frontend dependencies (npm install)"
    Push-Location (Join-Path $Root "frontend")
    npm install
    Pop-Location
}

Write-Host ""
Write-Host "Setup complete. Start the app:"
Write-Host "  Backend:  .venv\Scripts\python.exe -m uvicorn pie.api.app:app --reload --host 0.0.0.0 --port 8000"
Write-Host "  Frontend: cd frontend; npm run dev"
