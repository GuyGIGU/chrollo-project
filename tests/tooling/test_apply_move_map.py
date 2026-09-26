"""The branch porter is idempotent and correct.

``tools/maintenance/apply_move_map.py`` ports files written before the 2026-09
domain refactor onto the new layout. The rewriter it replaces was not
idempotent: a second pass rewrote the package prefix inside an already-new
name and imported a sibling module from the implementation module, which does
not resolve. These tests pin the two properties that matter - running twice
equals running once, and every import it writes resolves in the current tree -
on real pre-refactor files, plus the exact regression and one JS and one
markdown case.

Old module names are built by concatenation where a literal would trip
tests/integration/test_moved_module_paths.py.
"""
import ast
import json
import os
import posixpath
import re
import subprocess
import sys

import pytest

from _paths import BACKEND_DIR, REPO_ROOT
from tools.maintenance import apply_move_map as amm

BASELINE = "3bd4531"
MM = amm.MoveMap()
with open(amm.MAP_PATH, encoding="utf-8") as _f:
    MAP = json.load(_f)

# The broken import the old rewriter produced on its second pass.
DOUBLE_REWRITE = "from core.pipeline.universe.descriptor import " + "ticker_admission"


def _twice(rel, text, **kwargs):
    once, _ = amm.rewrite(MM, rel, text, **kwargs)
    twice, _ = amm.rewrite(MM, rel, once, **kwargs)
    return once, twice


# ── a static import resolver, independent of the tool ─────────────────────────

_ROOTS = (str(REPO_ROOT), str(BACKEND_DIR))
_ALIASES = {n["module"]: n["alias_of"] for n in MAP["notes"] if "alias_of" in n}
# Imports the tool reports instead of rewriting: modules that were split or deleted.
_REPORTED = {n["module"] for n in MAP["notes"] if n.get("report")}


def _bare(dotted):
    return dotted[len("webapp.backend."):] if dotted.startswith("webapp.backend.") else dotted


def _module_file(dotted):
    """The .py file, package __init__, or namespace folder behind a dotted name."""
    for base in _ROOTS:
        path = os.path.join(base, *dotted.split("."))
        if os.path.isfile(path + ".py"):
            return path + ".py"
        if os.path.isdir(path):
            init = os.path.join(path, "__init__.py")
            return init if os.path.isfile(init) else path
    return None


# Top-level names the old layout had, including packages that are gone now: an
# import of one must count as local, or a vanished package reads as "resolved".
_OLD_TOPS = {m["old"].split(".")[0] for m in MAP["module_moves"]}


def _is_local(dotted):
    top = _bare(dotted).split(".")[0]
    return top in _OLD_TOPS or any(
        os.path.exists(os.path.join(base, top)) or os.path.isfile(os.path.join(base, top + ".py"))
        for base in _ROOTS)


def _bound_names(path):
    """Top-level names a module binds (defs, assignments, imports, ``__all__``)."""
    if os.path.isdir(path):
        return set(), False
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names, star = set(), False

    def visit(body):
        nonlocal star
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names.update(n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name))
                if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                    names.update(ast.literal_eval(node.value))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    star = star or alias.name == "*"
                    names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                for block in (node.body, getattr(node, "orelse", []), getattr(node, "finalbody", [])):
                    visit(block)
                for handler in getattr(node, "handlers", []):
                    visit(handler.body)
    visit(tree.body)
    return names, star


def unresolved_imports(source):
    """Every absolute local import in ``source`` that the current tree cannot satisfy."""
    missing = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            missing += [(node.lineno, a.name, None) for a in node.names
                        if _is_local(a.name) and not _module_file(a.name)]
        elif isinstance(node, ast.ImportFrom) and not node.level and _is_local(node.module):
            path = _module_file(_ALIASES.get(_bare(node.module), node.module))
            if not path:
                missing.append((node.lineno, node.module, None))
                continue
            names, star = _bound_names(path)
            missing += [(node.lineno, node.module, a.name) for a in node.names
                        if not (a.name == "*" or star or a.name in names
                                or _module_file(f"{node.module}.{a.name}"))]
    return missing


