"""Service-boot smoke guards.

The NSSM service runs uvicorn with cwd=webapp/backend, which puts the backend
directory FIRST on sys.path — a backend-local module can silently shadow a
repo-root package there. That produced the proven "tests green from the repo
root, service boot dead" incident class (a backend config.py shadowing the root
config package crashed every core/ import at boot). These tests exercise the
service's actual import path so that class fails the build instead of the boot.

Importing main does NOT run the FastAPI lifespan (no scheduler, no broker
touch) — safe by house rules.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"


def test_backend_boots_from_service_cwd_and_registers_routes():
    """Import main exactly the way the service does (cwd=webapp/backend) in a
    clean subprocess and assert the app actually registered its route tree —
    an import-time crash or a router that failed to include drops the count."""
    code = (
        "import main; n = len(main.app.routes); "
        "assert n > 70, f'only {n} routes registered'"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"backend boot-import failed (exit {proc.returncode}):\n"
        f"{proc.stdout}\n{proc.stderr}"
    )


def test_backend_does_not_shadow_root_config():
    """webapp/backend must never grow a config.py (or config/ package): with
    the service's cwd it would shadow the repo-root config package and crash
    the boot while root-cwd tests stay green."""
    assert not (BACKEND_DIR / "config.py").exists(), (
        "webapp/backend/config.py shadows the repo-root config package under "
        "the service's cwd — rename it (see broker_config.py precedent)"
    )
    assert not (BACKEND_DIR / "config").exists(), (
        "webapp/backend/config/ shadows the repo-root config package under "
        "the service's cwd — rename it"
    )
