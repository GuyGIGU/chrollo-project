# Chrollo nightly backup - snapshots the irreplaceable local data.
#
# Canonical copy: tools\ChrolloBackup.ps1 in the repo (this file).
# Deployed copy:  %USERPROFILE%\ChrolloBackup.ps1 - what Task Scheduler runs.
# Edit the repo copy, then redeploy (docs\deploy.md section 4). Self-contained on
# purpose - no repo imports - so the deployed copy works regardless of branch state.
#
# Every run appends to %USERPROFILE%\ChrolloBackups\backup.log. Any failure removes
# a partial snapshot, logs FAILED, and exits 1 (visible as the task's Last Run
# Result). It must never fail silently.
param(
    [string]$Repo   = "C:\Users\User\Documents\Projects\Chrollo Project",
    [string]$Root   = (Join-Path $env:USERPROFILE "ChrolloBackups"),
    # Off-disk mirror for each snapshot. Set to OneDrive: this box has a single
    # physical disk, so a locally-synced cloud folder is what gives off-machine
    # durability (the sync client uploads each snapshot). S4U scheduled tasks
    # cannot reach network drives, so a synced LOCAL folder like this - not a UNC
    # path - is the right choice. To disable, set to "". To use a second physical
    # disk instead, point it there (e.g. "D:\ChrolloBackups"). Mirrored database
    # copies are hash-verified.
    [string]$Mirror = $(if ($env:OneDrive) { Join-Path $env:OneDrive "ChrolloBackups" } else { "" })
)

$ErrorActionPreference = "Stop"

# The DB snapshot runs a tiny stdlib-only Python (sqlite3). Resolve the SERVICE's
# own interpreter from nssm instead of a bare `python`: a bare name resolves against
# the scheduled task's machine PATH, which now front-loads a second, dependency-less
# Python 3.14 (added for the CI runner). sqlite3 (stdlib) happens to work under any
# CPython, but pinning to the service interpreter keeps this robust if the PATH order
# ever shifts or an install is removed. Falls back to a bare `python` only if nssm
# cannot answer (the snapshot needs nothing beyond the standard library).
function Resolve-ServicePython {
    try {
        $app = & nssm get ChrolloDashboard Application |
            Where-Object { $_ -and $_.Trim() } | Select-Object -First 1
        if ($app) {
            $app = ($app -replace "`0", '').Trim()
            if (Test-Path -LiteralPath $app) { return $app }
        }
    } catch { }
    return 'python'
}
$SnapshotPython = Resolve-ServicePython

$stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
$dest  = Join-Path $Root $stamp
$log   = Join-Path $Root "backup.log"
$dbSnapshotDone = $false

function Write-Log([string]$msg) {
    $line = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $msg
    Add-Content -Path $log -Value $line
    Write-Output $line
}

# SQLite snapshot helper (Python stdlib only). VACUUM INTO takes a consistent
# point-in-time copy even while the dashboard service holds the database open in
# WAL mode - a plain Copy-Item of a live db/-wal/-shm set is not guaranteed
# restorable. The copy is then opened and integrity-checked before it counts.
$dbSnapshotPy = @'
import os, sqlite3, sys

KEY_TABLES = ("setup_archive", "trade_logs", "executions")

def fail(msg):
    print("SNAPSHOT FAILED: " + msg)
    sys.exit(1)

def ro_uri(path):
    return "file:" + os.path.abspath(path).replace("\\", "/") + "?mode=ro"

try:
    src, dest = sys.argv[1], sys.argv[2]
    if not os.path.exists(src):
        fail("source database not found: " + src)
    if os.path.exists(dest):
        fail("destination already exists: " + dest)

    conn = sqlite3.connect(ro_uri(src), uri=True)
    try:
        conn.execute("VACUUM INTO ?", (dest,))
    finally:
        conn.close()

    check = sqlite3.connect(ro_uri(dest), uri=True)
    try:
        verdict = check.execute("PRAGMA integrity_check").fetchone()[0]
        if verdict != "ok":
            fail("integrity_check on the copy returned: " + verdict)
        counts = []
        for table in KEY_TABLES:
            n = check.execute("SELECT count(*) FROM " + table).fetchone()[0]
            counts.append("%s=%d" % (table, n))
    finally:
        check.close()

    size_mb = os.path.getsize(dest) / 1e6
    print("snapshot ok (%.1f MB, integrity ok, %s)" % (size_mb, ", ".join(counts)))