def _reported(module, name):
    return _bare(module) in _REPORTED or (name and _bare(f"{module}.{name}") in _REPORTED)


def test_the_resolver_sees_the_double_rewrite():
    """Guard the guard: the resolver must flag the exact import the old rewriter broke,
    and an import of a package that no longer exists."""
    assert unresolved_imports(DOUBLE_REWRITE + "\n")
    for gone in ("from routers import calibration\n", "import routers." + "archive\n", "import schemas\n"):
        assert unresolved_imports(gone), gone
    assert not unresolved_imports("from core.pipeline.universe import ticker_admission\n")
    assert not unresolved_imports("from engine_alpha.structure.narrative import bricks, read_structure\n")


# ── (c) the exact regression, and the rewrites around it ──────────────────────

@pytest.mark.parametrize("old, new", [
    ("from core.pipeline import ticker_admission\n",
     "from core.pipeline.universe import ticker_admission\n"),
    ("from engine_alpha.structure import bricks\n",
     "from engine_alpha.structure.narrative import bricks\n"),
    ("from core.pipeline import universe\n",
     "from core.pipeline.universe import descriptor as universe\n"),
    ("from engine_alpha.structure.lps import detect_lps, _profile_unit\n",
     "from engine_alpha.structure.lps.detection import detect_lps, _profile_unit\n"),
    ("import engine_alpha.structure.narrative as narrative\n",
     "import engine_alpha.structure.narrative.reader as narrative\n"),
    ("from webapp.backend.services import scan_runner, " + "csv_import\n",
     "from webapp.backend.services import scan_runner\n"
     "from webapp.backend.domains.trading import csv_import\n"),
])
def test_imports_are_rewritten_once(old, new):
    once, twice = _twice("tests/pipeline/test_example.py", old)
    assert once == new
    assert twice == once, "a second pass rewrote an already-new import"
    assert DOUBLE_REWRITE not in twice


def test_new_style_imports_are_left_alone():
    """What the refactor itself writes is never rewritten, facade names included."""
    source = ("from core.pipeline.universe import ticker_admission, tickers\n"
              "from core.pipeline.universe import descriptor as universe_mod\n"
              "from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE\n"
              "from engine_alpha.structure.narrative import bricks\n"
              "from engine_alpha.structure.metrics import pivots, measure_equilibrium\n")
    assert amm.rewrite(MM, "tests/pipeline/test_example.py", source)[0] == source


@pytest.mark.parametrize("old, new", [
    ('patch("core.pipeline.' + 'tickers.get_cached_tickers")',
     'patch("core.pipeline.universe.tickers.get_cached_tickers")'),
    ('patch("engine_alpha.structure.lps.detect_lps")',
     'patch("engine_alpha.structure.lps.detection.detect_lps")'),
    ('SPEC = "services.' + 'trigger_grade"', 'SPEC = "domains.calibration.trigger_grade"'),
    ('cmd = "python -m tools.' + 'reader_pin --check"', 'cmd = "python -m tools.regression.reader_pin --check"'),
    ("# see engine_alpha/structure/" + "pivots.py", "# see engine_alpha/structure/metrics/pivots.py"),
])
def test_dotted_names_and_paths_are_rewritten_once(old, new):
    once, twice = _twice("tests/engine/test_example.py", old + "\n")
    assert once == new + "\n"
    assert twice == once


def test_imports_written_as_text_are_ported_like_code():
    """A from-import inside a string (a ``-c`` script) or a comment follows the
    import rules, so the regression cannot come back through text."""
    source = ('CHILD = "from core.pipeline import ticker_admission; '
              'from core.pipeline.universe import tickers"\n'
              "# e.g. from engine_alpha.structure.narrative import bricks, read_structure\n")
    once, twice = _twice("tests/pipeline/test_example.py", source)
    assert once == ('CHILD = "from core.pipeline.universe import ticker_admission; '
                    'from core.pipeline.universe import tickers"\n'
                    "# e.g. from engine_alpha.structure.narrative import bricks, read_structure\n")
    assert twice == once
    assert "universe.descriptor import" not in twice


