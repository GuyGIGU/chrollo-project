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
"""
from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Basis provenance (Task 5) - the census's two verified divergence mechanisms
# turned from prose (the event_map BASIS NOTE) into values that ride every
# folded record. These are FIXED properties of which reader produced a record
# - structural per input channel, never inferred from an event's type (the
# wrong-side-of-the-wire re-declaration Fowler's seam rule forbids).
# ---------------------------------------------------------------------------
BASIS_CONSTANTS: dict[str, dict] = {
    "puzzle": {
        "zone_geometry": "box_relative",        # TRAVERSAL_LOW/HIGH_ZONE fractions
        "breach_basis": "extremes_vs_local_swing",  # e.g. S:failed = low < valley low - buf
        "span_origin": "box",                   # bars are box-relative (0 = box.start_bar)
    },
    "episode": {
        "zone_geometry": "atr_fixed",           # TOUCH_TOLERANCE_ATR bands
        "breach_basis": "close_vs_rail",        # failed = close beyond the rail - buf
        "span_origin": "window",                # bars are window-relative (0 = frame start)
    },
    "inner_box": {
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
        "word": "mini_consolidation",
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
    return {"events": folded, "n_puzzle": len(puzzle), "n_episode": len(episodes),
            "n_inner": 0 if inner_box is None else 1}
