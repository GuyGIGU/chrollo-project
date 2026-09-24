"""Production code never imports tools/.

tools/ holds command-line instruments over production code, so imports run
from tools to production, never back (docs/architecture.md section 2). The
calibration chips once imported tools.calibration.* inside their functions; that
code now lives in core/calibration/ and domains/calibration/grading.py. A lazy
import hides from every boot check, so this walks every import at any depth.
engine_alpha has its own, stricter leaf test in test_engine_alpha_runtime.py.
"""
import ast

from _paths import REPO_ROOT

_PRODUCTION = ("core", "config", "webapp/backend")
_ENTRY_POINTS = ("run_screener.py",)


def _production_files():
    for folder in _PRODUCTION:
        yield from (p for p in sorted((REPO_ROOT / folder).rglob("*.py"))
                    if "__pycache__" not in p.parts)
    for name in _ENTRY_POINTS:
        yield REPO_ROOT / name


def _tools_imports(path):
    """(line, module) for every absolute import of tools or a tools submodule."""
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            if module == "tools" or module.startswith("tools."):
                yield node.lineno, module


def test_production_code_never_imports_tools():
    files = list(_production_files())
    assert len(files) >= 150, f"scan went vacuous ({len(files)} files)"
    offences = [f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: {module}"
                for path in files for line, module in _tools_imports(path)]
    assert not offences, "production code imports tools/:\n" + "\n".join(offences)
