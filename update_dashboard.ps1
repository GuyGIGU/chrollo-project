# update_dashboard.ps1 — preflight the backend, rebuild the Chrollo frontend,
# and restart the service.
#
# Double-click update_dashboard.bat (or run this directly) after any code change.
# It self-elevates once via UAC, because restarting a Windows service needs
# administrator rights. Before touching the service it verifies the backend
# actually boots (compileall + an import-main smoke from the service's own cwd),
# so a broken deploy is caught BEFORE the running service is killed.
#
# The previous frontend bundle is kept in webapp\frontend\dist_previous. If a
# deploy looks wrong in the browser, roll the frontend back with:
#     powershell -File update_dashboard.ps1 -Rollback
# (Backend code comes from git — rollback only swaps the frontend bundle.)
#
# SAFETY: this script NEVER sets IBKR_LIVE_CONFIRMED and never changes the
# service's broker-free configuration. It only rebuilds dist/ and bounces the
# service, so the dashboard stays broker-free at boot exactly as before.
# (The import-main smoke does not run the app lifespan — no scheduler, no broker.)

param([switch]$Rollback)

$ErrorActionPreference = 'Stop'

# --- self-elevate -------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting administrator rights (needed to restart the service)..."
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"")
    if ($Rollback) { $argList += '-Rollback' }
    Start-Process powershell -Verb RunAs -ArgumentList $argList
    exit
}

$repo = $PSScriptRoot
Set-Location $repo
$dist = Join-Path $repo 'webapp\frontend\dist'
$distPrevious = Join-Path $repo 'webapp\frontend\dist_previous'

function Fail([string]$message) {
    Write-Host $message -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

function Restart-ServiceAndVerify {
    Write-Host "`nRestarting ChrolloDashboard service..." -ForegroundColor Cyan
    nssm restart ChrolloDashboard

    Write-Host "Waiting for the service to answer /health..." -ForegroundColor Cyan
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
            $status = if ($resp.status) { $resp.status } else { 'ok' }
            Write-Host "Service is up. /health => $status" -ForegroundColor Green
            $resp | ConvertTo-Json -Depth 4 | Write-Host
            return $true
        } catch {
            # service still restarting; retry
        }
    }
    Write-Host "Service did not answer /health within 20s. Check output\chrollo-service-error.log" -ForegroundColor Yellow
    return $false
}

# --- rollback: swap the previous frontend bundle back in ------------------------
if ($Rollback) {
    if (-not (Test-Path $distPrevious)) {
        Fail "No previous frontend bundle at $distPrevious - nothing to roll back to."
    }
    Write-Host "`nRolling frontend back to the previous bundle..." -ForegroundColor Cyan
    if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
    # Copy (not move) so the backup survives repeated rollbacks.
    Copy-Item -Recurse $distPrevious $dist
    [void](Restart-ServiceAndVerify)
    Write-Host "`nRollback done." -ForegroundColor Green
    Read-Host "Press Enter to close"
    exit
}

# --- 1. backend preflight -------------------------------------------------------
Write-Host "`n[1/4] Backend preflight (compile + boot-import smoke)..." -ForegroundColor Cyan
& python -m compileall -q core webapp\backend
if ($LASTEXITCODE -ne 0) {
    Fail "Backend compile FAILED (exit $LASTEXITCODE). Service NOT restarted."
}
# Import main exactly the way the service boots (cwd=webapp\backend). Importing
# does NOT run the lifespan, so nothing starts and nothing touches the broker.
Push-Location (Join-Path $repo 'webapp\backend')
& python -c "import main; n = len(main.app.routes); assert n > 70, 'only %d routes registered' % n"
$smokeExit = $LASTEXITCODE
Pop-Location
if ($smokeExit -ne 0) {
    Fail "Backend boot-import smoke FAILED (exit $smokeExit). Service NOT restarted."
}

# --- 2. keep the current frontend bundle for rollback ---------------------------
Write-Host "`n[2/4] Snapshotting current frontend bundle for rollback..." -ForegroundColor Cyan
if (Test-Path $dist) {
    if (Test-Path $distPrevious) { Remove-Item -Recurse -Force $distPrevious }
    Copy-Item -Recurse $dist $distPrevious
    Write-Host "Previous bundle kept at webapp\frontend\dist_previous (restore: update_dashboard.ps1 -Rollback)"
} else {
    Write-Host "No existing dist\ to snapshot (first build)."
}

# --- 3. build the frontend ------------------------------------------------------
Write-Host "`n[3/4] Building frontend (npm run build)..." -ForegroundColor Cyan
& npm --prefix "$repo\webapp\frontend" run build
if ($LASTEXITCODE -ne 0) {
    # vite empties dist\ before it fails - put the last good bundle back.
    if (Test-Path $distPrevious) {
        if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
        Copy-Item -Recurse $distPrevious $dist
        Write-Host "Previous bundle restored." -ForegroundColor Yellow
    }
    Fail "Frontend build FAILED (exit $LASTEXITCODE). Service NOT restarted."
}

# --- 4. restart the service and verify ------------------------------------------
Write-Host "`n[4/4] Restart + health check..." -ForegroundColor Cyan
[void](Restart-ServiceAndVerify)

Write-Host "`nDone." -ForegroundColor Green
Read-Host "Press Enter to close"
