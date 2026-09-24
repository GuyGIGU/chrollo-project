"""Service-boot smoke guards.

The NSSM service runs uvicorn with cwd=webapp/backend, which puts the backend
directory FIRST on sys.path — a backend-local module can silently shadow a
repo-root package there. That produced the proven "tests green from the repo
root, service boot dead" incident class (a backend config.py shadowing the root
config package crashed every core/ import at boot). These tests exercise the
service's actual import path so that class fails the build instead of the boot.

Importing main does NOT run the FastAPI lifespan (no scheduler, no broker
touch) — safe by house rules. It DOES run initialize_database() at import
scope, which is why tests/conftest.py points CHROLLO_DB_PATH at a throwaway
file for the whole session; the child below inherits it, so this boot never
migrates the operator's live archive (tests/integration/test_db_isolation.py guards that).
"""
import subprocess
import sys

from _paths import REPO_ROOT as ROOT
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
        # Importing main does not run the lifespan, whose first act is the
        # scheduler reading the root settings through this loader. A loader that
        # only breaks at lifespan passes the import and then kills the restarted
        # service, so exercise it here too.
        "from app.core_settings import load_core_settings\n"
        "assert load_core_settings().SCAN_SCHEDULE_HOUR_ET is not None\n"
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


def test_boot_installs_the_default_origin_guard_over_every_registered_route():
    """The default-on half of the same-app posture rule is only worth anything
    if it is actually mounted and has no per-route escape hatch (council
    2026-09-07, finding 3: the opt-in header guard reached 15 of 85 routes).

    So: assert the middleware is in the real app's stack, then walk every
    registered mutating route and drive the guard at that exact path with what
    a hostile page sends. The guard is driven around a STUB app — a route's own
    handler is never invoked, so a broken guard fails this test instead of
    starting a 17-minute scan. A route added tomorrow is walked by this test
    the day it is added, and an exemption list would fail it here."""
    code = (
        "import asyncio\n"
        "import main\n"
        "from starlette.routing import Mount\n"
        "from middleware.same_app import SameAppOriginGuard\n"
        "installed = [m.cls for m in main.app.user_middleware]\n"
        "assert SameAppOriginGuard in installed, "
        "f'guard not mounted; stack={installed}'\n"
        "def leaves(routes):\n"
        "    out = []\n"
        "    for r in routes:\n"
        "        orig = getattr(r, 'original_router', None)\n"
        "        sub = orig.routes if orig is not None else (r.routes if isinstance(r, Mount) else None)\n"
        "        out += leaves(sub) if sub else [(getattr(r, 'path', ''), getattr(r, 'methods', None) or set())]\n"
        "    return out\n"
        "async def inner(scope, receive, send):\n"
        "    raise AssertionError('handler reached: ' + scope['path'])\n"
        "def refused(path, method, extra):\n"
        "    seen = {}\n"
        "    async def send(message):\n"
        "        if message['type'] == 'http.response.start':\n"
        "            seen['status'] = message['status']\n"
        "    scope = {'type': 'http', 'method': method, 'path': path, 'scheme': 'http',\n"
        "             'headers': [(b'host', b'localhost:8000'),\n"
        "                         (b'sec-fetch-site', b'cross-site')] + extra}\n"
        "    asyncio.run(SameAppOriginGuard(inner)(scope, None, send))\n"
        "    return seen.get('status')\n"
        # Both shapes a hostile page takes: a fetch/form POST, which carries an
        # Origin, and an EventSource/<img> GET, which carries none. Only the
        # Sec-Fetch-Site leg catches the second, and that is the leg the SSE
        # scan streams depend on entirely.
        "shapes = {'with Origin': [(b'origin', b'https://evil.example')],\n"
        "          'no Origin': []}\n"
        "mutating = [(p, sorted(m & {'POST', 'PUT', 'PATCH', 'DELETE'})[0])\n"
        "            for p, m in leaves(main.app.routes)\n"
        "            if m & {'POST', 'PUT', 'PATCH', 'DELETE'}]\n"
        "assert len(mutating) > 20, f'only {len(mutating)} mutating routes walked'\n"
        "streams = [p for p, m in leaves(main.app.routes)\n"
        "           if 'GET' in m and ('stream' in p or 'download-data' in p)]\n"
        "assert len(streams) >= 4, f'only {len(streams)} streaming GETs walked: {streams}'\n"
        "for path, method in mutating + [(p, 'GET') for p in streams]:\n"
        "    for label, extra in shapes.items():\n"
        "        status = refused(path, method, extra)\n"
        "        assert status == 403, (\n"
        "            f'{method} {path} answered {status} to a cross-site page ({label})')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, (
        f"origin-guard boot pin failed (exit {proc.returncode}):\n"
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
