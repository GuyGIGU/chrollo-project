"""The chain coordinator — one reader re-consulted, the parent frozen.

Story-chain program Task 6 (docs/story_chain_program_2026-08.md; theory:
strategy_alpha.md "The chain grammar"). A chain is a story with a sequel: a
resolved parent structure, the displacement that resolved it, and a child
structure read AFTER it that inherits the parent's cause. The design laws,
each the answer to a measured failure:

* **ONE reader.** The child is read by ``narrative.read_structure`` — the
  same spine, the same calibrated bricks — through the spine's sanctioned
  injection seam: a provider that delegates EVERY brick to the real ones and
  serves exactly one new root, the displacement-root (the post-displacement
  run peak -> reaction pair, a mini climax->AR in the Reading Model's own
  fractal vocabulary). A sibling reader is the fork the One System rule
  forbids.
* **The parent is FROZEN as recorded constants.** Rails, span and resolution
  day are captured once, at the parent's own as-of frame, and carried as
  dates + absolute prices (positions never cross frames). Re-electing the
  parent on the longer child frame is the WCC defect — a wider frame elected
  a 2.2x-wider box.
* **As-of true.** The displacement-root reads only the skip-trimmed evidence
  (the collector's edge reserve): the run peak and reaction low visible on
  THIS frame — prefix extremes, never a hindsight-final value (EC-45; the
  first_legal_look lesson). The whole read is a pure function of the frame,
  so replay-at-T equals live-at-T by construction.
* **Inheritance is recorded, never silent.** The child's own cause verdict
  (the cause-before-effect read) is measured and RECORDED raw; the chain's
  law — the parent is the cause — satisfies the veto, with the raw verdict
  archived for the census so the inheritance rule itself stays measurable.

Parent SELECTION (stated here, implemented at the lane's enumeration —
program Task 9): when several resolved parents exist on one frame, the lane
takes the YOUNGEST parent whose resolution precedes the child window; ties
break on (later resolution date, earlier start date) — a stated
deterministic election, because in this engine election order-sensitivity IS
behavior.

Both displacement forms read: ``breakout_up`` (the child roots on the
post-breakout run peak -> reaction) and ``shakeout_down`` (the recovery view
— program Task 7 — adjudicates first, per the operator's law "what happens
next though is what's truly important"; a recovering tape then roots the
child on the recovery high -> pullback, the contracting seller pullback that
may legally sit below the old floor). Everything here is measure-only and
engine-internal: nothing serializes until the archive family lands (Task 8,
blocked on the operator's naming ruling).
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.bricks import RootSwing
from engine_alpha.structure.event_map import read_recovery_view
from engine_alpha.structure.htf import window_override
from engine_alpha.structure.narrative import Structure, read_structure

__all__ = [
    "ChainRead",
    "DISPLACEMENT_KINDS",
    "CHAIN_STATES",
    "FrozenParent",
    "displacement_root",
    "freeze_parent",
    "read_chain",
]

# Closed sets — internal, provisional pending the operator's naming ruling;
# they reach the archive/wire only through the Task-8 family.
DISPLACEMENT_KINDS = ("breakout_up", "shakeout_down")
CHAIN_STATES = ("child_elected", "child_refused", "no_displacement_root",
                "no_recovery")


@dataclass(frozen=True)
class FrozenParent:
    """The resolved parent as recorded constants — captured at the parent's
    OWN as-of frame, carried by dates + absolute prices, never re-derived."""
    R: float
    S: float
    base_len: int
    start_date: str          # ISO — the cross-frame identity axis
    resolution_date: str     # ISO — the displacement day
    kind: str                # DISPLACEMENT_KINDS


@dataclass
class ChainRead:
    """The composition: parent + displacement + child. The ``Structure`` atom
    is untouched — chain consumers get one coherent object, standalone
    consumers see zero change."""
    parent: FrozenParent
    displacement: Optional[dict]
    child: Optional[Structure]
    child_cause_raw: Optional[dict]   # the REAL cause verdict, recorded
    recovery: Optional[dict]          # the recovery view (shakeout_down form)
    state: str                        # CHAIN_STATES


def freeze_parent(df, structure, resolution_bar, kind) -> FrozenParent:
    """Capture the parent's identity VERBATIM from a ``Structure`` read at the
    parent's own as-of frame ``df``. ``resolution_bar`` is df-positional on
    THAT frame; only its date travels."""
    if kind not in DISPLACEMENT_KINDS:
        raise ValueError(
            f"unknown displacement kind {kind!r} — the closed set is "
            f"{'/'.join(DISPLACEMENT_KINDS)}")
    idx = df.index
    pbs = int(structure.phase_b_start_bar)
    return FrozenParent(
        R=float(structure.R),
        S=float(structure.S),
        base_len=int(getattr(structure.box, "base_len", len(df) - pbs)),
        start_date=str(pd.Timestamp(idx[pbs]).date()),
        resolution_date=str(pd.Timestamp(idx[int(resolution_bar)]).date()),
        kind=kind,
    )


def _locate_resolution(df, parent: FrozenParent):
    """(res, eval_end) — the parent's resolution day on THIS frame (by DATE;
    positions never cross frames) and the skip-trimmed read edge. None when
    the frame does not span the resolution or leaves no room after it."""
    pos = df.index.get_indexer([pd.Timestamp(parent.resolution_date)])
    res = int(pos[0])
    if res < 0:
        return None
    skip = int(settings.STRUCTURE_EDGE_SKIP_BARS)
    n = len(df)
    eval_end = n - skip if n > skip else n
    if res + 2 >= eval_end:
        return None
    return res, eval_end


def _root_off_peak(df, peak, peak_high, eval_end) -> Optional[RootSwing]:
    """The mini climax -> reaction pair off a given peak, under the house AR
    law VERBATIM (the one reaction arithmetic both displacement forms
    share): the argmin low within ``AR_MAX_BARS`` of the peak whose close
    confirmed ``AR_MIN_DROP_PCT``. None while no reaction has confirmed."""
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)
    j0 = int(peak) + 1
    j1 = min(int(eval_end), int(peak) + 1 + int(settings.AR_MAX_BARS))
    if j0 >= j1:
        return None
    thr = float(peak_high) * (1.0 - float(settings.AR_MIN_DROP_PCT))
    if float(closes[j0:j1].min()) > thr:
        return None                        # reaction never confirmed yet
    ar = j0 + int(np.argmin(lows[j0:j1]))
    low = float(lows[ar])
    return RootSwing(
        kind="BC",                         # a mini climax->reaction, up form
        climax_bar=int(peak),
        ar_bar=int(ar),
        R=float(peak_high),
        S=low,
        reaction_pct=round((float(peak_high) - low) / float(peak_high), 4),
        reaction_bars=int(ar - int(peak)),
    )


def displacement_root(df, parent: FrozenParent) -> Optional[RootSwing]:
    """The breakout_up form's injected brick: the post-breakout run peak ->
    reaction pair, read AS-OF this frame under the collector's edge reserve.

    The peak is the prefix argmax of the skip-trimmed window after the
    parent's resolution (what the walk can see today — a peak still rising
    means the child has not started, and the read honestly refuses); the
    reaction is ``_root_off_peak``'s house AR law."""
    located = _locate_resolution(df, parent)
    if located is None:
        return None
    res, eval_end = located
    highs = df["High"].to_numpy(dtype=float)
    peak = res + int(np.argmax(highs[res:eval_end]))
    peak_high = float(highs[peak])
    if peak_high <= float(parent.R):
        return None                        # the run never left the parent
    return _root_off_peak(df, peak, peak_high, eval_end)


