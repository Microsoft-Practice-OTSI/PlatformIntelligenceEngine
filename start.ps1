# One-command dev launcher (Windows / PowerShell)
# Starts the PIE backend (FastAPI/uvicorn) and frontend (Vite) together.
# Press Ctrl+C to stop both. Requires setup.ps1 to have been run once.

param(
    [int]$BackendPort  = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# ---- Prerequisite checks ---------------------------------------------------
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "ERROR: Backend venv missing. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "ERROR: Frontend deps missing. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# ---- Launch backend + frontend in the same console --------------------------
$Backend = Start-Process `
    -FilePath (Join-Path $Root ".venv\Scripts\python.exe") `
    -ArgumentList @("-m", "uvicorn", "pie.api.app:app", "--reload",
                    "--host", "0.0.0.0", "--port", "$BackendPort") `
    -WorkingDirectory $Root `
    -NoNewWindow `
    -PassThru

$Frontend = Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--port", "$FrontendPort") `
    -WorkingDirectory (Join-Path $Root "frontend") `
    -NoNewWindow `
    -PassThru

Write-Host ""
Write-Host "PIE is starting up..." -ForegroundColor Green
Write-Host "  Backend : http://localhost:$BackendPort   (API docs: http://localhost:$BackendPort/docs)"
Write-Host "  Frontend: http://localhost:$FrontendPort"
Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor Yellow
Write-Host ""

try {
    # Keep this script alive while the children run. Ctrl+C is delivered to the
    # whole console group, so the children stop as well.
    while (-not ($Backend.HasExited -and $Frontend.HasExited)) {
        Start-Sleep -Milliseconds 500
    }
} catch {
    # Ctrl+C or unexpected error - fall through to cleanup
} finally {
    Write-Host "`nStopping PIE servers..." -ForegroundColor Yellow
    foreach ($proc in @($Backend, $Frontend)) {
        if ($proc -and -not $proc.HasExited) {
            taskkill /PID $proc.Id /T /F 2>$null | Out-Null
        }
    }
    Write-Host "Stopped." -ForegroundColor Green
}
