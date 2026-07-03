# GTA Copilot — brain-side setup (run from the repo root).
# Creates .venv, installs deps, downloads Piper TTS + voice, pulls the Ollama model.
$ErrorActionPreference = "Stop"

if (-not (Test-Path "src\brain\requirements.txt")) {
    Write-Error "Run this from the repo root (src\brain\requirements.txt not found)."
}

# 1. Python venv + deps
if (-not (Test-Path ".venv")) {
    Write-Host "[setup] creating .venv..." -ForegroundColor Cyan
    python -m venv .venv
}
& .venv\Scripts\python.exe -m pip install --quiet --upgrade pip
& .venv\Scripts\python.exe -m pip install --quiet -r src\brain\requirements.txt
Write-Host "[setup] Python deps installed" -ForegroundColor Green

# 2. Piper TTS binary + voice model
$piperDir = "models\piper"
if (-not (Test-Path "$piperDir\piper.exe")) {
    Write-Host "[setup] downloading Piper TTS..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force $piperDir | Out-Null
    $zip = "$piperDir\piper.zip"
    Invoke-WebRequest -Uri "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $piperDir -Force
    Remove-Item $zip
    # The zip nests a piper/ subfolder — flatten it
    if (Test-Path "$piperDir\piper\piper.exe") {
        Move-Item "$piperDir\piper\*" $piperDir -Force
        Remove-Item "$piperDir\piper" -Recurse -Force
    }
}
if (-not (Test-Path "$piperDir\en_US-lessac-medium.onnx")) {
    Write-Host "[setup] downloading Piper voice (en_US-lessac-medium)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx" -OutFile "$piperDir\en_US-lessac-medium.onnx"
    Invoke-WebRequest -Uri "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json" -OutFile "$piperDir\en_US-lessac-medium.onnx.json"
}
Write-Host "[setup] Piper TTS ready" -ForegroundColor Green

# 3. Ollama + model
try {
    $null = Get-Command ollama -ErrorAction Stop
    Write-Host "[setup] pulling hermes3:3b (skips if present)..." -ForegroundColor Cyan
    ollama pull hermes3:3b
    Write-Host "[setup] Ollama model ready" -ForegroundColor Green
} catch {
    Write-Warning "Ollama not found — install from https://ollama.com then run: ollama pull hermes3:3b"
}

# 4. Sanity: run the test suite (no game/model needed)
& .venv\Scripts\python.exe -m unittest discover -s tests 2>&1 | Select-Object -Last 3

Write-Host ""
Write-Host "Setup complete. Next:" -ForegroundColor Green
Write-Host "  1. Install Script Hook V + SHVDN Enhanced into the GTA root (see README)"
Write-Host "  2. Copy GtaCopilot.Mod.dll into <GTA root>\scripts\"
Write-Host "  3. .\scripts\run.ps1   (then launch GTA in Borderless, story mode)"
