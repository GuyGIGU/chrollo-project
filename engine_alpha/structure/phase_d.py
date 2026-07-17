"""Shared Phase-D boundary evidence.

Phase D is the right-side campaign where the setup becomes actionable. The LPS
is mandatory proof that a setup exists now, but it is not always the earliest
structural start of Phase D. This module ranks available right-side evidence
and falls back to the LPS only when no richer anchor is present.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from config import settings
# Canonical monotonicity metric — reused so the DRAWN trim is consistent with
# the engine's reported ``descent_frac`` (lps is a leaf module; no import cycle).
from engine_alpha.structure.market_structure import _pairwise_descent_fraction


@dataclass(frozen=True)
class PhaseDEvidence:
    source: str
    start_bar: int
    end_bar: Optional[int] = None
    quality: Optional[float] = None
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "start_bar": int(self.start_bar),
            "end_bar": int(self.end_bar) if self.end_bar is not None else None,
            "quality": float(self.quality) if self.quality is not None else None,
            "meta": dict(self.meta or {}),
        }


@dataclass(frozen=True)
class PhaseDBoundary:
    start_bar: Optional[int]
    source: Optional[str]
    evidence: dict = field(default_factory=dict)


PHASE_D_EVIDENCE_SOURCES = (
    "support_tests",
    "rising_support",
    "sos_reclaim",
    "inner_box",
    "v_tip",
    "lps",
)

# Earliest credible evidence wins; this rank only breaks same-bar ties.
_EVIDENCE_RANK = {
    "support_tests": 0,
    "sos_reclaim": 1,
    "rising_support": 2,
    "inner_box": 3,
    "v_tip": 4,
    "lps": 5,
}


def _clamp_start(start: int, *, last: int, b: Optional[int]) -> int:
    out = max(0, min(int(start), int(last)))
    if b is not None and out < b:
        out = int(b)
    return out


def _phase_d_evidence(source: str, bar: Optional[int], *, end_bar: Optional[int] = None,
                      quality: Optional[float] = None, **meta) -> Optional[PhaseDEvidence]:
    if bar is None:
        return None
    try:
        return PhaseDEvidence(
            source=source,
            start_bar=int(bar),
            end_bar=int(end_bar) if end_bar is not None else None,
            quality=float(quality) if quality is not None else None,
            meta={k: v for k, v in meta.items() if v is not None},
        )
    except (TypeError, ValueError):
        return None


def support_test_evidence_starts(lps_tests, box_start: int, base_len: int) -> dict[str, Optional[int]]:
    """Classify right-side LPS/Test candidates into Phase-D evidence starts."""
    out = {"support_tests": None, "sos_reclaim": None, "rising_support": None}
    if not lps_tests:
        return out

    right_half = int(box_start) + int(base_len) // 2
    tests = []
    for test in lps_tests:
        try:
            start = int(test["start_index"])
            low = float(test["low"])
        except (KeyError, TypeError, ValueError):
            continue
        if start < right_half:
            continue
        tests.append({
            "start": start,
            "end": int(test.get("end_index", start + 1)),
            "low": low,
            "zone": test.get("zone_type"),
            "pullback_profile": test.get("pullback_profile"),
        })
    tests.sort(key=lambda t: t["start"])
    if not tests:
        return out

    starts = [t["start"] for t in tests]
    if len(starts) >= 2:
        out["support_tests"] = min(starts)

    sos = [t["start"] for t in tests if t["zone"] == "OVERSHOOT_R"]
    if sos:
        out["sos_reclaim"] = min(sos)

    # Evidence-only rising support: two or more right-side tests whose terminal
    # lows step up. This does not validate a setup; the active LPS remains the
    # gate underneath it.
    run = [tests[0]]
    best_run = []
    for test in tests[1:]:
        if test["low"] >= run[-1]["low"] * 0.995:
            run.append(test)
        else:
            if len(run) > len(best_run):
                best_run = run
            run = [test]
    if len(run) > len(best_run):
        best_run = run
    if len(best_run) >= 2:
        out["rising_support"] = int(best_run[0]["start"])
    return out


def drawn_support_tests(
    lps_tests,
    *,
    right_floor_bar: Optional[int],
    min_descent_frac: float,
) -> list:
    """Filter the support-test staircase down to what should be DRAWN on the chart.

    The staircase (``detect_lps_tests``) is measure-only — it does not elect the
    active LPS or gate firing — so this presentation filter is recall-safe by
    construction. It keeps only footprints that read as a genuine support test:

      * down or sideways into support — ``descent_frac >= min_descent_frac`` (a
        pure reaction is 1.0, sideways ~0.5; an up-swing / rising shelf is low and
        is dropped), and
      * on the right side — starting at/after ``right_floor_bar`` (the Phase-C
        spring recovery if a spring exists, else the final V-tip, else the
        inner-box Phase-D start). ``None`` means no right-side floor is known, so
        only the direction filter applies.

    The unfiltered ``lps_tests`` still feed the Phase-D boundary evidence
    (``support_test_evidence_starts``), which has its own right-half rule and
    legitimately uses rising-support runs — so that path is unchanged.
    """
    floor = None if right_floor_bar is None else int(right_floor_bar)
    threshold = float(min_descent_frac)
    out = []
    for test in lps_tests or []:
        try:
            start = int(test["start_index"])
            descent = float(test.get("descent_frac", 1.0))
        except (KeyError, TypeError, ValueError):
            continue
        if floor is not None and start < floor:
            continue
        if descent < threshold:
            continue
        out.append(test)
    return out


def drawn_lps_zone_start(low_values, *, min_descent_frac: float) -> int:
    """Offset into the elected LPS window where its DRAWN zone should start.

    The active LPS zone is the bounding box of the elected window's bars. For a
    rising shelf (an ascending-support pivot the election deliberately keeps —
    see ``LPS_MIN_DESCENT_FRAC = 0``), that window includes the climb INTO the
    shelf, so the drawn gold box reads as an up-swing. This trims the DRAWN start
    forward to the longest down/sideways suffix (pairwise low-descent fraction
    ``>= min_descent_frac``), so the highlight shows the reaction, not the run-up.

    Display-only and recall-safe: callers apply the returned offset to the zone's
    drawn start/low/high alone — the structural window (LPS length, V-tip, Phase-D
    boundary, every gate/score) is computed on the full window and never moves.
    Returns 0 (no trim) when the threshold is off, the full window already
    qualifies, no >=3-bar suffix qualifies, or the window is shorter than 4 bars.
    """
    threshold = float(min_descent_frac)
    if threshold <= 0.0:
        return 0
    n = len(low_values)
    if n < 4:
        return 0
    # Always leave >= 3 bars in the drawn suffix: shaving a valid shelf to a 2-bar
    # stub reads as "too aggressive" (operator feedback — one or two more bars
    # still fit the LPS definition).
    for start in range(0, n - 2):
        if _pairwise_descent_fraction(low_values[start:]) >= threshold:
            return start
    return 0


def _coerce_evidence_items(items: Optional[list[PhaseDEvidence | dict]]) -> list[PhaseDEvidence]:
    signals: list[PhaseDEvidence] = []
    for item in items or []:
        if isinstance(item, PhaseDEvidence):
            signals.append(item)
            continue
        if not isinstance(item, dict):
            continue
        ev = _phase_d_evidence(
            str(item.get("source")),
            item.get("start_bar"),
            end_bar=item.get("end_bar"),
            quality=item.get("quality"),
            **(item.get("meta") or {}),
        )
        if ev is not None:
            signals.append(ev)
    return signals


def resolve_phase_d_boundary(
    *,
    last: int,
    has_lps_window: bool,
    lps_start: Optional[int],
    b: Optional[int],
    phase_c_recovery_bar: Optional[int] = None,
    phase_d_start_bar: Optional[int] = None,
    v_tip_bar: Optional[int] = None,
    support_test_start_bar: Optional[int] = None,
    sos_reclaim_start_bar: Optional[int] = None,
    rising_support_start_bar: Optional[int] = None,
    search_start_bar: Optional[int] = None,
    evidence_items: Optional[list[PhaseDEvidence | dict]] = None,
) -> PhaseDBoundary:
    """Resolve where Phase D begins, and on what evidence.

    Spring recovery and search_start are floors only. Among right-side evidence
    at/after that floor, the earliest credible bar wins. The LPS minimum is the
    mandatory gate and fallback when no richer evidence sits after the floor.
    """
    floor_marks = [m for m in (phase_c_recovery_bar, search_start_bar) if m is not None]
    floor = max(int(m) for m in floor_marks) if floor_marks else (
        int(b) if b is not None else None)

    evidence = {
        "spring_recovery_bar": phase_c_recovery_bar,
        "search_start_bar": search_start_bar,
        "inner_box": phase_d_start_bar,
        "support_tests": support_test_start_bar,
        "sos_reclaim": sos_reclaim_start_bar,
        "rising_support": rising_support_start_bar,
        "v_tip": v_tip_bar,
        "lps": lps_start if has_lps_window else None,
        "floor": floor,
        "signals": [],
        "selected": None,
    }

    signals = _coerce_evidence_items(evidence_items)
    for source, bar in (
        ("support_tests", support_test_start_bar),
        ("sos_reclaim", sos_reclaim_start_bar),
        ("rising_support", rising_support_start_bar),
        ("inner_box", phase_d_start_bar),
        ("v_tip", v_tip_bar),
    ):
        ev = _phase_d_evidence(source, bar)
        if ev is not None and not any(
            s.source == ev.source and int(s.start_bar) == int(ev.start_bar)
            for s in signals
        ):
            signals.append(ev)
    if has_lps_window:
        ev = _phase_d_evidence("lps", lps_start)
        if ev is not None:
            signals.append(ev)
    evidence["signals"] = [s.as_dict() for s in signals]

    after_floor = []
    for signal in signals:
        if signal.source == "lps" or signal.source not in _EVIDENCE_RANK:
            continue
        bar = int(signal.start_bar)
        if floor is not None and bar < floor:
            continue
        after_floor.append((bar, _EVIDENCE_RANK[signal.source], signal))
    if after_floor:
        bar, _, signal = min(after_floor)
        selected_bar = _clamp_start(bar, last=last, b=b)
        evidence["selected"] = {**signal.as_dict(), "start_bar": selected_bar}
        return PhaseDBoundary(selected_bar, signal.source, evidence)

    if has_lps_window and lps_start is not None:
        start = int(lps_start)
        if floor is not None:
            start = max(start, floor)
        selected_bar = _clamp_start(start, last=last, b=b)
        evidence["selected"] = {
            "source": "lps",
            "start_bar": selected_bar,
            "end_bar": None,
            "quality": None,
            "meta": {"fallback": True},
        }
        return PhaseDBoundary(selected_bar, "lps", evidence)
    return PhaseDBoundary(None, None, evidence)


def final_v_tip_bar(df: pd.DataFrame, box_start: int, base_len: int) -> Optional[int]:
    """The deepest recovered Low in the late base: the tip of the final V."""
    n = len(df)
    if base_len <= 0 or n == 0:
        return None
    late = box_start + int(base_len * settings.PHASE_D_VTIP_LATE_FRACTION)
    start = max(late, box_start + 1)
    if start >= n - 1:
        return None
    lows = df["Low"].values
    highs = df["High"].values
    rec = settings.PHASE_D_VTIP_RECOVERY_BARS
    best_bar = None
    best_low = None
    for i in range(start, n - 1):
        if float(highs[i + 1:min(n, i + 1 + rec)].max()) <= float(highs[i]):
            continue
        low_i = float(lows[i])
        if best_low is None or low_i < best_low:
            best_bar, best_low = i, low_i
    return best_bar
