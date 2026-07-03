# GTA Copilot — start the brain (listener + voice + overlay).
# Start this BEFORE launching GTA. Hold Right Ctrl to talk.
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "No .venv found — run .\scripts\setup.ps1 first."
}

& .venv\Scripts\python.exe -m src.brain.copilot @args
