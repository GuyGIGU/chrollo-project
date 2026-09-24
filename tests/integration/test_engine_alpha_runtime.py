"""Engine Alpha extraction lockdown (plan tasks 6-7).

The seams the in-process suite cannot see, pinned as machine checks:
Windows spawn re-imports the eval callable + skip sentinel by qualified
name in child processes; tools must resolve the engine from a decoy cwd
(the backend-cwd config-shadow trap); FastAPI boot must stay engine-free;
the engine package must stay a leaf (import allowlist, one documented
outward seam); and no consumer may still name the old core.* engine paths
(a lazy import with a stale spelling passes every compile-time gate and
detonates weeks later on the scheduled path).
"""
import ast
import pickle
import subprocess
import sys
from pathlib import Path

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

PY = sys.executable


def _run(code: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-c", code], cwd=str(cwd),
                          capture_output=True, text=True, timeout=180)


def test_eval_callable_and_sentinel_pickle_by_their_new_names():
    from engine_alpha.evaluation import EVAL_ERROR, _evaluate_ticker
    assert pickle.loads(pickle.dumps(_evaluate_ticker)) is _evaluate_ticker
    assert pickle.loads(pickle.dumps(EVAL_ERROR)) is EVAL_ERROR
    assert _evaluate_ticker.__module__ == "engine_alpha.evaluation"


def test_spawned_child_resolves_the_pickled_worker(tmp_path):
    # A genuinely fresh interpreter (what ProcessPoolExecutor spawn does on
    # win32): unpickle the worker + sentinel bytes and confirm they resolve
    # to the SAME objects the child imports by name — `result is EVAL_ERROR`
    # in the pool parent depends on exactly this identity.
    from engine_alpha.evaluation import EVAL_ERROR, _evaluate_ticker
    blob = tmp_path / "worker.pkl"
    blob.write_bytes(pickle.dumps((_evaluate_ticker, EVAL_ERROR)))
    code = (
        "import pickle, sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        f"fn, err = pickle.loads(open({str(blob)!r}, 'rb').read())\n"
        "import engine_alpha.evaluation as ev\n"
        "assert fn is ev._evaluate_ticker, 'worker resolved to a different object'\n"
        "assert err is ev.EVAL_ERROR, 'sentinel resolved to a different object'\n"
    )
    proc = _run(code, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr


def test_engine_imports_from_the_backend_decoy_cwd():
    # The backend runs with cwd=webapp/backend, where a bare `config` name can
    # shadow the repo-root package (the historical collision). The engine +
    # the REAL settings must still resolve through the shared bootstrap.
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import engine_alpha.evaluation\n"
        "from config import settings\n"
        "assert hasattr(settings, 'MIN_PRICE'), 'wrong config module resolved'\n"
    )
    proc = _run(code, cwd=ROOT / "webapp" / "backend")
    assert proc.returncode == 0, proc.stderr


def test_fastapi_boot_stays_engine_free():
    # Importing main does NOT run the lifespan (sanctioned check — the boot
    # chain itself must never pull the reading engine); after import, no
    # engine_alpha module may be loaded.
    code = (
        "import sys\n"
        f"sys.path.append({str(ROOT)!r})\n"
        "import main\n"
        "loaded = [m for m in sys.modules if m.startswith('engine_alpha')]\n"
        "assert not loaded, f'engine modules on the boot path: {loaded}'\n"
    )
    proc = _run(code, cwd=ROOT / "webapp" / "backend")
    assert proc.returncode == 0, proc.stderr


# ── the leaf-purity invariant (Hunt): engine_alpha imports nothing from the
# app, the plumbing, or any network/broker/ORM library ──────────────────────

_FORBIDDEN_PREFIXES = (
    "webapp", "tools", "ib_async", "sqlalchemy", "yfinance", "requests",
    "httpx", "apscheduler", "fastapi", "uvicorn",
)
# The ONE documented flag-gated outward seam (plan task 4 ruling): the eval
# chain may lazily consult the advisory layer; nothing else in core.
_ALLOWED_CORE = {"core.fundamentals.advisory"}


def _imported_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_engine_alpha_is_a_leaf_package():
    files = sorted((ROOT / "engine_alpha").rglob("*.py"))
    assert len(files) >= 25, "glob went vacuous — the engine package is missing files"
    offences = []
    for f in files:
        for name in _imported_names(f):
            if name.startswith(_FORBIDDEN_PREFIXES):
                offences.append(f"{f.name}: {name}")
            if (name == "core" or name.startswith("core.")) \
                    and name not in _ALLOWED_CORE:
                offences.append(f"{f.name}: {name}")
    assert not offences, "engine_alpha must stay a leaf; offending imports:\n" \
        + "\n".join(offences)


def test_engine_alpha_never_touches_sys_path():
    # Libraries never own the path; entry points do (tools/_bootstrap).
    offences = []
    for f in sorted((ROOT / "engine_alpha").rglob("*.py")):
        src = f.read_text(encoding="utf-8")
        if "sys.path" in src:
            offences.append(f.name)
    assert not offences, f"sys.path manipulation inside the engine: {offences}"


def test_no_consumer_still_names_the_old_engine_paths():
    # Text-level guard (Ramírez): lazy imports are invisible to compile-time
    # gates, so a stale old-package spelling of any moved engine module
    # anywhere in the repo's Python is a latent 3 AM failure on the scheduled
    # path. Zero occurrences allowed.
    # Built by concatenation so this guard's own source never matches itself.
    stale = tuple("core." + tail for tail in (
        "structure", "scoring", "freeze", "pipeline.evaluation",
        "pipeline.stability", "pipeline.election_identity"))
    skip_parts = {".git", ".claude", "__pycache__", "node_modules",
                  "context-handling", ".council"}
    offences = []
    n_scanned = 0
    for f in ROOT.rglob("*.py"):
        # Repo-relative parts only: an absolute-path filter goes vacuous when
        # the checkout itself lives under .claude/worktrees/<name>/.
        if any(part in skip_parts for part in f.relative_to(ROOT).parts):
            continue
        n_scanned += 1
        src = f.read_text(encoding="utf-8", errors="replace")
        for needle in stale:
            if needle in src:
                offences.append(f"{f.relative_to(ROOT)}: {needle}")
    assert n_scanned >= 150, "scan went vacuous"
    assert not offences, "stale engine paths survive:\n" + "\n".join(offences)
