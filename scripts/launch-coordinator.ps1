<#
.SYNOPSIS
THE THIRD EYE — Projects-Level Multi-Lane Coordinator & Relay (Lanes A, B, C)
Can be launched from inside any repository clone or from C:\Users\<USER>\projects.
Automatically scans Lanes A, B, and C, reviews git/handoff status, picks the active lane needing work, and executes the autonomous review-and-fix loop.

USAGE:
  powershell -ExecutionPolicy Bypass -File .\scripts\launch-coordinator.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\launch-coordinator.ps1 -Role P5 -UseAgyForJudge
#>

param(
    [Parameter(Mandatory=$false, Position=0)]
    [string]$Role = "",

    [Parameter(Mandatory=$false)]
    [switch]$UseAgyForJudge,

    [Parameter(Mandatory=$false)]
    [int]$PollIntervalSeconds = 45,

    [Parameter(Mandatory=$false)]
    [switch]$Once
)

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
$ErrorActionPreference = "Continue"

# 1. Resolve Repository Root & Current Directory
$CurrentDir = (Get-Location).Path
$RepoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $RepoRoot) {
    $candidates = Get-ChildItem -Path $CurrentDir -Directory -Filter "the-third-eye*" -ErrorAction SilentlyContinue
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c.FullName ".git")) {
            $RepoRoot = $c.FullName
            break
        }
    }
    if (-not $RepoRoot) { $RepoRoot = $CurrentDir }
}
$RepoRoot = (Resolve-Path $RepoRoot).Path

# 2. Resolve Projects Directory
$ProjectsDir = Split-Path $RepoRoot -Parent
if (-not $ProjectsDir -or -not (Test-Path $ProjectsDir)) {
    $ProjectsDir = "$HOME\projects"
}

# 3. Auto-Detect Role if not passed
if (-not $Role) {
    $Branch = (git -C "$RepoRoot" rev-parse --abbrev-ref HEAD 2>$null)
    if ($Branch -match "(?i)^p([1-5])/" -or $Branch -match "(?i)task/P([1-5])-") {
        $Role = "P" + $Matches[1]
    } elseif ($RepoRoot -match "(?i)[-_]p([1-5])" -or $CurrentDir -match "(?i)[-_]p([1-5])") {
        $Role = "P" + $Matches[1]
    } else {
        $Role = "P3"
    }
}
$Role = $Role.ToUpper().Trim()

# 4. Auto-detect P5 agy judge requirement or missing Codex
$HasCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue)
if (-not $HasCodex -or $Role -eq "P5") {
    $UseAgyForJudge = $true
}

Clear-Host
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  THE THIRD EYE — MULTI-LANE AGENT COORDINATOR (Role: $Role)" -ForegroundColor Cyan
Write-Host "  Repo Root:          $RepoRoot" -ForegroundColor Cyan
Write-Host "  Projects Directory: $ProjectsDir" -ForegroundColor Cyan
Write-Host "  Judge Engine:       $(if ($UseAgyForJudge) {'agy CLI (headless print)'} else {'Codex CLI (sandbox)'})" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

