"""
Doctrine-invariant gate - asserts the Reading Model's hard claims against the
engine's OWN output on every setup in the live payload.

The rest of the battery proves the engine didn't CHANGE (parity/shadow/recall
against snapshots of itself); this gate proves the reading is RIGHT: a fallback
that paints plausible-but-doctrinally-wrong output passes every self-referential
gate forever (the FLXS climax bug, 2026-07-19) and only a doctrine assertion can
catch it. Every check cites docs/strategy_alpha.md (Reading Model).

Sanctioned forms the checks encode (operator rulings, 2026-07-19/20): one-bar
climax+AR pairs (climax_bar == ar_bar); pokes past the climax within
PHASE_A_CLIMAX_TERMINALITY_EXCESS x height; one-bar wick springs (tip ==
reclaim); TERMINAL_SHAKEOUT's buffered-band reclaim (looser than close-above-S);
inner boxes above parent R (nesting is temporal, not price-bounded); LPS
end_bar is exclusive. SC roots mirror every climax check on LOWS.

Each payload ticker is replayed on its own frame (cache trimmed to its last
payload candle) through the SAME eval-twin prep the live scan used, so the
asserted Structure is the one the operator sees. A ticker that refuses to
re-measure is a coverage hole and fails the gate.

Usage:
    python -m tools.doctrine_audit --check    # exit 1 on any violation/refusal
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path()

from config import settings
from engine_alpha import evaluation
from engine_alpha.structure import bricks
from engine_alpha.structure.narrative import read_structure

_PAYLOAD = os.path.join(_PROJECT_ROOT, "output", "screener_data.json")
_CACHE = os.path.join(_PROJECT_ROOT, "market_data_cache_5y.parquet")


def _audit_setup(tk, daily, atr, s, root_kind, payload_fields, check):
    H = daily["High"].values.astype(float)
    L = daily["Low"].values.astype(float)
    C = daily["Close"].values.astype(float)
    n = len(daily)
    cx, ar, pbs = int(s.climax_bar), int(s.ar_bar), int(s.phase_b_start_bar)
    pbe = int(s.phase_b_end_bar)
    R, S = float(s.R), float(s.S)
    box = s.box

    # -- Phase A: the trend-end pair (one-bar climax+AR form sanctioned) --
    check("A1 climax<=ar", tk, cx <= ar, f"cx={cx} ar={ar}")
    check("A2 ar<=box_start", tk, ar <= pbs, f"ar={ar} pbs={pbs}")
    # Climax terminality is law on every resolution path (guard's own formula,
    # by the elected root's kind; kinds beyond BC/SC carry no terminality claim)
    if 0 <= cx <= ar <= pbs < n and root_kind in ("BC", "SC"):
        atr_floor = float(atr) if (np.isfinite(atr) and atr > 0) else 0.0
        excess = settings.PHASE_A_CLIMAX_TERMINALITY_EXCESS
        if root_kind == "BC":
            height = max(H[cx] - L[ar], atr_floor)
            post = H[cx + 1:pbs + 1]
            ok = (not len(post)) or float(np.max(post)) <= H[cx] + excess * height
            check("A3 terminality", tk, ok,
                  f"BC post_max={float(np.max(post)):.2f} lim={H[cx] + excess * height:.2f}"
                  if len(post) else "")
        else:
            height = max(H[ar] - L[cx], atr_floor)
            post = L[cx + 1:pbs + 1]
            ok = (not len(post)) or float(np.min(post)) >= L[cx] - excess * height
            check("A3 terminality", tk, ok,
                  f"SC post_min={float(np.min(post)):.2f} lim={L[cx] - excess * height:.2f}"
                  if len(post) else "")

    # -- Phase B: the anchors PRODUCE the rails, inside the consolidation --
    check("B1 S<R", tk, S < R, f"S={S} R={R}")
    ra, sa = int(box.r_anchor_bar), int(box.s_anchor_bar)
    check("B2 High[r_anchor]==R", tk,
          0 <= ra < n and abs(H[ra] - R) < max(1e-6 * R, 1e-9),
          f"r_anchor={ra} H={H[ra] if 0 <= ra < n else '?'} R={R}")
    check("B3 Low[s_anchor]==S", tk,
          0 <= sa < n and abs(L[sa] - S) < max(1e-6 * S, 1e-9),
          f"s_anchor={sa} L={L[sa] if 0 <= sa < n else '?'} S={S}")
    check("B4 anchors-in-box", tk, pbs <= ra < n and pbs <= sa < n,
          f"pbs={pbs} r_anchor={ra} s_anchor={sa}")
    check("B5 box.start==pbs", tk, int(box.start_bar) == pbs,
          f"box.start={box.start_bar} pbs={pbs}")
    same_R = abs(R - float(payload_fields.get("R") or 0)) < 0.005
    same_S = abs(S - float(payload_fields.get("S") or 0)) < 0.005
    same_len = (n - pbs) == int(payload_fields.get("base_len") or -1)
    check("B6 payload-immobility", tk, same_R and same_S and same_len,
          f"R {R} vs {payload_fields.get('R')}  S {S} vs {payload_fields.get('S')}  "
          f"len {n - pbs} vs {payload_fields.get('base_len')}")

    # -- Phase C: penetration -> reclaim -> hold --
    sp = s.spring
    if sp is not None:
        tip, rec = int(sp.tip_bar), int(sp.recovery_bar)
        sp_type = getattr(sp, "spring_type", "SPRING")
        check("C1 spring-low<S", tk, 0 <= tip < n and L[tip] < S,
              f"L[tip]={L[tip] if 0 <= tip < n else '?'} S={S}")
        check("C2 reclaim-window", tk, tip <= rec < n, f"tip={tip} rec={rec}")
        if sp_type == "SPRING" and tip <= rec < n:
            # the calibrated spring's own reclaim rule; TERMINAL_SHAKEOUT uses
            # its buffered-band reclaim, enforced inside its detector
            check("C3 spring-reclaim>=S", tk, C[rec] >= S - 1e-9,
                  f"C[rec]={C[rec]} S={S}")
        check("C4 spring-in-box", tk, pbs <= tip, f"tip={tip} pbs={pbs}")
        check("C5 undercut>0", tk, float(sp.undercut_atr) > 0, f"{sp.undercut_atr}")
        check("C6 spring<=lps", tk, tip <= int(s.lps.start_bar),
              f"tip={tip} lps.start={s.lps.start_bar}")

    # -- Phase D: the mandatory terminal LPS (end_bar exclusive) --
    lps = s.lps
    check("D1 lps-exists", tk, lps is not None, "")
    if lps is not None:
        lst, lend, llow = int(lps.start_bar), int(lps.end_bar), int(lps.low_bar)
        check("D2 lps-window-order", tk, lst <= llow < lend <= n,
              f"start={lst} low={llow} end={lend} n={n}")
        check("D3 lps-in-box", tk, pbs <= lst, f"lps.start={lst} pbs={pbs}")
        check("D4 lps-price-order", tk, float(lps.low) <= float(lps.high),
              f"low={lps.low} high={lps.high}")
        if getattr(lps, "swing_type", "terminal_valley") == "buec_shelf":
            check("D5 buec-above-R", tk, float(lps.low) >= R - 1e-6 * R,
                  f"low={lps.low} R={R}")
    if s.terminator == "spring":
        check("D6 terminator", tk, sp is not None and pbe == int(sp.tip_bar),
              f"pbe={pbe} tip={sp.tip_bar if sp else None}")
    else:
        check("D6 terminator", tk, lps is not None and pbe == int(lps.start_bar),
              f"term={s.terminator} pbe={pbe} lps.start={lps.start_bar if lps else None}")
    check("D7 A-B-spine", tk, cx <= ar <= pbs <= pbe,
          f"cx={cx} ar={ar} pbs={pbs} pbe={pbe}")

    # -- Inner: temporal nesting only (price-bounded nesting is NOT doctrine) --
    inner = s.inner
    if inner is not None:
        check("E1 inner-starts-in-parent", tk, int(inner.start_bar) >= pbs,
              f"inner.start={inner.start_bar} pbs={pbs}")
        check("E2 inner-rails-ordered", tk, float(inner.S) < float(inner.R),
              f"iS={inner.S} iR={inner.R}")


def run_audit() -> int:
    payload = json.load(open(_PAYLOAD))
    cd = payload["chart_data"]
    cache = pd.read_parquet(_CACHE)
    cached = set(cache.columns.get_level_values(0))
    tickers = [t for t, f in cd.items() if f.get("candles")]

    violations = defaultdict(list)
    counts = defaultdict(int)

    def check(inv, tk, ok, detail=""):
        counts[inv] += 1
        if not ok:
            violations[inv].append((tk, detail))

    # spy: the elected root's kind, per read (resolve_phase_a runs once per
    # completed Structure, so the last call before return is the elected one)
    kind_seen = {"kind": None}
    orig_resolve = bricks.resolve_phase_a

    def resolve_spy(df, root, box, atr):
        kind_seen["kind"] = getattr(root, "kind", None)
        return orig_resolve(df, root, box, atr)

    measured, refused = 0, []
    bricks.resolve_phase_a = resolve_spy
    try:
        for tk in tickers:
            if tk not in cached:
                refused.append((tk, "not in cache")); continue
            df = cache[tk].dropna(subset=["Close"])
            as_of = cd[tk]["candles"][-1].get("time") or cd[tk]["candles"][-1].get("date")
            if as_of:
                df = df[df.index <= str(as_of)[:10]]
            try:
                prep = evaluation._prepare_eval_frame(df)
            except Exception as e:
                refused.append((tk, f"prep {type(e).__name__}")); continue
            if prep is None:
                refused.append((tk, "baseline refused")); continue
            daily = prep["df"]
            kind_seen["kind"] = None
            try:
                atr = float(daily.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
                s = read_structure(daily, atr)
            except Exception as e:
                refused.append((tk, f"read {type(e).__name__}")); continue
            if s is None:
                refused.append((tk, "no structure")); continue
            measured += 1
            _audit_setup(tk, daily, atr, s, kind_seen["kind"], cd[tk], check)
    finally:
        bricks.resolve_phase_a = orig_resolve

    n_viol = sum(len(v) for v in violations.values())
    print("=" * 64)
    print("  DOCTRINE GATE - Reading Model asserted over the live payload")
    print("=" * 64)
    print(f"setups: {len(tickers)}  measured: {measured}  refused: {len(refused)}")
    print(f"{'invariant':<26}{'applied':>8}{'violations':>12}")
    print("-" * 46)
    for inv in sorted(counts):
        print(f"{inv:<26}{counts[inv]:>8}{len(violations.get(inv, [])):>12}")
    for inv in sorted(violations):
        if not violations[inv]:
            continue
        print(f"\n== {inv}:")
        for tk, detail in violations[inv][:12]:
            print(f"   {tk:<7} {detail}")
        if len(violations[inv]) > 12:
            print(f"   ... and {len(violations[inv]) - 12} more")
    if refused:
        print("\nREFUSED (coverage holes):")
        for tk, why in refused[:12]:
            print(f"   {tk:<7} {why}")
    print()
    if n_viol == 0 and not refused:
        print("PASS - every Reading Model invariant holds on every live setup.")
        return 0
    print(f"FAIL - {n_viol} violation(s), {len(refused)} refusal(s); "
          "the reading disagrees with the doctrine somewhere above.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--check", action="store_true",
                    help="run the gate (exit 1 on any violation or refusal)")
    ap.parse_args()
    return run_audit()


if __name__ == "__main__":
    sys.exit(main())
