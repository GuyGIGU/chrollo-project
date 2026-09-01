"""Doc-sync guards: the generated Settings Quick-Reference cannot rot, and the
registers cannot go back to citing code by line number.

docs/strategy_alpha.md's quick-reference was hand-maintained and had already
drifted (stale values, newer constants missing). It is now a GENERATED block
(``tools.settings_reference``) built from the frozen engine-identity allow-list
(``engine_alpha.freeze.manifest.ENGINE_SETTINGS_KEYS``) + live ``config/settings.py``
values. This test asserts the committed doc matches the generator, so any
settings or manifest change that skips regenerating the doc fails the suite -
"update strategy_alpha.md in the same change", enforced.
"""
from __future__ import annotations

import os
import re

from tools import settings_reference

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The two ROW registers the citation rule speaks about, plus the one program
# record written entirely after the rule (covered in full - it has no rows to
# date-scope, and every line of it postdates 2026-09-01).
_REGISTERS = ("docs/pattern_register.md", "docs/flag_ledger.md")
_RULE_HOME = "docs/pattern_register.md"
_POST_RULE_DOCS = ("docs/consolidation_method_2026-09.md",)

# A LINE citation: a path/filename with an extension, then ``:`` and a bar
# number or range - ``metrics.py:214``, ``ScreenerCard.jsx:148-152``. The
# lookbehind keeps the match anchored at a token start; requiring a DIGIT
# after the colon is what lets ``tests/test_x.py::test_name`` (the symbol
# form the rule asks for) through untouched, and requiring a path before the
# colon is what lets the register's own retrospective ``:39-42`` prose - a
# bare range quoting a citation that USED to exist - through as well.
_LINE_CITATION = re.compile(
    r"(?<![\w:./\\-])"
    r"([A-Za-z0-9_][A-Za-z0-9_./\\-]*\.[A-Za-z][A-Za-z0-9]{0,5})"
    r":(\d+(?:[-–]\d+)?)")
_RULE_DATE = re.compile(r"\*\*Citation rule \((\d{4}-\d{2}-\d{2})\)")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _read(rel_path: str) -> str:
    with open(os.path.join(_ROOT, *rel_path.split("/")), "r",
              encoding="utf-8") as f:
        return f.read()


def _line_citations(text: str) -> list[str]:
    """Every ``path.ext:NNN`` citation in ``text``, in order."""
    return [m.group(0) for m in _LINE_CITATION.finditer(text)]


def _rule_date(register_text: str) -> str:
    """The Citation rule's own date, read out of the register that states it.

    Deleting the rule paragraph therefore fails the suite rather than quietly
    disabling the guard that enforces it.
    """
    match = _RULE_DATE.search(register_text)
    assert match is not None, (
        "docs/pattern_register.md no longer states the **Citation rule "
        "(YYYY-MM-DD):** paragraph - the rule the guard below enforces was "
        "deleted, which would have silently disabled the guard too")
    return match.group(1)


def _table_rows(text: str):
    """Yield ``(line_no, cells, line)`` for each markdown table BODY row."""
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in _UNESCAPED_PIPE.split(stripped.strip("|"))]
        if len(cells) < 2:
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue                      # the header separator
        if cells[0] in ("#", "Flag"):
            continue                      # the header itself
        yield line_no, cells, line


def _covered_rows(text: str, rule_date: str) -> list[tuple[int, str]]:
    """The ``(line_no, row_text)`` pairs the citation rule governs: every table
    row EXCEPT one whose date column names a date strictly BEFORE the rule.
    Fail-closed - a row with no parseable date is covered, so the scope cannot
    be dodged by omitting one."""
    covered = []
    for line_no, cells, line in _table_rows(text):
        opened = _ISO_DATE.search(cells[1])
        if opened is not None and opened.group(0) < rule_date:
            continue                  # grandfathered: written before the rule
        covered.append((line_no, line))
    return covered


def _offending_rows(text: str, rule_date: str) -> list[tuple[int, str]]:
    """Every ``(line_no, citation)`` carried by a covered row of ``text``."""
    return [(line_no, cite)
            for line_no, line in _covered_rows(text, rule_date)
            for cite in _line_citations(line)]


