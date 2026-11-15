param(
    [switch]$Once,
    [int]$RefreshSeconds = 15
)

$ErrorActionPreference = "Continue"

function Show-HandoffDashboard {
    git fetch origin handoff integration --quiet 2>$null
    $HeadSha = (git rev-parse --short origin/handoff 2>$null)
    $IntSha  = (git rev-parse --short origin/integration 2>$null)
    $AllFiles = git ls-tree -r --name-only origin/handoff 2>$null

    if (-not $Voice -and -not $Once) { Clear-Host }
    Write-Host "========================================================================================" -ForegroundColor Cyan
    Write-Host " THE THIRD EYE — LIVE HANDOFF & QA MONITOR (handoff @ $HeadSha | integration @ $IntSha) | $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================================================================" -ForegroundColor Cyan

    # Parse all tasks from fixed/ and verdicts/
    $Tasks = @{}
    foreach ($f in $AllFiles) {
        if ($f -match "^handoff/fixed/(P[1-5])/([A-Za-z0-9_-]+)/r(\d+)\.md$") {
            $Role = $Matches[1]
            $TaskId = $Matches[2]
            $Round = [int]$Matches[3]
            if (-not $Tasks.ContainsKey($TaskId)) {
                $Tasks[$TaskId] = @{ Role = $Role; MaxFixed = 0; MaxVerdict = 0; VerdictStatus = "NONE"; TestedSha = "-"; FullSha = ""; Escalated = $false }
            }
            if ($Round -gt $Tasks[$TaskId].MaxFixed) {
                $Tasks[$TaskId].MaxFixed = $Round
                $RawFixed = (git show "origin/handoff:$f" 2>$null) -join "`n"
                if ($RawFixed -match '(?i)\b(?:Tested|Result)\s+SHA[\*\s:]*`?([0-9a-fA-F]{7,40})`?') {
                    $Tasks[$TaskId].FullSha = $Matches[1]
                    $Tasks[$TaskId].TestedSha = $Matches[1].Substring(0, [Math]::Min(7, $Matches[1].Length))
                }
            }
        }
        elseif ($f -match "^handoff/verdicts/(P[1-5])/([A-Za-z0-9_-]+)/r(\d+)-P5\.md$") {
            $Role = $Matches[1]
            $TaskId = $Matches[2]
            $Round = [int]$Matches[3]
            if (-not $Tasks.ContainsKey($TaskId)) {
                $Tasks[$TaskId] = @{ Role = $Role; MaxFixed = 0; MaxVerdict = 0; VerdictStatus = "NONE"; TestedSha = "-"; FullSha = ""; Escalated = $false }
            }
            if ($Round -ge $Tasks[$TaskId].MaxVerdict) {
                $Tasks[$TaskId].MaxVerdict = $Round
                $RawVerdict = (git show "origin/handoff:$f" 2>$null) -join "`n"
                if ($RawVerdict -match '(?i)\b(?:Tested|Result)\s+SHA[\*\s:]*`?([0-9a-fA-F]{7,40})`?') {
                    $Tasks[$TaskId].FullSha = $Matches[1]
                    $Tasks[$TaskId].TestedSha = $Matches[1].Substring(0, [Math]::Min(7, $Matches[1].Length))
                }
                if ($RawVerdict -match "(?i)(?:Verdict|Status|Overall)[\s\*:-]*FAIL" -or ($RawVerdict -match "\bFAIL\b" -and $RawVerdict -notmatch "(?i)Verdict[\s\*:-]*PASS")) {
                    $Tasks[$TaskId].VerdictStatus = "FAIL (r$Round)"
                } else {
                    $Tasks[$TaskId].VerdictStatus = "PASS (r$Round)"
                }
            }
        }
    }

    foreach ($f in $AllFiles) {
        if ($f -match "^handoff/escalations/(P[1-5])/([A-Za-z0-9_-]+)-r(\d+)\.md$") {
            $EscRole = $Matches[1]
            $EscTask = $Matches[2]
            $EscRound = [int]$Matches[3]
            if ($Tasks.ContainsKey($EscTask)) {
                if ($EscRound -ge $Tasks[$EscTask].MaxFixed -and $EscRound -ge $Tasks[$EscTask].MaxVerdict) {
                    $Tasks[$EscTask].Escalated = $true
                }
            }
        }
    }

    Write-Host ""
    Write-Host ("{0,-6} {1,-14} {2,-10} {3,-10} {4,-16} {5}" -f "ROLE", "TASK ID", "FIXED RN", "SHA", "LATEST VERDICT", "NEXT ACTION / OWNER") -ForegroundColor White
    Write-Host ("-" * 88) -ForegroundColor DarkGray

    foreach ($TaskId in ($Tasks.Keys | Sort-Object)) {
        $t = $Tasks[$TaskId]
        $FixedStr = if ($t.MaxFixed -gt 0) { "r$($t.MaxFixed)" } else { "-" }
        
        if ($t.Escalated) {
            $Action = "HUMAN ESCALATION (Stop Rule)"
            $Color = "Magenta"
        }
        elseif ($t.MaxFixed -gt $t.MaxVerdict) {
            $Action = "WAITING FOR P5 QA (r$($t.MaxFixed))"
            $Color = "Yellow"
        }
        elseif ($t.VerdictStatus -like "FAIL*") {
            $Action = "WAITING FOR $($t.Role) FIX (r$($t.MaxVerdict + 1))"
            $Color = "Red"
        }
        elseif ($t.VerdictStatus -like "PASS*") {
            $IsMerged = $false
            if ($t.FullSha) {
                git merge-base --is-ancestor "$($t.FullSha)" origin/integration 2>$null
                if ($LASTEXITCODE -eq 0) { $IsMerged = $true }
            }
            if ($IsMerged) {
                $Action = "MERGED INTO INTEGRATION (DONE)"
                $Color = "Cyan"
            } else {
                $Action = "READY FOR P4 AUTO-MERGE (PASS)"
                $Color = "Green"
            }
        }
        else {
            $Action = "IDLE"
            $Color = "Gray"
        }

        Write-Host ("{0,-6} {1,-14} {2,-10} {3,-10} {4,-16} {5}" -f $t.Role, $TaskId, $FixedStr, $t.TestedSha, $t.VerdictStatus, $Action) -ForegroundColor $Color
    }

    # Recent Commits on origin/handoff
    Write-Host ""
    Write-Host "--- LAST 8 HANDOFF EVENTS (git log origin/handoff) ---" -ForegroundColor Cyan
    $RecentLogs = git log origin/handoff -n 8 --pretty=format:"  %C(yellow)%h%Creset %C(cyan)%cr%Creset - %s" 2>$null
    $RecentLogs | ForEach-Object { Write-Host $_ }

    # Escalations check
    $Escalations = $AllFiles | Where-Object { $_ -match "^handoff/escalations/.+\.md$" }
    if ($Escalations) {
        Write-Host ""
        Write-Host "--- ACTIVE ESCALATIONS ---" -ForegroundColor Magenta
        foreach ($e in $Escalations) {
            Write-Host "  ! $e" -ForegroundColor Magenta
        }
    }
    Write-Host "========================================================================================" -ForegroundColor Cyan
}

if ($Once) {
    Show-HandoffDashboard
} else {
    while ($true) {
        Show-HandoffDashboard
        Write-Host "Refreshing in $RefreshSeconds seconds... (Press Ctrl+C to exit)" -ForegroundColor DarkGray
        Start-Sleep -Seconds $RefreshSeconds
    }
}
