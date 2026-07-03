# Register (or update) the nightly agent as a Windows Scheduled Task at 03:30.
# Run once: .\scripts\nightly-register.ps1        (no admin needed, current user)
# Remove:   schtasks /delete /tn GtaCopilotNightly /f
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$cmd = "pwsh -NoProfile -ExecutionPolicy Bypass -File `"$repo\scripts\nightly.ps1`""

schtasks /create /f /tn "GtaCopilotNightly" /sc daily /st 03:30 /tr $cmd | Out-Null
Write-Host "Registered 'GtaCopilotNightly' daily at 03:30." -ForegroundColor Green
Write-Host "Dry-run now with:  schtasks /run /tn GtaCopilotNightly"
Write-Host "Logs land in .nightly\ ; PRs appear at https://github.com/b1335009/gta-copilot/pulls"