def test_no_new_name_in_the_map_matches_an_old_one():
    """The whole map, not a sample: every destination survives the text pass
    unchanged, so no future rewrite can walk into an already-new name."""
    for new in MM.modules.values():
        assert amm.rewrite_text(MM, new) == new, new
        assert amm.rewrite_text(MM, "webapp.backend." + new) == "webapp.backend." + new, new
    for new in MM.path_forms.values():
        assert amm.rewrite_text(MM, new) == new, new
    for package in MM.packages:
        for child in MM.children[package]:
            line = f"from {package} import {child}\n"
            assert amm.rewrite(MM, "tests/x/test_example.py", line)[0] == line
            assert amm.rewrite_text(MM, f"{package}.{child}") == f"{package}.{child}"


def test_split_modules_are_reported_not_guessed():
    source = "from services." + "startup import migrate_universe_type, initialize_database\n"
    new, notes = amm.rewrite(MM, "tests/backend/test_example.py", source)
    assert new == source
    assert any("app.migrations.archive" in n for n in notes)
    assert any("app.startup" in n for n in notes)


def test_a_relative_import_that_no_longer_resolves_is_reported():
    source = ("from .gone_module import x\nfrom .service import get_ibkr_service\n"
              "from . import gone_sibling\nfrom . import service\n")
    new, notes = amm.rewrite(MM, "webapp/backend/domains/ibkr/__init__.py", source)
    assert new == source
    assert [n.split(":")[0] for n in notes] == ["line 1", "line 3"]


@pytest.mark.parametrize("source", ["from routers import *\n", "import routers\n", "from output import *\n"])
def test_an_import_of_a_deleted_package_is_reported(source):
    new, notes = amm.rewrite(MM, "tests/backend/test_example.py", source)
    assert new == source
    assert any("no longer exists" in n for n in notes), notes


def test_a_split_import_keeps_its_comment_and_line_endings():
    source = "import os\r\nfrom engine_alpha.structure import bricks, lps  # noqa: E402\r\n"
    once, twice = _twice("tests/engine/test_example.py", source)
    assert once == ("import os\r\n"
                    "from engine_alpha.structure.narrative import bricks  # noqa: E402\r\n"
                    "from engine_alpha.structure.lps import detection as lps  # noqa: E402\r\n")
    assert twice == once
    _, notes = amm.rewrite(MM, "tests/engine/test_example.py",
                           "from engine_alpha.structure import (\n    bricks,  # the bricks\n    lps,\n)\n")
    assert any("comments inside the split import were dropped" in n for n in notes), notes


def test_a_moved_tool_gets_the_category_folder_fallback():
    """The old direct-run fallback imported ``_bootstrap`` from the script's own folder,
    which a category folder no longer is."""
    old = ("try:\n    from tools._bootstrap import configure_path\n"
           "except ModuleNotFoundError:\n    from _bootstrap import configure_path  # type: ignore\n")
    once, twice = _twice("tools/regression/shadow_diff.py", old)
    assert once == ("try:\n    from tools._bootstrap import configure_path\n"
                    "except ModuleNotFoundError:\n    import os, sys\n"
                    "    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname("
                    "os.path.abspath(__file__)))))\n"
                    "    from tools._bootstrap import configure_path  # type: ignore\n")
    assert twice == once
    assert amm.rewrite(MM, "tools/_example.py", old)[0] == old, "a tool still in tools/ keeps it"


def test_the_ported_fallback_runs_as_a_script(tmp_path):
    """Run the ported fallback as a direct script would: repo root NOT on sys.path."""
    ported, _ = amm.rewrite(MM, "tools/regression/shadow_diff.py",
                            "try:\n    from tools._bootstrap import configure_path\n"
                            "except ModuleNotFoundError:\n    from _bootstrap import configure_path\n")
    script_path = os.path.join(str(REPO_ROOT), "tools", "regression", "shadow_diff.py")
    code = f"__file__ = {script_path!r}\n" + ported + "print(configure_path())\n"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    run = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert os.path.samefile(run.stdout.strip(), REPO_ROOT)


