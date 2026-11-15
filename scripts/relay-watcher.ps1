<#
.SYNOPSIS
THE THIRD EYE — Automated Multi-Agent Git Relay & Watcher (P1-P5)
Automates the complete review-and-fix and testing loop across all 5 teammates:
- For P1, P2, P3, P4: Watches for incoming verdicts -> Codex/agy judge -> Kiro fix -> Codex/agy verify -> push branch & handoff/fixed/
- For P5: Watches for incoming fixed notes -> pulls branch -> runs tests -> agy/Codex verdict -> pushes handoff/verdicts/
- For P4: Merges P5-approved task branches into integration.

USAGE:
  .\scripts\relay-watcher.ps1 -Role P3 -Worktree "..\the-third-eye-P3-A"
  .\scripts\relay-watcher.ps1 -Role P5 -Worktree "..\the-third-eye-P5-B" -UseAgyForJudge
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("P1", "P2", "P3", "P4", "P5")]
    [string]$Role,

    [Parameter(Mandatory=$false)]
    [string]$Worktree = "",

    [Parameter(Mandatory=$false)]
    [int]$PollIntervalSeconds = 60,

    [Parameter(Mandatory=$false)]
    [switch]$UseAgyForJudge,

    [Parameter(Mandatory=$false)]
    [switch]$RunOnce
)

$ErrorActionPreference = "Continue"
$RepoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $RepoRoot) {
    Write-Error "Must run inside a git repository."
    exit 1
}

if (-not $Worktree) {
    $Worktree = "$RepoRoot"
}

# Auto-detect if codex is available; if not, fallback to agy
$HasCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue)
if (-not $HasCodex) {
    $UseAgyForJudge = $true
}

$StateDir = "$HOME\.the-third-eye-relay"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$HandledLog = "$StateDir\handled_${Role}.txt"
if (-not (Test-Path $HandledLog)) {
    New-Item -ItemType File -Force -Path $HandledLog | Out-Null
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " THE THIRD EYE — AUTOMATED RELAY WATCHER (${Role})" -ForegroundColor Cyan
Write-Host " Worktree: $Worktree" -ForegroundColor Cyan
Write-Host " Judge:    $(if ($UseAgyForJudge) {'agy CLI (non-interactive)'} else {'Codex CLI (sandbox)'})" -ForegroundColor Cyan
Write-Host " State:    $HandledLog" -ForegroundColor Cyan
Write-Host " Interval: $PollIntervalSeconds s" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

function Invoke-Judge {
    param(
        [string]$Prompt,
        [string]$InputContent,
        [string]$WorktreePath,
        [string]$OutputFile
    )
    if (-not $UseAgyForJudge -and $HasCodex) {
        $InputContent | codex exec --sandbox read-only -C "$WorktreePath" -o "$OutputFile" "$Prompt"
    } else {
        $FullPrompt = "$Prompt`n`nINPUT CONTEXT:`n$InputContent"
        $Res = agy -p "$FullPrompt" --output-format text --print-timeout 15m --dangerously-skip-permissions
        $Res | Set-Content -Path "$OutputFile" -Encoding utf8
    }
}

function Push-HandoffFile {
    param([string]$SourceFile, [string]$DestPath)
    
    $HandoffWorktree = "$RepoRoot\..\the-third-eye-handoff-relay"
    if (-not (Test-Path $HandoffWorktree)) {
        git -C "$RepoRoot" worktree add "$HandoffWorktree" handoff 2>$null
        if (-not (Test-Path $HandoffWorktree)) {
            git -C "$RepoRoot" worktree add -b handoff "$HandoffWorktree" origin/handoff 2>$null
        }
    }

    git -C "$HandoffWorktree" fetch origin handoff
    git -C "$HandoffWorktree" checkout handoff 2>$null
    git -C "$HandoffWorktree" pull --rebase origin handoff

    $TargetFull = "$HandoffWorktree\$DestPath"
    $TargetDir = Split-Path $TargetFull -Parent
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item -Path $SourceFile -Destination $TargetFull -Force

    git -C "$HandoffWorktree" add "$DestPath"
    git -C "$HandoffWorktree" commit -m "chore(handoff): relay $DestPath"
    
    $PushSuccess = $false
    for ($i = 0; $i -lt 3; $i++) {
        git -C "$HandoffWorktree" pull --rebase origin handoff
        $res = git -C "$HandoffWorktree" push origin handoff 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PushSuccess = $true
            break
        }
        Start-Sleep -Seconds 2
    }
    if ($PushSuccess) {
        Write-Host "  -> Pushed to origin/handoff: $DestPath" -ForegroundColor Green
        return $true
    } else {
        Write-Error "Failed to push $DestPath to origin/handoff: $res"
        return $false
    }
}