def shakeout_root(df, parent: FrozenParent, atr):
    """The shakeout_down form: the recovery view adjudicates FIRST (the
    operator's law — depth never disqualifies; what forms afterwards does),
    then the child roots on the recovery high -> pullback pair, the
    contracting seller pullback. No altitude guard: a pullback below the old
    floor is legal by decree (the tactical long).

    Returns ``(root_or_None, recovery_dict)`` — the recovery read always
    travels, so a refusal states WHICH question refused (no recovery vs no
    confirmed pullback yet)."""
    located = _locate_resolution(df, parent)
    if located is None:
        return None, None
    res, eval_end = located
    recovery = read_recovery_view(df, parent.R, parent.S, res, atr)
    if recovery["character"] in (None, "none"):
        return None, recovery
    root = _root_off_peak(df, recovery["recovery_high_bar"],
                          recovery["recovery_high"], eval_end)
    return root, recovery


class _ChainBricks:
    """The spine's brick provider for a chain read: every brick delegates to
    the real provider; ``find_root_swing`` serves THE displacement-root once
    (a failed child story ends the walk — there is no other root to try);
    ``cause_maturity`` records the raw verdict and answers with the chain's
    inheritance law (the parent IS the cause), so the veto is satisfied
    honestly and the raw read stays measurable."""

    def __init__(self, real, root: RootSwing):
        self._real = real
        self._root = root
        self._served = False
        self.cause_log: list = []

    def find_root_swing(self, df, search_from_bar=0, atr=None):
        if self._served:
            return None
        self._served = True
        return self._root

    def validate_equilibrium(self, df, root, atr, **kw):
        return self._real.validate_equilibrium(df, root, atr, **kw)

    def find_spring(self, df, box, atr):
        return self._real.find_spring(df, box, atr)

    def find_inner_box(self, df, box, atr):
        return self._real.find_inner_box(df, box, atr)

    def find_lps(self, df, box, atr, **kw):
        return self._real.find_lps(df, box, atr, **kw)

    def resolve_phase_a(self, df, root, box, atr, terminal_floor=None):
        return self._real.resolve_phase_a(df, root, box, atr, terminal_floor)

    def cause_maturity(self, df, box, atr, lps=None):
        raw = self._real.cause_maturity(df, box, atr, lps)
        self.cause_log.append(raw)
        return SimpleNamespace(
            matured=True,
            bridge_validated=getattr(raw, "bridge_validated", None),
            pre_box_trend=getattr(raw, "pre_box_trend", None),
            box_trend=getattr(raw, "box_trend", None),
            lps_tightness_ratio=getattr(raw, "lps_tightness_ratio", None),
        )