def test_paths_it_cannot_port_are_reported():
    """A moved file's own-location paths, and paths spelled as separate segments."""
    mm = amm.MoveMap(extra_moves=[("tests/test_new.py", "tests/pipeline/test_new.py")])
    _, notes = amm.rewrite(mm, "tests/pipeline/test_new.py", "ROOT = Path(__file__).resolve().parents[1]\n")
    assert any("own location" in n for n in notes), notes
    _, notes = amm.rewrite(MM, "tests/pipeline/test_example.py",
                           'P = ROOT / "webapp" / "backend" / "services" / "trade_risk.py"\n'
                           'R = ROOT / "webapp" / "backend" / "routers"\n')
    assert [n.split(":")[0] for n in notes if "separate segments" in n] == ["line 1", "line 2"], notes
    _, notes = amm.rewrite(MM, "tests/pipeline/test_example.py",
                           'ROOT = Path(__file__).parent\nP = ROOT / "webapp" / "backend"\n')
    assert notes == [], "a file that did not move, naming a path that exists, is quiet"


@pytest.mark.parametrize("source, needle", [
    ("from webapp.backend import services\nservices.trade_risk.compute()\n", "never imports"),
    ("from core.pipeline import universe\nuniverse.tickers.get_cached_tickers()\n", "used as the package"),
])
def test_a_rewrite_it_cannot_bind_is_reported(source, needle):
    _, notes = amm.rewrite(MM, "tests/pipeline/test_example.py", source)
    assert any(needle in n for n in notes), notes


def test_windows_scripts_get_their_backslash_paths_ported():
    source = "& .venv\\Scripts\\python.exe tools\\shadow_diff.py --check\r\n"
    once, twice = _twice("tools/ops/example.ps1", source)
    assert once == "& .venv\\Scripts\\python.exe tools\\regression\\shadow_diff.py --check\r\n"
    assert twice == once


# ── (d) JS specifiers and markdown links ──────────────────────────────────────

def test_js_specifiers_follow_the_moves():
    rel = "webapp/frontend/src/shared/setup/ScreenerCard.jsx"  # was src/components/
    source = ("import { fx } from '../utils/format.js'\n"
              "import useSSE from '../hooks/useSSE'\n"
              "import { chartTheme } from './chartTheme'\n"
              "const lazy = import('./ScreenerModal.jsx')\n"
              "import React from 'react'\n")
    once, twice = _twice(rel, source)
    assert once == ("import { fx } from '../formatting/format.js'\n"
                    "import useSSE from '../../features/portfolio/hooks/useSSE'\n"
                    "import { chartTheme } from '../charts/chartTheme'\n"
                    "const lazy = import('./ScreenerModal.jsx')\n"
                    "import React from 'react'\n")
    assert twice == once


def test_a_move_of_your_own_ports_like_the_refactors():
    """A file a branch added in an old folder, moved by the porter with --move."""
    mm = amm.MoveMap(extra_moves=[
        ("tools/yardstick.py", "tools/calibration/yardstick.py"),
        ("engine_alpha/structure/line_words.py", "engine_alpha/structure/narrative/line_words.py"),
        ("webapp/frontend/src/components/NewPanel.jsx", "webapp/frontend/src/shared/setup/NewPanel.jsx"),
    ])
    source = ("from tools import yardstick\n"
              "from engine_alpha.structure import line_words\n"
              'TARGET = "engine_alpha.structure.line_words.read"\n')
    once, _ = amm.rewrite(mm, "tests/tooling/test_example.py", source)
    assert once == ("from tools.calibration import yardstick\n"
                    "from engine_alpha.structure.narrative import line_words\n"
                    'TARGET = "engine_alpha.structure.narrative.line_words.read"\n')
    assert amm.rewrite(mm, "tests/tooling/test_example.py", once)[0] == once
    js = "import { fx } from '../utils/format.js'\n"
    assert amm.rewrite(mm, "webapp/frontend/src/shared/setup/NewPanel.jsx", js)[0] == (
        "import { fx } from '../formatting/format.js'\n")


