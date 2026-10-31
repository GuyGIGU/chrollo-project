"""The inert contract: every default-off engine flag declares the result-row keys it may add.

When a dark flag DISSOLVES (its behavior becomes unconditional and the boolean
retires), its flag-off boom proofs cannot survive — there is no flag left to
hold off. This file is the DECLARED REPLACEMENT those proofs re-scope into:

* **OFF-state acceptance = canonical-field byte-identity**, checked against
  ``shadow_diff``'s OWN frozen list (never a re-typed copy), over the shadow
  fixture + the sealed ratchet — the two standing guards.
* **A declared additive field set per lane** — every field a lane may add to
  a result row is named here and provably DISJOINT from the canonical
  surface, so "additive only" is a checked property, not a promise.

**Enrollment is enforced, not promised** (2026-09-25, council review
2026-09-01 finding 11b): every default-off ``*_ENABLED`` key the frozen
identity registers must have an entry, and every entry must name such a flag.

The old engine's 39 dark lanes and the reader switch that replaced the reader
left this contract when that engine retired (Sat 31/10/2026): the alpha reader
has no flags, only its numbers (engine_alpha/numbers.py, hashed into
the version stamp). What remains enrolled is the advisory post-pass.
"""
from __future__ import annotations

import sys

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.stamp import ENGINE_SETTINGS_KEYS
from tools.regression.shadow_diff import CANONICAL_FIELDS

# The declared additive field sets — result-row keys each lane may ADD.
# The advisory lanes add nothing in the evaluation; the scan conductor's
# post-pass (core/fundamentals/post_pass.attach_fundamentals_post_pass) adds
# these to the FIRING rows: the four filing-gated metrics and days to earnings.
# The vendor keys need the network and are read from the code. The RS rating
# left this lane 2026-10-02: core/regime/scan_context.attach_rs_ratings writes
# _rs_rating on every scan with no flag, and the post-pass no longer emits
# _rs_trailing_return.
DECLARED_ADDITIVE_FIELDS: dict[str, frozenset[str]] = {
    "FUNDAMENTALS_ENABLED": frozenset({
        "_fund_eps_growth_yoy", "_fund_sales_growth_yoy",
        "_fund_eps_growth_accel", "_fund_earnings_surprise",
        "_fund_quarter_end", "_days_to_earnings"}),
    # Same post-pass, the RS-line half.
    "RS_LINE_ENABLED": frozenset({"_rs_line_latest", "_rs_line_new_high"}),
    # The sector rank is mapped straight onto archive columns at write time
    # (core/archive/writer.sector_rank_columns), never onto a result row.
    "SECTOR_RANKING_ENABLED": frozenset(),
}

# Flags enrolled while dark that have since FLIPPED LIVE without dissolving.
# Their entry stays: this contract is what their proofs re-scope into when
# they do dissolve. A live flag joins only by a deliberate edit here.
# FUNDAMENTALS_ENABLED flipped live 2026-10-03 (display + archive only).
ENROLLED_THEN_FLIPPED_LIVE = frozenset({"FUNDAMENTALS_ENABLED"})


def _default_off_engine_flags() -> set[str]:
    """Every ``*_ENABLED`` key of the frozen identity whose default is off,
    read off the manifest and ``config.settings`` (never re-typed)."""
    return {key for key in ENGINE_SETTINGS_KEYS
            if key.endswith("_ENABLED") and getattr(settings, key) is False}


def test_every_declared_additive_set_is_disjoint_from_the_canonical_surface():
    canonical = set(CANONICAL_FIELDS)
    for flag, fields in DECLARED_ADDITIVE_FIELDS.items():
        overlap = fields & canonical
        assert not overlap, (
            f"{flag} declares additive field(s) {sorted(overlap)} that are ON "
            "the canonical shadow surface — 'additive only' just broke; the "
            "lane is moving frozen output")


def test_the_canonical_surface_is_pinned_literally():
    # The disjointness law above reads CANONICAL_FIELDS as its SINGLE
    # authority, so a trimmed tuple would weaken the dissolution-era
    # acceptance and that law at once, silently and everywhere (council
    # review 2026-09-01, finding 11a). The literal makes shrinking the surface
    # a deliberate, visible edit: this is the alpha reader's surface, pruned to
    # what its row fills when the fleet shadow was re-based on it (Sat 31/10/2026).
    assert tuple(CANONICAL_FIELDS) == (
        "Score", "Tier", "Current Price", "Box Width", "_R", "_S",
        "_trigger_price", "_phase_b_start_date", "_lps_zone_end_date")


def test_every_default_off_engine_flag_is_enrolled():
    # The enrollment rule (docs/flag_ledger.md): a new dark lane declares, in
    # the same change, the result-row keys it may add. Without an entry it has
    # no inert contract to re-scope into at its dissolution.
    unenrolled = _default_off_engine_flags() - set(DECLARED_ADDITIVE_FIELDS)
    assert not unenrolled, (
        f"{sorted(unenrolled)} default off and are registered engine flags "
        "(engine_alpha/stamp.ENGINE_SETTINGS_KEYS) but declare no "
        "additive field set: measure the result-row keys each adds (flag off "
        "vs on over the shadow fixture and the sealed marks fixture) and enroll "
        "it in DECLARED_ADDITIVE_FIELDS — the empty set if it adds none")


def test_every_enrolled_name_is_a_default_off_engine_flag():
    # The mechanical half: a row naming a flag that never reached the frozen
    # identity (a typo, a name left behind by a rename or a deletion), or one
    # that flipped live unannounced, would declare a contract over a lane that
    # does not exist as named — and read as covered. The manifest is where
    # every engine flag is registered before its first read, so it is the one
    # list this checks against.
    stray = (set(DECLARED_ADDITIVE_FIELDS) - _default_off_engine_flags()
             - ENROLLED_THEN_FLIPPED_LIVE)
    assert not stray, (
        f"{sorted(stray)} declare an additive field set but are not default-off "
        "engine flags (engine_alpha/stamp.ENGINE_SETTINGS_KEYS, default "
        "False in config.settings): drop the row for a deleted or dissolved flag, "
        "fix a typo, or name a flag that flipped live in ENROLLED_THEN_FLIPPED_LIVE")


def test_the_flipped_live_exemption_names_only_live_enrolled_engine_flags():
    for flag in ENROLLED_THEN_FLIPPED_LIVE:
        assert flag in DECLARED_ADDITIVE_FIELDS, f"{flag} is exempted but not enrolled"
        assert flag in ENGINE_SETTINGS_KEYS, f"{flag} is not a registered engine flag"
        assert getattr(settings, flag) is True, (
            f"{flag} is exempted as flipped live but defaults to {getattr(settings, flag)!r}")


def test_the_reader_has_no_switch_and_no_dark_lane():
    """The alpha reader is read as built: its numbers are in the version stamp
    (engine_alpha/numbers.py) and no boolean on settings chooses a
    reader or arms a lane inside it. A reader flag added to settings would land
    in the manifest first, and then here."""
    assert not hasattr(settings, "TWO_EYES_READER_ENABLED")
    reader_flags = [k for k in ENGINE_SETTINGS_KEYS
                    if k.endswith("_ENABLED") and k not in DECLARED_ADDITIVE_FIELDS]
    assert reader_flags == [], reader_flags
