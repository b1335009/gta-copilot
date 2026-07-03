# GTA Copilot — nightly agent runner (Milestone 5).
# Runs a headless Claude Code session under the NIGHTLY_AGENT.md contract:
# one backlog item -> one branch -> one PR -> stop. Never merges.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$logDir = ".nightly"
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir ("run-" + (Get-Date -Format "yyyyMMdd-HHmm") + ".log")

# Safety preflight: clean tree on master, up to date
git fetch origin 2>&1 | Out-Null
$dirty = git status --porcelain
if ($dirty) {
    "ABORT: working tree dirty — a human or another agent left changes." | Tee-Object $log
    exit 1
}
git checkout master 2>&1 | Out-Null
git pull --ff-only 2>&1 | Out-Null

$contract = Get-Content "docs\NIGHTLY_AGENT.md" -Raw
$prompt = @"
$contract

Tonight's run. Follow the contract exactly. Begin with the workflow step 1.
"@

# Headless Claude Code. Tools are scoped; the contract + morning audit are the
# real guardrails — every PR is reviewed before any merge.
npx --yes @anthropic-ai/claude-code -p $prompt `
    --allowedTools "Read" "Glob" "Grep" "Edit" "Write" "Bash" `
    --max-turns 80 2>&1 | Tee-Object $log

"nightly run finished: $log"
