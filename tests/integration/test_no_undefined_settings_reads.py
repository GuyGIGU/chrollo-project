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

A setting can also be named as DATA, to a scoped override: the keyword names of
``flag_capture(...)`` (``**{...}`` included), and the literal dict keys given to
``window_override`` / ``read_structure_under`` / ``snapped_election`` (a dict,
or a list of dicts). ``tools/research/ta_grade_archive_replay.py`` kept
``flag_capture(TA_SCORE_V2=True)`` for a month after that flag was deleted, and
the override raised on every run. Names that reach an override through a
variable are not seen here; ``flag_capture`` refuses them loudly at run time.
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


# The scoped overrides that take setting NAMES as data (module docstring).
_KEYWORD_OVERRIDES = {"flag_capture"}
_DICT_OVERRIDES = {"window_override", "read_structure_under", "snapped_election"}
# Made up on purpose, to prove flag_capture refuses an unknown name
# (tests/tooling/test_replay_layer.py). Never the name of a real setting.
_INVENTED = {"NO_SUCH_FLAG_EVER"}


def _literal_keys(node):
    """The string keys of a dict literal, or of each dict in a list/tuple literal."""
    dicts = node.elts if isinstance(node, (ast.List, ast.Tuple)) else [node]
    return [key.value for d in dicts if isinstance(d, ast.Dict) for key in d.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)]


def override_names(call):
    """(override, [setting names]) one call hands a scoped override as literals."""
    func = call.func
    callee = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if callee in _KEYWORD_OVERRIDES:
        return callee, [name for kw in call.keywords
                        for name in ([kw.arg] if kw.arg else _literal_keys(kw.value))]
    if callee in _DICT_OVERRIDES:
        args = [*call.args, *(kw.value for kw in call.keywords)]
        return callee, [name for arg in args for name in _literal_keys(arg)]
    return callee, []


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
        if isinstance(node, ast.Call):
            callee, named = override_names(node)
            reads += [(node.lineno, f"{callee}(... {name} ...)")
                      for name in named if name not in defined]
    return reads


def test_the_scan_is_not_vacuous():
    files = list(_live_files())
    assert len(files) >= 400, f"scan went vacuous ({len(files)} files)"
    trees = [ast.parse(p.read_text(encoding="utf-8")) for p in files]
    readers = sum(1 for tree in trees if _settings_bindings(tree)[0])
    assert readers >= 150, f"only {readers} files bind config.settings - the resolver broke"
    named = sum(len(override_names(node)[1]) for tree in trees
                for node in ast.walk(tree) if isinstance(node, ast.Call))
    assert named >= 25, f"only {named} names seen in override calls - an override was renamed"


def test_no_live_code_reads_an_undefined_setting():
    assert not _INVENTED & set(dir(settings)), "an invented name became a real setting"
    defined = set(dir(settings)) | _INVENTED
    offences = [f"{path.relative_to(REPO_ROOT).as_posix()}:{line}: {read}"
                for path in _live_files()
                for line, read in undefined_reads(path.read_text(encoding="utf-8"), defined)]
    assert not offences, (
        "live code reads or overrides settings that config.settings does not define "
        "(a deleted flag is always OFF - drop the read or the override, or use "
        "getattr(settings, NAME, default) where a record must still name it):\n"
        + "\n".join(offences))


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


def test_the_resolver_reads_the_names_handed_to_scoped_overrides():
    defined = {"CACHE_FILENAME"}
    caught = undefined_reads(
        "with flag_capture(GONE_A=True, CACHE_FILENAME='x'):\n"
        "    pass\n"
        "with replay.flag_capture(**{'GONE_B': 1}):\n"
        "    pass\n"
        "with window_override({'GONE_C': 1, 'CACHE_FILENAME': 'x'}):\n"
        "    pass\n"
        "read_structure_under(df, 1.0, {'GONE_D': 1})\n"
        "replay.snapped_election(raw, ts, [{}, {'GONE_E': 1}])\n", defined)
    assert sorted(read for _, read in caught) == sorted([
        "flag_capture(... GONE_A ...)", "flag_capture(... GONE_B ...)",
        "window_override(... GONE_C ...)", "read_structure_under(... GONE_D ...)",
        "snapped_election(... GONE_E ...)"])
    # A name that reaches the override through a variable is flag_capture's own
    # run-time refusal to make; statically it is not guessed.
    assert undefined_reads(
        "flag_capture(**variant)\n"
        "flag_capture(**{_FLAG: True})\n"
        "window_override(preset)\n"
        "some_other_call(GONE=True, x={'GONE': 1})\n", defined) == []
