# Chrollo service-interpreter recovery + Python de-collision (one-click, elevated).
#
# Why this exists: this box carries TWO Python 3.14 installs that both claim the
# `PythonCore\3.14` registry tag (a per-user PyManager "pythoncore" and an all-users
# Program Files install added for CI). A PyManager runtime reset once wiped the
# pythoncore interpreter the service booted with, and the service could not restart.
# The durable fix is to run the service off a DEDICATED VENV that depends on neither
# registry tag. This script points the service at that venv, verifies it, and
# (optionally) removes the registry value that lets a broken interpreter hide.
#
# Run it by double-clicking `recover_service_python.bat` (or right-click -> Run as
# administrator). It self-elevates via UAC. It never sets IBKR_LIVE_CONFIRMED and
# never changes the service's broker-free environment.

param(
    [string]$VenvPython  = "C:\Users\User\AppData\Local\ChrolloDashboard\venv\Scripts\python.exe",
    [string]$Service     = "ChrolloDashboard",
    [string]$HealthUrl   = "http://127.0.0.1:8000/health",
    [string]$ProgramFilesPython = "C:\Program Files\Python314\python.exe"
)

$ErrorActionPreference = "Stop"

# --- Self-elevate ----------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()
).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Requesting administrator rights (restarting a service needs elevation)..."
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`""
    )
    exit
}

function Say([string]$m, [string]$color = "Gray") { Write-Host $m -ForegroundColor $color }
function Ok ([string]$m) { Write-Host "  OK   $m" -ForegroundColor Green }
function Warn([string]$m) { Write-Host "  WARN $m" -ForegroundColor Yellow }
function Die ([string]$m) { Write-Host "  STOP $m" -ForegroundColor Red; throw $m }

# nssm output is UTF-16 and can carry stray NULs; normalize before comparing.
function Clean([object]$o) { (@($o) -join "`n") -replace "`0", "" }

try {
    Say "=== Chrollo service-interpreter recovery ===" "Cyan"

    # --- Resolve nssm ------------------------------------------------------
    $nssm = (Get-Command nssm -ErrorAction SilentlyContinue).Source
    if (-not $nssm) {
        $glob = Get-ChildItem "C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\NSSM.NSSM_*\*\win64\nssm.exe" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($glob) { $nssm = $glob.FullName }
    }
    if (-not $nssm) { Die "nssm.exe not found. Open the shell where 'nssm' works and run this from there." }
    Ok "nssm: $nssm"

    # --- Preconditions: the venv must be real and have the deps ------------
    if (-not (Test-Path -LiteralPath $VenvPython)) { Die "venv interpreter missing: $VenvPython" }
    & $VenvPython -c "import fastapi, uvicorn, sqlalchemy, pandas" 2>$null
    if ($LASTEXITCODE -ne 0) { Die "venv interpreter is missing dependencies (fastapi/uvicorn/...). Rebuild it before repointing." }
    Ok "venv interpreter healthy (fastapi/uvicorn/sqlalchemy/pandas import)"

    # --- Service must exist, and MUST stay broker-free --------------------
    $current = Clean (& $nssm get $Service Application) | ForEach-Object { $_.Trim() }
    if ($LASTEXITCODE -ne 0 -or -not $current) { Die "service '$Service' not found (nssm get Application failed)." }
    Say "  current interpreter: $current"

    $envExtra = Clean (& $nssm get $Service AppEnvironmentExtra)
    if ($envExtra -notmatch "IBKR_AUTO_CONNECT\s*=\s*false") {
        Die "refusing to restart: AppEnvironmentExtra does not contain IBKR_AUTO_CONNECT=false. The boot must stay broker-free. Fix the service env first."
    }
    Ok "broker-free boot preserved (IBKR_AUTO_CONNECT=false present)"

    # --- Repoint (idempotent) ---------------------------------------------
    if ($current -ieq $VenvPython) {
        Ok "already pointed at the venv - no change needed"
    } else {
        Say "  repointing $Service -> venv ..." "White"
        & $nssm set $Service Application $VenvPython | Out-Null
        if ($LASTEXITCODE -ne 0) { Die "nssm set Application failed." }
        $now = Clean (& $nssm get $Service Application) | ForEach-Object { $_.Trim() }
        if ($now -ine $VenvPython) { Die "verification failed: Application is '$now', expected the venv." }
        Ok "Application now: $now  (AppParameters/AppDirectory/AppEnvironmentExtra untouched)"
    }

    # --- Restart + health --------------------------------------------------
    Say "  restarting $Service ..." "White"
    & $nssm restart $Service | Out-Null

    $healthy = $false
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 2
        try {
            $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
            $healthy = $true
            Ok ("health responded after ~{0}s: {1}" -f ($i * 2), ($r | ConvertTo-Json -Compress -Depth 3))
            break
        } catch { }
    }
    if (-not $healthy) {
        Warn "no /health response after ~40s. The service is on the venv now, but check the logs:"
        Warn "  Get-Content 'C:\Users\User\Documents\Projects\Chrollo Project\output\chrollo-service-error.log' -Encoding UTF8 -Tail 40"
        Warn "Skipping the registry de-collision until the service is confirmed healthy."
    } else {
        # --- Optional registry de-collision (reversible, guarded) ---------
        Say ""
        Say "The registry value HKLM\SOFTWARE\Python\PythonCore\3.14\PythonPath lets a" "Gray"
        Say "half-broken interpreter borrow Program Files' stdlib instead of failing loudly." "Gray"
        Say "Removing it is safe (the venv + CI both find their stdlib without it) and is" "Gray"
        Say "backed up first, with automatic rollback if anything stops importing." "Gray"
        $ans = Read-Host "Remove the masking registry value now? (y/N)"
        if ($ans -match '^(y|yes)$') {
            $regKey  = "HKLM\SOFTWARE\Python\PythonCore\3.14\PythonPath"
            $regPath = "HKLM:\SOFTWARE\Python\PythonCore\3.14\PythonPath"
            if (-not (Test-Path $regPath)) {
                Ok "already absent - nothing to remove."
            } else {
                $bkDir = Join-Path $env:USERPROFILE "ChrolloBackups\reg"
                New-Item -ItemType Directory -Force -Path $bkDir | Out-Null
                $stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
                $bkFile = Join-Path $bkDir "PythonCore-3.14-PythonPath_$stamp.reg"
                & reg.exe export $regKey $bkFile /y | Out-Null
                if ($LASTEXITCODE -ne 0 -or -not (Test-Path $bkFile)) { Die "registry export failed - NOT removing anything." }
                Ok "backed up to: $bkFile"

                Remove-Item -Path $regPath -Recurse -Force
                Say "  removed. verifying interpreters still resolve their stdlib ..." "White"

                & $ProgramFilesPython -c "import os, sys, ssl, json; print('pf-ok')" 2>$null
                $pfOk = ($LASTEXITCODE -eq 0)
                & $VenvPython -c "import fastapi, ssl, json; print('venv-ok')" 2>$null
                $venvOk = ($LASTEXITCODE -eq 0)

                if ($pfOk -and $venvOk) {
                    Ok "both interpreters still import cleanly - de-collision complete."
                } else {
                    Warn "an interpreter failed to import after removal - ROLLING BACK."
                    & reg.exe import $bkFile | Out-Null
                    Warn "restored the registry value from backup. No harm done; leave it as-is."
                }
            }
        } else {
            Say "  skipped the registry change (repoint + restart still applied)." "Gray"
        }
    }

    Say ""
    Say "=== done ===" "Cyan"
    Say "Next: double-click update_dashboard.bat to rebuild the frontend (restores the" "Gray"
    Say "calibration v2 ledger), then open the Chrollo Dashboard shortcut." "Gray"
}
catch {
    Say ""
    Say "RECOVERY FAILED: $($_.Exception.Message)" "Red"
}
finally {
    Say ""
    Read-Host "Press Enter to close"
}