function Get-LaneStatus {
    param([string]$LaneLetter)

    $Path = ""
    $wtLines = git -C "$RepoRoot" worktree list --porcelain 2>$null
    $currentWt = ""
    foreach ($line in ($wtLines -split "`n")) {
        if ($line -match "^worktree\s+(.+)$") {
            $currentWt = $Matches[1].Trim()
        } elseif ($line -match "^branch\s+refs/heads/(.+)$") {
            $br = $Matches[1].Trim()
            if ($br -like "task/$Role-$LaneLetter*") {
                if (Test-Path $currentWt) {
                    $Path = (Resolve-Path $currentWt).Path
                    break
                }
            }
        }
    }

    if (-not $Path) {
        $Candidates = @(
            (Join-Path $ProjectsDir "the-third-eye-${Role}-${LaneLetter}"),
            (Join-Path $ProjectsDir "the-third-eye-$($Role.ToLower())-${LaneLetter}"),
            (Join-Path $ProjectsDir "the-third-eye-${LaneLetter}")
        )
        foreach ($c in $Candidates) {
            if (Test-Path $c) {
                $Path = (Resolve-Path $c).Path
                break
            }
        }
    }

    if (-not $Path) {
        return [PSCustomObject]@{
            Lane   = $LaneLetter
            Path   = "Not Found"
            Branch = "-"
            SHA    = "-"
            Status = "IDLE (Not Initialized)"
        }
    }

    $Branch = (git -C "$Path" rev-parse --abbrev-ref HEAD 2>$null)
    $Porcelain = (git -C "$Path" status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") }
    $Dirty  = [bool]($Porcelain)

    # Auto-fast-forward clean lanes to remote branch if behind
    if (-not $Dirty -and $Branch -and $Branch -ne "HEAD") {
        git -C "$Path" fetch origin "$Branch" --quiet 2>$null
        $LocalHead  = (git -C "$Path" rev-parse HEAD 2>$null)
        $RemoteHead = (git -C "$Path" rev-parse "origin/$Branch" 2>$null)
        if ($RemoteHead -and $LocalHead -ne $RemoteHead) {
            git -C "$Path" checkout -- .kiro/agents/the-third-eye-coder.json 2>$null
            git -C "$Path" merge --ff-only "origin/$Branch" --quiet 2>$null
            $KiroSrc = Join-Path $RepoRoot ".kiro\agents\the-third-eye-coder.json"
            if (Test-Path $KiroSrc) {
                Copy-Item -Path $KiroSrc -Destination (Join-Path $Path ".kiro\agents\the-third-eye-coder.json") -Force -ErrorAction SilentlyContinue
            }
        }
    }

    $SHA = (git -C "$Path" rev-parse --short HEAD 2>$null)
    $IsMerged = $false
    if ($SHA) {
        git -C "$Path" merge-base --is-ancestor HEAD origin/integration 2>$null
        if ($LASTEXITCODE -eq 0) { $IsMerged = $true }
    }

    $Status = if ($Dirty) {
        "DIRTY (Uncommitted)"
    } elseif ($IsMerged) {
        "MERGED INTO INTEGRATION (PASS)"
    } else {
        "CLEAN"
    }

    return [PSCustomObject]@{
        Lane   = $LaneLetter
        Path   = $Path
        Branch = $Branch
        SHA    = $SHA
        Status = $Status
    }
}

function Show-Dashboard {
    Write-Host "`n--- LANE STATUS OVERVIEW ---" -ForegroundColor Yellow
    foreach ($L in @("A", "B", "C")) {
        $Obj = Get-LaneStatus -LaneLetter $L
        $Color = if ($Obj.Status -like "CLEAN*" -or $Obj.Status -like "MERGED*") { "Green" } elseif ($Obj.Status -like "*IDLE*") { "DarkGray" } else { "Yellow" }
        Write-Host "  Lane $L [${Role}-${L}]: $($Obj.Branch) ($($Obj.SHA)) | Status: $($Obj.Status)" -ForegroundColor $Color
    }
    Write-Host "----------------------------" -ForegroundColor Yellow
}

$RelayScript = Join-Path $RepoRoot "scripts\relay-watcher.ps1"
if (-not (Test-Path $RelayScript)) {
    Write-Error "Cannot locate relay-watcher script at $RelayScript"
    exit 1
}

do {
    git -C "$RepoRoot" fetch origin handoff integration 2>$null
    git -C "$RepoRoot" checkout origin/handoff -- start.bat start.ps1 monitor.bat monitor.ps1 sync-data.bat scripts .kiro/agents/the-third-eye-coder.json 2>$null
    $env:THE_THIRD_EYE_DATA_DIR = "$HOME\the-third-eye-data\weekly"
    Show-Dashboard

    $RelayArgs = @("-ExecutionPolicy", "Bypass", "-File", $RelayScript, "-Role", $Role, "-RunOnce")
    if ($UseAgyForJudge) { $RelayArgs += "-UseAgyForJudge" }
    powershell @RelayArgs

    if ($Once) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
} while ($true)
