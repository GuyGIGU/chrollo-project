"""The re-scoped inert contract (consolidation-method Task 11 — Beck).

When a dark flag DISSOLVES (Task 14: its behavior becomes unconditional and
the boolean retires), its flag-off boom proofs cannot survive — there is no
flag left to hold off. This file is the DECLARED REPLACEMENT those proofs
re-scope into, named before any dissolution so deleting the booms without it
is impossible to miss:

* **OFF-state acceptance = canonical-field byte-identity**, checked against
  ``shadow_diff``'s OWN frozen list (never a re-typed copy), over the shadow
  fixture + the sealed ratchet — the two standing guards.
* **A declared additive field set per lane** — every field a lane may add to
  a result row is named here and provably DISJOINT from the canonical
  surface, so "additive only" is a checked property, not a promise.

A dissolution task (Task 14) cites THIS contract in place of the retired
boom tests; extending a lane's field set is a deliberate edit here, in the
operator-visible diff.

**Enrollment is enforced, not promised** (2026-09-25, council review
2026-09-01 finding 11b): every default-off ``*_ENABLED`` key the frozen
identity registers must have an entry, and every entry must name such a flag.
The old "all declared" test compared the dict to a literal in this same file,
so a lane that never enrolled could not trip it — and 36 of the 39 dark
flags had not.
"""
from __future__ import annotations

import sys

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from config import settings
from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.box.trace_export import ELECTION_TRACE_COLUMN_SQL
from engine_alpha.structure.context.strategy_read import STRATEGY_COLUMN_SQL
from engine_alpha.structure.events.event_vocabulary import SENTENCE_COLUMN_SQL
from engine_alpha.structure.events.line_words import _WORDS_BY_FLAG
from tools.regression.shadow_diff import CANONICAL_FIELDS

# The declared additive field sets — result-row keys each lane may ADD.
# DERIVED from the owning declarations wherever one exists (EC-33); a lane
# that adds nothing declares the empty set, which is itself the contract:
# its whole OFF-surface is the canonical fields + the fire set, owned by the
# shadow guard and the sealed ratchet.
#
# The sets enrolled 2026-09-25 are MEASURED, not guessed (integration head
# 663c7a1, engine ef5de2f0): each default-off flag OFF vs ON, plus the final
# method's 27 switches together and all 39 dark flags together, through the
# production evaluation path (core.pipeline.screening.screener._evaluate_ticker,
# overrides through core.calibration.replay.flag_capture) on EVERY day of the
# shadow fixture's fired windows (37 tickers) and the sealed marks fixture's
# fired-policy windows (35 setups) — 207 flag-off fire-days on 64 charts. A
# set is the ON keys minus the OFF keys, unioned over every chart; the paired
# same-day diff agreed. No lane added a key only in combination, none removed
# a key, and none touched the canonical surface. The advisory lanes add their
# keys in the scan conductor's post-pass instead, measured there offline (see
# their rows).
DECLARED_ADDITIVE_FIELDS: dict[str, frozenset[str]] = {
    # The sentence family (Tasks 8/9): the _-prefixed live-result keys of the
    # owning column dict.
    "SENTENCE_ARCHIVE_ENABLED": frozenset(
        "_" + col for col in SENTENCE_COLUMN_SQL),
    # The rescue lanes add NO result fields: a rescued fire is an ordinary
    # canonical row (its provenance rides elected_pool / the admission
    # profile, both pre-existing); their lane telemetry travels the sink,
    # never the result row.
    "CONTRACTION_RESCUE_ENABLED": frozenset(),
    "BAR_POSTURE_RESCUE_ENABLED": frozenset(),
    # The ceiling-rest exception changes only WHICH windows an LPS may
    # complete on — no new fields.
    "LPS_CEILING_REST_ENABLED": frozenset(),
    # Lanes that change which windows fire and how a fire reads, and add no
    # field: the universe-door exceptions, the final method's geometry, LPS
    # and election switches, and the contraction story form the rescue arms.
    **dict.fromkeys((
        "SMA50_DIP_EXCEPTION_ENABLED", "BOTTOMING_BASE_LANE_ENABLED",
        "RESPECT_WHOLE_BAR_ENABLED", "DWELL_GRADED_ENABLED",
        "BOX_HANDOVER_RANGES_ENABLED", "SPRING_BOUNDS_LIFTED_ENABLED",
        "LPS_RANGES_YARDSTICK_ENABLED", "LPS_GRADED_TRAITS_ENABLED",
        "LPS_WINDOW_RECEDING_ENABLED", "LPS_BUY_DAY_READS_HIGH_ENABLED",
        "LPS_REFUSALS_TO_GRADES_ENABLED", "LPS_SELLERS_RISING_FATAL_ENABLED",
        "TURN_LINE_ENABLED", "TURN_LINE_TREND_ENABLED",
        "BOX_WIDTH_CAPS_GRADED_ENABLED", "DEPTH_CAPS_GRADED_ENABLED",
        "RESPECT_GRADED_ENABLED", "BOX_OPENS_ON_ANCHORS_ENABLED",
        "BOX_END_ENABLED", "POWER_PLAY_STORY_FORM_ENABLED",
    ), frozenset()),
    # The words on the line (build step 5): every word flag adds the ONE JSON
    # cell (engine_alpha/evaluation.py, ``line_words_fields``); the word flags
    # themselves are the owning map's keys (line_words._WORDS_BY_FLAG).
    **{flag: frozenset({"_line_words_json"}) for flag in _WORDS_BY_FLAG},
    # engine_alpha/evaluation.py, ``base_age_fields`` (build step 6).
    "BASE_AGE_FROM_ANCHOR_ENABLED": frozenset({"_base_age_from_anchor"}),
    # engine_alpha/evaluation.py, the descent tail as a comment on the fire
    # (build step 12) in ``_build_live_result``.
    "LPS_LEAVES_ELECTION_ENABLED": frozenset({"_descent_tail"}),
    # engine_alpha/evaluation.py, ``_trend_run_fields`` (build step 10).
    "CLIMAX_FIRST_WALK_ENABLED": frozenset({"_trend_run_ranges", "_trend_run_days"}),
    # engine_alpha/evaluation.py, ``ledger_fields`` (build step 12).
    "GRADE_LEDGER_ENABLED": frozenset({
        "_height_ranges", "_turns_at_r", "_turns_at_s",
        "_window_spread_ranges", "_largest_limb_named"}),
    # engine_alpha/evaluation.py, ``stability_fields``.
    "ELECTION_STABILITY_ENABLED": frozenset({
        "_stability_same_frac", "_stability_streak", "_stability_probes",
        "_stability_refused"}),
    # The _-prefixed live-result keys of the owning column dicts.
    "ELECTION_TRACE_EXPORT_ENABLED": frozenset(
        "_" + col for col in ELECTION_TRACE_COLUMN_SQL),
    "STRATEGY_READ_ENABLED": frozenset("_" + col for col in STRATEGY_COLUMN_SQL),
    # The advisory lanes add nothing in the evaluation (measured above); the
    # scan conductor's post-pass adds these to the FIRING rows:
    # core/fundamentals/post_pass.attach_fundamentals_post_pass (the four
    # filing-gated metrics, days to earnings, the trailing return) and
    # core/regime/scan_context.attach_rs_ratings (the RS rating). Measured
    # offline on the shadow fixture's 34 fires with a provider that refuses
    # every call: _rs_trailing_return + _rs_rating appear; the vendor keys
    # need the network and are read from the code.
    "FUNDAMENTALS_ENABLED": frozenset({
        "_fund_eps_growth_yoy", "_fund_sales_growth_yoy",
        "_fund_eps_growth_accel", "_fund_earnings_surprise",
        "_days_to_earnings", "_rs_trailing_return", "_rs_rating"}),
    # Same post-pass, the RS-line half (measured: _rs_trailing_return).
    "RS_LINE_ENABLED": frozenset({
        "_rs_trailing_return", "_rs_line_latest", "_rs_line_new_high"}),
    # The sector rank is mapped straight onto archive columns at write time
    # (core/archive/writer.sector_rank_columns), never onto a result row.
    "SECTOR_RANKING_ENABLED": frozenset(),
}

