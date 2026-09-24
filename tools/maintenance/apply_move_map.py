"""
Port files written against the pre-2026-09 layout onto the domain layout.

Seven branches were cut before the domain refactor and edit files it moved. This
rewrites their references through ``docs/migrations/2026-09-domain-refactor.json``
so a port is mechanical:

* **Python** - import statements are rewritten from the AST (``from core.pipeline
  import ticker_admission`` becomes ``from core.pipeline.universe import
  ticker_admission``); dotted names elsewhere (``mock.patch`` targets, ``-m
  pkg.mod`` text, attribute chains) and repo-relative file paths go through one
  regex pass each.
* **JS/JSX** - relative import specifiers are resolved against the file,
  remapped through the frontend moves and made relative again.
* **Markdown** - link targets are resolved against the doc and remapped. Prose
  is left alone: it is often a historical record on purpose.

It is IDEMPOTENT: nothing it writes is ever rewritten again. Four old modules
became packages of the same name (``lps``, ``narrative``, ``metrics``,
``universe``), so an old name is a prefix of several new ones; every rewrite
therefore refuses a name that is already new (a submodule of the package, an
import the package's facade already serves, or a JS/markdown path that already
resolves). The previous rewriter lacked that guard and a second pass broke
imports.

Relative Python imports, and imports of the modules that were split rather than
moved (see the map's notes), are reported, never guessed; so are imports of the
deleted packages, paths a moved file builds from its own location (``__file__``,
``import.meta.url``) or from separate string segments, and dotted chains whose
head the file never imports. Historical and sealed records are left alone.
docs/migrations/2026-09-domain-refactor.md is the guide.

Usage:
    python -m tools.maintenance.apply_move_map <files...>          # rewrite in place
    python -m tools.maintenance.apply_move_map --check <files...>  # show the diff; exit 1 if any
    python -m tools.maintenance.apply_move_map --move OLD=NEW <files...>  # plus a move of your own
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import posixpath
import re
import sys

try:  # works under both `python -m tools.maintenance.apply_move_map` and a direct script run
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path, refuse_sealed_output

_REPO_ROOT = configure_path()
MAP_PATH = os.path.join(_REPO_ROOT, "docs", "migrations", "2026-09-domain-refactor.json")

# Records that keep the names they were written with (or are sealed outright).
_LEAVE_ALONE = ("docs/archive/", "docs/migrations/", "docs/marks/", "research/",
                "tests/baselines/", ".council/",
                # this porter and its test hold pre-refactor examples on purpose
                "tools/maintenance/apply_move_map.py", "tests/tooling/test_apply_move_map.py")
_BACKEND_PREFIX = "webapp.backend."
_JS_SUFFIXES = ("", ".js", ".jsx", ".mjs", "/index.js", "/index.jsx")
_JS_SPEC = re.compile(r"""(\bfrom\s*|\bimport\s*\(?\s*|\brequire\s*\(\s*)(['"])(\.\.?/[^'"\n]+)\2""")
_TEXT_FROM_IMPORT = re.compile(r"\bfrom[ \t]+[\w.]+[ \t]+import[ \t]+\w+(?:[ \t]+as[ \t]+\w+)?"
                               r"(?:[ \t]*,[ \t]*\w+(?:[ \t]+as[ \t]+\w+)?)*")
_MD_LINK = re.compile(r"(\[[^\]]*\]\()([^)\s]+)|^(\s*\[[^\]]+\]:\s*)(\S+)", re.MULTILINE)


def _module_of(path: str) -> tuple[str, str] | None:
    """(import root, dotted name) of a repo-relative .py path; None if it cannot import."""
    if not path.endswith(".py"):
        return None
    root, rel = ("backend", path[len("webapp/backend/"):]) if path.startswith("webapp/backend/") else ("repo", path)
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    return (root, ".".join(parts)) if parts and all(p.isidentifier() for p in parts) else None


class MoveMap:
    """The JSON map plus what the current tree says about the four new packages."""

    def __init__(self, path: str = MAP_PATH, root: str = _REPO_ROOT, extra_moves=()):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.root = root
        self.modules = {m["old"]: m["new"] for m in data["module_moves"]}
        self.backend = {m["old"] for m in data["module_moves"] if m["root"] == "backend"}
        self.packages = {m["old"]: m["new"] for m in data["module_moves"] if "package" in m}
        self.files = {m["old"]: m["new"] for m in data["file_moves"]}
        self.dirs = {m["old"]: m["new"] for m in data["dir_moves"]}
        self.notes = {n["module"]: n for n in data["notes"] if n.get("report")}
        # Packages whose __init__.py was deleted: an import of one no longer resolves.
        self.gone = {_module_of(d["path"])[1] for d in data["deleted"]
                     if d["path"].endswith("/__init__.py")}
        self.children = {pkg: self._children(pkg) for pkg in self.packages}
        self.exports = {pkg: self._exports(pkg) for pkg in self.packages}
        for old, new in extra_moves:
            self._add_move(old, new)
        self.old_path_of = {new: old for old, new in self.files.items()}
        self.dotted_re = self._dotted_regex()
        self.path_re = self._path_regex()

    def _add_move(self, old: str, new: str) -> None:
        """A file the porter moved by hand (one a branch added in an old folder),
        ported exactly like the refactor's own moves."""
        self.files[old] = new
        old_module, new_module = _module_of(old), _module_of(new)
        if old_module and new_module and old_module[0] == new_module[0]:
            self.modules[old_module[1]] = new_module[1]
            if old_module[0] == "backend":
                self.backend.add(old_module[1])
            parent, _, leaf = new_module[1].rpartition(".")
            if parent in self.children:  # keep the already-new guard complete
                self.children[parent].add(leaf)

    def _package_dir(self, pkg: str) -> str:
        return os.path.join(self.root, *pkg.split("."))

    def _children(self, pkg: str) -> set[str]:
        names, folder = set(), self._package_dir(pkg)
        for entry in os.listdir(folder):
            if entry.endswith(".py"):
                stem = entry[:-3]
            elif os.path.isfile(os.path.join(folder, entry, "__init__.py")):
                stem = entry
            else:
                continue  # __pycache__, stray files
            if stem.isidentifier() and stem != "__init__":
                names.add(stem)
        return names

    def _exports(self, pkg: str) -> set[str]:
        """The names the package's lazy facade re-exports (its ``__all__``)."""
        with open(os.path.join(self._package_dir(pkg), "__init__.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                return set(ast.literal_eval(node.value))
        return set()

    def _dotted_regex(self) -> re.Pattern:
        # One alternative per old dotted name, longest first. A name that became a
        # package refuses to match when a submodule of the new package follows it:
        # that text is already new (the guard the previous rewriter was missing).
        # No name followed by `` import`` matches either: a from-import written in
        # a string or comment is ported whole by _rewrite_import_text instead.
        alternatives = []
        for old in sorted((o for o in self.modules if "." in o), key=len, reverse=True):
            guard = ""
            if old in self.packages:
                guard = r"(?!\.(?:%s)(?!\w))" % "|".join(sorted(self.children[old]))
            alternatives.append(re.escape(old) + r"(?!\w)" + guard)
        return re.compile(r"(?<![\w.])(%s)?(%s)(?![ \t]+import\b)"
                          % (re.escape(_BACKEND_PREFIX), "|".join(alternatives)))

    def _path_forms(self, table: dict[str, str]) -> dict[str, str]:
        """Each move under its repo-relative spelling, plus the frontend ``src/...``
        and backend-relative spellings code and package.json use."""
        forms = {}
        for old, new in table.items():
            forms[old] = new
            for prefix in ("webapp/frontend/", "webapp/backend/"):
                short = old[len(prefix):]
                if old.startswith(prefix) and new.startswith(prefix) and "/" in short:
                    forms[short] = new[len(prefix):]
        return forms

    def _path_regex(self) -> re.Pattern:
        self.path_forms = {**self._path_forms(self.files), **self._path_forms(self.dirs)}
        dirs = set(self._path_forms(self.dirs))
        alternatives = [re.escape(p) + (r"(?![\w.-])" if p in dirs else r"(?![\w/-])")
                        for p in sorted(self.path_forms, key=len, reverse=True)]
        # The same moves spelled with backslashes, as .ps1 and .bat files write them.
        self.backslash_forms = {old.replace("/", "\\"): new.replace("/", "\\")
                                for old, new in self.path_forms.items()}
        backslashed = [re.escape(p.replace("/", "\\")) + (r"(?![\w.-])" if p in dirs else r"(?![\w\\-])")
                       for p in sorted(self.path_forms, key=len, reverse=True)]
        self.backslash_re = re.compile(r"(?<![\w.\\-])(?:%s)" % "|".join(backslashed))
        self.new_modules = set(self.modules.values())
        return re.compile(r"(?<![\w./-])(?:%s)" % "|".join(alternatives))

    def new_module(self, dotted: str) -> str | None:
        """The new name of an old module, keeping a ``webapp.backend.`` spelling."""
        if dotted.startswith(_BACKEND_PREFIX) and dotted[len(_BACKEND_PREFIX):] in self.backend:
            return _BACKEND_PREFIX + self.modules[dotted[len(_BACKEND_PREFIX):]]
        return self.modules.get(dotted)

    def note(self, dotted: str) -> dict | None:
        if dotted.startswith(_BACKEND_PREFIX):
            dotted = dotted[len(_BACKEND_PREFIX):]
        return self.notes.get(dotted)

    def exists(self, rel: str) -> bool:
        return bool(rel) and os.path.exists(os.path.join(self.root, rel))

    def is_file(self, rel: str) -> bool:
        return bool(rel) and os.path.isfile(os.path.join(self.root, rel))

    def is_gone(self, dotted: str) -> bool:
        """Whether ``dotted`` lives in a package that was deleted outright."""
        if dotted.startswith(_BACKEND_PREFIX):
            dotted = dotted[len(_BACKEND_PREFIX):]
        return any(dotted == g or dotted.startswith(g + ".") for g in self.gone)

    def moved_path(self, rel: str) -> str | None:
        if rel in self.files:
            return self.files[rel]
        for old, new in self.dirs.items():
            if rel == old or rel.startswith(old + "/"):
                return new + rel[len(old):]
        return None


# ── Python ────────────────────────────────────────────────────────────────────

def _from_targets(mm: MoveMap, module: str, alias: ast.alias, keep_exports: bool, notes: list[str]):
    """Where ``from <module> import <alias>`` points now: (module, name, asname)."""
    name, asname = alias.name, alias.asname
    if module in mm.packages:
        # A submodule of the new package is already a new name; so is a name its
        # facade re-exports, unless the statement must reach the implementation anyway.
        if name in mm.children[module] or (keep_exports and name in mm.exports[module]):
            return module, name, asname
        return mm.new_module(module), name, asname
    whole = f"{module}.{name}"
    new = mm.new_module(whole)
    note = mm.note(whole) or (None if new else mm.note(module))
    if note:
        home = note.get("names", {}).get(name)
        notes.append(f"{name} now lives in {home}" if home else note["text"])
    if new:  # the imported name is itself a moved module
        parent, leaf = new.rsplit(".", 1)
        return parent, leaf, asname or (name if leaf != name else None)
    return mm.new_module(module) or module, name, asname


def _import_targets(mm: MoveMap, alias: ast.alias, notes: list[str]):
    """The statement that replaces ``import <alias>``, or None if it did not move."""
    new = mm.new_module(alias.name)
    if not new:
        if mm.note(alias.name):
            notes.append(mm.note(alias.name)["text"])
        elif mm.is_gone(alias.name):
            notes.append(f"{alias.name} no longer exists; see docs/migrations/2026-09-domain-refactor.md")
        return None
    if alias.asname:
        return f"import {new} as {alias.asname}"
    if "." in alias.name:
        return f"import {new}"  # the dotted uses are rewritten by the text pass
    parent, leaf = new.rsplit(".", 1)  # a top-level module: keep the bound name
    return f"from {parent} import {leaf}" + (f" as {alias.name}" if leaf != alias.name else "")


def _render_from(module: str, names: list[tuple[str, str | None]]) -> str:
    parts = [name + (f" as {asname}" if asname else "") for name, asname in names]
    return f"from {module} import {', '.join(parts)}"


def _rewrite_import(mm: MoveMap, node: ast.stmt, segment: str, notes: list[str]) -> str | list[str] | None:
    """The replacement for one import statement (a list when it splits), or None to keep it."""
    if isinstance(node, ast.ImportFrom):
        public = mm.children.get(node.module, set()) | mm.exports.get(node.module, set())
        keep_exports = all(alias.name in public for alias in node.names)
        groups: dict[str, list] = {}
        for alias in node.names:
            module, name, asname = _from_targets(mm, node.module, alias, keep_exports, notes)
            groups.setdefault(module, []).append((name, asname))
        notes += [f"{module} no longer exists; see docs/migrations/2026-09-domain-refactor.md"
                  for module in groups if mm.is_gone(module)]
        original = [(a.name, a.asname) for a in node.names]
        if groups == {node.module: original}:
            return None
        if len(groups) == 1 and next(iter(groups.values())) == original:
            # Only the module moved: swap it in place, keeping the statement's layout.
            return re.sub(r"^from\s+[\w.]+", "from " + next(iter(groups)), segment, count=1)
        return [_render_from(module, names) for module, names in groups.items()]
    rewritten = [_import_targets(mm, alias, notes) for alias in node.names]
    if not any(rewritten):
        return None
    kept = [a.name + (f" as {a.asname}" if a.asname else "")
            for a, new in zip(node.names, rewritten) if not new]
    return ([f"import {', '.join(kept)}"] if kept else []) + [s for s in rewritten if s]


def _char_offset(lines: list[str], starts: list[int], lineno: int, byte_col: int) -> int:
    """ast columns count UTF-8 bytes; convert to a string offset."""
    line = lines[lineno - 1]
    return starts[lineno - 1] + len(line.encode("utf-8")[:byte_col].decode("utf-8"))


def _relative_resolves(mm: MoveMap, rel_file: str, node: ast.ImportFrom) -> bool:
    """Whether ``from .x import y`` finds its module from where the file sits now."""
    if rel_file.startswith("../"):
        return False
    base = posixpath.dirname(rel_file)
    for _ in range(node.level - 1):
        base = posixpath.dirname(base)
    if node.module:
        target = posixpath.join(base, *node.module.split("."))
        return mm.exists(target + ".py") or mm.exists(target)
    # ``from . import a, b``: each name is a sibling module or a name the package binds.
    init = posixpath.join(base, "__init__.py")
    init_text = ""
    if mm.is_file(init):
        with open(os.path.join(mm.root, init), encoding="utf-8") as f:
            init_text = f.read()
    return all(alias.name == "*" or mm.exists(posixpath.join(base, alias.name + ".py"))
               or mm.exists(posixpath.join(base, alias.name))
               or re.search(r"\b%s\b" % re.escape(alias.name), init_text)
               for alias in node.names)


def _bootstrap_fallback(rel_file: str, node: ast.stmt) -> list[str] | None:
    """A tool's direct-run fallback ``from _bootstrap import ...``, once the tool sits in a
    category folder: tools/ is no longer the script's own folder, so put the repo root on
    sys.path and import through the tools package, as every migrated tool does."""
    if not (rel_file.startswith("tools/") and rel_file.count("/") >= 2
            and isinstance(node, ast.ImportFrom) and not node.level and node.module == "_bootstrap"):
        return None
    root = "os.path.abspath(__file__)"
    for _ in range(rel_file.count("/") + 1):
        root = f"os.path.dirname({root})"
    names = ", ".join(a.name + (f" as {a.asname}" if a.asname else "") for a in node.names)
    return ["import os, sys", f"sys.path.insert(0, {root})", f"from tools._bootstrap import {names}"]


_OWN_LOCATION = re.compile(r"__file__|import\.meta\.url|__dirname")
_SEGMENTS = re.compile(r"""(['"])[\w.-]+\1(?:\s*[,/]\s*(['"])[\w.-]+\2)+""")


def _location_notes(mm: MoveMap, rel_file: str, old_rel: str, text: str) -> list[str]:
    """Paths the porter cannot see through, reported by line: one a moved file builds from
    its own location (it may now be a folder off), and one spelled as separate string
    segments that names a moved or deleted path."""
    notes = []
    if posixpath.dirname(old_rel) != posixpath.dirname(rel_file):
        fallback = _bootstrap_fallback(rel_file, ast.ImportFrom("_bootstrap", [ast.alias("x")], 0))
        for number, line in enumerate(text.splitlines(), 1):
            if _OWN_LOCATION.search(line) and (not fallback or line.strip() != fallback[1]):
                notes.append(f"line {number}: builds a path from the file's own location, and the file "
                             f"moved from {posixpath.dirname(old_rel)}/ to {posixpath.dirname(rel_file)}/; "
                             "check the depth by hand (a test can use `from _paths import REPO_ROOT`)")
    for m in _SEGMENTS.finditer(text):
        joined = "/".join(re.findall(r"""['"]([\w.-]+)['"]""", m.group(0)))
        if mm.exists(joined):
            continue
        moved = any(f"/{joined}/".find(f"/{old}/") >= 0 or old.startswith(joined + "/")
                    for old in mm.path_forms if "/" in old)
        if moved:
            number = text.count("\n", 0, m.start()) + 1
            notes.append(f"line {number}: the path {joined!r} is built from separate segments and "
                         "names a moved or deleted file; point it at the new home by hand")
    return notes


def _unbound_chains(mm: MoveMap, text: str) -> list[str]:
    """Dotted chains in code that name a new module whose head the file never imports:
    the text pass rewrote an attribute chain off a name it could not rebind."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((a.asname or a.name).split(".")[0] for a in node.names)
    notes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        parts, head = [node.attr], node.value
        while isinstance(head, ast.Attribute):
            parts.append(head.attr)
            head = head.value
        if not isinstance(head, ast.Name) or head.id in bound:
            continue
        dotted = ".".join([head.id] + parts[::-1])
        if any(".".join(dotted.split(".")[:i]) in mm.new_modules for i in range(2, dotted.count(".") + 2)):
            notes.append(f"line {node.lineno}: {dotted} names a module through {head.id!r}, "
                         "which the file never imports; fix it by hand")
    return list(dict.fromkeys(notes))


def _package_bindings(mm: MoveMap, node: ast.stmt, text: str) -> list[str]:
    """An import of one of the four packages that the port binds to its implementation
    module, while the file uses the bound name as the package (``name.<submodule>``)."""
    notes = []
    for alias in node.names:
        whole = f"{node.module}.{alias.name}" if isinstance(node, ast.ImportFrom) else alias.name
        bound = alias.asname or (alias.name if isinstance(node, ast.ImportFrom) else None)
        if whole in mm.packages and bound and re.search(
                r"(?<![\w.])%s\.(?:%s)\b" % (re.escape(bound), "|".join(sorted(mm.children[whole]))), text):
            notes.append(f"{bound} is used as the package ({bound}.<submodule>), but the port binds "
                         f"{mm.packages[whole]}; keep `{whole}` by hand")
    return notes


def rewrite_python(mm: MoveMap, rel_file: str, text: str, old_rel: str | None = None) -> tuple[str, list[str]]:
    old_rel = old_rel or rel_file
    tree = ast.parse(text)
    lines = re.split(r"(?<=\n)", text)  # ast counts lines on newlines only, unlike splitlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    edits, messages = [], []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.ImportFrom) and node.level:  # out of scope: report, never guess
            if not _relative_resolves(mm, rel_file, node):
                messages.append(f"line {node.lineno}: relative import does not resolve from here; "
                                "fix it by hand")
            continue
        start = _char_offset(lines, starts, node.lineno, node.col_offset)
        end = _char_offset(lines, starts, node.end_lineno, node.end_col_offset)
        notes = []
        new = _bootstrap_fallback(rel_file, node)
        split = new is None
        if split:
            new = _rewrite_import(mm, node, text[start:end], notes)
            notes += _package_bindings(mm, node, text)
        messages += [f"line {node.lineno}: {n}" for n in dict.fromkeys(notes)]
        if isinstance(new, list):
            lead = text[starts[node.lineno - 1]:start]
            eol = "\r\n" if lines[node.end_lineno - 1].endswith("\r\n") else "\n"
            tail = text[end:starts[node.end_lineno]].strip()
            # A trailing comment (a noqa) belongs to every line the statement becomes.
            comment = "  " + tail if split and tail.startswith("#") else ""
            if split and "#" in text[start:end]:
                messages.append(f"line {node.lineno}: comments inside the split import were dropped; "
                                "re-add them by hand")
            new = (comment + eol + lead if not lead.strip() else "; ").join(new)
        edits.append((start, end, new))
    out, cursor = [], 0
    for start, end, new in sorted(edits, key=lambda edit: edit[0]):
        out.append(rewrite_text(mm, text[cursor:start]))
        out.append(text[start:end] if new is None else new)
        cursor = end
    out.append(rewrite_text(mm, text[cursor:]))
    new_text = "".join(out)
    messages += _location_notes(mm, rel_file, old_rel, new_text) + _unbound_chains(mm, new_text)
    return new_text, messages


def _rewrite_import_text(mm: MoveMap, snippet: str) -> str:
    """A ``from x import y`` inside a string or comment (a ``-c`` script, a
    docstring example), ported by the same rules as a real import."""
    try:
        node = ast.parse(snippet).body[0]
    except SyntaxError:
        return snippet
    new = None if node.level else _rewrite_import(mm, node, snippet, [])
    if new is None:
        return snippet
    return "; ".join(new) if isinstance(new, list) else new


def rewrite_text(mm: MoveMap, text: str) -> str:
    """Dotted module names and repo-relative paths anywhere in free text."""
    text = _TEXT_FROM_IMPORT.sub(lambda m: _rewrite_import_text(mm, m.group(0)), text)
    text = mm.dotted_re.sub(lambda m: (m.group(1) or "") + mm.modules[m.group(2)], text)
    return mm.path_re.sub(lambda m: mm.path_forms[m.group(0)], text)


# ── JS and markdown: relative paths ───────────────────────────────────────────

def _remap_relative(mm: MoveMap, rel_file: str, old_rel: str, target: str, suffixes, exists) -> str | None:
    """A relative ``target`` written in ``rel_file`` or at its old location
    ``old_rel``, pointed at where the file it named lives now; None when nothing matches.
    ``exists`` says what counts as resolving: a JS import needs a file (a folder
    without an index resolves to nothing), a markdown link may name a folder."""
    here = posixpath.dirname(rel_file)
    joined = posixpath.normpath(posixpath.join(here, target))
    if any(exists(joined + s) for s in suffixes):
        return target  # already resolves in the current tree: never touched again
    for base in dict.fromkeys((posixpath.dirname(old_rel), here)):
        joined = posixpath.normpath(posixpath.join(base, target))
        for suffix in suffixes:
            found = mm.moved_path(joined + suffix)
            if not found and base != here and exists(joined + suffix):
                found = joined + suffix  # the file stayed; only the importer moved
            if found:
                if suffix:  # the spelling had no extension (or named a folder's index)
                    found = found[: -len(suffix)] if found.endswith(suffix) else posixpath.splitext(found)[0]
                new = posixpath.relpath(found, here)
                new = new if new.startswith("../") else "./" + new
                return new + ("/" if target.endswith("/") and not new.endswith("/") else "")
    return None


def rewrite_js(mm: MoveMap, rel_file: str, old_rel: str, text: str) -> tuple[str, list[str]]:
    messages = []

    def swap(m):
        new = _remap_relative(mm, rel_file, old_rel, m.group(3), _JS_SUFFIXES, mm.is_file)
        if new is None:
            messages.append(f"unresolved import specifier {m.group(3)!r} left as is")
        return m.group(1) + m.group(2) + (new or m.group(3)) + m.group(2)
    new_text = rewrite_text(mm, _JS_SPEC.sub(swap, text))
    return new_text, messages + _location_notes(mm, rel_file, old_rel, new_text)


def rewrite_markdown(mm: MoveMap, rel_file: str, old_rel: str, text: str) -> tuple[str, list[str]]:
    messages = []

    def swap(m):
        lead, target = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        if re.match(r"[a-z][a-z0-9+.-]*:|#|/", target):
            return m.group(0)  # a URL, an anchor, or a site-absolute path
        path, hash_, fragment = target.partition("#")
        new = _remap_relative(mm, rel_file, old_rel, path, ("",), mm.exists)
        if new is None:
            messages.append(f"unresolved link target {target!r} left as is")
        return lead + (new + hash_ + fragment if new else target)
    return _MD_LINK.sub(swap, text), messages


# ── files ─────────────────────────────────────────────────────────────────────

def rewrite(mm: MoveMap, rel_file: str, text: str) -> tuple[str, list[str]]:
    """The ported text of one file at repo-relative ``rel_file``, plus notes.

    A file that moved (in the map, or by ``--move``) had its relative paths
    written at its old location, so those are tried too."""
    old_rel = mm.old_path_of.get(rel_file, rel_file)
    suffix = posixpath.splitext(rel_file)[1]
    if suffix == ".py":
        return rewrite_python(mm, rel_file, text, old_rel)
    if suffix in (".js", ".jsx", ".mjs"):
        return rewrite_js(mm, rel_file, old_rel, text)
    if suffix == ".md":
        return rewrite_markdown(mm, rel_file, old_rel, text)
    text = rewrite_text(mm, text)
    if suffix in (".ps1", ".bat", ".cmd"):  # Windows scripts spell paths with backslashes
        text = mm.backslash_re.sub(lambda m: mm.backslash_forms[m.group(0)], text)
    return text, []


def _left_alone(rel_file: str) -> bool:
    if rel_file.startswith(_LEAVE_ALONE) or re.fullmatch(r"docs/[^/]+\.json", rel_file):
        return True
    try:
        refuse_sealed_output(os.path.join(_REPO_ROOT, rel_file))
    except ValueError:
        return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="print the diff instead of writing; exit 1 if anything would change")
    parser.add_argument("--move", action="append", default=[], metavar="OLD=NEW",
                        help="a file you moved yourself (repo-relative paths); repeatable")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args(argv)
    moves = [item.split("=", 1) for item in args.move]
    if any(len(move) != 2 for move in moves):
        parser.error("--move takes OLD=NEW")
    mm = MoveMap(extra_moves=[(old.replace(os.sep, "/"), new.replace(os.sep, "/")) for old, new in moves])
    changed = unparsed = 0
    for path in args.files:
        try:
            rel = os.path.relpath(os.path.abspath(path), _REPO_ROOT).replace(os.sep, "/")
        except ValueError:  # another drive: outside the repository
            rel = "../" + os.path.basename(path)
        if rel.startswith("../") and rel.endswith((".js", ".jsx", ".mjs", ".md")):
            print(f"{path}: skipped (outside the repository, so its relative paths cannot be resolved)")
            continue
        if _left_alone(rel):
            print(f"{path}: left alone (a historical or sealed record)")
            continue
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        bom = "﻿" if text.startswith("﻿") else ""  # kept, but never parsed
        text = text[len(bom):]
        try:
            new, notes = rewrite(mm, rel, text)
        except SyntaxError as exc:
            print(f"{path}: cannot parse (line {exc.lineno}): a merge-conflict marker or a syntax "
                  "error; fix it first")
            unparsed += 1
            continue
        for note in notes:
            print(f"{path}: {note}")
        if new == text:
            continue
        changed += 1
        if args.check:
            sys.stdout.writelines(difflib.unified_diff(
                text.splitlines(keepends=True), new.splitlines(keepends=True), path, path + " (ported)"))
        else:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(bom + new)
            print(f"{path}: rewritten")
    if args.check and changed:
        print(f"{changed} file(s) would change")
    return 1 if unparsed or (args.check and changed) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):  # a Windows console cannot print every character
        sys.stdout.reconfigure(errors="backslashreplace")
    sys.exit(main())