def read_chain(df, atr, parent: FrozenParent, *, bricks=None,
               window_preset=None, trace=None) -> ChainRead:
    """Read the chain's child chapter on ``df`` against a frozen ``parent``.

    ``bricks`` injects a fake provider for spine testing (the
    ``read_structure`` convention); None = the real calibrated bricks.
    ``window_preset`` is an optional declared settings dict entered through
    the ONE scoped override (AP-10 ``window_override``) — the chain-scoped
    read floors are a CALIBRATION question the census answers against the
    operator's specimens, so none are invented here; the default runs under
    live settings (a young child will usually refuse on the live floors —
    honest, and exactly what the wall fixture pins).
    """
    recovery = None
    if parent.kind == "breakout_up":
        root = displacement_root(df, parent)
    elif parent.kind == "shakeout_down":
        root, recovery = shakeout_root(df, parent, atr)
        if root is None and recovery is not None and recovery["character"] == "none":
            return ChainRead(parent=parent, displacement=None, child=None,
                             child_cause_raw=None, recovery=recovery,
                             state="no_recovery")
    else:
        raise ValueError(
            f"unknown displacement kind {parent.kind!r} — the closed set is "
            f"{'/'.join(DISPLACEMENT_KINDS)}")
    if root is None:
        return ChainRead(parent=parent, displacement=None, child=None,
                         child_cause_raw=None, recovery=recovery,
                         state="no_displacement_root")
    if bricks is None:
        from engine_alpha.structure import bricks as real_bricks
        bricks = real_bricks
    provider = _ChainBricks(bricks, root)
    displacement = {
        "resolution_date": parent.resolution_date,
        "run_peak_bar": int(root.climax_bar),
        "run_peak_high": float(root.R),
        "reaction_low_bar": int(root.ar_bar),
        "reaction_low": float(root.S),
        "reaction_pct": float(root.reaction_pct),
        "separation": float(root.S) - float(parent.R),   # child seed low vs old ceiling
    }
    cm = window_override(window_preset) if window_preset else contextlib.nullcontext()
    with cm:
        child = read_structure(df, atr, bricks=provider, trace=trace)
    raw = provider.cause_log[-1] if provider.cause_log else None
    child_cause_raw = None if raw is None else {
        "matured": bool(getattr(raw, "matured", True)),
        "bridge_validated": getattr(raw, "bridge_validated", None),
        "pre_box_trend": getattr(raw, "pre_box_trend", None),
        "box_trend": getattr(raw, "box_trend", None),
        "lps_tightness_ratio": getattr(raw, "lps_tightness_ratio", None),
    }
    return ChainRead(
        parent=parent,
        displacement=displacement,
        child=child,
        child_cause_raw=child_cause_raw,
        recovery=recovery,
        state="child_elected" if child is not None else "child_refused",
    )
