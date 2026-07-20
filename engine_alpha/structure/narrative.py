"""The chronological structure reader — the engine's "pair of eyes".

Reads a chart left-to-right and builds ONE Wyckoff narrative as a sequence of
bricks, each placed on the one before it (a Lego tower), backtracking when the
story doesn't hold:

    Phase A  the root swing       climax -> automatic reaction; anchors R/S
    Phase B  the equilibrium      opens at the AR low, runs FORWARD ...
      ... and ends at the FIRST of:
    Phase C  a spring             an excursion below S that reclaims & holds  (OPTIONAL)
    Phase D  the LPS / right side the last point of support; the REQUIRED minimum

The state machine is the only new logic. Every brick is validated by an existing,
calibrated detector, exposed as a pure ``fits_here?`` function in
``engine_alpha.structure.bricks``. Those bricks are *injected* (``read_structure(...,
bricks=...)``) so the spine is testable in isolation with fakes.

The single ``Structure`` it returns is the source of truth every consumer (chart
overlay, scoping, scoring, archive) reads from — which is why the legacy
``_resolve_phase_d_start`` reconciliation goes away: here the phase boundaries are
sequential by construction, not argued back into order after the fact.

We do NOT force a story onto a base: Phase C is optional, and a base with no valid
A->B->(C?)->D narrative simply returns ``None``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from config import settings
from engine_alpha.structure.lps import detect_lps_tests, lps_range_threshold
from engine_alpha.structure.phase_d import (
    final_v_tip_bar,
    resolve_phase_d_boundary,
    support_test_evidence_starts,
)

# Backtracking safety bound. ``find_root_swing`` already returns None once the
# candidate swings are exhausted; this just caps a pathological loop.
_MAX_ANCHORS = 64

# The spine reads these fields off the (duck-typed) brick results, so it stays
# decoupled from the exact dataclasses ``bricks`` defines:
#   root   : .climax_bar  .ar_bar  .R  .S
#   box    : .S  .R  .start_bar  .box_width
#   spring : .tip_bar  .recovery_bar          (optional brick — may be None)
#   lps    : .start_bar                       (required brick)


@dataclass
class Structure:
    """The complete A -> B -> (C?) -> D narrative for one base.

    The single source of truth for the A -> B spine: ``climax_bar <= ar_bar <=
    phase_b_start_bar <= phase_b_end_bar`` by construction. A one-bar
    climax+AR (``climax_bar == ar_bar``) is a sanctioned form — a single
    wide-spread bar can breach the trend extreme AND correct deep enough to
    serve as both boundaries (operator ruling 2026-07-20). ``phase_d_start_bar``
    is NOT on that spine: it is the right-side REGION boundary (evidence-based),
    while ``phase_b_end_bar`` is the terminator EVENT bar (spring tip / LPS
    start) — on most no-spring bases the D region opens before the LPS window,
    so ``phase_d_start_bar < phase_b_end_bar`` is normal, not drift.
    ``spring`` and ``lps`` carry the raw brick results so consumers can read their
    rich fields (trigger, zone, undercut, ...) without a second measurement pass.

    It is also the daily-chart reading object for both axes of analysis:
      * ``horizontal`` — the read along the TIME axis: base duration, rail tests,
        and whether the swing limbs travel the range rail-to-rail.
      * ``vertical`` — the read along the PRICE axis: the rail levels, the range
        height, the Phase-C undercut depth, and the right-side breakout thrust.
    Both are derived views composed from the bricks below — no new measurement.
    """
    # Phase A — the root swing
    climax_bar: int
    ar_bar: int                  # automatic-reaction low; A ends and B opens here
    R: float
    S: float
    # Phase B — the equilibrium (opens at the box start, ends at the terminator)
    phase_b_start_bar: int
    phase_b_end_bar: int         # where B ends = the spring tip, else the LPS start
    box_width: float
    # The parent equilibrium brick — carries the rich measured fields (touches,
    # breach, anchors, traversal) consumers need beyond the phase boundaries.
    box: Any
    # The tighter Phase-D mini-consolidation found in the parent's vicinity (VCP
    # inner range), or None. Nesting is TEMPORAL, not price-bounded: the inner
    # forms its own R/S and commonly sits ON the parent's R, treating it as its
    # new Support. The LPS triggers off this when it is tighter.
    inner: Optional[Any]
    # Phase C — the spring (None for a clean A->B->D base; we don't force it)
    spring: Optional[Any]
    # Phase D — anchored at the LPS minimum; runs to the right edge. ``lps`` is the
    # WINNING brick (inner-box LPS when tighter, else parent); ``lps_in_inner``
    # records which, mirroring legacy's trigger selection.
    lps: Any
    lps_in_inner: bool
    phase_d_start_bar: int
    phase_d_source: str
    phase_d_evidence: dict
    terminator: str              # "spring" | "lps" — what ended Phase B (provenance)

    @property
    def has_spring(self) -> bool:
        return self.spring is not None

    @property
    def horizontal(self) -> dict:
        """The range read along the TIME axis — how the base builds out in time:
        duration, rail tests, and whether the swing limbs travel rail-to-rail (vs.
        hang off one side and leave dead space). Composed from the Phase-B box
        (and inner box / spring when present); reads no bars, measures nothing new."""
        box = self.box
        return {
            "base_len": int(getattr(box, "base_len", self.phase_b_end_bar - self.phase_b_start_bar)),
            "r_touches": int(getattr(box, "r_touches", 0)),
            "s_touches": int(getattr(box, "s_touches", 0)),
            "full_traversals": int(getattr(box, "n_full_traversals", 0)),
            "traversal_density": float(getattr(box, "traversal_density", 0.0)),
            "breach_days": int(getattr(box, "breach_days", 0)),
            "lps_shelf_len": int(getattr(self.lps, "length", 0)),
            "lps_offset": int(getattr(self.lps, "offset", 0)),
            "inner_base_len": int(self.inner.base_len) if self.inner is not None else None,
            "spring_time_loc": float(self.spring.time_loc) if self.spring is not None else None,
        }

    @property
    def vertical(self) -> dict:
        """The price-axis read — the magnitudes of the moves: the rail levels, the
        range height, the Phase-C undercut depth below support, and the right-side
        thrust above resistance. Composed from the box / spring / LPS bricks; reads
        no bars, measures nothing new."""
        r = float(self.R)
        height = float(self.box_width)
        return {
            "R": r,
            "S": float(self.S),
            "box_height": height,
            "box_height_pct": height / r if r else 0.0,
            "spring_undercut_atr": float(self.spring.undercut_atr) if self.spring is not None else None,
            "lps_descent_frac": float(getattr(self.lps, "descent_frac", 0.0)),
            "right_side_extension_atr": float(getattr(self.lps, "high_extension_atr", 0.0)),
            "right_side_extension_box": float(getattr(self.lps, "high_extension_box", 0.0)),
            "inner_box_height": float(self.inner.box_width) if self.inner is not None else None,
        }


def _box_base_len(df, box) -> int:
    base_len = getattr(box, "base_len", None)
    if base_len is not None:
        return int(base_len)
    return len(df) - int(box.start_bar)


def _range_threshold(df, active_box, atr: float) -> Optional[float]:
    """Guard wrapper: None-routing stays here; the yardstick itself is the one
    ``lps_range_threshold`` (its spread read falls back to High-Low itself)."""
    if df is None or "High" not in df.columns or "Low" not in df.columns:
        return None
    base_df = df.iloc[int(active_box.start_bar):]
    if base_df.empty:
        return None
    return lps_range_threshold(base_df, atr)


def _support_evidence_starts(df, atr, box, active_box, *, inner_present: bool):
    empty = {"support_tests": None, "sos_reclaim": None, "rising_support": None}
    if inner_present or df is None or len(df) == 0:
        return empty
    required = {"High", "Low", "Close", "Volume", "Vol_50"}
    if not (required <= set(df.columns)):
        return empty
    threshold = _range_threshold(df, active_box, float(atr))
    if threshold is None:
        return empty
    work_df = df if "Spread" in df.columns else df.assign(Spread=df["High"] - df["Low"])
    try:
        swing_complete_idx = max(int(active_box.r_anchor_bar), int(active_box.s_anchor_bar))
    except (AttributeError, TypeError, ValueError):
        return empty
    lps_tests = detect_lps_tests(
        work_df,
        work_df.iloc[-1],
        active_box.S,
        active_box.R,
        float(atr),
        threshold,
        _box_base_len(work_df, active_box),
        swing_complete_idx,
    )
    return support_test_evidence_starts(
        lps_tests,
        int(box.start_bar),
        _box_base_len(work_df, box),
    )


def _phase_d_boundary(df, atr, box, inner, spring, lps, lps_in_inner):
    if df is None or len(df) == 0:
        last = max(int(lps.start_bar), int(getattr(box, "start_bar", 0)))
        v_tip = None
        support_start = None
    else:
        last = len(df) - 1
        v_tip = (
            None if inner is not None
            else final_v_tip_bar(df, int(box.start_bar), _box_base_len(df, box))
        )
        active_box = inner if lps_in_inner and inner is not None else box
        evidence_starts = _support_evidence_starts(
            df, atr, box, active_box, inner_present=inner is not None,
        )
        support_start = evidence_starts["support_tests"]

    return resolve_phase_d_boundary(
        last=last,
        has_lps_window=True,
        lps_start=int(lps.start_bar),
        b=int(box.start_bar),
        phase_c_recovery_bar=(int(spring.recovery_bar) if spring is not None else None),
        phase_d_start_bar=(int(inner.start_bar) if inner is not None else None),
        v_tip_bar=v_tip,
        support_test_start_bar=support_start,
        sos_reclaim_start_bar=(evidence_starts["sos_reclaim"] if df is not None and len(df) else None),
        rising_support_start_bar=(evidence_starts["rising_support"] if df is not None and len(df) else None),
        search_start_bar=(int(inner.search_start_bar) if inner is not None else None),
    )


def _box_brief(box) -> Optional[dict]:
    """Duck-typed snapshot of an equilibrium/inner box for the narrative trace."""
    if box is None:
        return None
    return {
        "R": round(float(box.R), 4),
        "S": round(float(box.S), 4),
        "start_bar": int(box.start_bar),
        "box_width": round(float(box.box_width), 4),
        "base_len": int(getattr(box, "base_len", 0)),
        "n_full_traversals": int(getattr(box, "n_full_traversals", 0)),
        "traversal_density": round(float(getattr(box, "traversal_density", 0.0)), 3),
        "r_touches": int(getattr(box, "r_touches", 0)),
        "s_touches": int(getattr(box, "s_touches", 0)),
    }


def _spring_brief(spring) -> Optional[dict]:
    if spring is None:
        return None
    return {
        "tip_bar": int(spring.tip_bar),
        "recovery_bar": int(getattr(spring, "recovery_bar", -1)),
        "undercut_atr": round(float(getattr(spring, "undercut_atr", 0.0)), 2),
    }


def _lps_brief(lps, in_inner: bool) -> Optional[dict]:
    if lps is None:
        return None
    return {
        "in_inner": bool(in_inner),
        "start_bar": int(lps.start_bar),
        "low_bar": int(getattr(lps, "low_bar", -1)),
        "length": int(getattr(lps, "length", 0)),
        "offset": int(getattr(lps, "offset", 0)),
        "zone_type": getattr(lps, "zone_type", None),
        "swing_type": getattr(lps, "swing_type", None),
        "trigger": round(float(getattr(lps, "trigger", 0.0)), 2),
    }


def _tape_brief(df, box, atr) -> Optional[dict]:
    """Compact Event Map swing-map summary for a trace record. Trace-only —
    the import and the pivot walk are paid only when the caller is tracing."""
    if df is None or box is None:
        return None
    from engine_alpha.structure.event_map import read_swing_map
    tape = read_swing_map(df, box, atr)
    return {
        "n_swings": int(tape["n_swings"]),
        "pre_box_trend": tape["pre_box"]["trend_state"],
        "box_trend": tape["box"]["trend_state"],
    }


def _roles_brief(df, box, atr, spring, lps) -> Optional[dict]:
    """Compact Event Map role-label summary over the ELECTED bricks. Trace-only."""
    if df is None or box is None:
        return None
    from engine_alpha.structure.event_map import read_role_labels
    roles = read_role_labels(df, box, atr, spring=spring, lps=lps)
    return {
        "n_labels": int(roles["n_labels"]),
        "n_committed": sum(1 for lbl in roles["labels"] if not lbl["in_progress"]),
    }


def _lps_reject_brief(bricks, df, box, inner, atr) -> dict:
    """Why did Phase D fail? Re-run the LPS detector in diagnose mode on each
    candidate box and report the reject counters. Trace-only (never on the live
    path), so it can afford the extra detector passes."""
    out: dict = {}
    if inner is not None:
        res = bricks.find_lps(df, inner, atr, diagnose=True)
        rej = res[1] if isinstance(res, tuple) else None
        out["inner"] = dict(rej) if rej else {}
    res = bricks.find_lps(df, box, atr, diagnose=True)
    rej = res[1] if isinstance(res, tuple) else None
    out["parent"] = dict(rej) if rej else {}
    return out


def read_structure(df, atr, *, bricks=None, trace=None) -> Optional[Structure]:
    """Walk candidate root swings oldest-first; return the first that yields a
    complete A -> B -> (C?) -> D narrative, or ``None`` if no coherent story holds.

    ``bricks`` is the brick-validator provider; it defaults to the real
    ``engine_alpha.structure.bricks`` (the calibrated detectors). Inject a fake to
    unit-test the orchestration in isolation.

    ``trace``: pass a list to record the story the spine builds — one entry per
    root attempted, with each brick's verdict + (on failure) the reject reasons,
    and the outcome ("no_box" / "no_lps" / "complete"). Each entry also carries
    ``box_cascade``: the pair election narrating itself — every candidate R/S
    pair examined inside ``validate_equilibrium`` with the stage that rejected
    it (width / window / respect / occupancy / traversal / rescue_unused), or
    "elected" (stage "selection") for the winner. This
    is the Root-Swing cascade of the Reading Model (strategy_alpha.md) made
    explicit. Each record with an elected box also carries a compact Event Map
    ``tape`` summary (swing count + pre-box/box trend), and a complete story a
    ``roles`` summary over the elected bricks — audit context riding the same
    per-root records, computed only when tracing. Default ``None`` = no trace,
    zero behaviour change (the live path never pays for it). This is the engine
    explaining its own walk, so consumers stop re-deriving it externally.
    """
    if bricks is None:
        from engine_alpha.structure import bricks  # noqa: PLC0415 — lazy: real validators

    search_from = 0
    for i in range(_MAX_ANCHORS):
        # Phase A: the next root swing at/after the cursor (oldest-first = longest cause).
        root = bricks.find_root_swing(df, search_from_bar=search_from, atr=atr)
        if root is None:
            return None                                   # no more limbs -> no structure
        # Backtrack target: the next pair of limbs, so a failed story advances.
        search_from = int(root.climax_bar) + 1

        rec = None
        if trace is not None:
            rec = {
                "root_index": i,
                "climax_bar": int(root.climax_bar),
                "ar_bar": int(root.ar_bar),
                "kind": getattr(root, "kind", None),
                "reaction_pct": round(float(getattr(root, "reaction_pct", 0.0)), 3),
                "box": None, "box_cascade": None, "spring": None, "inner": None,
                "lps": None, "lps_rejects": None, "outcome": None,
                "tape": None, "roles": None,
            }
            trace.append(rec)

        # Phase B: is the region a genuinely worked equilibrium? When tracing,
        # the pair election narrates its cascade — every candidate R/S pair
        # examined, the gate that rejected it, and why the winner was elected.
        if rec is not None:
            cascade: list = []
            box = bricks.validate_equilibrium(df, root, atr, trace=cascade)
            rec["box_cascade"] = cascade
        else:
            box = bricks.validate_equilibrium(df, root, atr)
        if box is None:
            if rec is not None:
                rec["outcome"] = "no_box"
            continue                                      # not a worked range -> backtrack
        if rec is not None:
            rec["box"] = _box_brief(box)
            rec["tape"] = _tape_brief(df, box, atr)

        # Phase C (optional) and the nested Phase-D mini-range (tighter trigger).
        spring = bricks.find_spring(df, box, atr)          # don't force it; may be None
        inner = bricks.find_inner_box(df, box, atr)
        if rec is not None:
            rec["spring"] = _spring_brief(spring)
            rec["inner"] = _box_brief(inner)

        # Phase D (required): prefer the tighter inner-box LPS (closer trigger /
        # stop), else the parent. Reject only when NEITHER yields one — the same
        # inner-first-then-parent selection legacy does.
        lps_in_inner = False
        lps = None
        if inner is not None:
            lps = bricks.find_lps(df, inner, atr)
            lps_in_inner = lps is not None
        if lps is None:
            lps = bricks.find_lps(df, box, atr)
        if lps is None:
            if rec is not None:
                rec["outcome"] = "no_lps"
                rec["lps_rejects"] = _lps_reject_brief(bricks, df, box, inner, atr)
            continue                                      # no Phase-D minimum -> not a setup
        if rec is not None:
            rec["lps"] = _lps_brief(lps, lps_in_inner)
            rec["outcome"] = "complete"
            rec["roles"] = _roles_brief(df, box, atr, spring, lps)

        # Phase A is the LOCAL root swing of THIS box — the climax -> AR bridge
        # whose reaction low lands at the box start, not the distant trend anchor
        # that merely seeded the search. Legacy patched this after the fact with
        # _resolve_phase_a_swing; in the narrative it's part of the story.
        climax_bar, ar_bar = bricks.resolve_phase_a(df, root, box, atr)

        # Cause before effect: a box may not be elected over a live trend that
        # never matured a cause (the MIDD class — price trends UP through both
        # rails into a blow-off, so the consolidation predates its own climax).
        # cause_maturity vetoes ONLY when ALL THREE reads agree the cause is
        # absent: the macro bridge abstains AND the HH/HL staircase reads up/up
        # each side of the box open AND the elected LPS shelf never tightened
        # (the AND-narrowing third leg that rescues tight-shelf winners).
        # ABSTAIN with return None, not continue: the box is emergent
        # (the same R/S wins from many later roots), so backtracking would
        # re-elect the identical causeless geometry — abstaining is the
        # operator's "no setup at all". Flag-gated: OFF -> the block is dead, no
        # call, zero cost, byte-identical.
        if settings.CAUSE_BEFORE_EFFECT_VETO_ENABLED:
            cause = bricks.cause_maturity(df, box, atr, lps)
            if not cause.matured:
                if rec is not None:
                    rec["outcome"] = "cause_absent"
                    rec["cause"] = {
                        "bridge_validated": cause.bridge_validated,
                        "pre_box_trend": cause.pre_box_trend,
                        "box_trend": cause.box_trend,
                        "lps_tightness_ratio": cause.lps_tightness_ratio,
                    }
                return None

        # Phase B ends at the FIRST terminator: the spring tip if there is one,
        # else the LPS start. Phase D opens at the best right-side evidence we
        # have, with the LPS as mandatory fallback.
        if spring is not None:
            phase_b_end = int(spring.tip_bar)
            terminator = "spring"
        else:
            phase_b_end = int(lps.start_bar)
            terminator = "lps"
        phase_d = _phase_d_boundary(df, atr, box, inner, spring, lps, lps_in_inner)
        phase_d_start = int(phase_d.start_bar)

        return Structure(
            climax_bar=int(climax_bar),
            ar_bar=int(ar_bar),
            R=float(box.R),
            S=float(box.S),
            phase_b_start_bar=int(box.start_bar),
            phase_b_end_bar=phase_b_end,
            box_width=float(box.box_width),
            box=box,
            inner=inner,
            spring=spring,
            lps=lps,
            lps_in_inner=lps_in_inner,
            phase_d_start_bar=phase_d_start,
            phase_d_source=phase_d.source,
            phase_d_evidence=phase_d.evidence,
            terminator=terminator,
        )

    return None