def test_markdown_links_follow_the_moves():
    source = ("See [the LPS read](../engine_alpha/structure/lps.py#L10), "
              "[the sheets](../tools/fidelity/pip_phase_a/), "
              "[the spec](strategy_alpha.md) and [a site](https://example.com/x.py).\n"
              "[ref]: ../core/pipeline/tickers.py\n")
    once, twice = _twice("docs/example.md", source)
    assert once == ("See [the LPS read](../engine_alpha/structure/lps/detection.py#L10), "
                    "[the sheets](../research/fidelity/pip_phase_a/), "
                    "[the spec](strategy_alpha.md) and [a site](https://example.com/x.py).\n"
                    "[ref]: ../core/pipeline/universe/tickers.py\n")
    assert twice == once


# ── (a)+(b) real pre-refactor files ───────────────────────────────────────────

def _git_show(path):
    return subprocess.run(["git", "show", f"{BASELINE}:{path}"], cwd=REPO_ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


def _baseline_reachable():
    return subprocess.run(["git", "cat-file", "-e", BASELINE + "^{commit}"], cwd=REPO_ROOT,
                          capture_output=True).returncode == 0


needs_baseline = pytest.mark.skipif(not _baseline_reachable(),
                                    reason=f"baseline {BASELINE} not in this clone (shallow checkout)")

# Old files that exercise every kind of move: the four modules that became
# packages, sibling imports inside them, dotted patch targets, backend routers
# and services under both spellings, the split modules, and tools.
_T = "tools/"
_R = "webapp/backend/" + "routers/"
PY_CORPUS = [
    "tests/test_bricks.py", "tests/test_ticker_admission.py", "tests/test_tickers.py",
    "tests/test_universe_descriptor.py", "tests/test_download_integrity.py",
    "tests/test_candles_router.py", "tests/test_lps.py", "tests/test_charter_measurements.py",
    "tests/test_miss_program_lanes.py", "tests/test_election_stability.py",
    "tests/test_doctrine_audit.py", "tests/test_health_board.py",
    "tests/test_trigger_grade_spec.py", "tests/test_backend_services.py",
    "webapp/backend/main.py", _R + "archive.py", _R + "calibration.py", _R + "watchlist.py",
    _T + "calibration_stat_card.py", _T + "structure_case_audit.py", _T + "marks_corpus.py",
]
# AppShell and useScanRunner import '../api', a module that became a folder
# (api/base.js): a folder is not an import target, so it must not count as resolved.
JS_CORPUS = ["webapp/frontend/src/App.jsx", "webapp/frontend/src/components/ScreenerCard.jsx",
             "webapp/frontend/src/components/PortfolioTab.jsx",
             "webapp/frontend/src/components/tradeDetail/TradeSetupChart.jsx",
             "webapp/frontend/src/components/AppShell.jsx", "webapp/frontend/src/hooks/useScanRunner.js"]


@needs_baseline
@pytest.mark.parametrize("old_path", PY_CORPUS)
def test_a_pre_refactor_python_file_ports_idempotently_and_resolves(old_path):
    source = _git_show(old_path)
    once, twice = _twice(MM.files.get(old_path, old_path), source)
    assert once != source, "the corpus file exercised no rewrite"
    assert twice == once, "a second pass changed the ported file"
    silent = [(line, module, name) for line, module, name in unresolved_imports(once)
              if not _reported(module, name)]
    assert not silent, f"{old_path}: imports that do not resolve and were not reported: {silent}"


@needs_baseline
@pytest.mark.parametrize("old_path", JS_CORPUS)
def test_a_pre_refactor_js_file_ports_idempotently_and_resolves(old_path):
    new_path = MM.files[old_path]
    once, twice = _twice(new_path, _git_show(old_path))
    assert twice == once
    here = posixpath.dirname(new_path)
    specs = re.findall(r"""(?:from|import)\s*\(?\s*['"](\.\.?/[^'"]+)['"]""", once)
    assert specs, "the corpus file has no relative imports"
    for spec in specs:
        target = posixpath.normpath(posixpath.join(here, spec))
        assert any(os.path.isfile(os.path.join(REPO_ROOT, target + s)) for s in amm._JS_SUFFIXES), spec


# ── the live tree, the CLI, and the map itself ────────────────────────────────

def _tracked(*patterns):
    out = subprocess.run(["git", "ls-files", "-z", *patterns], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p and not amm._left_alone(p)]


def test_the_migrated_tree_is_left_as_it_is():
    """Porting a merged file must not churn the refactor's own code. The one
    permitted rewrite is spelling out the implementation module for a name a
    package facade re-exports (in text, where it may be a patch target)."""
    spelled_out = [(re.compile(re.escape(pkg + "." + new.rsplit(".", 1)[1] + ".")
                               + r"(?=(?:%s)\b)" % "|".join(MM.exports[pkg])), pkg + ".")
                   for pkg, new in MM.packages.items()]
    files = _tracked("*.py", "*.md", "webapp/frontend/src/*.js", "webapp/frontend/src/*.jsx")
    assert len(files) > 600, "the scan went vacuous"

    def collapse(text):
        for pattern, collapsed in spelled_out:
            text = pattern.sub(collapsed, text)
        return text
    churned = []
    for rel in files:
        with open(os.path.join(REPO_ROOT, rel), encoding="utf-8") as f:
            text = f.read()
        if collapse(amm.rewrite(MM, rel, text)[0]) != collapse(text):
            churned.append(rel)
    assert not churned, f"the porter rewrites already-migrated files: {churned}"


def test_the_cli_checks_then_writes_then_is_clean(tmp_path):
    target = tmp_path / "test_example.py"
    target.write_text("from core.pipeline import ticker_admission\n", encoding="utf-8")
    assert amm.main(["--check", str(target)]) == 1
    assert target.read_text(encoding="utf-8") == "from core.pipeline import ticker_admission\n"
    assert amm.main([str(target)]) == 0
    assert target.read_text(encoding="utf-8") == "from core.pipeline.universe import ticker_admission\n"
    assert amm.main(["--check", str(target)]) == 0


def test_the_cli_keeps_a_bom_and_survives_another_drive(tmp_path, monkeypatch):
    target = tmp_path / "test_bom.py"
    target.write_text("\ufefffrom core.pipeline import ticker_admission\n", encoding="utf-8")
    assert amm.main([str(target)]) == 0
    assert target.read_text(encoding="utf-8") == "\ufefffrom core.pipeline.universe import ticker_admission\n"

    def other_drive(*_args):
        raise ValueError("path is on mount 'D:', start on mount 'C:'")
    monkeypatch.setattr(amm.os.path, "relpath", other_drive)
    assert amm.main(["--check", str(target)]) == 0


def test_records_and_sealed_files_are_left_alone():
    for rel in ("docs/decisions.md", "docs/marks/anything.json", "docs/archive/old.md",
                "docs/migrations/2026-09-domain-refactor.json", "research/fidelity/x/README.md",
                "docs/power_play_marks_2026-08.json"):
        assert amm._left_alone(rel), rel
    assert not amm._left_alone("tests/engine/test_lps.py")


def test_the_map_points_only_at_what_exists():
    """The porter's promise is that what it writes resolves; a destination that
    has since moved again breaks that promise. Compose the later move into the
    map (or retire the tool once the branches are ported)."""
    missing = [m["new"] for m in MAP["file_moves"] if not os.path.exists(os.path.join(REPO_ROOT, m["new"]))]
    missing += [m["new"] for m in MAP["module_moves"]
                if not _module_file(m["new"])]
    assert not missing, missing
    assert len(MAP["file_moves"]) > 500 and len(MM.packages) == 4


def test_the_migration_doc_lists_every_file_move():
    with open(os.path.join(REPO_ROOT, "docs", "migrations", "2026-09-domain-refactor.md"),
              encoding="utf-8") as f:
        doc = f.read()
    absent = [m["old"] for m in MAP["file_moves"] if f"`{m['old']}` | `{m['new']}`" not in doc]
    assert not absent, f"regenerate the doc tables from the JSON; missing rows: {absent[:5]}"
