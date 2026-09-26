"""The agreement harness as a command, run in a fresh interpreter.

``tests/tooling/test_calibration_harness.py`` drives the harness in-process, where
pytest has already put the repo root and the backend on ``sys.path``. The command
has to find both on its own, in both documented spellings (``python -m`` and a
direct script run), and keep its exit codes: 0 for a report or an empty ledger,
2 for a refused run. These pins run it the way the operator does.
"""
import os
import re
import subprocess
import sys

from sqlalchemy import create_engine

from _paths import BACKEND_DIR, REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402

HARNESS = "tools.calibration.calibration_harness"


def _run(args, tmp_path, cwd=REPO_ROOT):
    """The harness in a child with its own throwaway ledger and no PYTHONPATH."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["CHROLLO_DB_PATH"] = str(tmp_path / "ledger.db")
    return subprocess.run([sys.executable, "-B", *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=180)


def test_help_names_every_flag(tmp_path):
    proc = _run(["-m", HARNESS, "--help"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    for flag in ("--ticker", "--variant", "--json", "--fired", "--prev"):
        assert re.search(rf"(?<![\w-]){flag}(?![\w-])", proc.stdout), flag


def test_an_empty_ledger_reports_and_exits_zero(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    models.Base.metadata.create_all(bind=engine)
    engine.dispose()
    proc = _run(["-m", HARNESS], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "no calibration marks saved yet" in proc.stdout


def test_a_sealed_report_path_is_refused_with_exit_two(tmp_path):
    target = REPO_ROOT / "docs" / "marks" / "harness_cli_refusal_probe.json"
    proc = _run(["-m", HARNESS, "--json", str(target)], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "refusing to write under the sealed directory" in proc.stdout
    assert not target.exists()


def test_it_runs_as_a_direct_script_from_anywhere(tmp_path):
    script = REPO_ROOT / "tools" / "calibration" / "calibration_harness.py"
    proc = _run([str(script), "--help"], tmp_path, cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "--fired" in proc.stdout
