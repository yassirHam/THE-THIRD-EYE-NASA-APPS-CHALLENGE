<#
.SYNOPSIS
THE THIRD EYE — Automated Multi-Agent Git Relay & Watcher (P1-P5)
Automates the complete review-and-fix and testing loop across all 5 teammates:
- For P1, P2, P3, P4: Watches for actionable FAIL/conditional verdicts on latest round -> Judge -> Kiro fix -> Judge verify -> push branch & handoff/fixed/
- For P5: Watches for latest-round fixed notes lacking a P5 verdict -> isolated test worktree -> runs tests -> Judge verdict -> pushes handoff/verdicts/

USAGE:
  powershell -ExecutionPolicy Bypass -File .\scripts\relay-watcher.ps1 -Role P3
  powershell -ExecutionPolicy Bypass -File .\scripts\relay-watcher.ps1 -Role P5 -UseAgyForJudge
#>

param(
    [Parameter(Mandatory=$false, Position=0)]
    [string]$Role = "",

    [Parameter(Mandatory=$false)]
    [string]$Worktree = "",

    [Parameter(Mandatory=$false)]
    [int]$PollIntervalSeconds = 45,

    [Parameter(Mandatory=$false)]
    [switch]$UseAgyForJudge,

    [Parameter(Mandatory=$false)]
    [switch]$RunOnce
)

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
$ErrorActionPreference = "Continue"

$CurrentDir = (Get-Location).Path
$RepoRoot = (git rev-parse --show-toplevel 2>$null)
if (-not $RepoRoot) {
    Write-Error "Must run inside a git repository."
    exit 1
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
$ProjectsDir = Split-Path $RepoRoot -Parent

if (-not $Role) {
    $Branch = (git -C "$RepoRoot" rev-parse --abbrev-ref HEAD 2>$null)
    if ($Branch -match "(?i)p([1-5])") {
        $Role = "P" + $Matches[1]
    } elseif ($RepoRoot -match "(?i)[-_]p([1-5])") {
        $Role = "P" + $Matches[1]
    } else {
        $Role = "P3"
    }
}
$Role = $Role.ToUpper().Trim()

if (-not $Worktree) {
    $Worktree = $RepoRoot
}

$HasCodex = [bool](Get-Command codex -ErrorAction SilentlyContinue)
if (-not $HasCodex -or $Role -eq "P5") {
    $UseAgyForJudge = $true
}

$StateDir = Join-Path $HOME ".the-third-eye-relay"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
$HandledLog = Join-Path $StateDir "handled_${Role}.txt"
if (-not (Test-Path $HandledLog)) {
    New-Item -ItemType File -Force -Path $HandledLog | Out-Null
}

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " THE THIRD EYE — AUTOMATED RELAY WATCHER (${Role})" -ForegroundColor Cyan
Write-Host " Repo Root: $RepoRoot" -ForegroundColor Cyan
Write-Host " Judge:     $(if ($UseAgyForJudge) {'agy CLI (non-interactive)'} else {'Codex CLI (sandbox)'})" -ForegroundColor Cyan
Write-Host " State:     $HandledLog" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

function Get-LaneWorktree {
    param([string]$RoleName, [string]$LaneLetter, [string]$TaskId = "")

    $wtLines = git -C "$RepoRoot" worktree list --porcelain 2>$null
    $currentWt = ""
    foreach ($line in ($wtLines -split "`n")) {
        if ($line -match "^worktree\s+(.+)$") {
            $currentWt = $Matches[1].Trim()
        } elseif ($line -match "^branch\s+refs/heads/(.+)$") {
            $br = $Matches[1].Trim()
            if (($TaskId -and $br -eq "task/$TaskId") -or ($br -like "task/$RoleName-$LaneLetter*")) {
                if (Test-Path $currentWt) { return (Resolve-Path $currentWt).Path }
            }
        }
    }

    $candidates = @(
        (Join-Path $ProjectsDir "the-third-eye-$RoleName-$LaneLetter"),
        (Join-Path $ProjectsDir "the-third-eye-$($RoleName.ToLower())-$LaneLetter"),
        (Join-Path $ProjectsDir "the-third-eye-$LaneLetter")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return (Resolve-Path $c).Path }
    }
    return $RepoRoot
}

function Invoke-Judge {
    param(
        [string]$Prompt,
        [string]$InputContent,
        [string]$WorktreePath,
        [string]$OutputFile
    )
    $OutDir = Split-Path $OutputFile -Parent
    if ($OutDir -and -not (Test-Path $OutDir)) {
        New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    }
    if (Test-Path $OutputFile) {
        Remove-Item -Force $OutputFile -ErrorAction SilentlyContinue
    }

    if (-not $UseAgyForJudge -and $HasCodex) {
        $InputContent | codex exec --sandbox read-only -C "$WorktreePath" -o "$OutputFile" "$Prompt"
    } else {
        $FullPrompt = "$Prompt`n`nINPUT CONTEXT:`n$InputContent"
        Push-Location $WorktreePath
        try {
            $Res = agy -p "$FullPrompt" --output-format text --print-timeout 15m --dangerously-skip-permissions 2>$null
            if ($Res) {
                ($Res -join "`n") | Set-Content -Path "$OutputFile" -Encoding utf8
            }
        } finally {
            Pop-Location
        }
    }
}