def test_quick_reference_markers_present():
    """The generated block's markers must exist in the committed doc - if they
    vanish, --write has nowhere to land and the sync guard guards nothing."""
    assert os.path.exists(settings_reference._DOC_PATH)
    with open(settings_reference._DOC_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    # split_doc raises ValueError when markers are missing/misordered.
    settings_reference.split_doc(text)


def test_quick_reference_matches_live_settings():
    """The committed block must equal the generator's output byte-for-byte.

    Fails whenever a manifest constant's value, the allow-list membership, or
    the manifest hash moved without `python -m tools.settings_reference --write`
    being run and committed in the same change.
    """
    assert settings_reference.check_doc() is True, (
        "docs/strategy_alpha.md's Settings Quick-Reference drifted from "
        "config/settings.py - run `python -m tools.settings_reference --write` "
        "and commit the doc in the SAME change as the settings/manifest edit."
    )


# ── the registers cite code by SYMBOL, never by line number ────────────────
# pattern_register.md's Citation rule (2026-09-01). A line citation rots when
# some OTHER edit inserts above it, so the change that breaks one never
# touches the file that carries it and no diff review can catch it - and
# `tools.pointer_audit --check` cannot either, because it resolves paths and
# not line numbers. Measured on this changeset: five rotted inside their own
# review rounds with every gate green.


def test_the_citation_rule_is_stated_in_the_register():
    """The rule itself must stay written down. It is the guard's own input -
    ``_rule_date`` reads the scope date out of this paragraph - so deleting
    the paragraph would otherwise silently retire the guard below with it."""
    text = _read(_RULE_HOME)
    assert _rule_date(text) == "2026-09-01"
    assert "never by line number" in text, (
        "the Citation rule paragraph no longer says what it rules")


def test_the_line_citation_detector_tells_a_symbol_from_a_line_number():
    """The detector's own teeth, on a fixture holding FOUR candidates where
    only one is the defect - so a detector that flagged everything, or
    nothing, cannot pass here."""
    fixture = (
        "the `_fire_row` of `tools/miss_lane_census.py` reads the wrong keys; "
        "pinned by `tests/test_knob_pair_table.py::test_leg_headers_speak`; "
        "cited as `:39-42` until 2026-09-01; see `core/archive/writer.py:214`")
    assert _line_citations(fixture) == ["core/archive/writer.py:214"], (
        "the detector must flag the path+line citation and ONLY that one - a "
        "symbol citation, a `::test_name` citation and the register's own "
        "retrospective bare range are all legal")
    assert _line_citations("`ScreenerCard.jsx:148-152`") == [
        "ScreenerCard.jsx:148-152"]          # ranges too, not only single bars


def test_the_owned_registers_cite_by_symbol_not_by_line():
    """No row written on or after the Citation rule may cite code by line.

    COVERS: every markdown table row of docs/pattern_register.md and
    docs/flag_ledger.md whose date column names a date on/after the rule's own
    date (2026-09-01) or names no date at all (fail-closed), plus
    docs/consolidation_method_2026-09.md in FULL - that record has no rows to
    date-scope and every line of it postdates the rule.

    DOES NOT COVER: (a) rows dated before the rule - they are grandfathered,
    and pattern_register row 7's five frontend citations are the live example;
    (b) whether a SYMBOL citation still RESOLVES - nothing in this repo checks
    that a named function exists, and pointer_audit resolves paths only; (c)
    any other doc - decisions.md, README, strategy_alpha.md, code docstrings;
    (d) a line citation written in prose ("line 214 of metrics.py"), because
    the detection is textual on the ``path.ext:NNN`` form.
    """
    rule_date = _rule_date(_read(_RULE_HOME))
    offenders = []
    for rel_path in _REGISTERS:
        offenders += [(rel_path, line_no, cite) for line_no, cite
                      in _offending_rows(_read(rel_path), rule_date)]
    for rel_path in _POST_RULE_DOCS:
        assert os.path.exists(os.path.join(_ROOT, *rel_path.split("/"))), (
            f"{rel_path} moved - update _POST_RULE_DOCS rather than letting "
            "this guard fall silent on a record it was written to cover")
        offenders += [(rel_path, None, cite)
                      for cite in _line_citations(_read(rel_path))]
    assert offenders == [], (
        f"register rows cite code by LINE NUMBER: {offenders}. Cite the "
        "SYMBOL instead - file plus function, method, constant or "
        "::test_name (pattern_register.md's Citation rule, 2026-09-01). A "
        "line citation rots when an unrelated edit inserts above it and no "
        "gate can see it happen.")


def test_the_scope_grandfathers_only_rows_written_before_the_rule():
    """Anti-vacuity for the guard above, both halves.

    (1) The covered set must be non-empty and must include the rows this
    changeset added - a scope parser that silently matched nothing would make
    the guard pass on any register at all. (2) The line citations that DO
    survive in the registers must all sit in pre-rule rows: that is what makes
    the green above a statement about the rows rather than about the detector,
    on a file that genuinely still contains the thing being forbidden.
    """
    register = _read(_RULE_HOME)
    rule_date = _rule_date(register)
    covered_rows = _covered_rows(register, rule_date)
    assert len(covered_rows) >= 7, (
        "the citation-rule scope matched almost nothing - the register's row "
        "shape moved and the guard is now vacuous")

    all_cites = _line_citations(register)
    assert all_cites, (
        "pattern_register.md no longer carries ANY line citation, so this "
        "file can no longer prove the detector reads real content - move this "
        "anti-vacuity leg onto a register that still has one")
    assert _offending_rows(register, rule_date) == [], (
        "every surviving line citation must be grandfathered")


def test_the_guard_bites_on_a_line_citation_inside_a_covered_row():
    """The would-otherwise-be-present fixture: inject the defect into a REAL
    covered row of the real register and the guard must name it. Without this
    leg the green above is compatible with a guard that reads the file and
    reports nothing whatever it finds."""
    register = _read(_RULE_HOME)
    rule_date = _rule_date(register)
    covered = _covered_rows(register, rule_date)
    assert covered, "no covered row to inject into"

    victim = covered[-1][1]
    poisoned = register.replace(
        victim, victim + " see `engine_alpha/structure/metrics.py:214`", 1)
    assert poisoned != register, "the injection did not land"
    before = [cite for _, cite in _offending_rows(register, rule_date)]
    after = [cite for _, cite in _offending_rows(poisoned, rule_date)]
    assert after == before + ["engine_alpha/structure/metrics.py:214"], (
        "a line citation inside a covered row must be reported")
