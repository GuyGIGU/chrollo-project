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
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine_alpha.freeze.manifest import ENGINE_SETTINGS_KEYS
from engine_alpha.structure.event_vocabulary import SENTENCE_COLUMN_SQL
from tools.shadow_diff import CANONICAL_FIELDS

# The declared additive field sets — result-row keys each lane may ADD.
# DERIVED from the owning declarations wherever one exists (EC-33); a lane
# that adds nothing declares the empty set, which is itself the contract:
# its whole OFF-surface is the canonical fields + the fire set, owned by the
# shadow guard and the sealed ratchet.
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
}


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


def test_the_program_flags_are_all_declared():
    # Every flag this program minted or dissolves has its row here — a new
    # lane without a declared additive set has no inert contract to re-scope
    # into at dissolution time.
    assert set(DECLARED_ADDITIVE_FIELDS) == {
        "SENTENCE_ARCHIVE_ENABLED", "CONTRACTION_RESCUE_ENABLED",
        "BAR_POSTURE_RESCUE_ENABLED", "LPS_CEILING_REST_ENABLED"}


def test_every_declared_flag_is_a_registered_engine_flag():
    # The mechanical half of enrollment (the literal above is the deliberate
    # edit anchor): a row naming a flag that never reached the frozen
    # identity — a typo, or a name left behind by a rename — would declare an
    # additive contract over a lane that does not exist, and read as covered.
    # The manifest is where every program flag must be registered before its
    # first read, so it is the one list this can be checked against.
    orphans = set(DECLARED_ADDITIVE_FIELDS) - set(ENGINE_SETTINGS_KEYS)
    assert not orphans, (
        f"{sorted(orphans)} declare an additive field set but are not "
        "registered engine flags (engine_alpha/freeze/manifest."
        "ENGINE_SETTINGS_KEYS) — the contract names a lane the engine does "
        "not have")
