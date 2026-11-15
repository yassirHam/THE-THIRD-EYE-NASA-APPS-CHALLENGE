<#
.SYNOPSIS
THE THIRD EYE — Projects-Level Multi-Lane Coordinator & Relay (Lanes A, B, C)
Can be launched from the root repository or C:\Users\<USER>\projects.
Automatically scans Lanes A, B, and C, reviews git/handoff status, picks the active lane needing work, and executes the autonomous review-and-fix loop.

USAGE:
  powershell -ExecutionPolicy Bypass -File .\scripts\launch-coordinator.ps1 -Role P3
  powershell -ExecutionPolicy Bypass -File .\scripts\launch-coordinator.ps1 -Role P5 -UseAgyForJudge
#>

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("P1", "P2", "P3", "P4", "P5")]
    [string]$Role = "P3",

    [Parameter(Mandatory=$false)]
    [switch]$UseAgyForJudge,

    [Parameter(Mandatory=$false)]
    [int]$PollIntervalSeconds = 45,

    [Parameter(Mandatory=$false)]
    [switch]$Once
)

$ErrorActionPreference = "Continue"

# 1. Resolve Projects Directory
$CurrentDir = (Get-Location).Path
$ProjectsDir = ""

if (Test-Path "$CurrentDir\..\the-third-eye") {
    $ProjectsDir = (Resolve-Path "$CurrentDir\..").Path
} elseif (Test-Path "$CurrentDir\the-third-eye") {
    $ProjectsDir = $CurrentDir
} elseif ($CurrentDir -match "the-third-eye") {
    $ProjectsDir = (Resolve-Path "$CurrentDir\..\..").Path
} else {
    $ProjectsDir = "$HOME\projects"
}

$RepoRoot = "$ProjectsDir\the-third-eye"
if (-not (Test-Path $RepoRoot)) {
    Write-Error "Cannot locate main repository clone at $RepoRoot"
    exit 1
}

# Auto-detect Codex availability
$HasCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue)
if (-not $HasCodex) {
    $UseAgyForJudge = $true
}

Clear-Host
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  THE THIRD EYE — MULTI-LANE AGENT COORDINATOR (Role: $Role)" -ForegroundColor Cyan
Write-Host "  Projects Directory: $ProjectsDir" -ForegroundColor Cyan
Write-Host "  Judge Engine:       $(if ($UseAgyForJudge) {'agy CLI (headless print)'} else {'Codex CLI (sandbox)'})" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

function Get-LaneStatus {
    param([string]$LaneLetter)
    
    $Path = "$ProjectsDir\the-third-eye-${Role}-${LaneLetter}"
    if (-not (Test-Path $Path)) {
        return [PSCustomObject]@{
            Lane = $LaneLetter
            Path = "Not Found"
            Branch = "-"
            SHA = "-"
            Status = "MISSING"
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
        Write-Host "  Lane $L [${Role}-${L}]: $($Obj.Branch) ($($Obj.SHA)) | Status: $($Obj.Status)" -ForegroundColor $(if ($Obj.Status -eq "CLEAN") {"Green"} elseif ($Obj.Status -eq "MISSING") {"Red"} else {"Yellow"})
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

    # 2. Check for incoming verdicts addressed to this Role on handoff
    $Verdicts = git -C "$RepoRoot" ls-tree -r origin/handoff handoff/verdicts/${Role}/ 2>$null
    $ChosenLane = ""
    $ActiveTask = ""

    if ($Verdicts) {
        $Lines = $Verdicts -split "`n"
        foreach ($Line in $Lines) {
            if ($Line -match "\s+handoff/verdicts/${Role}/([^/]+)/(.+\.md)$") {
                $TaskId = $Matches[1]
                $VerdictFile = $Matches[2]
                
                # Check if this verdict was already handled
                $HandledLog = "$HOME\.the-third-eye-relay\handled_${Role}.txt"
                $Handled = @()
                if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }
                
                $FullPath = "handoff/verdicts/${Role}/$TaskId/$VerdictFile"
                if ($Handled -notcontains $FullPath) {
                    # Determine lane from Task ID
                    if ($TaskId -match "P[1-5]-([ABC])-") {
                        $ChosenLane = $Matches[1]
                        $ActiveTask = $TaskId
                        break
                    }
                }
            }
        }
    }

    $LaneStates = Show-Dashboard

    if ($ChosenLane) {
        Write-Host ">>> ACTION REQUIRED: Incoming verdict found for $ActiveTask -> Routing to Lane $ChosenLane" -ForegroundColor Green
        $TargetFolder = "$ProjectsDir\the-third-eye-${Role}-${ChosenLane}"
        
        # Invoke relay for this specific incoming event
        $RelayArgs = @("-ExecutionPolicy", "Bypass", "-File", $RelayScript, "-Role", $Role, "-Worktree", $TargetFolder, "-RunOnce")
        if ($UseAgyForJudge) { $RelayArgs += "-UseAgyForJudge" }
        
        powershell @RelayArgs
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] All lanes idling. No pending verdicts for ${Role}." -ForegroundColor Gray
    }

    if ($Once) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
} while ($true)
