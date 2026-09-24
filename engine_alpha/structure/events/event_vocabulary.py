"""The ONE event vocabulary - a pure projection over the rail readers' output.

The ONE-Event-Map program (PLAN-one-event-map Task 4; operator rulings
2026-08-29/30). Three readers describe "what price did at the rails" in three
dialects: the puzzle stack (``box_events.read_box_events`` - typed waves), the
role labels (``event_map.read_role_labels`` - resolution/knowability stamps on
those waves), and the rail episodes (``event_map.read_rail_episodes`` -
close-basis visits). This module folds their OUTPUT into one chronological
stream speaking one vocabulary.

THE LOAD-BEARING CONSTRAINT (the plan's verdict, verbatim): this layer receives
reader output and NOTHING else. No DataFrame, no OHLC array, no ATR, no rail
price may ever enter here - a naming layer that can measure will start
deciding, and a naming layer that decides is the fourth competing reader this
program exists to eliminate. ``read_role_labels`` is the in-repo proof of the
shape (it consumes the puzzle event list verbatim and stamps without
re-walking a bar); this module holds the same line for the whole vocabulary.

What a folded record adds is NAMES, never facts: the shared ``word`` (from the
declared tables below - operator-reworded by editing ONE dict), the shared
``verdict`` axis (held / breached / open / unreadable / None-for-unjudged -
operator-signed 2026-08-30: "breached" is his official term for price crossing
a boundary, the SAME word for both rails; what a breach MEANS is context,
never the verdict's job), and the label layer's
knowability stamps zipped onto the wave that earned them. Every source dict
rides along UNMODIFIED under ``raw`` - the emitted vocabulary is stored/wire
history (AP-12) and no cell's spelling changes here.

Dark by design (measure-first): nothing in the engine consults this module
yet; consumers repoint one at a time in later program tasks, each under the
reader-pin / fold-parity gates. Every record names its span's bar ORIGIN and
carries its channel's BASIS (fixed reader properties + the caller's declared
operands) so cross-reader comparison is possible only on one declared ruler.

THE TRANSLATION CONTRACT (consolidation-method Task 2). The sentence is a
pure function of (truncated frame, rails, ATR, manifest knobs) standing on
the substrates each channel DECLARES (the skeleton contract at
``BASIS_CONSTANTS``). A decision-day read is produced by TRUNCATING the
frame at the decision bar — never by filtering a longer frame's read: the
terminal flags are physical right-edge facts, and the stats layer refuses a
sub-edge as-of loudly (``episode_sequence_stats``). Every judged record
carries the dual causality stamps (``knowable_bar`` / ``in_progress``), and
the right edge is honestly UNDETERMINED: an unresolved engagement renders
its rail word with verdict ``open`` — the reader never pre-types what the
bars will turn out to be (the operator's 2026-08-30 ruling: "the bars
afterwards determine the meaning", and at the edge afterwards does not
exist yet).
"""
from __future__ import annotations

import json
import logging

# Off-ruler spans and causality stamps are rare and, when a whole channel
# takes one, they are the tell of an unrebased caller rather than an honest
# read - so the serializer SAYS so, for BOTH (see ``serialize_sentence``:
# an archived null is honest, a SILENT one is undetectable). Lower-case by
# module convention (``strategy_read._log``) and, deliberately, so the
# manifest-completeness derivation below reads only DECLARATIONS.
_log = logging.getLogger("chrollo.engine.event_vocabulary")

# ---------------------------------------------------------------------------
# The declared vocabulary - ONE dict per axis, so an operator re-wording is a
# one-line edit here and nowhere else. Words are his own phrases where one
# exists (decisions.md 2026-08-29 respect-form taxonomy; 2026-08-30 states):
# "bars that Touched the rail and pivoted back" -> touch_and_pivot; spring /
# sos / upthrust / markup / lps are his Wyckoff vocabulary verbatim; the
# support/resistance TEST words are neutral engagement names with the outcome
# carried on the verdict axis, never baked into the word.
# ---------------------------------------------------------------------------