# Flags enrolled while dark that have since FLIPPED LIVE without dissolving.
# Their entry stays: this contract is what their proofs re-scope into when
# they do dissolve. A live flag joins only by a deliberate edit here.
ENROLLED_THEN_FLIPPED_LIVE = frozenset({"SENTENCE_ARCHIVE_ENABLED"})


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
    # review 2026-09-01, finding 11a). Same derive-plus-literal pairing the
    # sentence set gets below: the derived side keeps the two in step, the
    # literal makes shrinking the surface a deliberate, visible edit.
    assert tuple(CANONICAL_FIELDS) == (
        "Setup", "Score", "Tier", "Base Len", "Box Width", "LPS Length",
        "_R", "_S", "_trigger_price")


def test_the_sentence_set_derives_from_the_owning_declaration():
    # EC-33: the declared set can never drift from the family it names.
    assert DECLARED_ADDITIVE_FIELDS["SENTENCE_ARCHIVE_ENABLED"] == frozenset(
        {"_sentence_tokens", "_sentence_n_tokens", "_sentence_nan_bars"})


def test_the_other_derived_sets_match_what_was_measured():
    # The derive-plus-literal pairing again: the owning declarations keep the
    # sets in step, these literals (the 2026-09-25 measurement) make a family
    # that grows or shrinks a visible edit here.
    assert DECLARED_ADDITIVE_FIELDS["ELECTION_TRACE_EXPORT_ENABLED"] == {"_election_trace"}
    assert DECLARED_ADDITIVE_FIELDS["STRATEGY_READ_ENABLED"] == {
        "_strategy_correction_depth_pct", "_strategy_floor_above_ar"}
    assert set(_WORDS_BY_FLAG) == {
        "LINE_WORD_SOS_ENABLED", "LINE_WORD_UPTHRUST_ENABLED",
        "LINE_WORD_LAST_SUPPER_ENABLED", "LINE_WORD_PHASE_C_ENABLED",
        "LINE_WORD_PHASE_D_ENABLED", "LINE_WORD_MINI_ENABLED"}


def test_every_default_off_engine_flag_is_enrolled():
    # The enrollment rule (docs/flag_ledger.md): a new dark lane declares, in
    # the same change, the result-row keys it may add. Without an entry it has
    # no inert contract to re-scope into at its dissolution.
    unenrolled = _default_off_engine_flags() - set(DECLARED_ADDITIVE_FIELDS)
    assert not unenrolled, (
        f"{sorted(unenrolled)} default off and are registered engine flags "
        "(engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS) but declare no "
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
        "engine flags (engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS, default "
        "False in config.settings): drop the row for a deleted or dissolved flag, "
        "fix a typo, or name a flag that flipped live in ENROLLED_THEN_FLIPPED_LIVE")


def test_the_flipped_live_exemption_names_only_live_enrolled_engine_flags():
    for flag in ENROLLED_THEN_FLIPPED_LIVE:
        assert flag in DECLARED_ADDITIVE_FIELDS, f"{flag} is exempted but not enrolled"
        assert flag in ENGINE_SETTINGS_KEYS, f"{flag} is not a registered engine flag"
        assert getattr(settings, flag) is True, (
            f"{flag} is exempted as flipped live but defaults to {getattr(settings, flag)!r}")
