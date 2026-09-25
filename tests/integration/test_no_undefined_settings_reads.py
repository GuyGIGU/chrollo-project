"""No live code reads a setting that ``config.settings`` does not define.

A deleted setting leaves its readers behind in files the deleting commit never
touched: ``tools/research/full_package_render.py`` kept reading
``settings.AR_FIRST_REACTION_ENABLED`` after that flag was deleted on
2026-09-08, and nothing noticed until the tool raised AttributeError. This
walks every live Python file (``_LIVE_ROOTS`` + ``_ENTRY_POINTS``; ``docs/`` and
``research/`` hold records, not live code) and fails on any such read.

Only names bound to the ROOT settings namespace are checked: ``from config
import settings [as x]`` and ``import config.settings [as x]``, at any depth in
the file. The backend's ``from broker_config import settings`` is a different
object and is never checked; a name the file ALSO binds from some other import
is skipped rather than guessed. ``from config.settings import X`` is a read of
``X``. ``getattr(settings, "X", default)`` and ``hasattr`` are probes, so they
are allowed; a two-argument ``getattr`` with a literal name is a read.
"""
import ast

from _paths import REPO_ROOT

from config import settings

_LIVE_ROOTS = ("engine_alpha", "core", "config", "webapp/backend", "tools", "tests")
_ENTRY_POINTS = ("run_screener.py",)


def _live_files():
    for folder in _LIVE_ROOTS:
        yield from (p for p in sorted((REPO_ROOT / folder).rglob("*.py"))
                    if "__pycache__" not in p.parts and "node_modules" not in p.parts)
    for name in _ENTRY_POINTS:
        yield REPO_ROOT / name


def _settings_bindings(tree):
    """(names bound to config.settings, [(line, name)] from config.settings imports)."""
    root_names, other_names, direct = set(), set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound = alias.asname or alias.name
                if not node.level and node.module == "config" and alias.name == "settings":
                    root_names.add(bound)
                elif not node.level and node.module == "config.settings":
                    direct.append((node.lineno, alias.name))
                else:
                    other_names.add(bound)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "config.settings":
                    root_names.add(alias.asname or alias.name)
                else:
                    other_names.add(alias.asname or alias.name.split(".")[0])
    return root_names - other_names, direct


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return ".".join([node.id, *reversed(parts)])


def undefined_reads(source, defined):
    """(line, read) for every read of a name ``defined`` lacks, on the root settings."""
    tree = ast.parse(source)
    names, direct = _settings_bindings(tree)
    reads = [(line, f"from config.settings import {name}")
             for line, name in direct if name != "*" and name not in defined]
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
                and _dotted(node.value) in names and node.attr not in defined):
            reads.append((node.lineno, f"{_dotted(node.value)}.{node.attr}"))
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "getattr" and len(node.args) == 2
                and not node.keywords and _dotted(node.args[0]) in names
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value not in defined):
            reads.append((node.lineno, f"getattr({_dotted(node.args[0])}, "
                                       f"{node.args[1].value!r})"))
    return reads


def test_the_scan_is_not_vacuous():
    files = list(_live_files())
    assert len(files) >= 400, f"scan went vacuous ({len(files)} files)"
    readers = sum(1 for p in files
                  if _settings_bindings(ast.parse(p.read_text(encoding="utf-8")))[0])
    assert readers >= 150, f"only {readers} files bind config.settings - the resolver broke"


def test_no_live_code_reads_an_undefined_setting():
    defined = set(dir(settings))
    offences = [f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: {read}"
                for path in _live_files()
                for line, read in undefined_reads(path.read_text(encoding="utf-8"), defined)]
    assert not offences, (
        "live code reads settings that config.settings does not define (a deleted "
        "flag is always OFF - drop the read, or use getattr(settings, NAME, default) "
        "where a record must still name it):\n" + "\n".join(offences))


def test_the_resolver_reads_only_the_root_settings_namespace():
    defined = {"CACHE_FILENAME"}
    caught = undefined_reads(
        "from config import settings\n"
        "import config.settings as cs\n"
        "from config.settings import GONE_B\n"
        "def f():\n"
        "    from config import settings as s\n"
        "    return settings.GONE_A, cs.GONE_C, s.GONE_D, getattr(settings, 'GONE_E')\n",
        defined)
    assert sorted(read for _, read in caught) == sorted([
        "from config.settings import GONE_B", "settings.GONE_A", "cs.GONE_C",
        "s.GONE_D", "getattr(settings, 'GONE_E')"])
    assert undefined_reads(
        "from config import settings\n"
        "settings.GONE = 1\n"
        "x = settings.CACHE_FILENAME, getattr(settings, 'GONE', False)\n"
        "y = hasattr(settings, 'GONE')\n", defined) == []
    assert undefined_reads(
        "from broker_config import settings\n"
        "x = settings.ib_host\n", defined) == []
