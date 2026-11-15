$ErrorActionPreference = "Continue"
$RepoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $RepoRoot) { $RepoRoot = $PSScriptRoot }
Set-Location $RepoRoot
git fetch origin handoff --quiet 2>$null
git checkout origin/handoff -- scripts/monitor-handoff.ps1 2>$null
& "$RepoRoot\scripts\monitor-handoff.ps1" @args
