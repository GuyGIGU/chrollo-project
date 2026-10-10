# deploy_guard.ps1 - is this checkout fit to deploy? (go-live plan task 10)
#
# update_dashboard.ps1 runs this FIRST, before it asks for administrator rights.
# The deploy restarts the service on whatever the checkout holds, so a deploy
# from a side branch, or from a tree with edits nobody committed, would put code
# live that no release ever named. This refuses both:
#   - HEAD must be the release branch (update_dashboard.ps1's -ReleaseBranch,
#     default "main"); a detached HEAD is refused too;
#   - no TRACKED file may differ from the commit (untracked files, such as the
#     output\ folder's runtime files, do not count).
# -AllowAnyCheckout lets the deploy go ahead anyway, saying what it overrides.
#
# Read-only: it runs `git rev-parse` and `git status`, nothing else.
# Exit 0 = fit to deploy (or overridden), 1 = refused, 2 = git could not answer.
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$ReleaseBranch = 'main',
    [switch]$AllowAnyCheckout
)

# 'Continue', not 'Stop': under Windows PowerShell 5.1 a native command's stderr
# line becomes an error record, and 'Stop' would turn git's own message into a
# crash instead of the plain refusal below.
$ErrorActionPreference = 'Continue'

# The same rule as update_dashboard.ps1's Resolve-Tool: this may run elevated, so
# a git that resolves inside the operator-writable repo is not trusted.
$gitCmd = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $gitCmd) {
    Write-Host "Deploy guard: git not found on PATH, so the checkout cannot be checked. Nothing was changed." -ForegroundColor Red
    exit 2
}
$git = $gitCmd.Source
if ($git.ToLowerInvariant().StartsWith((Resolve-Path $Repo).Path.ToLowerInvariant())) {
    Write-Host "Deploy guard: refusing git resolved to '$git' - inside the repo is untrusted. Nothing was changed." -ForegroundColor Red
    exit 2
}

$branch = (& $git -C $Repo rev-parse --abbrev-ref HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $branch) {
    Write-Host "Deploy guard: '$Repo' is not a git checkout git can read. Nothing was changed." -ForegroundColor Red
    exit 2
}
$branch = "$branch".Trim()
$dirty = @(& $git -C $Repo status --porcelain --untracked-files=no 2>$null | Where-Object { $_ })
if ($LASTEXITCODE -ne 0) {
    Write-Host "Deploy guard: git status failed in '$Repo'. Nothing was changed." -ForegroundColor Red
    exit 2
}

$problems = @()
if ($branch -eq 'HEAD') {
    $problems += "The checkout is on no branch (a detached HEAD), not on the release branch '$ReleaseBranch'."
} elseif ($branch -ne $ReleaseBranch) {
    $problems += "The checkout is on branch '$branch', not on the release branch '$ReleaseBranch'."
}
if ($dirty.Count -gt 0) {
    $problems += "$($dirty.Count) tracked file(s) have changes nobody committed:"
    $problems += ($dirty | Select-Object -First 10 | ForEach-Object { "    $_" })
    if ($dirty.Count -gt 10) { $problems += "    ... and $($dirty.Count - 10) more" }
}

if ($problems.Count -eq 0) {
    Write-Host "Deploy guard: on the release branch '$ReleaseBranch', no uncommitted tracked files." -ForegroundColor Green
    exit 0
}

if ($AllowAnyCheckout) {
    Write-Host "Deploy guard OVERRIDDEN (-AllowAnyCheckout). Deploying anyway, although:" -ForegroundColor Yellow
    $problems | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    exit 0
}

Write-Host "REFUSING TO DEPLOY. Nothing was changed." -ForegroundColor Red
$problems | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
Write-Host "Merge into '$ReleaseBranch' and switch to it (git switch $ReleaseBranch), commit or discard the changes, then run this again."
Write-Host "To deploy this checkout anyway: update_dashboard.bat -AllowAnyCheckout"
exit 1
