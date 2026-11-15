<#
.SYNOPSIS
THE THIRD EYE — Plan B Fast-Track Runner (bypasses local Codex retry loop & 45s relay wait).
Runs the role's critical-path task directly with Kiro (--model claude-opus-5.5), runs the real
acceptance suite, pushes the task/* branch, and posts handoff/fixed/<Role>/<TaskId>/r<N>.md.
P5 still runs independent QA and P4 merges PASS verdicts into origin/integration.

Usage (from main repo root on handoff branch):
  powershell -ExecutionPolicy Bypass -File .\scripts\run-plan-b.ps1 -Role P1 -Clean
  powershell -ExecutionPolicy Bypass -File .\scripts\run-plan-b.ps1 -Role P4 -Clean
  powershell -ExecutionPolicy Bypass -File .\scripts\run-plan-b.ps1 -Role P3
  powershell -ExecutionPolicy Bypass -File .\scripts\run-plan-b.ps1 -Role P5
  powershell -ExecutionPolicy Bypass -File .\scripts\run-plan-b.ps1 -Role P2 -Clean
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("P1", "P2", "P3", "P4", "P5")]
    [string]$Role,

    [switch]$Clean,
    [int]$PollSeconds = 15
)

$ErrorActionPreference = "Continue"
$RepoRoot    = Split-Path -Parent $PSScriptRoot
$ProjectsDir = Split-Path -Parent $RepoRoot

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " THE THIRD EYE — PLAN B FAST-TRACK ($Role)" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 1. Sync non-sealed P2 dataset if available
$SyncScript = Join-Path $PSScriptRoot "sync-p2-data.ps1"
if (Test-Path $SyncScript) {
    try {
        & $SyncScript
        $DataDir = Join-Path $HOME "the-third-eye-data\weekly"
        if (Test-Path $DataDir) { $env:THE_THIRD_EYE_DATA_DIR = $DataDir }
    } catch {
        Write-Warning "Data sync warning: $_"
    }
}

# 2. Sync Kiro agent config
$KiroSrc = Join-Path $RepoRoot ".kiro\agents\the-third-eye-coder.json"

function Get-LaneWorktree {
    param([string]$RoleName, [string]$LaneLetter = "A")
    $candidates = @(
        (Join-Path $ProjectsDir "the-third-eye-$RoleName-$LaneLetter"),
        (Join-Path $ProjectsDir "the-third-eye-$($RoleName.ToLower())-$LaneLetter"),
        (Join-Path $ProjectsDir "the-third-eye-$LaneLetter")
    )
    foreach ($c in $candidates) {
        if (Test-Path "$c\.git") { return $c }
    }
    return $null
}

function Test-TaskMergedInIntegration {
    param([string]$TaskId)
    $logs = git -C "$RepoRoot" log origin/integration --grep="$TaskId" --oneline -n 1 2>$null
    return [bool]($logs)
}

function Push-HandoffFile {
    param([string]$SourceFile, [string]$DestPath)
    $HandoffWt = Join-Path $ProjectsDir "the-third-eye-handoff-relay"
    git -C "$RepoRoot" fetch origin handoff --quiet 2>$null
    git -C "$RepoRoot" worktree prune 2>$null
    if (-not (Test-Path "$HandoffWt\.git")) {
        if (Test-Path $HandoffWt) { Remove-Item -Recurse -Force $HandoffWt -ErrorAction SilentlyContinue }
        git -C "$RepoRoot" worktree add --detach "$HandoffWt" origin/handoff 2>$null
    } else {
        git -C "$HandoffWt" fetch origin handoff --quiet 2>$null
        git -C "$HandoffWt" checkout --detach origin/handoff 2>$null
        git -C "$HandoffWt" reset --hard origin/handoff 2>$null
        git -C "$HandoffWt" clean -fd 2>$null
    }

    $DestFull = Join-Path $HandoffWt $DestPath
    New-Item -ItemType Directory -Force -Path (Split-Path $DestFull -Parent) | Out-Null
    Copy-Item -Path $SourceFile -Destination $DestFull -Force
    git -C "$HandoffWt" add "$DestPath" 2>$null
    git -C "$HandoffWt" diff --cached --quiet 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Already up-to-date on origin/handoff: $DestPath" -ForegroundColor Gray
        return $true
    }
    git -C "$HandoffWt" commit -m "chore(handoff): relay $DestPath" 2>$null
    for ($i = 0; $i -lt 4; $i++) {
        git -C "$HandoffWt" fetch origin handoff --quiet 2>$null
        git -C "$HandoffWt" rebase origin/handoff 2>$null
        git -C "$HandoffWt" push origin HEAD:refs/heads/handoff 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  -> Pushed to origin/handoff: $DestPath" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
    }
    Write-Error "Failed to push $DestPath to origin/handoff"
    return $false
}

function Invoke-PlanBTask {
    param(
        [string]$TaskId,
        [string]$Branch,
        [int]$Round,
        [string]$TestCmd,
        [string]$PromptText
    )

    $wt = Get-LaneWorktree -RoleName $Role -LaneLetter "A"
    if (-not $wt) {
        Write-Error "Worktree for $Role Lane A not found under $ProjectsDir"
        return $false
    }

    if (Test-Path $KiroSrc) {
        $destDir = Join-Path $wt ".kiro\agents"
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
        Copy-Item -Path $KiroSrc -Destination (Join-Path $destDir "the-third-eye-coder.json") -Force -ErrorAction SilentlyContinue
    }

    if ($Clean) {
        Write-Host "[CLEAN] Resetting $wt..." -ForegroundColor Yellow
        git -C "$wt" merge --abort 2>$null
        git -C "$wt" rebase --abort 2>$null
        git -C "$wt" reset --hard HEAD 2>$null
        git -C "$wt" clean -fdx 2>$null
    }

    $dirty = (git -C "$wt" status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") -and ($_ -notmatch "\.relay-tmp[\\/]") }
    if ($dirty) {
        Write-Error "$wt has uncommitted changes. Re-run with -Clean to reset it."
        return $false
    }

    git -C "$wt" fetch origin integration "$Branch" --quiet 2>$null
    git -C "$wt" show-ref --verify --quiet "refs/remotes/origin/$Branch"
    if ($LASTEXITCODE -eq 0) {
        git -C "$wt" checkout -B "$Branch" "origin/$Branch" 2>$null
        git -C "$wt" merge --no-edit origin/integration 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Merge conflict integrating origin/integration into $Branch; starting fresh from origin/integration."
            git -C "$wt" merge --abort 2>$null
            git -C "$wt" checkout -B "$Branch" origin/integration 2>$null
        }
    } else {
        git -C "$wt" checkout -B "$Branch" origin/integration 2>$null
    }

    $TempDir = Join-Path $RepoRoot ".relay-tmp"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $PromptFile = Join-Path $TempDir "planb_${TaskId}_r${Round}.txt"
    $PromptText | Set-Content -Path $PromptFile -Encoding utf8

    Write-Host "[1/3] Running Kiro (claude-opus-5.5) for $TaskId Round $Round in $wt..." -ForegroundColor Cyan
    Push-Location $wt
    try {
        Get-Content $PromptFile | kiro-cli chat --v2 --no-interactive --trust-all-tools --model claude-opus-5.5 --agent the-third-eye-coder
        $postDirty = (git status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") -and ($_ -notmatch "\.relay-tmp[\\/]") }
        if ($postDirty) {
            git add -A -- . ':!.kiro' ':!.relay-tmp' 2>$null
            git commit -m "feat($TaskId): Plan B Round $Round" 2>$null
        }
        Write-Host "[2/3] Running acceptance suite: $TestCmd" -ForegroundColor Cyan
        Invoke-Expression $TestCmd
        $testCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if ($testCode -ne 0) {
        Write-Error "$TaskId acceptance suite failed (exit $testCode). Fix and re-run."
        return $false
    }

    $sha = (git -C "$wt" rev-parse HEAD 2>$null) -join ""
    Write-Host "[3/3] Pushing $Branch ($sha) and handoff/fixed/$Role/$TaskId/r$Round.md..." -ForegroundColor Cyan
    git -C "$wt" push -u origin "$Branch" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to push $Branch to origin."
        return $false
    }

    $fixedNote = Join-Path $TempDir "planb_fixed_${TaskId}_r${Round}.md"
    @"
# Handoff / Ready For Review: $TaskId Round $Round
- Task ID: $TaskId
- Owner: $Role
- Branch: ``$Branch``
- Tested SHA: ``$sha``
- Result SHA: ``$sha``
- Acceptance Command: ``$TestCmd`` (exit 0)
- Status: Ready for P5 verification
"@ | Set-Content -Path $fixedNote -Encoding utf8

    return (Push-HandoffFile -SourceFile $fixedNote -DestPath "handoff/fixed/$Role/$TaskId/r$Round.md")
}

# --- ROLE DISPATCH ---
if ($Role -eq "P5") {
    Write-Host "Running fast P5 QA loop (${PollSeconds}s poll) via relay-watcher.ps1..." -ForegroundColor Green
    & (Join-Path $PSScriptRoot "relay-watcher.ps1") -Role P5 -PollIntervalSeconds $PollSeconds
    exit $LASTEXITCODE
}

if ($Role -eq "P1") {
    $p1Prompt = @"
Using P2's non-sealed real dataset at `$env:THE_THIRD_EYE_DATA_DIR\focus_weekly_CA_BC.parquet (California ADM1_CODE 3218 and British Columbia ADM1_CODE 826; years 2002-2019 and 2022-2025; NEVER read 2020-2021):
1. Add a reproducible Stage A real-data calibration module under science/methods/ that loads focus_weekly_CA_BC.parquet (if present at `$env:THE_THIRD_EYE_DATA_DIR), computes Stage A calibration (2016-2018 train, 2019 dev, 2022-2025 applicability), verifies the 8.2/2.8 vs 5.5/5.5 composition counterexample behavior, and writes a compact frozen parameter summary JSON (no raw parquet files committed to Git).
2. Add synthetic unit tests in tests/science/ verifying the module without requiring external parquet files at CI time.
3. Run 'python -m pytest tests/science -q -p no:cacheprovider' and confirm all tests pass.
Edit only science/ and tests/science/.
"@
    Invoke-PlanBTask -TaskId "P1-A-002" -Branch "task/P1-A-002" -Round 1 -TestCmd "python -m pytest tests/science -q -p no:cacheprovider" -PromptText $p1Prompt
    exit 0
}

if ($Role -eq "P2") {
    $p2Prompt = @"
Make pipeline/grid/coverage.py, pipeline/grid/COVERAGE_RULE.md, and tests/unit/test_coverage.py pass ALL requirements below (Contract 1.6.0):
1. Exclude the union of [2020-01-01..2021-12-31] and any caller-supplied sealed_window independently (never min(start)..max(end)); validate ws <= we; raise ValueError if any 2020-2021 day in day_present is truthy.
2. Enforce c_min == 1.0 (never classify coverage < 1.0 as complete via caller-supplied c_min < 1.0).
3. Reject record_end > date(2025, 12, 31) with ValueError, but allow period_end > record_end when period_start <= record_end (so 2026-W01 clips at 2025-12-31 as partial with 'period_clipped'). Emit 'partition_boundary' ONLY for sealed-window exclusions, never for non-sealed partition crossings (such as 2024-12-30..2025-01-05).
4. Validate every value in day_present is isinstance(v, bool); when wholly sealed return state='unavailable' with reasons=('partition_boundary',) and no 'no_file'; in footprint_evidence_summary never return supports_status='partial' with coverage_fraction=None or coverage_fraction == 0.0 (only emit supports_status='partial' when 0.0 < coverage_fraction < 1.0; emit 'unavailable'/'unverified' when coverage_fraction is None or 0.0, per contracts/schemas/calendar.py:263).
5. Align pipeline/grid/COVERAGE_RULE.md with Contract 1.6.0 and paired_comparison_eligible in contracts/schemas/calendar.py.
Run 'python -m pytest tests/unit -q -p no:cacheprovider' and confirm 0 failures. Only edit pipeline/grid/coverage.py, pipeline/grid/COVERAGE_RULE.md, and tests/unit/test_coverage.py.
"@
    Invoke-PlanBTask -TaskId "P2-A-002" -Branch "task/P2-A-002" -Round 2 -TestCmd "python -m pytest tests/unit -q -p no:cacheprovider" -PromptText $p2Prompt
    exit 0
}

if ($Role -eq "P4") {
    Write-Host "Waiting for P1-A-002 in origin/integration (auto-merging any PASS verdicts while waiting)..." -ForegroundColor Yellow
    while ($true) {
        git -C "$RepoRoot" fetch origin handoff integration --quiet 2>$null
        # Run one P4 pass of relay-watcher auto-merge by invoking relay-watcher -RunOnce if P1-A-002 not merged yet
        if (Test-TaskMergedInIntegration -TaskId "P1-A-002") {
            Write-Host "  -> P1-A-002 is merged in origin/integration!" -ForegroundColor Green
            break
        }
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Checking PASS verdicts for merge + waiting on P1-A-002..." -ForegroundColor Gray
        & (Join-Path $PSScriptRoot "relay-watcher.ps1") -Role P4 -RunOnce
        if (Test-TaskMergedInIntegration -TaskId "P1-A-002") { break }
        Start-Sleep -Seconds $PollSeconds
    }

    $p4Prompt = @"
Update artifact_pipeline/ to consume P1's frozen Stage A real-data summary (from science/methods/ and `$env:THE_THIRD_EYE_DATA_DIR\focus_weekly_CA_BC.parquet when available, never reading 2020-2021) and emit the static JSON evidence bundle including populated counterexample_interpretations (write output under artifact_pipeline/build/bundle/ or build/bundle/ so it can be copied to frontend/public/artifacts/). Run 'python -m pytest artifact_pipeline -q -p no:cacheprovider' and confirm all tests pass. Edit only artifact_pipeline/.
"@
    $ok = Invoke-PlanBTask -TaskId "P4-A-002" -Branch "task/P4-A-002" -Round 1 -TestCmd "python -m pytest artifact_pipeline -q -p no:cacheprovider" -PromptText $p4Prompt
    if ($ok) {
        Write-Host "P4-A-002 pushed. Now running P4 fast auto-merge loop (${PollSeconds}s)..." -ForegroundColor Green
        & (Join-Path $PSScriptRoot "relay-watcher.ps1") -Role P4 -PollIntervalSeconds $PollSeconds
    }
    exit 0
}

if ($Role -eq "P3") {
    Write-Host "Waiting for P4-A-002 in origin/integration..." -ForegroundColor Yellow
    while ($true) {
        git -C "$RepoRoot" fetch origin integration --quiet 2>$null
        if (Test-TaskMergedInIntegration -TaskId "P4-A-002") {
            Write-Host "  -> P4-A-002 is merged in origin/integration!" -ForegroundColor Green
            break
        }
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Waiting for P4-A-002 merge into integration..." -ForegroundColor Gray
        Start-Sleep -Seconds $PollSeconds
    }

    $p3Prompt = @"
In frontend/ ONLY:
1. Run the artifact_pipeline bundle generator (or locate emitted static JSON bundle files + bundle_index.json in artifact_pipeline/) and copy the emitted static JSON bundle into frontend/public/artifacts/ so Lab.tsx loads real data on mount.
2. Confirm frontend/src/contracts/, frontend/test-fixtures/contract-1.6.0/, sealed_window rendering, and counterexample_interpretations rendering are intact.
3. Run 'npm --prefix frontend run test:contract' and 'npm --prefix frontend run build' and confirm exit code 0.
"@
    Invoke-PlanBTask -TaskId "P3-A-003" -Branch "task/P3-A-003" -Round 1 -TestCmd "npm --prefix frontend run test:contract; if (`$LASTEXITCODE -eq 0) { npm --prefix frontend run build }" -PromptText $p3Prompt
    exit 0
}