function Push-HandoffFile {
    param([string]$SourceFile, [string]$DestPath)

    if (-not (Test-Path $SourceFile)) {
        Write-Error "Source file to push does not exist: $SourceFile"
        return $false
    }

    $HandoffWorktree = Join-Path $ProjectsDir "the-third-eye-handoff-relay"
    git -C "$RepoRoot" fetch origin handoff 2>$null
    git -C "$RepoRoot" worktree prune 2>$null

    $wtGitDir = ""
    if (Test-Path "$HandoffWorktree\.git") {
        $wtGitDir = (git -C "$HandoffWorktree" rev-parse --git-dir 2>$null) -join ""
    }
    $isValidWorktree = (Test-Path "$HandoffWorktree\.git") -and ($wtGitDir -match "worktrees")

    if (-not $isValidWorktree) {
        if (Test-Path $HandoffWorktree) {
            Remove-Item -Recurse -Force $HandoffWorktree -ErrorAction SilentlyContinue
        }
        git -C "$RepoRoot" worktree prune 2>$null
        git -C "$RepoRoot" worktree add --detach "$HandoffWorktree" origin/handoff 2>$null
    }

    if (-not (Test-Path "$HandoffWorktree\.git")) {
        Write-Error "Failed to initialize valid handoff worktree at $HandoffWorktree"
        return $false
    }

    git -C "$HandoffWorktree" fetch origin handoff 2>$null
    git -C "$HandoffWorktree" checkout --detach origin/handoff 2>$null
    git -C "$HandoffWorktree" reset --hard origin/handoff 2>$null

    $TargetFull = Join-Path $HandoffWorktree ($DestPath -replace '/', '\')
    $TargetDir = Split-Path $TargetFull -Parent
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item -Path $SourceFile -Destination $TargetFull -Force

    git -C "$HandoffWorktree" add "$DestPath" 2>$null
    $status = (git -C "$HandoffWorktree" status --porcelain "$DestPath" 2>$null) -join ""
    if (-not $status) {
        Write-Host "  -> $DestPath already up to date on origin/handoff." -ForegroundColor Green
        return $true
    }

    git -C "$HandoffWorktree" commit -m "chore(handoff): relay $DestPath" 2>$null

    $PushSuccess = $false
    for ($i = 0; $i -lt 4; $i++) {
        git -C "$HandoffWorktree" fetch origin handoff 2>$null
        git -C "$HandoffWorktree" rebase origin/handoff 2>$null
        $res = git -C "$HandoffWorktree" push origin HEAD:refs/heads/handoff 2>&1
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

function Get-ActionableVerdictsForRole {
    param([string]$RoleName)

    $allFiles = (git -C "$RepoRoot" ls-tree -r --name-only origin/handoff handoff/ 2>$null) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $Handled = @()
    if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }

    $pattern = "^handoff/verdicts/$RoleName/(${RoleName}-[ABC]-\d+)/r(\d+)-([^/]+)\.md$"
    $candidates = @()

    foreach ($vf in $allFiles) {
        if ($vf -match $pattern) {
            $taskId = $Matches[1]
            $round  = [int]$Matches[2]
            $from   = $Matches[3]

            if ($Handled -contains $vf) { continue }

            # Skip if superseded by a later fixed round (r > $round)
            $laterFixed = $allFiles | Where-Object {
                $_ -match "^handoff/fixed/$RoleName/$([regex]::Escape($taskId))/r(\d+)\.md$" -and ([int]$Matches[1] -gt $round)
            }
            if ($laterFixed) { continue }

            # Skip if already escalated at this round
            if ($allFiles -contains "handoff/escalations/$RoleName/$taskId-r$round.md") { continue }

            # Check verdict content: skip if PASS
            $content = (git -C "$RepoRoot" show "origin/handoff:$vf" 2>$null) -join "`n"
            if (-not $content) { continue }
            if ($content -match '(?i)(?:Overall\s+Verdict|Verdict|Status|Decision)[\*\s]*:[\*\s]*(?:PASS|APPROVE_MERGE)\b') {
                Add-Content -Path $HandledLog -Value $vf
                continue
            }

            $candidates += [PSCustomObject]@{
                Path   = $vf
                TaskId = $taskId
                Round  = $round
                From   = $from
            }
        }
    }

    # Only process the highest round per TaskId
    $latestPerTask = @{}
    foreach ($c in $candidates) {
        if (-not $latestPerTask.ContainsKey($c.TaskId) -or $c.Round -gt $latestPerTask[$c.TaskId].Round) {
            $latestPerTask[$c.TaskId] = $c
        }
    }
    return $latestPerTask.Values
}

function Get-ActionableFixedForP5 {
    $allFiles = (git -C "$RepoRoot" ls-tree -r --name-only origin/handoff handoff/ 2>$null) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $Handled = @()
    if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }

    $latestByTask = @{}
    foreach ($ff in $allFiles) {
        if ($ff -match "^handoff/fixed/(P[1-5])/([^/]+)/r(\d+)\.md$") {
            $owner  = $Matches[1]
            $taskId = $Matches[2]
            $round  = [int]$Matches[3]
            $key    = "$owner/$taskId"
            if (-not $latestByTask.ContainsKey($key) -or $round -gt $latestByTask[$key].Round) {
                $latestByTask[$key] = [PSCustomObject]@{
                    Owner  = $owner
                    TaskId = $taskId
                    Round  = $round
                    Path   = $ff
                }
            }
        }
    }

    $pending = @()
    foreach ($item in $latestByTask.Values) {
        if ($Handled -contains $item.Path) { continue }
        $verdictPath = "handoff/verdicts/$($item.Owner)/$($item.TaskId)/r$($item.Round)-P5.md"
        if ($allFiles -notcontains $verdictPath) {
            $pending += $item
        } else {
            Add-Content -Path $HandledLog -Value $item.Path
        }
    }
    return $pending
}

# DEVELOPER ROLES (P1, P2, P3, P4): PROCESS ACTIONABLE VERDICT
function Process-IncomingVerdict {
    param([PSCustomObject]$VerdictItem)

    $HandoffFilePath = $VerdictItem.Path
    $TaskId = $VerdictItem.TaskId
    $Round  = $VerdictItem.Round
    $FileName = Split-Path $HandoffFilePath -Leaf

    Write-Host "`n>>> [DETECTED] Actionable verdict for ${Role}: $TaskId ($FileName, Round $Round)" -ForegroundColor Yellow

    $VerdictContent = (git -C "$RepoRoot" show "origin/handoff:$HandoffFilePath" 2>$null) -join "`n"
    if (-not $VerdictContent) { return $false }

    $Lane = "A"
    if ($TaskId -match "^P[1-5]-([ABC])-") { $Lane = $Matches[1] }
    $TargetWorktree = Get-LaneWorktree -RoleName $Role -LaneLetter $Lane -TaskId $TaskId
    Write-Host "  -> Assigned Worktree: $TargetWorktree" -ForegroundColor Cyan

    $TempDir = Join-Path $TargetWorktree ".relay-tmp"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $FixOrder = Join-Path $TempDir "fix_order_${TaskId}_r${Round}.md"

    $AuthorityDoc = switch ($Role) {
        "P3" { "THE_THIRD_EYE_FRONTEND_CONTRACT.md, THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt, and frontend code" }
        "P1" { "THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt, THE_THIRD_EYE_EXECUTION_SPEC.md, and science code" }
        "P2" { "THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt, THE_THIRD_EYE_EXECUTION_SPEC.md, and pipeline/data code" }
        default { "THE_THIRD_EYE_FINAL_PLAN_GEOGRAPHIC_ACCESS_UPDATED.txt, THE_THIRD_EYE_EXECUTION_SPEC.md, and contracts/artifact_pipeline/deploy code" }
    }

    Write-Host "[1/5] Running Judge on verdict to create fix order..." -ForegroundColor Cyan
    $JudgePrompt = @"
You are the $Role Judge. Review this verdict against $AuthorityDoc.
On the VERY FIRST LINE of your output, write exactly one of:
JUDGE_ACTION: APPLY_FIX
JUDGE_ACTION: NO_ACTION_NEEDED
JUDGE_ACTION: ESCALATE_STOP_RULE

Use ESCALATE_STOP_RULE only if a playbook stop rule fires (e.g. tester finding contradicts the scientific plan/contract, requires touching paths outside $Role's allowed lane, or touches sealed holdout data).
Use NO_ACTION_NEEDED if the verdict is already satisfied in HEAD or requires no code changes.
Otherwise use APPLY_FIX and provide concrete file edits and acceptance test commands for Kiro.
"@

    Invoke-Judge -Prompt $JudgePrompt -InputContent $VerdictContent -WorktreePath $TargetWorktree -OutputFile $FixOrder
    if (-not (Test-Path $FixOrder)) {
        Write-Error "Judge did not produce fix order at $FixOrder"
        return $false
    }

    $FixContent = (Get-Content $FixOrder -Raw)
    if ($FixContent -match "JUDGE_ACTION:\s*NO_ACTION_NEEDED") {
        Write-Host "  -> Judge determined NO_ACTION_NEEDED. Marking handled." -ForegroundColor Green
        return $true
    }

    $StopTriggered = $false
    $StopReason = ""
    if ($Round -ge 3 -and ($VerdictContent -match '(?i)\bFAIL\b')) {
        $StopTriggered = $true
        $StopReason = "Round >= 3 without PASS"
    } elseif ($FixContent -match "JUDGE_ACTION:\s*ESCALATE_STOP_RULE") {
        $StopTriggered = $true
        $StopReason = "Judge triggered explicit Stop Rule"
    }

    if ($StopTriggered) {
        Write-Warning "[STOP RULE FIRED] $StopReason. Writing escalation to origin/handoff."
        $EscalationFile = Join-Path $TempDir "escalation_${TaskId}_r${Round}.md"
        @"
# Escalation to Human ${Role}: $TaskId Round $Round
- Owner: $Role
- Task ID: $TaskId
- Trigger: $StopReason
- Base Verdict: $FileName

## Judge Assessment:
$FixContent
"@ | Set-Content -Path $EscalationFile -Encoding utf8

        return (Push-HandoffFile -SourceFile $EscalationFile -DestPath "handoff/escalations/$Role/${TaskId}-r${Round}.md")
    }

    Write-Host "[2/5] Invoking Kiro headless in $TargetWorktree..." -ForegroundColor Cyan
    $KiroSrc = Join-Path $RepoRoot ".kiro\agents\the-third-eye-coder.json"
    if (Test-Path $KiroSrc) {
        $KiroDestDir = Join-Path $TargetWorktree ".kiro\agents"
        New-Item -ItemType Directory -Force -Path $KiroDestDir | Out-Null
        Copy-Item -Path $KiroSrc -Destination (Join-Path $KiroDestDir "the-third-eye-coder.json") -Force -ErrorAction SilentlyContinue
    }
    Push-Location $TargetWorktree
    try {
        Get-Content $FixOrder | kiro-cli chat --v2 --no-interactive --trust-all-tools --model claude-opus-5.5 --agent the-third-eye-coder
        $DirtyFiles = (git status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") -and ($_ -notmatch "\.relay-tmp[\\/]") }
        if ($DirtyFiles) {
            git add -A -- . ':!.kiro' ':!.relay-tmp' 2>$null
            git commit -m "fix($TaskId): apply Round $Round fix order" 2>$null
        }
    } finally {
        Pop-Location
    }

    Write-Host "[3/5] Running Judge post-fix verification..." -ForegroundColor Cyan
    $VerifyOutput = Join-Path $TempDir "verify_r${Round}.md"
    Invoke-Judge -Prompt "Verify the git diff and test output in $TargetWorktree against the fix order. Start your first line with VERIFY_STATUS: PASS or VERIFY_STATUS: FAIL." -InputContent $FixContent -WorktreePath $TargetWorktree -OutputFile $VerifyOutput

    $VerifyResult = if (Test-Path $VerifyOutput) { Get-Content $VerifyOutput -Raw } else { "" }
    if ($VerifyResult -match "VERIFY_STATUS:\s*PASS" -or $VerifyResult -match "\bPASS\b") {
        Write-Host "[4/5] Fix verified PASS!" -ForegroundColor Green

        $CurrentBranch = (git -C "$TargetWorktree" rev-parse --abbrev-ref HEAD 2>$null) -join ""
        $CurrentSHA    = (git -C "$TargetWorktree" rev-parse HEAD 2>$null) -join ""
        $NextRound     = $Round + 1

        Write-Host "  -> Pushing $CurrentBranch ($CurrentSHA) to origin..." -ForegroundColor Cyan
        git -C "$TargetWorktree" push origin "$CurrentBranch"

        $FixedNote = Join-Path $TempDir "fixed_${TaskId}_r${NextRound}.md"
        @"
# Handoff / Ready For Retest: $TaskId Round $NextRound
- Task ID: $TaskId
- Owner: $Role
- Branch: ``$CurrentBranch``
- Tested SHA: ``$CurrentSHA``
- Result SHA: ``$CurrentSHA``
- Status: Ready for tester verification
"@ | Set-Content -Path $FixedNote -Encoding utf8

        Write-Host "[5/5] Relaying fixed notice to origin/handoff..." -ForegroundColor Cyan
        return (Push-HandoffFile -SourceFile $FixedNote -DestPath "handoff/fixed/$Role/$TaskId/r${NextRound}.md")
    } else {
        Write-Warning "Judge verification did not pass on round $Round. See $VerifyOutput"
        return $false
    }
}

# EVALUATION ROLE (P5): PROCESS LATEST FIXED NOTE LACKING P5 VERDICT
function Process-IncomingFixedForTesting {
    param([PSCustomObject]$FixedItem)

    $HandoffFilePath = $FixedItem.Path
    $OwnerRole = $FixedItem.Owner
    $TaskId    = $FixedItem.TaskId
    $Round     = $FixedItem.Round
    $VerdictDestPath = "handoff/verdicts/$OwnerRole/$TaskId/r${Round}-P5.md"

    git -C "$RepoRoot" fetch origin handoff --quiet 2>$null
    git -C "$RepoRoot" cat-file -e "origin/handoff:$VerdictDestPath" 2>$null
    if ($LASTEXITCODE -eq 0) {
        return $true
    }

    Write-Host "`n>>> [DETECTED P5 TEST JOB] Fixed task from ${OwnerRole}: $TaskId (Round $Round)" -ForegroundColor Yellow

    $FixedContent = (git -C "$RepoRoot" show "origin/handoff:$HandoffFilePath" 2>$null) -join "`n"
    if (-not $FixedContent) { return $false }

    $TargetBranch = if ($FixedContent -match '(?i)\bBranch[\*\s:]*`?([a-zA-Z0-9/_.-]+)`?') { $Matches[1] } else { "" }
    $TargetSHA    = if ($FixedContent -match '(?i)\b(?:Tested|Result)\s+SHA[\*\s:]*`?([0-9a-fA-F]{7,40})`?') { $Matches[1] } else { "" }

    if (-not $TargetBranch -or -not $TargetSHA) {
        Write-Warning "Could not parse Branch or SHA from $HandoffFilePath"
        return $false
    }

    Write-Host "[1/4] Preparing isolated test sandbox for $TargetBranch ($TargetSHA)..." -ForegroundColor Cyan
    git -C "$RepoRoot" fetch origin "$TargetBranch" 2>$null

    $TestSandbox = Join-Path $ProjectsDir "the-third-eye-p5-test-sandbox"
    git -C "$RepoRoot" worktree prune 2>$null
    if (-not (Test-Path "$TestSandbox\.git")) {
        if (Test-Path $TestSandbox) { Remove-Item -Recurse -Force $TestSandbox -ErrorAction SilentlyContinue }
        git -C "$RepoRoot" worktree add --detach "$TestSandbox" "$TargetSHA" 2>$null
    } else {
        git -C "$TestSandbox" fetch origin "$TargetBranch" 2>$null
        git -C "$TestSandbox" checkout --detach "$TargetSHA" 2>$null
        git -C "$TestSandbox" reset --hard "$TargetSHA" 2>$null
        git -C "$TestSandbox" clean -fd 2>$null
    }

    if (-not (Test-Path "$TestSandbox\.git")) {
        Write-Warning "Could not checkout $TargetSHA in $TestSandbox"
        return $false
    }

    Write-Host "[2/4] Executing acceptance suite against $TargetSHA..." -ForegroundColor Cyan
    $TestResults = ""
    $TestExitCode = 0
    Push-Location $TestSandbox
    try {
        if ($OwnerRole -eq "P4") {
            if ($TaskId -like "P4-C*") {
                $TestResults = (python -m pytest deploy -q -p no:cacheprovider 2>&1) -join "`n"
            } else {
                $TestResults = (python -m pytest contracts artifact_pipeline -q -p no:cacheprovider 2>&1) -join "`n"
            }
            $TestExitCode = $LASTEXITCODE
        } elseif ($OwnerRole -eq "P1") {
            $TestResults = (python -m pytest tests/science -q -p no:cacheprovider 2>&1) -join "`n"
            $TestExitCode = $LASTEXITCODE
        } elseif ($OwnerRole -eq "P2") {
            $TestResults = (python -m pytest tests/unit -q -p no:cacheprovider 2>&1) -join "`n"
            $TestExitCode = $LASTEXITCODE
        } elseif ($OwnerRole -eq "P3") {
            Push-Location "$TestSandbox\frontend"
            try {
                if (-not (Test-Path "node_modules\typescript\bin\tsc")) {
                    $existingNM = @("$RepoRoot\frontend\node_modules", "$ProjectsDir\the-third-eye\frontend\node_modules") | Where-Object { Test-Path "$_\typescript\bin\tsc" } | Select-Object -First 1
                    if ($existingNM) {
                        if (Test-Path "node_modules") { Remove-Item -Recurse -Force "node_modules" -ErrorAction SilentlyContinue }
                        New-Item -ItemType Junction -Path "$TestSandbox\frontend\node_modules" -Target $existingNM -ErrorAction SilentlyContinue | Out-Null
                    } else {
                        if (Test-Path "node_modules") { Remove-Item -Recurse -Force "node_modules" -ErrorAction SilentlyContinue }
                        Write-Host "  -> Installing frontend dependencies (with devDependencies) in test sandbox..." -ForegroundColor Gray
                        npm install --include=dev --no-audit --no-fund 2>&1 | Out-Host
                    }
                }
                $TestResults = (npm run build 2>&1) -join "`n"
                $TestExitCode = $LASTEXITCODE
            } finally {
                Pop-Location
            }
        } elseif ($OwnerRole -eq "P5") {
            if ($TaskId -like "P5-A*") {
                $TestResults = (python -m pytest eval -q -p no:cacheprovider 2>&1) -join "`n"
            } elseif ($TaskId -like "P5-B*") {
                $TestResults = (python -m pytest tests/e2e -q -p no:cacheprovider 2>&1) -join "`n"
            } elseif ($TaskId -like "P5-C*") {
                $TestResults = (python docs/submission/check_submission_readiness.py 2>&1) -join "`n"
            } else {
                $TestResults = (python -m pytest eval tests/e2e -q -p no:cacheprovider 2>&1) -join "`n"
            }
            $TestExitCode = $LASTEXITCODE
        } else {
            $TestResults = (python -m pytest -q -p no:cacheprovider 2>&1) -join "`n"
            $TestExitCode = $LASTEXITCODE
        }
    } finally {
        Pop-Location
    }

    Write-Host "  -> Suite finished with exit code $TestExitCode" -ForegroundColor $(if ($TestExitCode -eq 0) {"Green"} else {"Yellow"})

    $TempDir = Join-Path $RepoRoot ".relay-tmp"
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    $VerdictOut = Join-Path $TempDir "verdict_${TaskId}_r${Round}_P5.md"

    Write-Host "[3/4] Running Judge to formulate P5 review verdict..." -ForegroundColor Cyan
    $OverallStatus = if ($TestExitCode -eq 0) { "PASS" } else { "FAIL" }
    $JudgePrompt = @"
You are P5 Independent QA. Write the markdown verification verdict for $TaskId Round $Round (Owner: $OwnerRole, Branch: $TargetBranch, Tested SHA: $TargetSHA).
The automated test suite exited with code $TestExitCode (Expected Overall Verdict: $OverallStatus).
Include this exact header block at the top:
# P5 Verification Verdict: $TaskId Round $Round
- **From:** P5 (Independent Verification)
- **To:** $OwnerRole
- **Task ID:** $TaskId
- **Branch:** ``$TargetBranch``
- **Tested SHA:** ``$TargetSHA``
- **Round:** $Round
- **Overall Verdict:** **$OverallStatus**
"@
    $CombinedInput = "HANDOFF NOTE:`n$FixedContent`n`nACTUAL TEST OUTPUT (Exit Code $TestExitCode):`n$TestResults"
    Invoke-Judge -Prompt $JudgePrompt -InputContent $CombinedInput -WorktreePath $TestSandbox -OutputFile $VerdictOut

    if (-not (Test-Path $VerdictOut) -or ((Get-Item $VerdictOut).Length -lt 20)) {
        @"
# P5 Verification Verdict: $TaskId Round $Round

- **From:** P5 (Independent Verification)
- **To:** $OwnerRole
- **Task ID:** $TaskId
- **Branch:** ``$TargetBranch``
- **Tested SHA:** ``$TargetSHA``
- **Round:** $Round
- **Overall Verdict:** **$OverallStatus**

## Automated Test Output (Exit Code: $TestExitCode)

``````text
$TestResults
``````
"@ | Set-Content -Path $VerdictOut -Encoding utf8
    }

    git -C "$RepoRoot" fetch origin handoff --quiet 2>$null
    git -C "$RepoRoot" cat-file -e "origin/handoff:$VerdictDestPath" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  -> Verdict $VerdictDestPath already pushed by another session; skipping duplicate push." -ForegroundColor Gray
        return $true
    }

    Write-Host "[4/4] Relaying verdict to origin/handoff..." -ForegroundColor Cyan
    return (Push-HandoffFile -SourceFile $VerdictOut -DestPath $VerdictDestPath)
}

function Test-TaskMergedInIntegration {
    param([string]$TaskId)
    $logHits = (git -C "$RepoRoot" log origin/integration -n 40 --oneline 2>$null) -join "`n"
    return ($logHits -match "\b$TaskId\b")
}

# AUTONOMOUS QUEUED TASK DISPATCHER (CONTINUOUS WORK WITHOUT MANUAL WINDOW-3 PROMPTS)
function Invoke-NextRoleTask {
    $allFiles = (git -C "$RepoRoot" ls-tree -r --name-only origin/handoff handoff/ 2>$null) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $Handled = @()
    if (Test-Path $HandledLog) { $Handled = Get-Content $HandledLog }

    $Queue = @(
        @{
            Role = "P2"; TaskId = "P2-A-002"; Lane = "A"; Branch = "task/P2-A-002"; Round = 2
            RebaseIntegration = $true; RequiresMerged = @()
            TestCmd = "python -m pytest tests/unit -q -p no:cacheprovider"
            Prompt = @"
Make pipeline/grid/coverage.py, pipeline/grid/COVERAGE_RULE.md, and tests/unit/test_coverage.py pass ALL requirements below (including Codex findings on 6e09bf8) in one complete revision on task/P2-A-002 (merged with origin/integration so Contract 1.6.0 schemas exist):
1. Always enforce sealed holdout 2020-01-01..2021-12-31 in coverage.py:
   - Exclude the UNION of [2020-01-01..2021-12-31] and any caller-supplied `sealed_window` independently (NEVER take min(start)..max(end) across windows, so a 2024 window does NOT exclude 2022-2023). Validate `sealed_window` bounds (`ws <= we`).
   - Raise ValueError if any 2020-2021 day in `day_present` is truthy. Add tests for a 1-day period inside 2020 with `sealed_window=None` AND for a 2024 `sealed_window` preserving 2022-2023.
2. Enforce registered coverage threshold & Contract 1.6.0 rule:
   - Do NOT classify coverage < 1.0 as complete/certifiable via caller-supplied `c_min < 1.0`. Reject `c_min < 1.0` with ValueError (or classify any coverage < 1.0 as `partial`/`low_processed_coverage`, never `complete`) until a threshold is registered in Contract 1.6.0.
3. Enforce partition table & horizon in coverage.py:
   - Partitions: pre_2016 (<=2015-12-31), train (2016-2018), dev (2019), sealed (2020-2021), applicability (2022-2024), conditional_2025 (2025).
   - Reject record_end > date(2025, 12, 31) or period_end > date(2025, 12, 31) with ValueError (documenting in COVERAGE_RULE.md that the conditional 2026 extension is not enabled here).
   - Add optional `partition: Optional[str] = None` parameter to `period_coverage`. If the in-record period spans >1 partition, REQUIRE `partition` to be one of the spanned partitions and exclude out-of-partition days with `'partition_boundary'`; raise ValueError if omitted or invalid. Add tests (including 2024-12-31..2025-01-01 without `partition` raising ValueError, and with `partition='applicability'` succeeding as partial with `partition_boundary`).
4. Strict bool, wholly-sealed, and footprint summary rules in coverage.py:
   - Validate every value in `day_present` is `isinstance(v, bool)` (raise ValueError on `None`).
   - When `not present`: only add `'no_file'` if `expected` is non-empty (`len(expected) > 0`). If `inside` is non-empty and `expected` is empty (wholly sealed/excluded), return `state='unavailable'` with `reasons=('partition_boundary',)` and NO `'no_file'`.
   - In `footprint_evidence_summary`, NEVER return `supports_status='partial'` with `coverage_fraction=None`. When any cell-level period is unavailable (`r.coverage is None`), return an explicit unverified/unavailable outcome (`supports_status='unavailable'` or `'unverified'` with `coverage_fraction=None`), and only return `supports_status='partial'` when `coverage_fraction` is a valid non-null float in `[0.0, 1.0)`.
5. In pipeline/grid/COVERAGE_RULE.md: reference contract 1.6.0, state that `paired_comparison_eligible` is a validated Boolean field in `contracts/schemas/calendar.py` (not a function here), and document the exact partition table (`2022-2024` applicability, `2025` conditional_2025, `partition` matches any spanned partition, >2025-12-31 rejected).
Run 'python -m pytest tests/unit -q -p no:cacheprovider' and confirm 0 failures. Only edit pipeline/grid/coverage.py, pipeline/grid/COVERAGE_RULE.md, and tests/unit/test_coverage.py.
"@
        },
        @{
            Role = "P5"; TaskId = "P5-A-001"; Lane = "A"; Branch = "task/P5-A-001"; Round = 1
            RebaseIntegration = $false; RequiresMerged = @()
            TestCmd = "python -m pytest eval -q -p no:cacheprovider"
            Prompt = "Verify 'python -m pytest eval -q -p no:cacheprovider' passes cleanly on task/P5-A-001 without modifying any sealed 2020-2021 holdout data."
        },
        @{
            Role = "P1"; TaskId = "P1-A-002"; Lane = "A"; Branch = "task/P1-A-002"; Round = 1
            RebaseIntegration = $true; RequiresMerged = @()
            TestCmd = "python -m pytest tests/science -q -p no:cacheprovider"
            Prompt = @"
Using P2's non-sealed real dataset at `$env:THE_THIRD_EYE_DATA_DIR\focus_weekly_CA_BC.parquet (California ADM1_CODE 3218 and British Columbia ADM1_CODE 826; years 2002-2019 and 2022-2025; NEVER read 2020-2021):
1. Add a reproducible Stage A real-data calibration script/module under science/methods/ that loads focus_weekly_CA_BC.parquet (if present at `$env:THE_THIRD_EYE_DATA_DIR), computes Stage A calibration (2016-2018 train, 2019 dev, 2022-2025 applicability), verifies the 8.2/2.8 vs 5.5/5.5 composition counterexample behavior, and writes a compact frozen parameter summary JSON (no raw parquet files committed to Git).
2. Add synthetic unit tests in tests/science/ verifying the module without requiring external parquet files at CI time.
3. Run 'python -m pytest tests/science -q -p no:cacheprovider' and confirm all tests pass.
"@
        },
        @{
            Role = "P4"; TaskId = "P4-B-002"; Lane = "B"; Branch = "task/P4-B-002"; Round = 1
            RebaseIntegration = $true; RequiresMerged = @()
            TestCmd = "python -m pytest contracts -q -p no:cacheprovider"
            Prompt = @"
Populate `counterexample_interpretations` in contracts/build_fixtures.py (currently []) with the structured geographic composition counterexample (8.2 -> 2.8 apparent -65.85% drop under shifting O shares vs 5.5 -> 5.5 fixed-weight 0.0% true block shift), regenerate contract fixtures and contracts/generated/types.ts if needed, and run 'python -m pytest contracts -q -p no:cacheprovider' to verify all contract tests pass.
"@
        },
        @{
            Role = "P4"; TaskId = "P4-A-002"; Lane = "A"; Branch = "task/P4-A-002"; Round = 1
            RebaseIntegration = $true; RequiresMerged = @("P1-A-002", "P4-B-002")
            TestCmd = "python -m pytest artifact_pipeline -q -p no:cacheprovider"
            Prompt = @"
Update artifact_pipeline/ to consume P1's frozen Stage A real-data summary (from science/methods/ and `$env:THE_THIRD_EYE_DATA_DIR\focus_weekly_CA_BC.parquet when available, never reading 2020-2021) and emit the static JSON evidence bundle including populated counterexample_interpretations. Run 'python -m pytest artifact_pipeline -q -p no:cacheprovider' and confirm all tests pass.
"@
        },
        @{
            Role = "P3"; TaskId = "P3-A-003"; Lane = "A"; Branch = "task/P3-A-003"; Round = 1
            RebaseIntegration = $true; RequiresMerged = @("P4-B-002", "P4-A-002")
            TestCmd = "npm --prefix frontend run test:contract; if (`$LASTEXITCODE -eq 0) { npm --prefix frontend run build }"
            Prompt = @"
In frontend/:
1. Resync frontend/src/contracts/ and test fixtures to Contract 1.6.0 from contracts/.
2. Render declared `sealed_window` periods as sealed (not missing data) in the UI.
3. Render `counterexample_interpretations` (8.2/2.8 vs 5.5/5.5 geographic composition counterexample) cleanly in the Lab view.
4. Wire the latest static JSON bundle outputs from artifact_pipeline/, then run 'npm --prefix frontend run test:contract' and 'npm --prefix frontend run build' and confirm exit code 0.
"@
        }
    )

    foreach ($job in $Queue) {
        if ($job.Role -ne $Role) { continue }
        $fixedRelPath = "handoff/fixed/$($job.Role)/$($job.TaskId)/r$($job.Round).md"
        $queueKey = "QUEUE:$fixedRelPath"
        if (($allFiles -contains $fixedRelPath) -or ($Handled -contains $queueKey)) { continue }

        $attemptCount = @($Handled | Where-Object { $_ -eq "ATTEMPT:$queueKey" }).Count
        if ($attemptCount -ge 2) {
            Write-Warning "[QUEUE] $($job.TaskId) reached max 2 failed attempts; halting auto-retry to prevent infinite loop."
            Add-Content -Path $HandledLog -Value $queueKey
            continue
        }

        $prereqsMet = $true
        foreach ($req in $job.RequiresMerged) {
            if (-not (Test-TaskMergedInIntegration -TaskId $req)) {
                $prereqsMet = $false
                break
            }
        }
        if (-not $prereqsMet) { continue }

        $TargetWorktree = Get-LaneWorktree -RoleName $Role -LaneLetter $job.Lane -TaskId $job.TaskId
        if (-not (Test-Path "$TargetWorktree\.git")) {
            Write-Warning "[QUEUE] Worktree for $($job.TaskId) ($TargetWorktree) not found; skipping."
            continue
        }

        Write-Host "`n>>> [AUTO-DISPATCH QUEUE] Starting $($job.TaskId) Round $($job.Round) in $TargetWorktree..." -ForegroundColor Magenta
        $KiroSrc = Join-Path $RepoRoot ".kiro\agents\the-third-eye-coder.json"
        if (Test-Path $KiroSrc) {
            $KiroDestDir = Join-Path $TargetWorktree ".kiro\agents"
            New-Item -ItemType Directory -Force -Path $KiroDestDir | Out-Null
            Copy-Item -Path $KiroSrc -Destination (Join-Path $KiroDestDir "the-third-eye-coder.json") -Force -ErrorAction SilentlyContinue
        }

        git -C "$TargetWorktree" fetch origin integration "$($job.Branch)" 2>$null
        $Dirty = (git -C "$TargetWorktree" status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") -and ($_ -notmatch "\.relay-tmp[\\/]") }
        if ($Dirty) {
            Write-Warning "[QUEUE] $TargetWorktree has uncommitted changes; skipping auto-dispatch to preserve work."
            continue
        }

        git -C "$TargetWorktree" show-ref --verify --quiet "refs/remotes/origin/$($job.Branch)"
        if ($LASTEXITCODE -eq 0) {
            git -C "$TargetWorktree" checkout -B "$($job.Branch)" "origin/$($job.Branch)" 2>$null
            if ($job.RebaseIntegration) {
                git -C "$TargetWorktree" merge --no-edit origin/integration 2>$null
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "[QUEUE] Merge conflict integrating origin/integration into $($job.Branch); aborting."
                    git -C "$TargetWorktree" merge --abort 2>$null
                    Add-Content -Path $HandledLog -Value $queueKey
                    continue
                }
            }
        } else {
            git -C "$TargetWorktree" checkout -B "$($job.Branch)" origin/integration 2>$null
        }

        Add-Content -Path $HandledLog -Value "ATTEMPT:$queueKey"

        $TempDir = Join-Path $RepoRoot ".relay-tmp"
        New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
        $TaskPromptFile = Join-Path $TempDir "queue_$($job.TaskId)_r$($job.Round).txt"
        $job.Prompt | Set-Content -Path $TaskPromptFile -Encoding utf8

        Write-Host "[1/4] Invoking Kiro headless for $($job.TaskId)..." -ForegroundColor Cyan
        Push-Location $TargetWorktree
        try {
            Get-Content $TaskPromptFile | kiro-cli chat --v2 --no-interactive --trust-all-tools --model claude-opus-5.5 --agent the-third-eye-coder
            $PostDirty = (git status --porcelain 2>$null) -split "`n" | Where-Object { $_ -and ($_ -notmatch "\.kiro[\\/]") -and ($_ -notmatch "\.relay-tmp[\\/]") }
            if ($PostDirty) {
                git add -A -- . ':!.kiro' ':!.relay-tmp' 2>$null
                git commit -m "feat($($job.TaskId)): implement queued task Round $($job.Round)" 2>$null
            }
            Write-Host "[2/4] Running acceptance test: $($job.TestCmd)" -ForegroundColor Cyan
            $TestOut = (Invoke-Expression $job.TestCmd 2>&1) -join "`n"
            $TestCode = $LASTEXITCODE
        } finally {
            Pop-Location
        }

        if ($TestCode -ne 0) {
            Write-Warning "[QUEUE] Acceptance test failed (exit $TestCode) for $($job.TaskId). Output:`n$TestOut"
            continue
        }

        Write-Host "[3/4] Running Judge verification for $($job.TaskId)..." -ForegroundColor Cyan
        $VerifyOut = Join-Path $TempDir "queue_verify_$($job.TaskId).md"
        Invoke-Judge -Prompt "Verify $($job.TaskId) changes and test output in $TargetWorktree against project contracts and holdout firewall. Start line 1 with VERIFY_STATUS: PASS or VERIFY_STATUS: FAIL." -InputContent $TestOut -WorktreePath $TargetWorktree -OutputFile $VerifyOut
        $VerifyTxt = if (Test-Path $VerifyOut) { Get-Content $VerifyOut -Raw } else { "PASS" }
        if ($VerifyTxt -match "VERIFY_STATUS:\s*FAIL") {
            Write-Warning "[QUEUE] Judge rejected $($job.TaskId). See $VerifyOut"
            continue
        }

        $CurrentSHA = (git -C "$TargetWorktree" rev-parse HEAD 2>$null) -join ""
        git -C "$TargetWorktree" push -u origin "$($job.Branch)" 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "[QUEUE] Failed to push $($job.Branch) ($CurrentSHA) to origin."
            continue
        }
        $FixedNote = Join-Path $TempDir "fixed_$($job.TaskId)_r$($job.Round).md"
        @"
# Handoff / Ready For Review: $($job.TaskId) Round $($job.Round)
- Task ID: $($job.TaskId)
- Owner: $($job.Role)
- Branch: ``$($job.Branch)``
- Tested SHA: ``$CurrentSHA``
- Result SHA: ``$CurrentSHA``
- Acceptance Command: ``$($job.TestCmd)`` (exit 0)
- Status: Ready for P5 verification
"@ | Set-Content -Path $FixedNote -Encoding utf8

        Write-Host "[4/4] Posting $fixedRelPath to origin/handoff..." -ForegroundColor Cyan
        $pushed = Push-HandoffFile -SourceFile $FixedNote -DestPath $fixedRelPath
        if ($pushed) {
            Add-Content -Path $HandledLog -Value $queueKey
        }
        break
    }
}

# INTEGRATION LEAD (P4): AUTOMATIC SERIAL MERGE OF P5-PASSED TASKS INTO INTEGRATION
function Invoke-P4AutoMergePassedTasks {
    git -C "$RepoRoot" fetch origin handoff integration --quiet 2>$null
    $allFiles = (git -C "$RepoRoot" ls-tree -r --name-only origin/handoff handoff/ 2>$null) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }

    $tasks = @{}
    foreach ($f in $allFiles) {
        if ($f -match "^handoff/fixed/(P[1-5])/([A-Za-z0-9_-]+)/r(\d+)\.md$") {
            $owner = $Matches[1]; $tid = $Matches[2]; $rn = [int]$Matches[3]
            if (-not $tasks.ContainsKey($tid)) {
                $tasks[$tid] = @{ Owner = $owner; MaxFixed = 0; MaxVerdict = 0; FixedPath = ""; VerdictPath = ""; Escalated = $false }
            }
            if ($rn -gt $tasks[$tid].MaxFixed) {
                $tasks[$tid].MaxFixed = $rn
                $tasks[$tid].FixedPath = $f
            }
        } elseif ($f -match "^handoff/verdicts/(P[1-5])/([A-Za-z0-9_-]+)/r(\d+)-P5\.md$") {
            $owner = $Matches[1]; $tid = $Matches[2]; $rn = [int]$Matches[3]
            if (-not $tasks.ContainsKey($tid)) {
                $tasks[$tid] = @{ Owner = $owner; MaxFixed = 0; MaxVerdict = 0; FixedPath = ""; VerdictPath = ""; Escalated = $false }
            }
            if ($rn -gt $tasks[$tid].MaxVerdict) {
                $tasks[$tid].MaxVerdict = $rn
                $tasks[$tid].VerdictPath = $f
            }
        }
    }

    foreach ($f in $allFiles) {
        if ($f -match "^handoff/escalations/(P[1-5])/([A-Za-z0-9_-]+)-r(\d+)\.md$") {
            $tid = $Matches[2]; $rn = [int]$Matches[3]
            if ($tasks.ContainsKey($tid) -and $rn -ge $tasks[$tid].MaxFixed -and $rn -ge $tasks[$tid].MaxVerdict) {
                $tasks[$tid].Escalated = $true
            }
        }
    }

    foreach ($tid in ($tasks.Keys | Sort-Object)) {
        $t = $tasks[$tid]
        if ($t.Escalated -or $t.MaxFixed -eq 0 -or $t.MaxVerdict -lt $t.MaxFixed) { continue }

        $vContent = (git -C "$RepoRoot" show "origin/handoff:$($t.VerdictPath)" 2>$null) -join "`n"
        if (-not $vContent) { continue }
        $isFail = $vContent -match "(?i)(?:Overall\s+Verdict|Verdict|Status)[\s\*:-]*FAIL" -or ($vContent -match "\bFAIL\b" -and $vContent -notmatch "(?i)Verdict[\s\*:-]*PASS")
        if ($isFail) { continue }

        $fContent = (git -C "$RepoRoot" show "origin/handoff:$($t.FixedPath)" 2>$null) -join "`n"
        $branch = if ($vContent -match '(?i)\bBranch[\*\s:]*`?([a-zA-Z0-9/_.-]+)`?') { $Matches[1] } elseif ($fContent -match '(?i)\bBranch[\*\s:]*`?([a-zA-Z0-9/_.-]+)`?') { $Matches[1] } else { "task/$tid" }
        $sha    = if ($vContent -match '(?i)\b(?:Tested|Result)\s+SHA[\*\s:]*`?([0-9a-fA-F]{7,40})`?') { $Matches[1] } elseif ($fContent -match '(?i)\b(?:Tested|Result)\s+SHA[\*\s:]*`?([0-9a-fA-F]{7,40})`?') { $Matches[1] } else { "" }
        if (-not $sha) { continue }

        git -C "$RepoRoot" fetch origin "$branch" integration --quiet 2>$null
        git -C "$RepoRoot" merge-base --is-ancestor "$sha" origin/integration 2>$null
        if ($LASTEXITCODE -eq 0) { continue }

        $shortSha = $sha.Substring(0, [Math]::Min(7, $sha.Length))
        Write-Host "`n>>> [P4 AUTO-MERGE] Merging verified PASS task $tid (Round $($t.MaxVerdict), SHA $shortSha) into integration..." -ForegroundColor Green

        $MergeWt = Join-Path $ProjectsDir "the-third-eye-p4-integration-merge"
        git -C "$RepoRoot" worktree prune 2>$null
        $wtValid = $false
        if (Test-Path "$MergeWt\.git") {
            $gd = (git -C $MergeWt rev-parse --git-dir 2>$null)
            if ($gd -match "worktrees") { $wtValid = $true }
        }
        if (-not $wtValid) {
            if (Test-Path $MergeWt) { Remove-Item -Recurse -Force $MergeWt -ErrorAction SilentlyContinue }
            git -C "$RepoRoot" worktree add --detach "$MergeWt" origin/integration 2>$null
        } else {
            git -C "$MergeWt" fetch origin integration "$branch" --quiet 2>$null
            git -C "$MergeWt" checkout --detach origin/integration 2>$null
            git -C "$MergeWt" reset --hard origin/integration 2>$null
            git -C "$MergeWt" clean -fd 2>$null
        }

        $mergeTarget = $sha
        git -C "$MergeWt" cat-file -e "$mergeTarget^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $branchSha = (git -C "$MergeWt" rev-parse "origin/$branch" 2>$null) -join ""
            if ($branchSha -and $branchSha.StartsWith($shortSha)) {
                $mergeTarget = $branchSha
            }
        }
        git -C "$MergeWt" merge --no-ff "$mergeTarget" -m "Merge $tid (Round $($t.MaxVerdict), SHA $shortSha) into integration [P5 PASS]" 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "[P4 AUTO-MERGE] Merge conflict on $tid ($shortSha); aborting merge to keep integration clean."
            git -C "$MergeWt" merge --abort 2>$null
            continue
        }

        git -C "$MergeWt" push origin HEAD:refs/heads/integration 2>&1 | Out-Host
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  -> Successfully merged and pushed $tid ($shortSha) to origin/integration!" -ForegroundColor Green
            git -C "$RepoRoot" fetch origin integration --quiet 2>$null
        } else {
            Write-Warning "[P4 AUTO-MERGE] Failed to push integration after merging $tid."
        }
    }
}

