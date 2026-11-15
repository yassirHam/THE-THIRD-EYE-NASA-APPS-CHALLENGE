<#
THE THIRD EYE: frontend deployment to Vercel, from one pinned commit in a clean checkout.

Run (from anywhere):
  powershell -ExecutionPolicy Bypass -File .\RUN_DEPLOY.ps1 -VercelProject <existing-project-name>
Options:
  -Production   deploy to the production domain (default: a preview URL)
  -DryRun       stop after the checkout, data check, tests and build (no Vercel)
  -RepoRoot     your normal clone (default: $HOME\projects\the-third-eye)
  -DeployDir    clean deploy checkout (default: $HOME\projects\the-third-eye-deploy)
Token: optional $env:VERCEL_TOKEN; otherwise the script runs `vercel login`.
There is no backend service in the repo, so nothing is deployed to Railway.
#>
param(
  [string]$VercelProject,
  [switch]$Production,
  [switch]$DryRun,
  [string]$RepoRoot = "$HOME\projects\the-third-eye",
  [string]$DeployDir = "$HOME\projects\the-third-eye-deploy"
)

$DeployRef   = 'origin/task/P3-A-003'
$ExpectedSha = '492d6c5640f6a3579119f7d860c881b52acbca94'
$EvidenceRel = 'frontend\public\artifacts\evidence\stage-a-real-CA-BC-1\stage_a_real_CA_BC\stage_a_real_CA_BC.6c92fce7f0e55032.json'
$EvidenceSha = '6c92fce7f0e550324d63d66a8ae59509331f8375da5b70456b49c5eabc7a7936'

function Fail($msg) { Write-Host "STOPPED: $msg" -ForegroundColor Red; exit 1 }
function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Sha256Hex([byte[]]$bytes) {
  $h = [System.Security.Cryptography.SHA256]::Create()
  ([System.BitConverter]::ToString($h.ComputeHash($bytes)) -replace '-', '').ToLower()
}
if (-not $DryRun -and -not $VercelProject) { Fail 'Pass -VercelProject <existing Vercel project name> (ask P3/P4 if unsure).' }

Step 'Tools'
foreach ($t in 'git', 'node', 'npm') { if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { Fail "$t is not installed" } }
Write-Host "node $(node -v), npm $(npm -v)"
if (-not $DryRun -and -not (Get-Command vercel -ErrorAction SilentlyContinue)) {
  npm install -g vercel
  if ($LASTEXITCODE -ne 0) { Fail 'could not install the vercel CLI' }
}

Step "Clean checkout of $DeployRef"
if (-not (Test-Path "$RepoRoot\.git")) { Fail "$RepoRoot is not a git clone. Pass -RepoRoot <your clone>." }
git -C $RepoRoot fetch origin
if ($LASTEXITCODE -ne 0) { Fail 'git fetch failed' }
$remote = (git -C $RepoRoot rev-parse $DeployRef).Trim()
if ($remote -ne $ExpectedSha) { Fail "$DeployRef is at $remote, not the reviewed $ExpectedSha. Ask P3 which commit to deploy." }
if (Test-Path $DeployDir) {
  if (git -C $DeployDir status --porcelain) { Fail "$DeployDir has local changes. Remove them first." }
  git -C $DeployDir checkout --quiet --detach $ExpectedSha
} else {
  git -C $RepoRoot worktree add --detach $DeployDir $ExpectedSha
}
if ($LASTEXITCODE -ne 0) { Fail 'checkout failed' }
$head = (git -C $DeployDir rev-parse HEAD).Trim()
if ($head -ne $ExpectedSha) { Fail "deploy checkout is at $head" }
Write-Host "OK: $DeployDir @ $head" -ForegroundColor Green

Step 'Real-data bundle'
if (-not (Test-Path "$DeployDir\frontend\public\artifacts\bundle_index.json")) { Fail 'bundle_index.json is missing' }
$got = Sha256Hex ([System.IO.File]::ReadAllBytes((Join-Path $DeployDir $EvidenceRel)))
if ($got -ne $EvidenceSha) { Fail "evidence hash $got does not match" }
Write-Host 'OK: evidence file matches its sha256' -ForegroundColor Green