# Puzzle-stack emitted type -> (word, verdict). Verdict None = the reader
# genuinely does not judge this type (range is Phase-B cause OR a loose hold;
# lps is a Phase-D rest, not a rail verdict) - preserved as unjudged, never
# guessed (the census's ambiguous/wildcard classes, kept honest).
WORD_BY_PUZZLE_TYPE: dict[str, tuple[str, str | None]] = {
    "spring":      ("spring", "held"),
    "test":        ("support_test", "held"),
    "failed":      ("support_test", "breached"),
    "lps":         ("lps", None),
    "SOS":         ("sos", "breached"),
    "markup":      ("markup", "breached"),
    "upthrust":    ("upthrust", "held"),
    "rejection":   ("touch_and_pivot", "held"),
    "range":       ("range", None),
    "in_progress": (None, "open"),   # word resolved from the rail below
}

# An in_progress wave's word is its rail engagement - the outcome is open, and
# pretending a type ("upthrust"? "sos"?) before resolution would be lookahead
# by naming.
WORD_IN_PROGRESS_BY_RAIL: dict[str, str] = {
    "R": "resistance_test",
    "S": "support_test",
}

# Episode rail -> word; episode outcome -> verdict. An episode is one
# close-basis VISIT to a rail; its identity is the engagement, its outcome is
# the verdict (terminal posture rides on ``raw``).
WORD_BY_EPISODE_RAIL: dict[str, str] = {
    "S": "support_test",
    "R": "resistance_test",
}
VERDICT_BY_EPISODE_OUTCOME: dict[str, str] = {
    "completed": "held",
    "failed": "breached",
    "open": "open",
    "unreadable": "unreadable",
}

# The mini-consolidation's word — declared once so the fold and the closed-set
# derivation below share one spelling (the operator's shelf; ruling 2026-08-23:
# one event, position an attribute).
WORD_MINI_CONSOLIDATION = "mini_consolidation"


# ---------------------------------------------------------------------------
# The CLOSED token sets (consolidation-method Task 1) — enumerables DERIVED
# from the declared tables above (EC-33: consumers derive membership, never
# re-type it), so the archived sentence's write-time membership assert
# (EC-55, below) and any later catalog-completeness check verify against the
# same declaration the operator signed (word table signed in full 2026-08-30,
# decisions.md). Extending a declared table extends these by construction; a
# NEW word is an operator SIGNING — his words, no coinages (naming doctrine).
# ---------------------------------------------------------------------------

def _declared_words() -> tuple[str, ...]:
    words = {w for w, _v in WORD_BY_PUZZLE_TYPE.values() if w is not None}
    words |= set(WORD_IN_PROGRESS_BY_RAIL.values())
    words |= set(WORD_BY_EPISODE_RAIL.values())
    words.add(WORD_MINI_CONSOLIDATION)
    return tuple(sorted(words))


def _declared_verdicts() -> tuple[str, ...]:
    verdicts = {v for _w, v in WORD_BY_PUZZLE_TYPE.values() if v is not None}
    verdicts |= set(VERDICT_BY_EPISODE_OUTCOME.values())
    return tuple(sorted(verdicts))


WORDS: tuple[str, ...] = _declared_words()
VERDICTS: tuple[str, ...] = _declared_verdicts()


def assert_token(word, verdict) -> None:
    """The EC-55 write-time assertion, beside the tuples that declare the
    sets: every archived sentence token must be a named member of the signed
    closed vocabulary at the moment it is minted — the producing writer
    (the Task-8 archive family) calls this per token, so an unsigned word
    fails in the stack frame that invented it, never at the column CHECK.
    ``verdict=None`` is the legal unjudged state (a rest, a Phase-B range);
    any other value must be a signed verdict-axis member."""
    if word not in WORDS:
        raise ValueError(
            f"event_vocabulary: word {word!r} is not a member of the signed "
            "closed set — new words are an operator signing, never a coinage")
    if verdict is not None and verdict not in VERDICTS:
        raise ValueError(
            f"event_vocabulary: verdict {verdict!r} is not a member of the "
            "signed verdict axis (held / breached / open / unreadable)")