# DEVELOPER ROLES (P1, P2, P3, P4): PROCESS INCOMING VERDICTS
function Process-IncomingVerdict {
    param([string]$HandoffFilePath)

    $FileName = Split-Path $HandoffFilePath -Leaf
    $TaskId = (Split-Path (Split-Path $HandoffFilePath -Parent) -Leaf)
    Write-Host "`n>>> [DETECTED] New verdict for ${Role}: $TaskId ($FileName)" -ForegroundColor Yellow

    $Round = 1
    if ($FileName -match "r(\d+)-") {
        $Round = [int]$Matches[1]
    }

    $VerdictContent = git show "origin/handoff:$HandoffFilePath" 2>$null
    if (-not $VerdictContent) {
        Write-Warning "Could not read verdict content from origin/handoff."
        return $false
    }

    # If already PASS, no code fixes needed
    if ($VerdictContent -match "Overall Verdict:\s*PASS" -or $VerdictContent -match "status:\s*PASS") {
        Write-Host "  -> Verdict is PASS. No fixes needed." -ForegroundColor Green
        return $true
    }

    # Auto-detect target worktree from Task ID (e.g. P3-A-001 -> the-third-eye-P3-A)
    $TargetWorktree = $Worktree
    if ($TaskId -match "P[1-5]-([ABC])-") {
        $Lane = $Matches[1]
        $LaneWorktree = "$RepoRoot\..\the-third-eye-${Role}-${Lane}"
        if (Test-Path $LaneWorktree) {
            $TargetWorktree = $LaneWorktree
        }
    }
    Write-Host "  -> Assigned Worktree: $TargetWorktree" -ForegroundColor Cyan

    $TempDir = "$TargetWorktree\.relay-tmp"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $LocalVerdict = "$TempDir\$FileName"
    $FixOrder = "$TempDir\fix_order_${TaskId}_r${Round}.md"
    $VerdictContent | Set-Content -Path $LocalVerdict -Encoding utf8

    Write-Host "[1/5] Running Judge on verdict to create fix order..." -ForegroundColor Cyan
    $JudgePrompt = "Judge each ${Role} finding in this verdict against THE_THIRD_EYE_FRONTEND_CONTRACT.md, the scientific plan, and UI code. Write a structured fix order with accepted findings, rejected findings with reasons, files to edit, and acceptance commands."
    
    Invoke-Judge -Prompt $JudgePrompt -InputContent $VerdictContent -WorktreePath $TargetWorktree -OutputFile $FixOrder
    if (-not (Test-Path $FixOrder)) {
        Write-Error "Judge did not produce fix order at $FixOrder"
        return $false
    }
    Write-Host "  -> Fix order generated: $FixOrder" -ForegroundColor Green

    # Check Stop Rules
    $FixContent = Get-Content $FixOrder -Raw
    $StopTriggered = $false
    $StopReason = ""

    if ($Round -ge 3 -and $VerdictContent -match "FAIL") {
        $StopTriggered = $true
        $StopReason = "Round >= 3 without dual PASS"
    }
    elseif ($FixContent -match "REJECT" -or $FixContent -match "disagree") {
        $StopTriggered = $true
        $StopReason = "Judge rejects tester finding"
    }
    elseif ($FixContent -match "STOP RULE" -or $FixContent -match "BLOCKED") {
        $StopTriggered = $true
        $StopReason = "Fix order triggered explicit Stop Rule"
    }

    if ($StopTriggered) {
        Write-Warning "[STOP RULE FIRED] $StopReason. Writing escalation to human."
        $EscalationFile = "$TempDir\escalation_${TaskId}_r${Round}.md"
        @"
# Escalation to Human ${Role}: $TaskId Round $Round
- Owner: $Role
- Task ID: $TaskId
- Trigger: $StopReason
- Base Verdict: $FileName

## Fix Order / Disagreement:
$FixContent
"@ | Set-Content -Path $EscalationFile -Encoding utf8

        Push-HandoffFile -SourceFile $EscalationFile -DestPath "handoff/escalations/$Role/${TaskId}-r${Round}.md"
        return $true
    }

    # Invoke Kiro Headless
    Write-Host "[2/5] Invoking Kiro headless in $TargetWorktree..." -ForegroundColor Cyan
    Push-Location $TargetWorktree
    try {
        Get-Content $FixOrder | kiro-cli chat --v3 --no-interactive --trust-all-tools --trust-workspace --agent the-third-eye-coder
    } finally {
        Pop-Location
    }

    # Verify Kiro's commit
    Write-Host "[3/5] Running Judge post-fix verification..." -ForegroundColor Cyan
    $VerifyOutput = "$TempDir\verify_r${Round}.md"
    Invoke-Judge -Prompt "Verify the git diff and build/test output against the fix order. Output PASS or FAIL with findings." -InputContent (Get-Content $FixOrder -Raw) -WorktreePath $TargetWorktree -OutputFile $VerifyOutput

    $VerifyResult = Get-Content $VerifyOutput -Raw
    if ($VerifyResult -match "PASS") {
        Write-Host "[4/5] Fix verified PASS!" -ForegroundColor Green

        $CurrentBranch = git -C "$TargetWorktree" rev-parse --abbrev-ref HEAD
        $CurrentSHA = git -C "$TargetWorktree" rev-parse HEAD
        Write-Host "  -> Pushing $CurrentBranch ($CurrentSHA) to origin..." -ForegroundColor Cyan
        git -C "$TargetWorktree" push origin "$CurrentBranch"

        $FixedNote = "$TempDir\fixed_${TaskId}_r${Round}.md"
        @"
# Handoff / Ready For Retest: $TaskId Round $Round
- Task ID: $TaskId
- Owner: $Role
- Branch: $CurrentBranch
- Tested SHA: $CurrentSHA
- Status: Ready for tester verification
"@ | Set-Content -Path $FixedNote -Encoding utf8

        Write-Host "[5/5] Relaying fixed notice to origin/handoff..." -ForegroundColor Cyan
        Push-HandoffFile -SourceFile $FixedNote -DestPath "handoff/fixed/$Role/$TaskId/r${Round}.md"
        return $true
    } else {
        Write-Warning "Judge verification FAIL on round $Round. Logged to $VerifyOutput"
        return $false
    }
}

