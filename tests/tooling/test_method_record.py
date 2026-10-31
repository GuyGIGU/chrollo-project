"""The method's written record: his rulings in, the theory first, the ledger trued up.

Task 1 of the two-eyes-reader build plan. Nothing in the rewrite may rest on a
rule that is not written down, so this module guards the three documents the
build reads from:

* ``docs/decisions.md`` - his rulings, verbatim and dated (append-only).
* ``docs/strategy_alpha.md`` - the THEORY: his method in his order, naming no
  switch and carrying no build log (AGENTS.md: it "deliberately names no files
  or functions so it cannot rot").
* ``docs/flag_ledger.md`` - every dark switch once, and every switch of the
  twelve-step method with a recorded fate in the rewrite.

Why it exists: the Sun 20/09/2026 rulings were spoken into a planning session,
and four more rulings (Tue 01/09 and Wed 02/09/2026) live only on the still-open
pull request ``claude/eager-chatelet-65e8d4``, which is not an ancestor of this
branch. A ruling that exists only in a chat log or on an unmerged branch is a
ruling the next session will reinvent. The ledger duplication is the same class
of loss: the method branch merged the SOS branch and eleven dark rows landed
twice, so "never silently carried" (flag_ledger.md's own header) could be read
two ways for the same switch.
"""
from __future__ import annotations

from _paths import REPO_ROOT
import os
import re

_DOCS = os.path.join(str(REPO_ROOT), "docs")


def _read(name: str) -> str:
    with open(os.path.join(_DOCS, name), "r", encoding="utf-8") as f:
        return f.read()


# --- his words, exactly as he typed them -----------------------------------
# Sun 20/09/2026, in the planning session that produced .council/plans/two-eyes-reader.md.
_SUN_20_09 = {
    "the two-legs walk": (
        "I move one pair right until I find it, not only a single time. -> one "
        "line can stay on its anchor while the other moves, but they are "
        "connected like 2 lets placing one in front of the other"
    ),
    "the mini": (
        "if you are reffering to mini consolidations then both boxes live, they "
        "are a part of the same setup"
    ),
    "the seven stages": "1. yes 2. yes 3. okay 4.",
}

# Tue 01/09 and Wed 02/09/2026 - ruled in the consolidation-method sitting, recorded
# only on the open pull request's branch until Task 1 copied them here.
_STRANDED = {
    "the asks sweep": (
        "it couldn't be that complicated right? at the end of the day we're just "
        "drawing lines framing a consolidation at an uptrend across multiple time frames"
    ),
    "W1, widened": (
        "'LPS at Resistance' but this should apply generally when the LPS is in the "
        "approximate vicinity of the Resistance"
    ),
    "the tight-base widening": "Yeah they look good.",
    "the sentence archive": "`SENTENCE_ARCHIVE_ENABLED` — FLIP, with one armed trial night",
}


def test_decisions_carries_his_rulings_of_sun_20_09_2026():
    """His three rulings of the planning day, in his own words.

    They are the specification for stages 2, 3 and 4 of the new reader: the walk
    right one foot at a time, "huge spread" measured against the box itself, and
    the mini as a second live box of the same setup.
    """
    text = _read("decisions.md")
    missing = [what for what, words in _SUN_20_09.items() if words not in text]
    assert not missing, (
        "docs/decisions.md is missing his Sun 20/09/2026 ruling(s): "
        f"{missing}. They are the specification the rewrite is built to - "
        "record them verbatim, dated, in the Rulings table."
    )


def test_decisions_carries_the_rulings_stranded_on_the_open_pull_request():
    """Four rulings that lived only on `claude/eager-chatelet-65e8d4`.

    That branch is not an ancestor of this one (merge base 2a5dd13, main as of
    Thu 03/09/2026), so until they are copied across, this branch's engine is
    being built against a record that never heard them.
    """
    text = _read("decisions.md")
    missing = [what for what, words in _STRANDED.items() if words not in text]
    assert not missing, (
        "docs/decisions.md is missing the ruling(s) that live only on the open "
        f"pull request: {missing}. Copy each verbatim with its own date and say "
        "where it was recorded."
    )


