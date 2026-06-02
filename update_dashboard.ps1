# update_dashboard.ps1 — rebuild the Chrollo frontend and restart the service.
#
# Double-click update_dashboard.bat (or run this directly) after any code change.
# It self-elevates once via UAC, because restarting a Windows service needs
# administrator rights. This replaces the manual two-step:
#     npm --prefix webapp\frontend run build
#     nssm restart ChrolloDashboard   (from an elevated shell)
#
# SAFETY: this script NEVER sets IBKR_LIVE_CONFIRMED and never changes the
# service's broker-free configuration. It only rebuilds dist/ and bounces the
# service, so the dashboard stays broker-free at boot exactly as before.

$ErrorActionPreference = 'Stop'

# --- self-elevate -------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting administrator rights (needed to restart the service)..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`""
    )
    exit
}

$repo = $PSScriptRoot
Set-Location $repo

# --- 1. build the frontend ----------------------------------------------------
Write-Host "`n[1/3] Building frontend (npm run build)..." -ForegroundColor Cyan
& npm --prefix "$repo\webapp\frontend" run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build FAILED (exit $LASTEXITCODE). Service NOT restarted." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# --- 2. restart the service ---------------------------------------------------
Write-Host "`n[2/3] Restarting ChrolloDashboard service..." -ForegroundColor Cyan
nssm restart ChrolloDashboard

# --- 3. health check ----------------------------------------------------------
Write-Host "`n[3/3] Waiting for the service to answer /health..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 3
        $status = if ($resp.status) { $resp.status } else { 'ok' }
        Write-Host "Service is up. /health => $status" -ForegroundColor Green
        $resp | ConvertTo-Json -Depth 4 | Write-Host
        $ok = $true
        break
    } catch {
        # service still restarting; retry
    }
}
if (-not $ok) {
    Write-Host "Service did not answer /health within 20s. Check output\chrollo-service-error.log" -ForegroundColor Yellow
}

Write-Host "`nDone." -ForegroundColor Green
Read-Host "Press Enter to close"
