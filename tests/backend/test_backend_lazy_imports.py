"""Every function-level import in the backend must resolve.

The backend imports vendor-heavy and engine modules lazily, inside handlers, so
``import main`` (the boot smoke and the deploy preflight) never executes them. A
lazy import that names a moved or deleted module therefore passes every boot
check and fails only when an operator clicks the route: the 2026-09 domain
refactor left five such imports in POST /archive/add-setup and one in the
calibration chart path. This walks the source, collects every local import
that is NOT at module level, and imports each target for real in a clean child
with the service's sys.path (backend first, then the repo root).
"""
import ast
import json
import subprocess
import sys

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"

# Top-level names that resolve inside this repo (backend first, then the root).
# A lazy import of anything else is a vendor library and is not this guard's job.
_LOCAL_TOPS = {
    "app", "domains", "services", "middleware", "database", "models",
    "archive_models", "broker_config", "frame_store", "marks_validity",
    "schemas", "ibkr", "routers", "main",
    "core", "engine_alpha", "config", "tools", "output",
}


def _lazy_imports():
    """(file, line, module, names) for every local import below module level."""
    found = []
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        top_level = {id(node) for node in tree.body}
        package = ".".join(path.relative_to(BACKEND_DIR).with_suffix("").parts[:-1])
        for node in ast.walk(tree):
            if id(node) in top_level:
                continue
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in _LOCAL_TOPS:
                        found.append((str(path.relative_to(ROOT)), node.lineno, alias.name, []))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package.split(".")[: len(package.split(".")) - node.level + 1]
                    module = ".".join(base + ([node.module] if node.module else []))
                elif node.module and node.module.split(".")[0] in _LOCAL_TOPS:
                    module = node.module
                else:
                    continue
                names = [a.name for a in node.names if a.name != "*"]
                found.append((str(path.relative_to(ROOT)), node.lineno, module, names))
    return found


_CHILD = r"""
import importlib, json, sys
failures = []
for where, line, module, names in json.loads(sys.stdin.read()):
    try:
        mod = importlib.import_module(module)
        for name in names:
            if not hasattr(mod, name):
                importlib.import_module(module + "." + name)
    except Exception as exc:
        failures.append(f"{where}:{line}: {module} {names}: {type(exc).__name__}: {exc}")
print(json.dumps(failures))
"""


def test_the_scan_found_the_lazy_imports():
    # A walk that finds nothing guards nothing.
    assert len(_lazy_imports()) >= 50


def test_every_lazy_backend_import_resolves():
    imports = _lazy_imports()
    proc = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path[:0] = [{str(BACKEND_DIR)!r}, {str(ROOT)!r}]\n" + _CHILD],
        input=json.dumps(imports), cwd=str(BACKEND_DIR),
        capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stderr
    failures = json.loads(proc.stdout.strip().splitlines()[-1])
    assert not failures, "lazy backend imports that no longer resolve:\n" + "\n".join(failures)