def _rows_under(heading: str) -> list[tuple[str, str, str]]:
    """(first flag name, the Built cell, whole row) per row of the table under ``heading``."""
    text = _read("flag_ledger.md")
    start = text.index(heading)
    end = text.find("\n## ", start + 1)
    if end == -1:
        end = len(text)
    rows = []
    for line in text[start:end].splitlines():
        line = line.strip()
        if not line.startswith("| `"):
            continue
        cells = line.strip("|").split("|")
        m = re.search(r"`([A-Z][A-Z0-9_]+)`", cells[0])
        if m:
            rows.append((m.group(1), cells[1].strip(), line))
    return rows


def _dark_rows() -> list[tuple[str, str, str]]:
    return _rows_under("## Dark flags")


def _retired_rows() -> list[tuple[str, str, str]]:
    """The Retired table: since Sat 31/10/2026 the method's switches sit here, deleted with the old engine."""
    return _rows_under("## Retired")


def test_flag_ledger_lists_every_dark_switch_exactly_once():
    """One switch, one row.

    The method branch merged the SOS branch and eleven rows landed twice, each
    pair disagreeing about its own kill-by date or about what the switch does.
    Two rows for one switch means the ledger cannot answer its own question.
    """
    names = [n for n, _, _ in _dark_rows()]
    duplicated = sorted({n for n in names if names.count(n) > 1})
    assert not duplicated, (
        f"docs/flag_ledger.md lists these dark switches more than once: "
        f"{duplicated}. Keep the current row (the newer text, the re-dated "
        "kill-by) and delete the stale twin."
    )


def test_every_method_switch_has_a_recorded_fate_in_the_rewrite():
    """The twelve-step method's switches are never flipped - they are inherited.

    The new reader is built beside the old engine, so each of these switches is
    either carried into a stage of the new reader or deliberately dropped. Without
    a fate table the rulings they hold (the buy day reads the high; the 1.35-range
    ceiling; fifteen days from the anchor) vanish with the old engine.
    """
    text = _read("flag_ledger.md")
    # "Built" says which build step raised the switch; the older lanes only MENTION
    # the method in their re-dating reason, so the cell is read, never the whole row.
    # The switches were Dark until the old engine retired (Sat 31/10/2026); they are Retired rows now,
    # and the fate table below still owes each one its row.
    method = [n for n, built, _ in _dark_rows() + _retired_rows()
              if "final method" in built or "SOS sitting" in built
              or "AEF answer" in built]
    assert len(method) == 27, (
        f"expected the method's 27 switches in the ledger's Dark or Retired table, parsed "
        f"{len(method)}: {sorted(method)}"
    )

    start = text.find("## The final-method switches")
    assert start != -1, (
        "docs/flag_ledger.md has no fate table for the final-method switches. "
        "Add a '## The final-method switches - their fate in the rewrite' section "
        "naming every switch, the ruling it holds, its fate and what carries it."
    )
    end = text.find("\n## ", start + 1)
    table = text[start:] if end == -1 else text[start:end]
    absent = sorted(n for n in method if f"`{n}`" not in table)
    assert not absent, (
        f"these method switches have no row in the fate table: {absent}"
    )


def test_the_theory_states_his_seven_stages_and_carries_no_build_log():
    """`strategy_alpha.md` is theory; the build log belongs in the reference.

    His method has seven stages and the order is the point. The section had grown
    a ninety-line step-by-step build log naming switches - implementation, which
    rots, in the one doc AGENTS.md keeps free of file and function names.
    """
    text = _read("strategy_alpha.md")
    start = text.index("### The final method")
    end = text.index("### The legend", start)
    section = text[start:end]

    for n, stage in enumerate(
        ["The line.", "The end of the trend", "Answered and alive.",
         "The box's life.", "The story", "The LPS and the trigger.",
         "The grade"], start=1):
        assert f"{n}. **{stage}" in section, (
            f"the theory's final-method section does not state stage {n} "
            f"({stage!r}) in his order"
        )

    assert "Build status:" not in section, (
        "the step-by-step build log is still in the theory doc; it belongs in "
        "docs/engine_reference.md, which is where the build and its reasoning live"
    )
    switches = sorted(set(re.findall(r"`([A-Z][A-Z0-9_]{4,}_ENABLED)`", section)))
    assert not switches, (
        f"the theory names engine switches: {switches}. strategy_alpha.md "
        "deliberately names no files, functions or flags so it cannot rot "
        "(AGENTS.md); the switch belongs in the flag ledger and the reference."
    )