except SystemExit:
    raise
except Exception as exc:
    fail("unexpected error: %r" % (exc,))
'@

try {
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    # 1) The database: journal, executions, watchlist, and the matured setup
    #    archive - the data that cannot be re-downloaded.
    $pyFile = Join-Path $env:TEMP "chrollo_db_snapshot.py"
    Set-Content -Path $pyFile -Value $dbSnapshotPy -Encoding ASCII
    $liveDb = Join-Path $Repo "webapp\backend\trading_journal.db"
    $pyOut = & $SnapshotPython $pyFile $liveDb (Join-Path $dest "trading_journal.db")
    foreach ($line in @($pyOut)) { Write-Log "  db_snapshot: $line" }
    if ($LASTEXITCODE -ne 0) { throw "SQLite snapshot failed (see db_snapshot lines above)" }
    $dbSnapshotDone = $true

    # 2) Journal chart attachments (uploads\<trade_id>\...). The directory only
    #    appears once the first attachment is saved.
    $uploads = Join-Path $Repo "webapp\backend\uploads"
    if (Test-Path $uploads) {
        Copy-Item $uploads (Join-Path $dest "uploads") -Recurse
    } else {
        Write-Log "  note: no uploads directory yet, skipped"
    }

    # 3) Small state files, all universes. The market_data_cache_5y*.parquet price
    #    caches are deliberately NOT backed up: they are re-downloadable (deleting
    #    one triggers a clean cold rebuild) and would bloat every snapshot.
    $stateFiles = @(Get-ChildItem -Path $Repo -File |
        Where-Object { $_.Name -like "cache_meta*.json" -or $_.Name -like "market_context*.json" })
    $stateFiles | Copy-Item -Destination $dest
    Write-Log ("  state files: {0} copied" -f $stateFiles.Count)

    $sizeMb = ((Get-ChildItem $dest -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB
    Write-Log ("OK  snapshot {0} written ({1:N1} MB)" -f $stamp, $sizeMb)

    # Retention: keep the 14 most recent snapshots.
    Get-ChildItem -Path $Root -Directory |
        Sort-Object Name -Descending |
        Select-Object -Skip 14 |
        Remove-Item -Recurse -Force

    # 4) Off-disk mirror leg.
    if ($Mirror) {
        New-Item -ItemType Directory -Force -Path $Mirror | Out-Null
        Copy-Item $dest (Join-Path $Mirror $stamp) -Recurse -Force
        $srcHash = (Get-FileHash (Join-Path $dest "trading_journal.db") -Algorithm SHA256).Hash
        $mirHash = (Get-FileHash (Join-Path $Mirror "$stamp\trading_journal.db") -Algorithm SHA256).Hash
        if ($srcHash -ne $mirHash) { throw "mirror copy hash mismatch for trading_journal.db" }
        Get-ChildItem -Path $Mirror -Directory |
            Sort-Object Name -Descending |
            Select-Object -Skip 14 |
            Remove-Item -Recurse -Force
        Write-Log ("OK  mirrored {0} to {1}" -f $stamp, $Mirror)
    } else {
        Write-Log "WARN mirror not configured - all snapshots are on the same disk as the originals (set `$Mirror in this script)"
    }
} catch {
    # Only discard the snapshot dir if the database snapshot itself never
    # completed; a verified db copy is worth keeping even if a later step failed.
    if (-not $dbSnapshotDone -and (Test-Path $dest)) {
        Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Log ("FAILED {0}: {1}" -f $stamp, $_.Exception.Message)
    exit 1
}
