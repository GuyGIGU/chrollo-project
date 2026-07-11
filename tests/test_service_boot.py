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
    an import-time crash or a router that failed to include drops the count.

    The leaf count is walked recursively: FastAPI >=0.139 / Starlette >=1.3 no
    longer flattens included routers into ``app.routes`` — each ``include_router``
    leaves one ``_IncludedRouter`` wrapper (``.original_router`` holds the real
    routes), and a mount holds its own ``.routes``. Counting only top-level
    entries would read ~22 there and spuriously fail even though every endpoint
    is registered, so the guard tests reachable endpoints, not a version-fragile
    internal representation."""
    code = (
        "import main\n"
        "from starlette.routing import Mount\n"
        "def leaves(routes):\n"
        "    out = []\n"
        "    for r in routes:\n"
        "        orig = getattr(r, 'original_router', None)\n"
        "        sub = orig.routes if orig is not None else (r.routes if isinstance(r, Mount) else None)\n"
        "        out += leaves(sub) if sub else [getattr(r, 'path', '')]\n"
        "    return out\n"
        "paths = leaves(main.app.routes)\n"
        "assert len(paths) > 70, f'only {len(paths)} routes registered'\n"
        # Named-path pins: the coarse count has enough slack to absorb a
        # whole dropped include_router (the SPA catch-all then answers the
        # paths with index.html — the proven service_stale incident).
        "for must in ('/calibration/chart', '/calibration/marks'):\n"
        "    assert must in paths, f'{must} not registered'\n"
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
