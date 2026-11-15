# THE THIRD EYE — Universal One-Click Relay Launcher (P1-P5)
# Zero-configuration bootstrap for all 5 team laptops.

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
$ErrorActionPreference = "Continue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  THE THIRD EYE — AUTO-LAUNCH BOOTSTRAPPER" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Update scripts and Kiro agent config from handoff branch
Write-Host "[1/3] Syncing latest relay scripts & Kiro permissions from origin..." -ForegroundColor Yellow
git fetch origin handoff 2>$null
git checkout origin/handoff -- scripts monitor.bat monitor.ps1 .kiro/agents/the-third-eye-coder.json 2>$null

# Propagate unlocked Kiro permissions to all local git worktrees
$KiroConfig = ".kiro\agents\the-third-eye-coder.json"
if (Test-Path $KiroConfig) {
    $wtLines = git worktree list --porcelain 2>$null
    foreach ($line in ($wtLines -split "`n")) {
        if ($line -match "^worktree\s+(.+)$") {
            $wtPath = $Matches[1].Trim()
            $destDir = Join-Path $wtPath ".kiro\agents"
            if ((Test-Path $wtPath) -and ($wtPath -ne (Get-Location).Path)) {
                New-Item -ItemType Directory -Force -Path $destDir -ErrorAction SilentlyContinue | Out-Null
                Copy-Item -Path $KiroConfig -Destination (Join-Path $destDir "the-third-eye-coder.json") -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# 2. Determine Role
$CurrentPath = (Get-Location).Path
$DetectedRole = ""

$Branch = (git rev-parse --abbrev-ref HEAD 2>$null)
if ($Branch -match "(?i)^p([1-5])/" -or $Branch -match "(?i)task/P([1-5])-") {
    $DetectedRole = "P" + $Matches[1].ToUpper()
}

if (-not $DetectedRole) {
    if ($CurrentPath -match "(?i)[-_]p([1-5])") {
        $DetectedRole = "P" + $Matches[1].ToUpper()
    }
}

if (-not $DetectedRole) {
    Write-Host "`nCould not automatically detect your role from path/branch." -ForegroundColor Yellow
    Write-Host "Please enter your role number (1-5):"
    Write-Host "  1 = P1 (Science)"
    Write-Host "  2 = P2 (Data)"
    Write-Host "  3 = P3 (Frontend)"
    Write-Host "  4 = P4 (Integration)"
    Write-Host "  5 = P5 (Evaluation)"
    $Choice = Read-Host "Enter 1, 2, 3, 4, or 5"
    if ($Choice -match "^[1-5]$") {
        $DetectedRole = "P$Choice"
    } else {
        $DetectedRole = "P3"
    }
}

Write-Host "[2/3] Detected Role: $DetectedRole" -ForegroundColor Green

# 3. Detect Judge Engine
$HasCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue)
$JudgeFlag = @()
if (-not $HasCodex -or $DetectedRole -eq "P5") {
    Write-Host "[3/3] Judge: agy CLI (acting as Codex)" -ForegroundColor Cyan
    $JudgeFlag = @("-UseAgyForJudge")
} else {
    Write-Host "[3/3] Judge: Codex CLI (sandbox)" -ForegroundColor Cyan
}

Write-Host "`nLaunching coordinator for $DetectedRole...`n" -ForegroundColor Green

$Coordinator = Join-Path $PSScriptRoot "scripts\launch-coordinator.ps1"
if (-not (Test-Path $Coordinator)) {
    $Coordinator = ".\scripts\launch-coordinator.ps1"
}

powershell -ExecutionPolicy Bypass -File "$Coordinator" -Role $DetectedRole @JudgeFlag