# EVALUATION ROLE (P5): PROCESS INCOMING FIXED NOTES TO TEST
function Process-IncomingFixedForTesting {
    param([string]$HandoffFilePath)

    $FileName = Split-Path $HandoffFilePath -Leaf
    $OwnerRole = (Split-Path (Split-Path (Split-Path $HandoffFilePath -Parent) -Parent) -Leaf)
    $TaskId = (Split-Path (Split-Path $HandoffFilePath -Parent) -Leaf)
    
    # Extract round: r<round>.md
    $Round = 1
    if ($FileName -match "r(\d+)\.md") {
        $Round = [int]$Matches[1]
    }

    Write-Host "`n>>> [DETECTED P5 TEST JOB] Fixed task from ${OwnerRole}: $TaskId round $Round" -ForegroundColor Yellow

    $FixedContent = git show "origin/handoff:$HandoffFilePath" 2>$null
    if (-not $FixedContent) {
        return $false
    }

    # Extract Branch and Tested SHA
    $TargetBranch = ""
    $TargetSHA = ""
    if ($FixedContent -match "(?:Tested|Result)\s+SHA:\s*`?([0-9a-fA-F]{7,40})`?") { $TargetSHA = $Matches[1] }
    if ($FixedContent -match "Branch:\s*`?([a-zA-Z0-9/_.-]+)`?") { $TargetBranch = $Matches[1] }

    if (-not $TargetBranch -or -not $TargetSHA) {
        Write-Warning "Could not parse Branch or SHA from $HandoffFilePath"
        return $false
    }

    Write-Host "[1/4] Fetching and checking out $TargetBranch ($TargetSHA) for testing..." -ForegroundColor Cyan
    git -C "$Worktree" fetch origin "$TargetBranch"
    
    # Run test suite based on owner role
    Write-Host "[2/4] Executing test suite against $TargetSHA..." -ForegroundColor Cyan
    $TestResults = ""
    if ($OwnerRole -eq "P4") {
        $TestResults = pytest contracts/tests -v 2>&1
    } elseif ($OwnerRole -eq "P3") {
        $TestResults = npm --prefix frontend run build 2>&1
        $E2eResults = pytest tests/e2e -v 2>&1
        $TestResults = "$TestResults`n$E2eResults"
    } elseif ($OwnerRole -eq "P1") {
        $TestResults = pytest tests/science -v 2>&1
    } else {
        $TestResults = pytest tests/ -v 2>&1
    }

    # Judge test results
    Write-Host "[3/4] Running Judge (agy/codex) to formulate P5 review verdict..." -ForegroundColor Cyan
    $VerdictOut = "$Worktree\.relay-tmp\verdict_${TaskId}_r${Round}_P5.md"
    $JudgePrompt = "You are P5 Independent QA. Evaluate these test results for $TaskId ($TargetSHA) from $OwnerRole. Write a clean PASS or FAIL verdict file strictly following the handoff template."
    Invoke-Judge -Prompt $JudgePrompt -InputContent $TestResults -WorktreePath $Worktree -OutputFile $VerdictOut

    Write-Host "[4/4] Relaying verdict to origin/handoff..." -ForegroundColor Cyan
    Push-HandoffFile -SourceFile $VerdictOut -DestPath "handoff/verdicts/$OwnerRole/$TaskId/r${Round}-P5.md"
    return $true
}

