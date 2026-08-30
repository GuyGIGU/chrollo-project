"""Correspondence census — do the THREE rail readers describe the same events?

Read-only, offline. For every operator CalibrationMark (verdict='box'), on the
operator's OWN drawn rails and drawn window (``tools.replay.drawn_box_window``,
the shared EC-13 derivation), run side by side:

  reader 1  event_map.read_rail_episodes + episode_sequence_stats
            -> rail EPISODES (ATR-fixed zones, TOUCH_TOLERANCE_ATR) + the
               profile sentence.
  reader 2  box_events.read_box_events / assemble_box_narrative
            -> the PUZZLE stack (box-relative zones, TRAVERSAL_LOW/HIGH_ZONE).
  reader 3  bricks.find_lps on the same drawn window
            -> the LPS FORM verdict (swing_type / zone_type) and where its rest
               sits in the box.

Then COMPARE reader 1 against reader 2 bar-span by bar-span, both directions,
and report where they disagree and whether the disagreement concentrates in
boxes whose ATR touch zones swallow the box (zone_coverage).

Committed as the ONE-Event-Map program's evidence instrument (PLAN Task 3):
the 2026-08-29 census that falsified a true fuse (77.7% strict agreement on
decided pairs, 22.3% contradiction; the merge-horizon and failed-referent
mechanisms) ran from a session scratchpad - this promotion makes those
numbers reproducible after the fold. Sidecar-only (EC-46); population +
fingerprint + manifest stamped (EC-13); --json passes the sealed-output
guard (EC-14).

REPRODUCIBILITY NOTE - two census-local conventions are deliberately FROZEN
even though later rulings superseded their design role; changing either
silently re-derives the recorded evidence:
  * ``_compatible`` is the census's own charitable semantic map (free
    passes on ambiguous/wildcard/open), not an engine artifact - the honest
    headline is the STRICT recomputation over decided pairs.
  * ``_five_way`` bands positions into five values; the operator's
    2026-08-29/30 rails-are-areas ruling collapsed the live vocabulary to
    THREE (``inner_box.mini_consolidation_position``). The five-way stays
    as the census's recorded measurement convention, never a live one.

Usage (the repo venv, from the repo root):
    python -m tools.correspondence_census [--ticker T] [--json OUT.json]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from types import SimpleNamespace

import numpy as np

try:  # works under both `python -m tools.correspondence_census` and direct
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_ROOT = configure_path(backend=True)

import database  # noqa: E402  binds the SQLite engine + SessionLocal

from config import settings  # noqa: E402
from webapp.backend import frame_store  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.box_events import (  # noqa: E402
    assemble_box_narrative,
    read_box_events,
)
from engine_alpha.structure.event_map import (  # noqa: E402
    episode_sequence_stats,
    read_rail_episodes,
)
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.calibration_stat_card import _num, _safe  # noqa: E402
from tools.replay import drawn_box_window  # noqa: E402


# ---------------------------------------------------------------------------
# The semantic dictionary between the two vocabularies
# ---------------------------------------------------------------------------
# Reader 1 says, per episode: rail (S|R) x outcome (completed|failed|open|
# unreadable). "completed" = the rail HELD (price engaged it and came back);
# "failed" = the rail GAVE WAY (the resolving close is beyond it).
#
# Reader 2 says, per event, a type from a 10-string closed set with no outcome
# field of its own. The map below is the honest translation of each type into
# the same held/gave/open axis, derived from the inventories:
#   R-rail: upthrust / rejection both END with price back under R -> R held.
#           SOS / markup both END with price holding at-or-above R -> R gave.
#           range (Phase B cause-building OR a loose Phase-D hold) -> ambiguous.
#           in_progress -> no verdict yet.
#   S-rail: test -> S held.  failed -> S gave.  in_progress -> no verdict.
#           spring -> a breach that RECLAIMED, which the episode reader also
#                     scores "completed" -> S held.
#           lps    -> not a rail verdict at all (a Phase-D rest) -> wildcard on S.
_PUZZLE_CLASS = {
    ("R", "upthrust"): "held",
    ("R", "rejection"): "held",
    ("R", "SOS"): "gave",
    ("R", "markup"): "gave",
    ("R", "range"): "ambiguous",
    ("R", "in_progress"): "open",
    ("S", "test"): "held",
    ("S", "failed"): "gave",
    ("S", "in_progress"): "open",
    ("S", "spring"): "held",
    ("S", "lps"): "wildcard",
}
_EPISODE_CLASS = {
    "completed": "held",
    "failed": "gave",
    "open": "open",
    "unreadable": "unreadable",
}
# Reader 2's brick families are not rail verdicts; the rail-family comparison
# excludes them but they are still reported.
_BRICK_TYPES = {"spring", "lps"}


def _episode_class(ep) -> str:
    cls = _EPISODE_CLASS.get(ep["outcome"], "?")
    # A terminal OPEN R episode whose last close is above R is the pre-breakout
    # stance — the rail has effectively given way at the right edge.
    if cls == "open" and ep.get("terminal_posture"):
        return "gave"
    return cls


def _compatible(pcls: str, ecls: str) -> bool:
    if pcls in ("ambiguous", "wildcard") or ecls == "unreadable":
        return True
    if pcls == "open" or ecls == "open":
        # an unresolved read on either side is not a conflict, only silence
        return True
    return pcls == ecls


def _overlap(a0, a1, b0, b1) -> bool:
    return a0 <= b1 and b0 <= a1


def _ep_word(ep) -> str:
    return (f"{ep['rail']}:{ep['outcome']}"
            + ("^" if ep.get("terminal_posture") else "")
            + f"[{ep['start_bar']}..{ep['end_bar']}]")


def _pz_word(e) -> str:
    return (f"{e.get('rail','?')}:{e['type']}"
            f"[{int(e['zone_start'])}..{int(e['zone_end'])}]"
            f"@{int(e.get('anchor_bar', e['zone_start']))}")


# ---------------------------------------------------------------------------
def census_mark(mark) -> dict:
    out = {
        "ticker": mark.ticker,
        "as_of": mark.as_of_date,
        "label": mark.label or "",
        "box_start": mark.box_start_date,
        "box_end": mark.box_end_date,
        "R": _num(mark.resistance),
        "S": _num(mark.support),
        "errors": [],
    }
    R, S = out["R"], out["S"]
    if R is None or S is None or not (R > S):
        out["errors"].append("no drawn rails")
        return out

    frozen = frame_store.load_frame(mark.ticker, mark.as_of_date,
                                    digest=mark.frame_digest)
    if frozen is None or frozen.empty:
        out["errors"].append("basis_mismatch: no frozen frame for this digest")
        return out
    try:
        window, atr = drawn_box_window(frozen, mark.box_start_date, mark.box_end_date)
    except ValueError as exc:
        out["errors"].append(str(exc))
        return out

    box_height = R - S
    out["bars"] = int(len(window))
    out["atr"] = round(float(atr), 4)
    out["box_width_atr"] = round(box_height / atr, 3)
    # The ATR-vs-box geometry ratio: how much of the box the two 0.5-ATR touch
    # zones cover between them. >= 1.0 means the zones swallow the whole box.
    out["zone_coverage"] = round(
        2.0 * settings.TOUCH_TOLERANCE_ATR * atr / box_height, 4)

    # --- reader 1: rail episodes ---------------------------------------
    read, err = _safe(read_rail_episodes, window, R, S, atr)
    episodes = []
    if err:
        out["errors"].append(f"episodes: {err}")
    elif isinstance(read, dict):
        episodes = list(read.get("episodes") or [])
        out["episode_nan_bars"] = int(read.get("nan_bars") or 0)
        st, err2 = _safe(episode_sequence_stats, read)
        if err2:
            out["errors"].append(f"episode_stats: {err2}")
        elif isinstance(st, dict):
            out["episode_profile"] = st.get("profile")
            for k in ("n_completed_s", "n_completed_r", "n_failed_s",
                      "alternations", "n_episodes", "terminal_r_posture",
                      "terminal_s_drift", "terminal_r_engagement"):
                v = st.get(k)
                if isinstance(v, bool):
                    out[k] = bool(v)
                elif isinstance(v, (int, float)):
                    out[k] = int(v)
    out["episodes"] = [
        {"rail": e["rail"], "outcome": e["outcome"],
         "start_bar": int(e["start_bar"]), "end_bar": int(e["end_bar"]),
         "n_bars": int(e["n_bars"]),
         "terminal_posture": bool(e.get("terminal_posture")),
         "in_progress": bool(e.get("in_progress"))}
        for e in episodes
    ]

    # --- reader 2: the puzzle stack ------------------------------------
    # box.start_bar = 0 so the puzzle's base frame IS the drawn window and both
    # readers share ONE bar origin. r/s_anchor_bar = 0 gives find_lps no
    # artificial start floor (the drawn window is the whole world here).
    box_ns = SimpleNamespace(start_bar=0, base_len=len(window), R=R, S=S,
                             r_anchor_bar=0, s_anchor_bar=0)
    pz, err = _safe(read_box_events, window, box_ns, atr)
    puzzle = []
    if err:
        out["errors"].append(f"box_events: {err}")
    elif isinstance(pz, list):
        puzzle = pz
    # how deep did price actually go inside each puzzle event's own span, in
    # BOX units (0 = S, 1 = R)?  This is the empirical check on WHAT each
    # reader's "failed" is measured against.
    w_lows = window["Low"].to_numpy(dtype=float)
    w_highs = window["High"].to_numpy(dtype=float)
    w_closes = window["Close"].to_numpy(dtype=float)

    def _span_stats(a, b):
        a, b = max(0, int(a)), min(len(window) - 1, int(b))
        if b < a:
            return None, None, None
        lo = float(np.nanmin(w_lows[a:b + 1]))
        hi = float(np.nanmax(w_highs[a:b + 1]))
        lc = float(np.nanmin(w_closes[a:b + 1]))
        return ((lo - S) / box_height, (hi - S) / box_height,
                (lc - S) / box_height)

    out["puzzle"] = []
    for e in puzzle:
        lo_pos, hi_pos, lc_pos = _span_stats(e["zone_start"], e["zone_end"])
        out["puzzle"].append({
            "type": e["type"], "rail": e.get("rail"),
            "zone_start": int(e["zone_start"]), "zone_end": int(e["zone_end"]),
            "anchor_bar": int(e.get("anchor_bar", e["zone_start"])),
            "resolution": e.get("resolution"),
            "phase": e.get("phase"),
            "swing_type": e.get("swing_type"),
            "valley_box_pos": e.get("valley_box_pos"),
            "peak_box_pos": e.get("peak_box_pos"),
            "span_min_low_box_pos": None if lo_pos is None else round(lo_pos, 3),
            "span_max_high_box_pos": None if hi_pos is None else round(hi_pos, 3),
            "span_min_close_box_pos": None if lc_pos is None else round(lc_pos, 3),
        })

    nar, err = _safe(assemble_box_narrative, window, box_ns, atr)
    if err:
        out["errors"].append(f"narrative: {err}")
    elif isinstance(nar, dict):
        out["completeness"] = int(nar.get("completeness") or 0)
        out["chronology"] = nar.get("chronology")
        out["n_held_tests"] = int(nar.get("tests") or 0)
        out["upthrust_terminal"] = bool(nar.get("upthrust_terminal"))

    # --- reader 3: the LPS form verdict on the drawn window -------------
    from engine_alpha.structure.bricks import find_lps  # leaf import
    lps, err = _safe(find_lps, window, box_ns, atr)
    if err:
        out["errors"].append(f"lps: {err}")
        out["lps_form"] = None
    elif lps is None:
        out["lps_form"] = None
        out["lps_note"] = "no LPS elects on the drawn window"
    else:
        low_pos = (float(lps.window_low) - S) / box_height
        out["lps_form"] = {
            "swing_type": lps.swing_type,
            "zone_type": lps.zone_type,
            "start_bar": int(lps.start_bar),
            "end_bar": int(lps.end_bar),
            "low_bar": int(lps.low_bar),
            "length": int(lps.length),
            # WHERE the rest sits, in box units (0 = S, 1 = R)
            "window_low_box_pos": round(low_pos, 3),
            "window_high_box_pos": round(
                (float(lps.window_high) - S) / box_height, 3),
            # the operator's five-way position, derived here for the census only
            "position_5way": _five_way(float(lps.window_low), R, S, atr),
        }

    # --- the correspondence --------------------------------------------
    rail_puzzle = [e for e in puzzle if e["type"] not in _BRICK_TYPES]
    pz_rows, ep_rows = [], []

    for e in puzzle:
        rail = e.get("rail")
        pcls = _PUZZLE_CLASS.get((rail, e["type"]), "?")
        a0, a1 = int(e["zone_start"]), int(e["zone_end"])
        same_rail, any_rail, agreeing = [], [], []
        for j, ep in enumerate(episodes):
            if not _overlap(a0, a1, int(ep["start_bar"]), int(ep["end_bar"])):
                continue
            any_rail.append(j)
            if ep["rail"] == rail:
                same_rail.append(j)
                if _compatible(pcls, _episode_class(ep)):
                    agreeing.append(j)
        pz_rows.append({
            "word": _pz_word(e), "type": e["type"], "rail": rail,
            "class": pcls, "brick": e["type"] in _BRICK_TYPES,
            "matched_same_rail": bool(same_rail),
            "matched_any_rail": bool(any_rail),
            "semantically_agrees": bool(agreeing),
            "episode_words": [_ep_word(episodes[j]) for j in same_rail],
            "cross_rail_words": [_ep_word(episodes[j])
                                 for j in any_rail if j not in same_rail],
        })

    for ep in episodes:
        b0, b1 = int(ep["start_bar"]), int(ep["end_bar"])
        ecls = _episode_class(ep)
        same_rail, any_rail, agreeing = [], [], []
        for i, e in enumerate(puzzle):
            if not _overlap(b0, b1, int(e["zone_start"]), int(e["zone_end"])):
                continue
            any_rail.append(i)
            if e.get("rail") == ep["rail"]:
                same_rail.append(i)
                if _compatible(_PUZZLE_CLASS.get((e.get("rail"), e["type"]), "?"),
                               ecls):
                    agreeing.append(i)
        ep_rows.append({
            "word": _ep_word(ep), "rail": ep["rail"], "outcome": ep["outcome"],
            "class": ecls,
            "matched_same_rail": bool(same_rail),
            "matched_any_rail": bool(any_rail),
            "matched_rail_family_only": bool(
                [i for i in same_rail if puzzle[i]["type"] not in _BRICK_TYPES]),
            "semantically_agrees": bool(agreeing),
            "puzzle_words": [_pz_word(puzzle[i]) for i in same_rail],
        })

    out["pz_rows"] = pz_rows
    out["ep_rows"] = ep_rows
    out["n_puzzle"] = len(puzzle)
    out["n_puzzle_rail"] = len(rail_puzzle)
    out["n_episodes_list"] = len(episodes)
    out["pz_matched"] = sum(1 for r in pz_rows if r["matched_same_rail"])
    out["pz_matched_rail_family"] = sum(
        1 for r in pz_rows if r["matched_same_rail"] and not r["brick"])
    out["pz_agree"] = sum(1 for r in pz_rows if r["semantically_agrees"])
    out["ep_matched"] = sum(1 for r in ep_rows if r["matched_same_rail"])
    out["ep_matched_rail_family"] = sum(
        1 for r in ep_rows if r["matched_rail_family_only"])
    out["ep_agree"] = sum(1 for r in ep_rows if r["semantically_agrees"])
    return out


def _five_way(price, R, S, atr) -> str:
    """The operator's five-way position, banded here ONLY for this census
    (0.5-ATR rail bands, box-relative 'high in the range' at 0.70)."""
    tol = settings.TOUCH_TOLERANCE_ATR * atr
    if price > R + tol:
        return "A_above_resistance"
    if price >= R - tol:
        return "B_at_resistance"
    if price < S - tol:
        return "E_below_support"
    if price <= S + tol:
        return "D_on_support"
    if (price - S) / (R - S) >= settings.TRAVERSAL_HIGH_ZONE:
        return "C_high_in_range"
    return "mid_range"


# ---------------------------------------------------------------------------
def print_mark(c: dict):
    hdr = f"{c['ticker']} @ {c['as_of']}"
    if c["label"]:
        hdr += f" [{c['label']}]"
    print("=" * 96)
    print(hdr)
    if c["errors"]:
        print("  ! " + "; ".join(c["errors"]))
    if "bars" not in c:
        return
    print(f"  box {c['box_start']}..{c['box_end']}  R={c['R']} S={c['S']}"
          f"  bars={c['bars']}  boxATR={c['box_width_atr']}"
          f"  zone_coverage={c['zone_coverage']}"
          + ("   << ATR zones SWALLOW the box" if c["zone_coverage"] >= 1.0
             else ("   << over the STORY_UNREADABLE floor"
                   if c["zone_coverage"] >= settings.STORY_UNREADABLE_ZONE_COVERAGE
                   else "")))
    print(f"  R1 sentence : {c.get('episode_profile') or '-'}"
          f"   ({c.get('n_episodes_list', 0)} episodes)")
    print(f"  R2 narrative: completeness={c.get('completeness')}"
          f"/4 chronology={c.get('chronology')} heldTests={c.get('n_held_tests')}"
          f"  ({c.get('n_puzzle', 0)} events, {c.get('n_puzzle_rail', 0)} rail-family)")
    lf = c.get("lps_form")
    if lf:
        print(f"  R3 LPS form : {lf['swing_type']} / {lf['zone_type']}"
              f"  bars[{lf['start_bar']}..{lf['end_bar']}]"
              f"  low_box_pos={lf['window_low_box_pos']}"
              f"  position={lf['position_5way']}")
    else:
        print(f"  R3 LPS form : - ({c.get('lps_note', 'unavailable')})")
    print(f"  correspondence: puzzle {c['pz_matched']}/{c['n_puzzle']} matched"
          f" ({c['pz_agree']} agree)   episodes {c['ep_matched']}"
          f"/{c['n_episodes_list']} matched ({c['ep_agree']} agree)")
    for r in c["pz_rows"]:
        if r["matched_same_rail"] and r["semantically_agrees"]:
            continue
        tag = "CONFLICT" if r["matched_same_rail"] else "UNSEEN-BY-R1"
        extra = ""
        if r["episode_words"]:
            extra = " vs " + ",".join(r["episode_words"])
        elif r["cross_rail_words"]:
            extra = " (only cross-rail: " + ",".join(r["cross_rail_words"]) + ")"
        print(f"    [{tag:12}] R2 {r['word']:34}{extra}")
    for r in c["ep_rows"]:
        if r["matched_same_rail"] and r["semantically_agrees"]:
            continue
        tag = "CONFLICT" if r["matched_same_rail"] else "UNSEEN-BY-R2"
        extra = (" vs " + ",".join(r["puzzle_words"])) if r["puzzle_words"] else ""
        print(f"    [{tag:12}] R1 {r['word']:34}{extra}")


def _pearson(xs, ys):
    if len(xs) < 3:
        return None
    ax, ay = np.array(xs, dtype=float), np.array(ys, dtype=float)
    if ax.std() == 0 or ay.std() == 0:
        return None
    return float(np.corrcoef(ax, ay)[0, 1])


def _rank(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def print_aggregate(cards):
    good = [c for c in cards if "bars" in c]
    print("\n" + "=" * 96)
    print(f"AGGREGATE  (n={len(good)} measurable marks of {len(cards)})")
    print("=" * 96)
    if not good:
        return

    tp = sum(c["n_puzzle"] for c in good)
    tpm = sum(c["pz_matched"] for c in good)
    tpa = sum(c["pz_agree"] for c in good)
    te = sum(c["n_episodes_list"] for c in good)
    tem = sum(c["ep_matched"] for c in good)
    tea = sum(c["ep_agree"] for c in good)
    tpr = sum(c["n_puzzle_rail"] for c in good)
    tprm = sum(c["pz_matched_rail_family"] for c in good)
    term = sum(c["ep_matched_rail_family"] for c in good)

    print(f"  puzzle events        : {tp:4d}   span-matched by an episode "
          f"(same rail): {tpm:4d} ({tpm / tp:.1%})   semantically agreeing: "
          f"{tpa:4d} ({tpa / tp:.1%})")
    print(f"   ... rail-family only: {tpr:4d}   span-matched: {tprm:4d} "
          f"({tprm / max(tpr, 1):.1%})")
    print(f"  rail episodes        : {te:4d}   span-matched by a puzzle event "
          f"(same rail): {tem:4d} ({tem / te:.1%})   semantically agreeing: "
          f"{tea:4d} ({tea / te:.1%})")
    print(f"   ... matched by a RAIL-FAMILY puzzle event (not spring/lps): "
          f"{term:4d} ({term / max(te, 1):.1%})")

    # type-level cross tab
    print("\n  Where the puzzle types land against the episode reader:")
    by_type = {}
    for c in good:
        for r in c["pz_rows"]:
            k = f"{r['rail']}:{r['type']}"
            d = by_type.setdefault(k, [0, 0, 0])
            d[0] += 1
            d[1] += 1 if r["matched_same_rail"] else 0
            d[2] += 1 if r["semantically_agrees"] else 0
    print(f"    {'puzzle type':22} {'n':>4} {'matched':>8} {'agree':>7}")
    for k in sorted(by_type, key=lambda k: -by_type[k][0]):
        n, m, a = by_type[k]
        print(f"    {k:22} {n:>4} {m:>8} {a:>7}")

    print("\n  Where the episode outcomes land against the puzzle stack:")
    by_out = {}
    for c in good:
        for r in c["ep_rows"]:
            k = f"{r['rail']}:{r['outcome']}"
            d = by_out.setdefault(k, [0, 0, 0])
            d[0] += 1
            d[1] += 1 if r["matched_same_rail"] else 0
            d[2] += 1 if r["semantically_agrees"] else 0
    print(f"    {'episode':22} {'n':>4} {'matched':>8} {'agree':>7}")
    for k in sorted(by_out, key=lambda k: -by_out[k][0]):
        n, m, a = by_out[k]
        print(f"    {k:22} {n:>4} {m:>8} {a:>7}")

    # LPS form census
    print("\n  Reader 3 — LPS form verdicts on the drawn window:")
    forms = {}
    for c in good:
        lf = c.get("lps_form")
        key = (f"{lf['swing_type']} / {lf['zone_type']}" if lf else "(no LPS)")
        forms.setdefault(key, []).append(c)
    for k in sorted(forms, key=lambda k: -len(forms[k])):
        rows = forms[k]
        poss = {}
        for c in rows:
            lf = c.get("lps_form")
            if lf:
                poss[lf["position_5way"]] = poss.get(lf["position_5way"], 0) + 1
        pos_txt = ", ".join(f"{p}={n}" for p, n in sorted(poss.items()))
        print(f"    {k:42} n={len(rows):>3}   {pos_txt}")

    # conflict pair cross-tab: WHAT does each side call the same bars?
    print("\n  CONFLICTING pairs (same rail, overlapping bars, incompatible verdict):")
    pairs = {}
    for c in good:
        for r in c["pz_rows"]:
            if not r["matched_same_rail"] or r["semantically_agrees"]:
                continue
            for w in r["episode_words"]:
                k = (f"{r['rail']}:{r['type']}", w.split("[")[0])
                pairs[k] = pairs.get(k, 0) + 1
    print(f"    {'reader 2 says':22} {'reader 1 says':18} {'n':>4}")
    for (a, b), n in sorted(pairs.items(), key=lambda kv: -kv[1]):
        print(f"    {a:22} {b:18} {n:>4}")

    # EMPIRICAL check: what is each reader's "failed" measured against?
    print("\n  What does reader 2's S:failed actually do to the rail?"
          "  (box units: 0 = S, 1 = R)")
    lows, closes_, never = [], [], 0
    for c in good:
        halfbuf = c["zone_coverage"] / 2.0   # BOUNDARY_ATR_BUFFER*atr / (R-S)
        for r, p in zip(c["pz_rows"], c["puzzle"]):
            if not (r["rail"] == "S" and r["type"] == "failed"):
                continue
            if p["span_min_low_box_pos"] is not None:
                lows.append(p["span_min_low_box_pos"])
            if p["span_min_close_box_pos"] is not None:
                closes_.append(p["span_min_close_box_pos"])
                if p["span_min_close_box_pos"] > -halfbuf:
                    never += 1
    if lows:
        print(f"    n={len(lows)}   deepest LOW inside the event span: median "
              f"{statistics.median(lows):+.3f}  min {min(lows):+.3f}")
        print(f"    deepest CLOSE inside the span: median "
              f"{statistics.median(closes_):+.3f}  min {min(closes_):+.3f}")
        print(f"    events whose deepest close NEVER got below S - "
              f"BOUNDARY_ATR_BUFFER*ATR (the episode reader's breach test): "
              f"{never}/{len(closes_)}")
    print("\n  Where reader 2's R waves top out (box units, 1.0 = R):")
    for t in ("rejection", "upthrust", "markup", "SOS", "range"):
        vals = [p["peak_box_pos"] for c in good for r, p in
                zip(c["pz_rows"], c["puzzle"])
                if r["rail"] == "R" and r["type"] == t
                and p["peak_box_pos"] is not None]
        if vals:
            print(f"    R:{t:12} n={len(vals):>4}  peak_box_pos median "
                  f"{statistics.median(vals):.3f}  min {min(vals):.3f}"
                  f"  max {max(vals):.3f}")

    # R-episode merge: does the ATR zone collapse many puzzle waves into one?
    print("\n  The R-rail merge: episode spans vs puzzle wave counts")
    ep_r_bars, pz_r_per_ep = [], []
    for c in good:
        rep = [e for e in c["episodes"] if e["rail"] == "R"]
        rpz = [e for e in c["puzzle"] if e.get("rail") == "R"]
        for e in rep:
            ep_r_bars.append(e["n_bars"])
        if rep:
            pz_r_per_ep.append(len(rpz) / len(rep))
    if ep_r_bars:
        print(f"    R episodes: n={len(ep_r_bars)}  median span "
              f"{statistics.median(ep_r_bars):.0f} bars  max {max(ep_r_bars)} bars")
        print(f"    puzzle R events per R episode: median "
              f"{statistics.median(pz_r_per_ep):.2f}  max {max(pz_r_per_ep):.2f}")
    ep_s_bars = [e["n_bars"] for c in good for e in c["episodes"]
                 if e["rail"] == "S"]
    if ep_s_bars:
        print(f"    S episodes: n={len(ep_s_bars)}  median span "
              f"{statistics.median(ep_s_bars):.0f} bars  max {max(ep_s_bars)} bars")

    # zone_coverage concentration
    print("\n  Does disagreement concentrate in tight boxes (high zone_coverage)?")
    print(f"    PREDICTION from the geometry: the episode ATR half-zone covers"
          f" zone_coverage/2 of the box;\n     the puzzle high/low zone covers"
          f" {1 - settings.TRAVERSAL_HIGH_ZONE:.2f}. They coincide at"
          f" zone_coverage = {2 * (1 - settings.TRAVERSAL_HIGH_ZONE):.2f}."
          f"\n     BELOW that the ATR zone is NARROWER (reader 1 should miss"
          f" puzzle events); ABOVE it, WIDER.")
    rows = []
    for c in good:
        if c["n_puzzle"] == 0 and c["n_episodes_list"] == 0:
            continue
        denom = c["n_puzzle"] + c["n_episodes_list"]
        unmatched = ((c["n_puzzle"] - c["pz_matched"])
                     + (c["n_episodes_list"] - c["ep_matched"]))
        conflicts = (sum(1 for r in c["pz_rows"]
                         if r["matched_same_rail"] and not r["semantically_agrees"])
                     + sum(1 for r in c["ep_rows"]
                           if r["matched_same_rail"] and not r["semantically_agrees"]))
        rows.append((c["zone_coverage"], unmatched / denom, c["ticker"],
                     c["n_puzzle"], c["n_episodes_list"], conflicts / denom))
    rows.sort()
    zs = [r[0] for r in rows]
    us = [r[1] for r in rows]
    cs = [r[5] for r in rows]
    cut = 2 * (1 - settings.TRAVERSAL_HIGH_ZONE)
    below = [r for r in rows if r[0] < cut]
    above = [r for r in rows if r[0] >= cut]
    for name, grp in (("ATR zone NARROWER than the box zone (zone_cov < "
                       f"{cut:.2f})", below),
                      (f"ATR zone WIDER  than the box zone (zone_cov >= {cut:.2f})",
                       above)):
        if not grp:
            continue
        print(f"    {name}: n={len(grp)} marks   span-unmatched median "
              f"{statistics.median([r[1] for r in grp]):.1%}   "
              f"semantic-conflict median {statistics.median([r[5] for r in grp]):.1%}")
    pc = _pearson(zs, cs)
    sc = _pearson(_rank(zs), _rank(cs))
    print(f"    pearson r(zone_coverage, SEMANTIC conflict share) = "
          f"{'n/a' if pc is None else f'{pc:+.3f}'}"
          f"   spearman = {'n/a' if sc is None else f'{sc:+.3f}'}")
    print(f"    zone_coverage  median={statistics.median(zs):.3f}"
          f"  min={min(zs):.3f}  max={max(zs):.3f}"
          f"   (>= {settings.STORY_UNREADABLE_ZONE_COVERAGE} = declared"
          f" unreadable by the episode reader: "
          f"{sum(1 for z in zs if z >= settings.STORY_UNREADABLE_ZONE_COVERAGE)}"
          f"/{len(zs)} marks)")
    k = max(1, len(rows) // 3)
    lo, hi = rows[:k], rows[-k:]
    print(f"    LOOSEST third (zone_coverage {lo[0][0]:.2f}..{lo[-1][0]:.2f}): "
          f"unmatched share median {statistics.median([r[1] for r in lo]):.1%}")
    print(f"    TIGHTEST third (zone_coverage {hi[0][0]:.2f}..{hi[-1][0]:.2f}): "
          f"unmatched share median {statistics.median([r[1] for r in hi]):.1%}")
    p = _pearson(zs, us)
    s = _pearson(_rank(zs), _rank(us))
    print(f"    pearson r(zone_coverage, unmatched share) = "
          f"{'n/a' if p is None else f'{p:+.3f}'}"
          f"   spearman = {'n/a' if s is None else f'{s:+.3f}'}")
    print(f"    {'ticker':10} {'zone_cov':>9} {'unmatched':>10} {'conflict':>9}"
          f" {'nPz':>4} {'nEp':>4}")
    for z, u, t, np_, ne, cf in rows:
        print(f"    {t:10} {z:>9.3f} {u:>9.1%} {cf:>8.1%} {np_:>4} {ne:>4}")

    # episode-count-zero trap
    zero_ep = [c for c in good if c["n_episodes_list"] == 0]
    zero_pz = [c for c in good if c["n_puzzle"] == 0]
    print(f"\n  marks where reader 1 sees ZERO episodes: {len(zero_ep)}"
          + (("  -> " + ", ".join(c["ticker"] for c in zero_ep)) if zero_ep else ""))
    print(f"  marks where reader 2 sees ZERO events   : {len(zero_pz)}"
          + (("  -> " + ", ".join(c["ticker"] for c in zero_pz)) if zero_pz else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker", help="limit to one ticker")
    ap.add_argument("--json", metavar="PATH", help="JSON sidecar path")
    args = ap.parse_args()

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session, args.ticker)
        cards = [census_mark(mk) for mk in marks]
    finally:
        session.close()

    scope = f"filtered: {args.ticker.upper()}" if args.ticker else "all box marks"
    print("=" * 96)
    print("  CORRESPONDENCE CENSUS — do the three rail readers describe the "
          "same events on the operator's own marks?")
    print("=" * 96)
    print(f"population: calibration marks ({scope})   "
          f"marks_fingerprint: {fingerprint[:16]}...")
    print(f"engine_config_version: {manifest_hash()[:16]}...   marks: {len(cards)}")
    print(f"TOUCH_TOLERANCE_ATR={settings.TOUCH_TOLERANCE_ATR}  "
          f"TRAVERSAL_LOW_ZONE={settings.TRAVERSAL_LOW_ZONE}  "
          f"TRAVERSAL_HIGH_ZONE={settings.TRAVERSAL_HIGH_ZONE}  "
          f"BOUNDARY_ATR_BUFFER={settings.BOUNDARY_ATR_BUFFER}")
    for c in cards:
        print_mark(c)
    print_aggregate(cards)

    if args.json:
        doc = {"population": "calibration_marks", "scope": scope,
               "marks_fingerprint": fingerprint,
               "engine_config_version": manifest_hash(),
               "settings": {
                   "TOUCH_TOLERANCE_ATR": settings.TOUCH_TOLERANCE_ATR,
                   "TRAVERSAL_LOW_ZONE": settings.TRAVERSAL_LOW_ZONE,
                   "TRAVERSAL_HIGH_ZONE": settings.TRAVERSAL_HIGH_ZONE,
                   "BOUNDARY_ATR_BUFFER": settings.BOUNDARY_ATR_BUFFER,
                   "STORY_UNREADABLE_ZONE_COVERAGE":
                       settings.STORY_UNREADABLE_ZONE_COVERAGE,
               },
               "cards": cards}
        refuse_sealed_output(args.json)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
