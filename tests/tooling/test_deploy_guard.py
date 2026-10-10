"""The deploy refuses a checkout that is not the release (go-live plan task 10).

update_dashboard.ps1 restarts the service on whatever the main checkout holds.
Before the guard it deployed any branch, and any uncommitted edit, without a
word. The guard (tools/ops/deploy_guard.ps1) runs first, before the script asks
for administrator rights.

A DRY RUN: the guard alone, on a throwaway git repo. update_dashboard itself is
never run here (it elevates and restarts the service); its wiring is read as
text.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest

from _paths import REPO_ROOT

GUARD = REPO_ROOT / "tools" / "ops" / "deploy_guard.ps1"
DEPLOY = REPO_ROOT / "update_dashboard.ps1"
SHELL = shutil.which("powershell") or shutil.which("pwsh")
GIT = shutil.which("git")

needs_shell = pytest.mark.skipif(not (SHELL and GIT), reason="needs PowerShell and git")


def _git(repo, *args):
    subprocess.run([GIT, "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    """A release checkout: on main, one committed file, nothing changed."""
    path = tmp_path / "checkout"
    path.mkdir()
    subprocess.run([GIT, "init", "-q", "-b", "main", str(path)], check=True)
    (path / "app.py").write_text("x = 1\n", encoding="utf-8")
    _git(path, "add", "app.py")
    _git(path, "commit", "-q", "-m", "release")
    return path


def _guard(repo, *extra):
    cmd = [SHELL, "-NoProfile"]
    if os.name == "nt":
        cmd += ["-ExecutionPolicy", "Bypass"]
    cmd += ["-File", str(GUARD), "-Repo", str(repo), *extra]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return done.returncode, done.stdout + done.stderr


@needs_shell
def test_the_release_branch_with_nothing_uncommitted_deploys(repo):
    code, out = _guard(repo)
    assert code == 0, out
    assert "release branch 'main'" in out


@needs_shell
def test_another_branch_is_refused_and_named(repo):
    _git(repo, "switch", "-q", "-c", "claude/leadership-read")
    code, out = _guard(repo)
    assert code == 1, out
    assert "REFUSING TO DEPLOY" in out
    assert "'claude/leadership-read', not on the release branch 'main'" in out


@needs_shell
def test_a_detached_head_is_refused(repo):
    _git(repo, "switch", "-q", "--detach")
    code, out = _guard(repo)
    assert code == 1, out
    assert "detached HEAD" in out


@needs_shell
def test_an_uncommitted_tracked_file_is_refused_and_named(repo):
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    code, out = _guard(repo)
    assert code == 1, out
    assert "app.py" in out


@needs_shell
def test_an_untracked_file_does_not_block(repo):
    """The service writes runtime files (output/); they are not code."""
    (repo / "runtime.json").write_text("{}", encoding="utf-8")
    code, out = _guard(repo)
    assert code == 0, out


@needs_shell
def test_the_release_branch_is_a_choice(repo):
    _git(repo, "switch", "-q", "-c", "release")
    assert _guard(repo)[0] == 1
    code, out = _guard(repo, "-ReleaseBranch", "release")
    assert code == 0, out


@needs_shell
def test_the_override_deploys_and_says_what_it_overrides(repo):
    _git(repo, "switch", "-q", "-c", "side")
    code, out = _guard(repo, "-AllowAnyCheckout")
    assert code == 0, out
    assert "OVERRIDDEN" in out and "'side'" in out


# --------------------------------------------------------------------------- #
# The wiring in update_dashboard.ps1, read as text (never run)                #
# --------------------------------------------------------------------------- #
def _deploy_text() -> str:
    return DEPLOY.read_text(encoding="utf-8")


@needs_shell
def test_update_dashboard_still_parses():
    """Read by PowerShell's own parser, never run: a syntax slip in the guard's
    wiring would otherwise surface only when he double-clicks the deploy."""
    script = ("$e = $null; $t = $null; "
              "[void][System.Management.Automation.Language.Parser]::ParseFile("
              f"'{DEPLOY}', [ref]$t, [ref]$e); "
              "$e | ForEach-Object { $_.Message }; exit $e.Count")
    done = subprocess.run([SHELL, "-NoProfile", "-Command", script],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_release_branch_is_named_once_and_defaults_to_main():
    text = _deploy_text()
    assert re.search(r"\[string\]\$ReleaseBranch\s*=\s*'main'", text)
    assert "[switch]$AllowAnyCheckout" in text


def test_the_guard_runs_before_the_script_asks_for_administrator_rights():
    text = _deploy_text()
    guard_at = text.find("deploy_guard.ps1")
    elevate_at = text.find("-Verb RunAs")
    assert guard_at != -1 and elevate_at != -1
    assert guard_at < elevate_at, "the guard must refuse before the UAC prompt"


def test_the_elevated_child_keeps_the_release_branch_and_the_override():
    """The elevated child runs the script again; a dropped argument would
    re-arm the guard against a branch the operator named."""
    text = _deploy_text()
    elevate = text[text.find("if (-not $isAdmin)"):text.find("-Verb RunAs")]
    assert "$ReleaseBranch" in elevate
    assert "-AllowAnyCheckout" in elevate
