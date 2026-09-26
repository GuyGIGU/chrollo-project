"""
Pointer audit - proves every committed evidence pointer still resolves.

This repo runs on citations. A ``decisions.md`` ruling names the evidence it was
made on, ``flag_ledger.md`` names the sheet a flag's eyeball reads, and EC-16
requires those pointers to resolve IN-REPO. Nothing enforced it, and the failure
is silent by construction: a link rots when some OTHER file moves, so the commit
that breaks it never touches the file that carries it.

It has bitten twice on record. Commit ``44f8293`` (2026-07-18) deleted 17 probe
tools and left three dangling pointers in ``flag_ledger.md`` that sat unnoticed
for a month. The 2026-08-20 bloat sweep then archived nine docs under
``docs/archive/`` and broke five more - files carrying sibling-relative links
that no longer resolved one directory deeper - in the very change whose ruling
row claimed pointers had been repointed rather than broken.

TWO CLASSES, and only one can be a hard gate:

* **Markdown links** ``[text](path)`` - GATED. Resolved relative to the file
  that carries them. A link is a promise the target is readable now, so a dead
  one is unambiguously a defect. This is the form every EC-16 evidence pointer
  uses.
* **Bare path mentions** - ``tools/foo.py`` in prose, a backticked span, or a
  Python comment - REPORTED, never gated. These are frequently historical on
  purpose: ``flag_ledger.md`` still names ``tools/candle_ab.py`` because that
  A/B is what the flag was eyeballed on, annotated "tool retired 2026-07-18".
  Failing on those would force an allowlist that rots faster than the pointers.
  Read the report; judge each one.

Deliberately IN pytest (``tests/tooling/test_pointer_audit.py``), not only here. The
lesson of the dark doctrine gate (2026-08-20) is that an out-of-pytest guard rots
invisibly - this one is fast and hermetic, so it has no excuse to live outside.

Hermetic: reads tracked files off disk via ``git ls-files``. No network.

Usage:
    python -m tools.audits.pointer_audit --check    # fail (exit 1) on a dangling link
    python -m tools.audits.pointer_audit --report   # add the advisory bare-path list
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

try:  # works under both `python -m tools.audits.pointer_audit` and `python tools/audits/pointer_audit.py`
    from tools._bootstrap import configure_path
except ModuleNotFoundError:  # a direct script run: put the repo root on sys.path first
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from tools._bootstrap import configure_path

# The repo root is the cwd for `git ls-files` and the base every link resolves
# against, so it comes from the ONE shared anchor, never from this file's own
# depth: a root that silently landed on tools/ would list only tools/ files and
# pass this gate while checking almost nothing.
_REPO_ROOT = configure_path()

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_SKIP_SCHEMES = ("http://", "https://", "mailto:", "#")

# A bare mention only counts when it is rooted at a real top-level directory AND
# carries a file extension - which is what separates a path from a module path
# (`tools.regression.shadow_diff`) or a dotted attribute (`manifest.ENGINE_SETTINGS_KEYS`).
# `output/` is deliberately absent: it holds generated artifacts, so a mention
# there is a tool naming what it WRITES, never a citation of standing evidence.
_TOP_DIRS = ("docs|tools|tests|core|engine_alpha|webapp|config|specs|research|"
             "calibration_frames")
_EXTS = "py|md|json|parquet|ps1|jsx|js|css|html|txt|csv|bat"
_BARE_PATH = re.compile(
    rf"(?<![\w./-])((?:{_TOP_DIRS})/[\w./-]*\.(?:{_EXTS}))(?![\w/-])")


def _tracked(*patterns: str) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", *patterns], cwd=_REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def _read(rel: str) -> str:
    with open(os.path.join(_REPO_ROOT, rel), encoding="utf-8",
              errors="replace") as f:
        return f.read()


def _tracked_paths() -> tuple[set[str], set[str]]:
    """(files, dirs) git tracks, repo-relative and slash-separated.

    A committed link must resolve for someone who CLONES this repo, so the
    basis is what git carries - not what happens to sit on this disk. Checking
    the filesystem instead passes a link into a gitignored file, which is the
    exact clone-only breakage this gate exists to catch (found 2026-08-20:
    four links in flag_ledger.md into root PLAN-*.md files that .gitignore
    excludes, green locally and dead on a fresh checkout).
    """
    files = set(_tracked())
    dirs = set()
    for path in files:
        parts = path.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return files, dirs


def _repo_rel(abs_path: str) -> str | None:
    """Repo-relative slash path, or None when it escapes the repo."""
    rel = os.path.relpath(abs_path, _REPO_ROOT)
    if rel == ".." or rel.startswith(".." + os.sep):
        return None
    return rel.replace(os.sep, "/")


# An archived doc is a sealed record of a closed program; the files it names are
# supposed to be gone. A migration map names every old path on purpose. Both are
# exempt from the ADVISORY only - the link gate above still holds them to
# resolving every markdown link they carry (EC-16).
_ARCHIVE_PREFIX = ("docs/archive/", "docs/migrations/")


def dangling_links() -> list[tuple[str, str]]:
    """(file, target) for every markdown link in a tracked .md that misses."""
    files, dirs = _tracked_paths()
    bad = []
    for rel in _tracked("*.md"):
        carrier_dir = os.path.dirname(os.path.join(_REPO_ROOT, rel))
        for target in _MD_LINK.findall(_read(rel)):
            if target.startswith(_SKIP_SCHEMES):
                continue
            # Strip an anchor; a link to a heading inside a real file resolves.
            clean = target.split("#")[0].strip()
            if not clean:
                continue
            resolved = _repo_rel(os.path.normpath(
                os.path.join(carrier_dir, clean)))
            if resolved is None or (resolved not in files
                                    and resolved not in dirs):
                bad.append((rel, target))
    return bad


def dangling_paths(include_archive: bool = False) -> list[tuple[str, str]]:
    """(file, path) for repo-rooted bare mentions that miss. ADVISORY.

    Deliberately filesystem-based, unlike the gate above: this asks the weaker
    question "does this thing exist at all", and a prose mention of a
    gitignored-but-real directory (``calibration_frames/``) is not a rotted
    reference. The gate is about what a clone can open; this is about what has
    moved or been deleted.

    Carriers under ``docs/archive/`` and ``docs/migrations/`` are excluded by
    default. An archived doc is a sealed record of a closed program: it names the
    files that program had, and those files SHOULD be gone; a migration map lists
    every old path on purpose. Counting them buried ~30 live-doc hits
    under 77 known-historical ones, and an advisory nobody reads is not an
    advisory. Pass ``include_archive=True`` for the unfiltered set - the report
    always prints how many were held back, so the suppression is never silent.
    """
    bad = set()
    for rel in _tracked("*.md", "*.py"):
        if not include_archive and rel.startswith(_ARCHIVE_PREFIX):
            continue
        for hit in _BARE_PATH.findall(_read(rel)):
            if not os.path.exists(os.path.join(_REPO_ROOT, hit)):
                bad.add((rel, hit))
    return sorted(bad)


def check(report: bool = False) -> bool:
    links = dangling_links()
    scanned = len(_tracked("*.md"))

    print("=" * 64)
    print("  POINTER AUDIT - every committed evidence pointer resolves")
    print("=" * 64)
    if links:
        for rel, target in links:
            print(f"  {rel} -> {target}")
        print()
        print(f"FAIL - {len(links)} markdown link(s) do not resolve.")
        print("Repoint them at where the evidence MOVED - archiving a doc keeps")
        print("its value, deleting the pointer destroys it (EC-16). If the target")
        print("is genuinely gone, say so in prose instead of leaving a dead link.")
    else:
        print(f"all markdown links resolve across {scanned} tracked docs.")
        print("PASS - no dangling evidence pointer.")

    if report:
        every = dangling_paths(include_archive=True)
        paths = [p for p in every if not p[0].startswith(_ARCHIVE_PREFIX)]
        print()
        print(f"  advisory: {len(paths)} bare path mention(s) in live files "
              "that do not exist")
        print("  (historical-on-purpose is legitimate here - judge each one)")
        print(f"  {len(every) - len(paths)} more under {' and '.join(_ARCHIVE_PREFIX)} not "
              "listed - a sealed record or migration map naming old files is not rot")
        for rel, hit in paths:
            print(f"    {rel}: {hit}")
    return not links


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Evidence-pointer resolution gate.")
    ap.add_argument("--check", action="store_true",
                    help="Fail (exit 1) if any markdown link does not resolve")
    ap.add_argument("--report", action="store_true",
                    help="Also list bare path mentions that do not exist (advisory)")
    args = ap.parse_args()
    if not (args.check or args.report):
        ap.error("nothing to do - pass --check and/or --report")
    sys.exit(0 if check(report=args.report) else 1)


if __name__ == "__main__":
    main()