# ---------------------------------------------------------------------------
# The hashed projection's SOURCE REGISTRY (round-three completeness critic,
# 2026-09-01). ``vocabulary_manifest`` used to hand-enumerate four tables plus
# one constant in its own body, and NOTHING derived that list — so a declaration
# outside it sat outside the frozen identity silently. Demonstrated on
# ``BASIS_CONSTANTS``: re-declaring the puzzle channel's ``span_origin`` from
# "box" to "window" — the field the serializer's offset guard keys on, and a
# value that rides in every archived token's ``basis`` cell — left
# ``manifest_hash()`` UNMOVED. Same class as the sets-vs-mapping hole round two
# closed, one level up.
#
# So: manifest key -> the module-level declaration it projects (resolved from
# ``globals()`` at call time, which is also why a row may name a table declared
# further down this file), and ``_assert_declarations_are_registered`` pins the
# registry against the module's ACTUAL declarations. Adding a table without a
# row here refuses LOUDLY instead of silently minting rows under a stale epoch.
# ---------------------------------------------------------------------------
_MANIFEST_SOURCES: dict[str, str] = {
    "words": "WORDS",
    "verdicts": "VERDICTS",
    "puzzle_type_words": "WORD_BY_PUZZLE_TYPE",
    "in_progress_rail_words": "WORD_IN_PROGRESS_BY_RAIL",
    "episode_rail_words": "WORD_BY_EPISODE_RAIL",
    "episode_outcome_verdicts": "VERDICT_BY_EPISODE_OUTCOME",
    "mini_consolidation_word": "WORD_MINI_CONSOLIDATION",
    "channel_basis": "BASIS_CONSTANTS",
}

# Declarations deliberately OUTSIDE the hashed identity, each with the reason
# it carries no meaning an archived sentence can inherit. EXCLUDING one is a
# deliberate act recorded here; FORGETTING one is not possible.
_MANIFEST_NON_IDENTITY: dict[str, str] = {
    "SENTENCE_COLUMN_SQL":
        "archive column names + SQL types: WHERE a measured cell lands, never "
        "what a sentence SAYS. The event-map family's own column table sits "
        "outside the frozen identity on the same ground; a rename is a schema "
        "move the writers' per-writer guard-asserts catch, and columns are "
        "never repurposed (AP-12).",
    "_MANIFEST_SOURCES": "the projection's own plumbing, not vocabulary",
    "_MANIFEST_NON_IDENTITY": "the exclusion register itself",
}


def _declared_constant_names() -> set[str]:
    """Every constant this module DECLARES, derived from its own globals.

    A declaration is an upper-case module-level name bound to a plain data
    value — which is exactly what a vocabulary table, a signed word, or a
    channel-basis block is. Helpers, the logger and the readers' functions are
    lower-case and excluded by name; a Logger (or any other object) is excluded
    by type as well, so the derivation cannot drift into plumbing.

    ``set``/``frozenset`` count as declared shapes (round-four critic,
    2026-09-01): a CLOSED SET of signed words is the most natural shape the
    next declaration here takes — ``WORDS``/``VERDICTS`` are tuples only
    because they are sorted for a stable projection — and recognising a
    declaration by shape meant an upper-case ``frozenset`` word table sat
    outside the hashed identity with no refusal at all. Same silent-omission
    class as ``BASIS_CONSTANTS``, one level down: this guard is the only thing
    standing between a re-meaning'd vocabulary and rows minted under a stale
    epoch, and the family forbids backfill EVER.
    """
    return {name for name, value in globals().items()
            if name.isupper()
            and isinstance(value, (dict, tuple, list, set, frozenset,
                                   str, int, float))}


def _assert_declarations_are_registered() -> None:
    """The completeness guard: every declaration is either PROJECTED into the
    frozen identity or EXCLUDED from it on the record — nothing may sit outside
    both. Mirrors ``freeze.manifest.collect_manifest``'s posture for a vanished
    settings key: the contract must not be able to rot quietly."""
    declared = _declared_constant_names()
    registered = set(_MANIFEST_SOURCES.values()) | set(_MANIFEST_NON_IDENTITY)
    unregistered = declared - registered
    if unregistered:
        raise ValueError(
            "event_vocabulary: declared table(s) "
            + ", ".join(sorted(unregistered))
            + " sit outside the hashed vocabulary identity — a declaration "
            "that decides what an archived sentence MEANS must project into "
            "_MANIFEST_SOURCES (rows written under different reader "
            "vocabularies are different epochs, and there is no backfill "
            "EVER); one that does not must say so in _MANIFEST_NON_IDENTITY "
            "with its reason. Silence is not an option here")
    vanished = registered - declared
    if vanished:
        raise ValueError(
            "event_vocabulary: the manifest projection names declaration(s) "
            + ", ".join(sorted(vanished))
            + " that no longer exist — update the registry deliberately (a "
            "rename or removal changes the engine's vocabulary contract)")