Step 'Install, test, build'
Push-Location "$DeployDir\frontend"
try {
  npm ci
  if ($LASTEXITCODE -ne 0) { Fail 'npm ci failed' }
  npm run test:contract
  if ($LASTEXITCODE -ne 0) { Fail 'frontend contract tests failed' }
  npm run build
  if ($LASTEXITCODE -ne 0) { Fail 'frontend build failed' }
} finally { Pop-Location }
Write-Host 'OK: tests and build passed' -ForegroundColor Green

Step 'Demo switches in this commit'
Select-String -Path "$DeployDir\frontend\src\lab\presentation.ts" -Pattern 'SHOW_REVIEW_NOTICES =|SHOW_PLACEHOLDER_REGIONS =' | ForEach-Object { Write-Host "  $($_.Line.Trim())" -ForegroundColor Yellow }
Write-Host '  (review notices hidden, display-only regions shown: the agreed state for the video)' -ForegroundColor Yellow

if ($DryRun) { Write-Host "`nDry run finished. Nothing was deployed." -ForegroundColor Green; exit 0 }

Step "Vercel ($(if ($Production) { 'PRODUCTION' } else { 'preview' }))"
$tok = @(); if ($env:VERCEL_TOKEN) { $tok = @('--token', $env:VERCEL_TOKEN) }
if (-not $env:VERCEL_TOKEN) {
  vercel whoami *> $null
  if ($LASTEXITCODE -ne 0) { vercel login; if ($LASTEXITCODE -ne 0) { Fail 'vercel login failed' } }
}
Push-Location "$DeployDir\frontend"
try {
  vercel link --yes --project $VercelProject @tok
  if ($LASTEXITCODE -ne 0) { Fail "vercel link failed: is '$VercelProject' the right project and team?" }
  $envName = if ($Production) { 'production' } else { 'preview' }
  vercel pull --yes --environment=$envName @tok
  if ($LASTEXITCODE -ne 0) { Fail 'vercel pull failed' }
  if ($Production) { vercel build --prod @tok } else { vercel build @tok }
  if ($LASTEXITCODE -ne 0) { Fail 'vercel build failed' }
  # stdout of `vercel deploy` is the deployment URL
  $out = if ($Production) { vercel deploy --prebuilt --prod --yes @tok } else { vercel deploy --prebuilt --yes @tok }
  if ($LASTEXITCODE -ne 0) { Fail 'vercel deploy failed' }
  $url = ($out | Select-String -Pattern 'https://[a-zA-Z0-9.-]+\.vercel\.app' | Select-Object -Last 1).Matches[0].Value
  if (-not $url) { Fail "no deployment URL in the output: $out" }
} finally { Pop-Location }
Write-Host "Deployed: $url" -ForegroundColor Green

Step 'Smoke test'
try {
  $idx = Invoke-WebRequest -Uri "$url/artifacts/bundle_index.json" -UseBasicParsing -TimeoutSec 30
  if ($idx.Content -notmatch '"bundle_version":\s*"stage-a-real-CA-BC-1"') { Fail 'bundle_index.json is missing or is the app page: wrong build' }
  $evUrl = "$url/" + (($EvidenceRel -replace '^frontend\\public\\', '') -replace '\\', '/')
  $ev = Invoke-WebRequest -Uri $evUrl -UseBasicParsing -TimeoutSec 30
  $live = Sha256Hex $ev.RawContentStream.ToArray()
  if ($live -ne $EvidenceSha) { Fail "live evidence hash $live does not match" }
  foreach ($p in '/', '/lab') { $r = Invoke-WebRequest -Uri "$url$p" -UseBasicParsing -TimeoutSec 30; Write-Host "  $p -> $($r.StatusCode)" }
  Write-Host "OK: $url serves commit $($ExpectedSha.Substring(0,7)) with the real-data bundle" -ForegroundColor Green
} catch {
  if ($_.Exception.Message -match '401') {
    Write-Host 'Preview is protected by Vercel Authentication (401). Open the URL in a logged-in browser and check /lab by hand.' -ForegroundColor Yellow
  } else { Fail "smoke test: $($_.Exception.Message)" }
}
Write-Host "`nDone. Send the team: $url  (commit $($ExpectedSha.Substring(0,7)))" -ForegroundColor Green
Write-Host 'By hand: open /lab. The Satellite menu says "Harmonized"; British Columbia and California are gold on the map.'