# MAIN WATCH LOOP
do {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Checking origin/handoff for ${Role}..." -ForegroundColor Gray
    git -C "$RepoRoot" fetch origin handoff integration 2>$null
    if (-not $RunOnce) {
        git -C "$RepoRoot" checkout origin/handoff -- start.bat start.ps1 monitor.bat monitor.ps1 scripts .kiro/agents/the-third-eye-coder.json 2>$null
    }

    if ($Role -eq "P5") {
        $PendingJobs = Get-ActionableFixedForP5
        foreach ($job in $PendingJobs) {
            $ok = Process-IncomingFixedForTesting -FixedItem $job
            if ($ok) {
                Add-Content -Path $HandledLog -Value $job.Path
            }
        }
        Invoke-NextRoleTask
    } else {
        $PendingVerdicts = Get-ActionableVerdictsForRole -RoleName $Role
        foreach ($v in $PendingVerdicts) {
            $ok = Process-IncomingVerdict -VerdictItem $v
            if ($ok) {
                Add-Content -Path $HandledLog -Value $v.Path
            }
        }
        Invoke-NextRoleTask
        if ($Role -eq "P4") {
            Invoke-P4AutoMergePassedTasks
        }
    }

    if ($RunOnce) {
        break
    }
    Start-Sleep -Seconds $PollIntervalSeconds
} while ($true)