def _json_native(value):
    """Coerce a declaration into JSON-native form for the hashed projection
    (tuples -> lists, nested throughout). Mirrors ``freeze.manifest._canonical``
    rather than importing it: the freeze layer imports THIS module, and the
    dependency may not run the other way."""
    if isinstance(value, (tuple, list)):
        return [_json_native(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_native(v) for k, v in value.items()}
    return value


def vocabulary_manifest() -> dict:
    """The signed vocabulary's hashable projection for the freeze manifest.

    The family's law is "rows written under different reader vocabularies are
    different epochs — no backfill, ever", and an epoch must partition MEANING,
    not just settings: a signed re-wording that rotated nothing would mint
    new-worded rows under the old stamp and the mixed population could never be
    partitioned again (council review 2026-09-01, finding 6). Derived from the
    same declaration ``assert_token`` polices (EC-33) — never a second copy of
    the tables; the freeze manifest hashes this beside the TA-grade chapter
    taxonomy, the in-house precedent for a non-settings identity block.

    The projection covers the MAPPINGS, not only the derived value sets. A
    re-ruling INSIDE the closed sets — ``spring`` re-assigned from ``held`` to
    ``breached``, the two episode rail words swapped — leaves both sets
    byte-identical while changing what every archived sentence SAYS, and a
    sets-only projection let exactly that slip the hash (round-two
    completeness critic, 2026-09-01). The operator's pending word signings are
    that shape, so the guarantee has to cover the assignment.

    The projection is DERIVED from ``_MANIFEST_SOURCES`` rather than typed out
    again here, and every declaration this module makes is guarded into that
    registry or onto the excluded record (round-three completeness critic,
    2026-09-01) — the hand-enumerated body was itself the same silent-omission
    class one level up, and it had already swallowed ``BASIS_CONSTANTS``, whose
    ``span_origin`` decides how every archived span is read.

    Row ORDER is deliberately NOT identity: these tables are lookups nothing
    reads positionally, and ``manifest_json``'s ``sort_keys`` canonicalises
    them, so a cosmetic reshuffle of the declaration rotates no epoch. Same
    split as the taxonomy block above it — ``TA_GRADE_CHAPTER_ORDER`` is a
    list because chapter order IS ruled meaning, ``chapter_map()`` a dict
    because registry order is not."""
    _assert_declarations_are_registered()
    return {key: _json_native(globals()[name])
            for key, name in _MANIFEST_SOURCES.items()}


# ---------------------------------------------------------------------------
# Basis provenance (Task 5) - the census's two verified divergence mechanisms
# turned from prose (the event_map BASIS NOTE) into values that ride every
# folded record. These are FIXED properties of which reader produced a record
# - structural per input channel, never inferred from an event's type (the
# wrong-side-of-the-wire re-declaration Fowler's seam rule forbids).
#
# THE SKELETON CONTRACT (consolidation-method Task 2): each channel DECLARES
# which substrate its words stand on, because a word that silently mixes
# skeletons changes meaning when the frame grows a bar. The puzzle channel
# stands on THE one calibrated order-1 collapsed swing walk (the L2
# staircase = the worked-equilibrium swings; event_map widens the same walk,
# never a second skeleton); the episode channel stands on NO skeleton at all
# (bar-level rail-zone visits); the inner-box channel stands on the inner
# election one scale down. ``market_structure``'s HH/HL labeled points are
# EXCLUDED as a sentence substrate by contract: their pivot order scales
# with frame length, so those labels are not truncation-stable — they remain
# trend-model diagnostics and may never carry a vocabulary word.
# ---------------------------------------------------------------------------
BASIS_CONSTANTS: dict[str, dict] = {
    "puzzle": {
        "skeleton": "collapsed_swing_walk",     # THE order-1 calibrated walk
        "zone_geometry": "box_relative",        # TRAVERSAL_LOW/HIGH_ZONE fractions
        "breach_basis": "extremes_vs_local_swing",  # e.g. S:failed = low < valley low - buf
        "span_origin": "box",                   # bars are box-relative (0 = box.start_bar)
    },
    "episode": {
        "skeleton": "none_bar_level",           # zone visits; no pivot walk
        "zone_geometry": "atr_fixed",           # TOUCH_TOLERANCE_ATR bands
        "breach_basis": "close_vs_rail",        # failed = close beyond the rail - buf
        "span_origin": "window",                # bars are window-relative (0 = frame start)
    },
    "inner_box": {
        "skeleton": "inner_box_election",       # the same walk, one scale down
        "zone_geometry": "atr_fixed",           # MINI_POSITION_TOL_ATR (the ruled 0.5)
        "breach_basis": "rail_proximity",       # position = inner rails vs parent rails
        "span_origin": "box",                   # detection bars are parent-box-relative
    },
}


def channel_basis(source: str, operands: dict | None) -> dict:
    """One basis dict per input channel: the reader's fixed properties plus
    the caller's DECLARED operands (rail pair, ATR, window identity - the
    values the caller handed that reader). This layer records them verbatim
    and never computes with them: provenance is pass-through, measurement
    stays upstream (the Task-4 constraint). The F9 self-disagreement is
    exactly what this preserves - two episode reads on two ATRs carry two
    distinguishable basis dicts instead of one shared word.

    An operand key that collides with the channel's FIXED properties is
    refused loudly (the _require posture): the structural constants are the
    one axis this module exists to protect, and a rich operand dict must
    never silently overwrite them into stored provenance (council review
    2026-08-30, Fowler)."""
    operands = operands or {}
    collisions = set(operands) & set(BASIS_CONSTANTS[source])
    if collisions:
        raise ValueError(
            f"operand keys {sorted(collisions)} collide with the {source} "
            "channel's fixed basis properties - declared operands may never "
            "overwrite structural provenance")
    return {**BASIS_CONSTANTS[source], **operands}


def window_span(record: dict) -> list[int] | None:
    """A record's span on the ONE window ruler, or None when unconvertible.

    Episode spans are already window-relative. A puzzle span converts only
    when its basis DECLARES ``box_start_in_window`` (the offset the caller
    knew when it ran the reader); without it this refuses - an off-by-start
    comparison must be impossible, never merely unlikely (McKinney). Pure
    relabeling arithmetic on declared operands; no measurement."""
    origin = record.get("origin")
    span = record.get("span")
    if span is None:
        return None
    if origin == "window":
        return list(span)
    if origin == "box":
        offset = (record.get("basis") or {}).get("box_start_in_window")
        if offset is None:
            return None
        return [int(span[0]) + int(offset), int(span[1]) + int(offset)]
    return None


def _require(table: dict, key, what: str):
    """A vocabulary miss is a programmer error - fail loudly, never coin a
    word by fallthrough (the register's silent-slug lesson, wireVocabulary
    2026-07-26)."""
    if key not in table:
        raise ValueError(f"event_vocabulary: unknown {what} {key!r} - the "
                         "declared table must name every emitted value")
    return table[key]


def _fold_puzzle(events: list[dict], labels: list[dict],
                 basis: dict) -> list[dict]:
    """Puzzle waves + their 1:1 role-label stamps -> folded records.

    ``read_role_labels`` builds one label per event in the SAME chokepoint
    order (``_box_events_with_meta``), so labels zip by index when the counts
    match; on any mismatch the stamps are dropped for ALL events (never
    misattributed to the wrong wave) and the mismatch is recorded on each
    affected record - honest absence over silent misalignment.
    """
    aligned = len(labels) == len(events)
    out = []
    for i, e in enumerate(events):
        etype = e.get("type")
        word, verdict = _require(WORD_BY_PUZZLE_TYPE, etype, "puzzle type")
        if word is None:
            word = _require(WORD_IN_PROGRESS_BY_RAIL, e.get("rail"),
                            "in_progress rail")
        rec = {
            "word": word,
            "verdict": verdict,
            "rail": e.get("rail"),
            "span": [int(e["zone_start"]), int(e["zone_end"])],
            "anchor": int(e["anchor_bar"]) if e.get("anchor_bar") is not None else None,
            "source": "puzzle",
            "origin": basis["span_origin"],
            "basis": basis,
            "raw": e,
        }
        if aligned:
            lab = labels[i]
            rec["knowable_bar"] = lab.get("knowable_bar")
            rec["in_progress"] = lab.get("in_progress")
            rec["election_dependent"] = lab.get("election_dependent")
            rec["label_raw"] = lab
        else:
            rec["labels_unaligned"] = True
        out.append(rec)
    return out


def _fold_episodes(episodes: list[dict], basis: dict) -> list[dict]:
    out = []
    for ep in episodes:
        out.append({
            "word": _require(WORD_BY_EPISODE_RAIL, ep.get("rail"), "episode rail"),
            "verdict": _require(VERDICT_BY_EPISODE_OUTCOME, ep.get("outcome"),
                                "episode outcome"),
            "rail": ep.get("rail"),
            "span": [int(ep["start_bar"]), int(ep["end_bar"])],
            "anchor": None,
            "source": "episode",
            "origin": basis["span_origin"],
            "basis": basis,
            # The dual causality stamps travel with every judged word
            # (consolidation-method Task 2) — lifted from the reader's own
            # episode record (the merge-horizon arithmetic lives there,
            # never re-derived here). Absent on a malformed input dict they
            # read None: unknown, never falsely settled.
            "knowable_bar": ep.get("knowable_bar"),
            "in_progress": ep.get("in_progress"),
            "raw": ep,
        })
    return out


def _fold_mini_consolidation(detection: dict, basis: dict,
                             operands: dict | None) -> dict:
    """The mini-consolidation (the operator's shelf) as ONE tape record.

    RULED 2026-08-23: the ceiling shelf and the inner mini-consolidation are
    ONE event — "no need to give it a new name just acknowledge its position."
    The input is the ELECTED inner box's own detection dict (select_inner_box's
    output, riding ``InnerBox.detection``) — an existing read, not a new
    detector; position and its raw signed distances were stamped there by the
    ruled four-value mechanism at the ±0.5-ATR tolerance (Task 6; touching_both
    joined the closed set 2026-08-30).

    Knowability (McKinney): a multi-bar rest is provisional while it can still
    extend. The caller DECLARES ``at_right_edge`` in the operands (it knows the
    frame; this layer never sees bars): at the edge the record is honestly
    ``in_progress`` with no knowable bar; otherwise its identity fixed when the
    first bar printed beyond its end (end + 1, box-relative like the span).
    A missing declaration reads as in_progress — the fail-closed direction
    (never claim a settled identity nobody attested).
    """
    start = int(detection["start_bar"])
    end = start + int(detection["base_len"]) - 1
    at_edge = bool((operands or {}).get("at_right_edge", True))
    return {
        "word": WORD_MINI_CONSOLIDATION,
        "verdict": None,                      # a rest, not a rail verdict
        "rail": None,
        "position": detection.get("position"),
        "position_distances": detection.get("position_distances"),
        "span": [start, end],
        "anchor": end,
        "source": "inner_box",
        "origin": basis["span_origin"],
        "basis": basis,
        "knowable_bar": None if at_edge else end + 1,
        "in_progress": at_edge,
        "election_dependent": True,           # its PRESENCE tracks this election
        "raw": detection,
    }


# ---------------------------------------------------------------------------
# Archive column family: the sentence tokens (consolidation-method Task 8).
# The owning declaration — names, SQL types, the cell serializer and the
# row extraction live HERE (the EVENT_MAP_COLUMN_SQL precedent); the ORM
# model declares matching nullable columns as MODEL-ONLY adds, and BOTH
# archive writers splat ``sentence_archive_values`` (EC-30: the producer
# rides every writer, guard-asserted per writer). Three-state law (Task 3),
# verbatim the event-map family's: NULL = not measured or refused (flag
# dark, pre-epoch rows, unreadable geometry — a refused read NULLs the
# WHOLE family); explicit zero = measured-empty evidence, always beside its
# readability companion; the tape cell anchors on DATES, never bar indexes.
# Rows written under different reader vocabularies are different epochs —
# no backfill, no re-reading old rows under new words, columns never
# repurposed (AP-12).
# ---------------------------------------------------------------------------
SENTENCE_COLUMN_SQL: dict[str, str] = {
    "sentence_tokens": "TEXT",      # the folded token tape, compact JSON, date-anchored
    "sentence_n_tokens": "INTEGER",  # explicit zero = measured-empty evidence
    "sentence_nan_bars": "INTEGER",  # readability companion (the three-state law)
}


def serialize_sentence(unified: dict, window_dates) -> dict:
    """Serialize a ``unify_events`` result into the family's cells — the ONE
    place the tape cell's shape is decided. ``window_dates`` is the judged
    window's DatetimeIndex; every span converts to the window ruler through
    ``window_span`` and anchors as dates (the serialization law). A record
    whose span cannot reach the window ruler keeps ``span: null`` with its
    origin recorded — honest absence over a guessed conversion. Every token
    passes the EC-55 write-time assert at THIS mint point: an unsigned word
    refuses the whole serialization loudly.

    Two single-caller trusts are refused here rather than assumed (council
    review 2026-09-01, finding 13): the tape's ORDER was decided upstream on
    RAW spans, which is chronological only while the box ruler and the window
    ruler share an origin — so a box-origin record must declare an EXPLICIT
    zero offset and ANY other declaration refuses, nonzero (a shuffle with
    honest dates) and ABSENT alike (the same shuffle with the dates nulled
    out, and nothing left to detect it by — round-two completeness critic
    2026-09-01); and the family's three-state law needs the readability
    companion beside every measured cell — so a read handed in without the
    episode channel refuses instead of minting the fourth, undeclared state.

    Returns the UNPREFIXED cell dict; the caller (the measurement producer)
    prefixes for the live result row. A refused/never-run read must NOT call
    this — the family's NULL state is the producer's job."""
    records = []
    n = len(window_dates)
    for rec in unified["events"]:
        assert_token(rec["word"], rec["verdict"])
        declared_offset = (rec.get("basis") or {}).get("box_start_in_window")
        if rec.get("origin") == "box" and declared_offset != 0:
            raise ValueError(
                "event_vocabulary: the tape is ordered on RAW spans, so a "
                "box-origin record declaring box_start_in_window="
                f"{declared_offset!r} would serialize correctly-dated but "
                "WRONGLY-ORDERED tokens - the sentence's ONE ruler is the "
                "elected window anchored at the box start, so the only legal "
                "declaration is an EXPLICIT 0. An ABSENT declaration refuses "
                "on the same ground: unknown means the two rulers are not "
                "KNOWN to share an origin, which is this same shuffle with "
                "the dates nulled out and nothing left to detect it by. A "
                "caller anchoring elsewhere must move the ordering onto the "
                "converted ruler first, never archive a shuffled sentence")
        span = window_span(rec)
        if span is not None and not (0 <= span[0] < n and 0 <= span[1] < n):
            # Honest absence, but never SILENT absence (round-three
            # completeness critic, 2026-09-01): the nulling used to happen with
            # no counter and no line, which is exactly how a whole channel
            # left off the caller's rebase went unnoticed — every downstream
            # assertion tolerates a null by construction. The archive contract
            # does NOT widen (the family's three states are settled); the
            # channel is named on the log instead, at WARNING, because one
            # record off the ruler is a read at the edge and a whole channel
            # off it is a broken ruler.
            _log.warning(
                "sentence: the %s channel's %r span %s (origin %s) falls "
                "outside the %d-trading-day judged window - archiving an "
                "honest null span. A whole channel nulling out means its "
                "bars were never rebased onto the elected window.",
                rec["source"], rec["word"], span, rec.get("origin"), n)
            span = None                      # off-ruler — never a wrong date
        # The knowable stamp converts through the SAME declared-offset rule
        # as the span (window-origin verbatim; box-origin only with the
        # declared box_start_in_window) — refused conversions stay None, and
        # say so on the same log the span nulling uses (just below).
        know = rec.get("knowable_bar")
        know_win = None
        if know is not None:
            if rec.get("origin") == "window":
                know_win = int(know)
            elif rec.get("origin") == "box":
                offset = (rec.get("basis") or {}).get("box_start_in_window")
                if offset is not None:
                    know_win = int(know) + int(offset)
        know_date = (str(window_dates[know_win].date())
                     if know_win is not None and 0 <= know_win < n else None)
        if know is not None and know_date is None:
            # The span warning's TWIN (round-four critic, 2026-09-01): a stamp
            # the reader DID make and that then failed to reach the ruler —
            # unconvertible origin, or a bar off the judged window — nulled out
            # in silence in this same function, and downstream a null
            # ``knowable`` is indistinguishable from the honest "not knowable
            # yet" of a record still in progress. Same logger, same shape, and
            # it names the channel, because one lost stamp is a read at the
            # edge and a whole channel losing them is a broken ruler.
            _log.warning(
                "sentence: the %s channel's %r knowable bar %s (origin %s) "
                "never reached the %d-trading-day judged window's ruler - "
                "archiving an honest null causality stamp. A whole channel "
                "nulling out means its bars were never rebased onto the "
                "elected window.",
                rec["source"], rec["word"], know, rec.get("origin"), n)
        records.append({
            "word": rec["word"],
            "verdict": rec["verdict"],
            "rail": rec.get("rail"),
            "span": ([str(window_dates[span[0]].date()),
                      str(window_dates[span[1]].date())]
                     if span is not None else None),
            "source": rec["source"],
            "basis": rec.get("basis"),
            "knowable": know_date,
            "in_progress": rec.get("in_progress"),
            "position": rec.get("position"),
        })
    nan_bars = unified.get("episode_nan_bars")
    if nan_bars is None:
        raise ValueError(
            "event_vocabulary: refusing to mint measured sentence tokens "
            "beside a NULL readability companion - the family has exactly "
            "THREE states (whole-family NULL = not measured or refused; "
            "measured beside its companion; measured-empty zero beside its "
            "companion), and a read handed in without the episode channel "
            "would archive a fourth, undeclared one that every three-state "
            "query misreads. A read with no episode channel is the "
            "producer's NULL state, not a serialization")
    return {
        "sentence_tokens": json.dumps(records, separators=(",", ":")),
        "sentence_n_tokens": len(records),
        "sentence_nan_bars": None if nan_bars is None else int(nan_bars),
    }


def sentence_archive_values(get, *, prefixed: bool) -> dict:
    """Map a result row to the family's {column: value} archive dict — the
    extraction BOTH writers splat (EC-30). ``get`` is the row's ``.get``;
    the LIVE result carries ``_``-prefixed keys (``prefixed=True``), the
    SEED result does not. Cells are NaN-scrubbed at the pandas boundary
    (EC-2), INTEGER cells coerced to plain int; a missing or scrubbed cell
    stays None (NULL = "not measured")."""
    import pandas as pd  # noqa: PLC0415 — the one pandas touch in this module
    out = {}
    for col, sql_type in SENTENCE_COLUMN_SQL.items():
        value = get(("_" + col) if prefixed else col)
        if value is not None:
            try:
                if pd.isna(value):
                    value = None
            except (TypeError, ValueError):
                pass
        if value is not None and sql_type == "INTEGER":
            value = int(value)
        out[col] = value
    return out


def unify_events(*, box_events=None, role_labels=None, episode_read=None,
                 inner_box=None,
                 puzzle_operands=None, episode_operands=None,
                 inner_operands=None) -> dict:
    """Fold the readers' OUTPUT dicts into one chronological stream.

    Inputs are exactly what the readers return - ``read_box_events``'s list,
    ``read_role_labels``'s dict (its ``labels`` list is consumed), and
    ``read_rail_episodes``'s dict (its ``episodes`` list is consumed). Any of
    them may be None/absent (a reader that never ran folds as nothing - the
    stream describes what WAS read, never fabricates). Inputs are not
    mutated; ``raw`` holds each source dict by reference.

    Returns ``{"events": [...], "n_puzzle": int, "n_episode": int}`` with
    events ordered by ``(span start, span end, source, rail, word)`` - one
    deterministic left-to-right tape. Puzzle spans are box-relative and
    episode spans are window-relative; every record names its ``origin`` and
    carries its channel's ``basis`` (the reader's fixed geometry/breach
    properties plus the caller's DECLARED ``*_operands`` - rail pair, ATR,
    window identity, and ``box_start_in_window`` when known). Cross-source
    span comparison goes through ``window_span``, which refuses rather than
    guesses when the declared offset is absent.
    """
    puzzle = list(box_events or [])
    labels = list((role_labels or {}).get("labels") or [])
    episodes = list((episode_read or {}).get("episodes") or [])

    folded = (_fold_puzzle(puzzle, labels, channel_basis("puzzle", puzzle_operands))
              + _fold_episodes(episodes, channel_basis("episode", episode_operands)))
    if inner_box is not None:
        folded.append(_fold_mini_consolidation(
            inner_box, channel_basis("inner_box", inner_operands), inner_operands))
    folded.sort(key=lambda r: (r["span"][0], r["span"][1], r["source"],
                               r.get("rail") or "", r["word"]))
    # The readability companion rides the stream under the THREE-STATE law
    # (consolidation-method Task 3 — verbatim the event-map family's law):
    # None = the reader never ran or refused (NULL, not-measured), an explicit
    # 0 = measured-empty evidence (the reader ran and every verdict bar was
    # finite). Lifted from the reader's own output — this layer counts
    # nothing (the naming-layer constraint).
    ep_nan = (episode_read or {}).get("nan_bars")
    ep_n = (episode_read or {}).get("n_bars")
    return {"events": folded, "n_puzzle": len(puzzle), "n_episode": len(episodes),
            "n_inner": 0 if inner_box is None else 1,
            "episode_nan_bars": None if ep_nan is None else int(ep_nan),
            "episode_n_bars": None if ep_n is None else int(ep_n)}
