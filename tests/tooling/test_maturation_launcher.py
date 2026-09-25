"""The scheduled maturation tick keeps the entry point its task runs.

Windows Task Scheduler's "Chrollo Forward Returns" task runs the forwarder at
the root of tools/ by its absolute path (it ran through it on 2026-09-24, exit
0). The task is not being re-registered, so that forwarder is its permanent
entry point: moving, renaming or deleting it would stop the backend-independent
maturation tick with nothing in the app to say so until the watchdog saw no
maturation row. The implementation lives in tools/ops/ (docs/deploy.md,
"Schedule Forward-Return Maturation"); the forwarder only calls it and passes
back its exit code.
"""
from _paths import REPO_ROOT

_ENTRY_POINT = REPO_ROOT / "tools" / "run_maturation.bat"
_IMPLEMENTATION = REPO_ROOT / "tools" / "ops" / "run_maturation.bat"


def _commands(path):
    """The script's non-comment lines, stripped (REM, blank and @echo off dropped)."""
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines
            if line and not line.upper().startswith(("REM", "@ECHO OFF"))]


def test_the_entry_point_only_forwards_to_the_ops_script():
    assert _ENTRY_POINT.is_file(), "the scheduled task's entry point is gone"
    assert _commands(_ENTRY_POINT) == [
        'call "%~dp0ops\\run_maturation.bat"',
        "exit /b %ERRORLEVEL%",
    ]


def test_the_ops_script_runs_the_maturation_updater():
    assert _IMPLEMENTATION.is_file()
    assert any("-m core.archive.forward_returns" in line
               for line in _commands(_IMPLEMENTATION))
