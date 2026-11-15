<#
.SYNOPSIS
THE THIRD EYE — Projects-Level Multi-Lane Coordinator & Relay (Lanes A, B, C)
Can be launched from inside any repository clone or from C:\Users\<USER>\projects.
Automatically scans Lanes A, B, and C, reviews git/handoff status, picks the active lane needing work, and executes the autonomous review-and-fix loop.

USAGE:
  .\scripts\launch-coordinator.ps1
  .\scripts\launch-coordinator.ps1 P5
  .\scripts\launch-coordinator.ps1 -Role P5 -UseAgyForJudge
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

$ErrorActionPreference = "Continue"

# 1. Resolve Repository Root & Current Directory
$CurrentDir = (Get-Location).Path
$RepoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $RepoRoot) {
    if (Test-Path "$CurrentDir\the-third-eye") {
        $RepoRoot = "$CurrentDir\the-third-eye"
    } elseif (Test-Path "$CurrentDir\the-third-eye-p5") {
        $RepoRoot = "$CurrentDir\the-third-eye-p5"
    } else {
        $RepoRoot = $CurrentDir
    }
}

# 2. Resolve Projects Directory
$ProjectsDir = (Split-Path $RepoRoot -Parent)
if (-not $ProjectsDir -or -not (Test-Path $ProjectsDir)) {
    $ProjectsDir = "$HOME\projects"
}

# 3. Auto-Detect Role if not passed
if (-not $Role) {
    if ($RepoRoot -match "[-_]p([1-5])" -or $CurrentDir -match "[-_]p([1-5])") {
        $Role = "P" + $Matches[1].ToUpper()
    } elseif ($RepoRoot -match "P([1-5])" -or $CurrentDir -match "P([1-5])") {
        $Role = "P" + $Matches[1].ToUpper()
    } else {
        $Role = "P3"
    }
}
$Role = $Role.ToUpper().Trim()

# Auto-detect P5 agy judge requirement or missing Codex
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
    
    # Try different naming conventions for worktrees
    $Candidates = @(
        "$ProjectsDir\the-third-eye-${Role}-${LaneLetter}",
        "$ProjectsDir\the-third-eye-$($Role.ToLower())-${LaneLetter}",
        "$ProjectsDir\the-third-eye-${LaneLetter}",
        "$RepoRoot\..\the-third-eye-${Role}-${LaneLetter}"
    )

    $Path = ""
    foreach ($c in $Candidates) {
        if (Test-Path $c) {
            $Path = (Resolve-Path $c).Path
            break
        }
    }

    if (-not $Path) {
        return [PSCustomObject]@{
            Lane = $LaneLetter
            Path = "Not Found"
            Branch = "-"
            SHA = "-"
            Status = "IDLE (Not Initialized)"
            PendingHandoff = $false
        }
    }

    $Branch = (git -C "$Path" rev-parse --abbrev-ref HEAD 2>$null)
    $SHA = (git -C "$Path" rev-parse --short HEAD 2>$null)
    $Dirty = [bool](git -C "$Path" status --porcelain 2>$null)
    $Status = if ($Dirty) { "DIRTY (Uncommitted)" } else { "CLEAN" }

    return [PSCustomObject]@{
        Lane = $LaneLetter
        Path = $Path
        Branch = $Branch
        SHA = $SHA
        Status = $Status
        PendingHandoff = $false
    }
}

function Show-Dashboard {
    Write-Host "`n--- LANE STATUS OVERVIEW ---" -ForegroundColor Yellow
    $Lanes = @("A", "B", "C")
    $LaneObjects = @()
    foreach ($L in $Lanes) {
        $Obj = Get-LaneStatus -LaneLetter $L
        $LaneObjects += $Obj
        Write-Host "  Lane $L [${Role}-${L}]: $($Obj.Branch) ($($Obj.SHA)) | Status: $($Obj.Status)" -ForegroundColor $(if ($Obj.Status -eq "CLEAN") {"Green"} elseif ($Obj.Status -like "*IDLE*") {"DarkGray"} else {"Yellow"})
    }
    Write-Host "----------------------------`n" -ForegroundColor Yellow
    return $LaneObjects
}

# Ensure relay script exists
$RelayScript = "$RepoRoot\scripts\relay-watcher.ps1"
if (-not (Test-Path $RelayScript)) {
    Write-Error "Cannot locate relay-watcher script at $RelayScript"
    exit 1
}

do {
    # 1. Fetch origin updates
    git -C "$RepoRoot" fetch origin handoff integration 2>$null

    # 2. Check for incoming verdicts or fixed tasks
    $ChosenLane = ""
    $ActiveTask = ""

    if ($Role -eq "P5") {
        # P5 checks for any newly pushed fixed notes to test
        $FixedList = git -C "$RepoRoot" ls-tree -r origin/handoff handoff/fixed/ 2>$null
        if ($FixedList) {
            $HandledLog = "$HOME\.the-third-eye-relay\handled_P5.txt"
            $Handled = @()
            if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }
            
            $Lines = $FixedList -split "`n"
            foreach ($Line in $Lines) {
                if ($Line -match "\s+(handoff/fixed/[^/]+/[^/]+/r\d+\.md)$") {
                    $P = $Matches[1]
                    if ($Handled -notcontains $P) {
                        $ChosenLane = "B" # P5 E2E default
                        $ActiveTask = $P
                        break
                    }
                }
            }
        }
    } else {
        # Developer roles (P1-P4) check for incoming verdicts
        $Verdicts = git -C "$RepoRoot" ls-tree -r origin/handoff handoff/verdicts/${Role}/ 2>$null
        if ($Verdicts) {
            $HandledLog = "$HOME\.the-third-eye-relay\handled_${Role}.txt"
            $Handled = @()
            if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }
            
            $Lines = $Verdicts -split "`n"
            foreach ($Line in $Lines) {
                if ($Line -match "\s+(handoff/verdicts/${Role}/([^/]+)/.+\.md)$") {
                    $FullPath = $Matches[1]
                    $TaskId = $Matches[2]
                    if ($Handled -notcontains $FullPath) {
                        if ($TaskId -match "P[1-5]-([ABC])-") {
                            $ChosenLane = $Matches[1]
                            $ActiveTask = $TaskId
                            break
                        }
                    }
                }
            }
        }
    }

    $LaneStates = Show-Dashboard

    if ($ChosenLane) {
        Write-Host ">>> ACTION REQUIRED: Detected incoming task/verdict for $ActiveTask -> Routing to Lane $ChosenLane" -ForegroundColor Green
        
        $RelayArgs = @("-ExecutionPolicy", "Bypass", "-File", $RelayScript, "-Role", $Role, "-RunOnce")
        if ($UseAgyForJudge) { $RelayArgs += "-UseAgyForJudge" }
        
        powershell @RelayArgs
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] All lanes idling. No pending incoming tasks for ${Role}." -ForegroundColor Gray
    }

    if ($Once) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
} while ($true)
