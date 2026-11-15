param(
    [string]$DataDir = "$HOME\the-third-eye-data\weekly"
)

$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

# P2 NASA-direct weekly export (California & British Columbia; 2002-2019, 2022-2025; sealed 2020-2021 excluded)
# Source folder: https://drive.google.com/drive/folders/1JbVT1cfNcRwim243boKGcMeb8DE79CCU
$Files = @(
    @{ Name = "report_weekly.json";         Id = "1sHucWhJp9mFO-nzOGFqLaqtgARSlbDCh" },
    @{ Name = "run_log.txt";                Id = "1Y1il_GUM7TKCzLCW0Q_5dM3RJbfAle5c" },
    @{ Name = "focus_weekly_CA_BC.parquet"; Id = "1WJo1AzT-YY1vH4qLnOs9FQWU6Iqil6oz" },
    @{ Name = "focus_daily_CA_BC.parquet";  Id = "1naiMFDtyfum7LFh9NUfSQaB1la55XcHH" }
)

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  THE THIRD EYE — P2 REAL DATA SYNC (NON-SEALED)" -ForegroundColor Cyan
Write-Host "  Target Directory (outside Git): $DataDir" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

foreach ($f in $Files) {
    $Dest = Join-Path $DataDir $f.Name
    if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 0)) {
        Write-Host "  [OK] $($f.Name) already present ($([math]::Round((Get-Item $Dest).Length / 1KB, 1)) KB)" -ForegroundColor Green
        continue
    }

    $Url = "https://drive.usercontent.google.com/download?id=$($f.Id)&export=download&confirm=t"
    Write-Host "  [DL] Downloading $($f.Name)..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing -TimeoutSec 120
        if ((Test-Path $Dest) -and ((Get-Item $Dest).Length -gt 0)) {
            Write-Host "  [OK] Saved $($f.Name) ($([math]::Round((Get-Item $Dest).Length / 1KB, 1)) KB)" -ForegroundColor Green
        } else {
            Write-Warning "  [FAIL] $($f.Name) downloaded empty."
        }
    } catch {
        Write-Warning "  [FAIL] Could not download $($f.Name): $_"
    }
}

$env:THE_THIRD_EYE_DATA_DIR = $DataDir
Write-Host "`nData directory ready: $DataDir" -ForegroundColor Cyan