# MAIN WATCH LOOP
do {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Checking origin/handoff for ${Role}..." -ForegroundColor Gray
    git -C "$RepoRoot" fetch origin handoff 2>$null

    $Handled = @()
    if (Test-Path $HandledLog) {
        $Handled = Get-Content $HandledLog
    }

    if ($Role -eq "P5") {
        # P5 watches handoff/fixed/ for newly ready-to-test code
        $FixedTree = git -C "$RepoRoot" ls-tree -r origin/handoff handoff/fixed/ 2>$null
        if ($FixedTree) {
            $Lines = $FixedTree -split "`n"
            foreach ($Line in $Lines) {
                if ($Line -match "\s+(handoff/fixed/[^/]+/[^/]+/r\d+\.md)$") {
                    $Path = $Matches[1]
                    if ($Handled -notcontains $Path) {
                        $ok = Process-IncomingFixedForTesting -HandoffFilePath $Path
                        if ($ok) {
                            Add-Content -Path $HandledLog -Value $Path
                        }
                    }
                }
            }
        }
    } else {
        # Developer roles (P1, P2, P3, P4) watch handoff/verdicts/<ROLE>/
        $HandoffTree = git -C "$RepoRoot" ls-tree -r origin/handoff handoff/verdicts/$Role/ 2>$null
        if ($HandoffTree) {
            $Lines = $HandoffTree -split "`n"
            foreach ($Line in $Lines) {
                if ($Line -match "\s+(handoff/verdicts/$Role/.+\.md)$") {
                    $Path = $Matches[1]
                    if ($Handled -notcontains $Path) {
                        $ok = Process-IncomingVerdict -HandoffFilePath $Path
                        if ($ok) {
                            Add-Content -Path $HandledLog -Value $Path
                        }
                    }
                }
            }
        }
    }

    if ($RunOnce) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
} while ($true)
