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
inner boxes anywhere against parent R, above or below (nesting is temporal, not
price-bounded), and an inner-elected LPS reading its zone class against the
INNER rails; LPS end_bar is exclusive; climax terminality (A3) keys its
polarity on the engine's OWN cause read (covering confirmed segment,
_cause_is_up — re-keyed e4471e0), never the seed's BC/SC label. Down-causes
mirror every climax check on LOWS.

Each payload ticker is replayed on its own frame (cache trimmed to its last
payload candle) through the SAME eval-twin prep the live scan used, so the
asserted Structure is the one the operator sees. A ticker that refuses to
re-measure is a coverage hole and fails the gate - UNLESS the engine's own
trace shows a cause-before-effect abstention (``cause_absent`` or
``lps_before_spring``): a name that fired into a pre-rule payload but now
legitimately abstains is an EXPECTED non-election, reported separately and
never a failure.

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


# The payload quantizes rails to 2 decimals (output/dashboard.py:261-262,
# ``round(float(row['_R']), 2)``). B6 must therefore ask "would today's rail still
# SERIALIZE to the value the payload recorded?" — quantize the same way the writer
# did rather than approximating its cell with an absolute epsilon. The old
# ``abs(engine - payload) < 0.005`` used a tolerance exactly equal to the
# quantization half-step, so a rail landing on a half-cent was written exactly
# 0.005 away from itself and could NEVER pass (PECO's S = 41.375 -> 41.38; the
# realized IEEE difference is 0.005000000000002558, so even ``<= 0.005`` fails).
# Latent since the gate was authored; first tripped when a half-cent rail entered
# the payload. Census at the fix: 664 rail comparisons, 1 case the epsilon failed
# and round-compare passes (the artifact), 0 the reverse (no regression).
_PAYLOAD_PRICE_DP = 2


def _same_price(engine_val, payload_val) -> bool:
    if payload_val is None:
        return False
    return abs(round(float(engine_val), _PAYLOAD_PRICE_DP) - float(payload_val)) < 1e-9


def _audit_setup(tk, daily, atr, s, cause_up, payload_fields, check):
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
    # Climax terminality is law wherever the ENGINE could key a direction for
    # its repair (the covering confirmed segment, seed label only as fallback —
    # _cause_is_up, re-keyed e4471e0). Keying this assertion on root.kind is
    # the Tested-DEAD keying the repair removed: the seed is a scan origin, not
    # the box's cause, and asserting by it measured 91 false violations on the
    # first post-repair run. cause_up None = the engine made no terminality
    # claim on this frame, so neither may the gate.
    if 0 <= cx <= ar <= pbs < n and cause_up is not None:
        atr_floor = float(atr) if (np.isfinite(atr) and atr > 0) else 0.0
        excess = settings.PHASE_A_CLIMAX_TERMINALITY_EXCESS
        if cause_up:
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
    same_R = _same_price(R, payload_fields.get("R"))
    same_S = _same_price(S, payload_fields.get("S"))
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
        # The zone class is a property of the box that OWNS the LPS. The
        # narrative elects inner-first-then-parent, so an inner-elected LPS was
        # typed against the INNER rails, while the published Structure.R/S are
        # always the PARENT's (B2/B3/B6 assert exactly that). Asserting the
        # class against ``s.R`` compared it to a rail the detector never saw.
        # Latent since the gate was authored; first tripped 2026-08-13 by TTC —
        # an OVERSHOOT_R LPS on an inner box sitting entirely BELOW the parent's
        # R (low 97.02 >= inner R 96.90, but < parent R 101.08). Census at the
        # fix, 271 payload setups: 48 OVERSHOOT_R, of which 2 are inner-elected
        # with inner R < parent R (TTC, HUBB) — both correct against their own
        # rail, 0 violations of any zone class against its active rails.
        active_R = (float(s.inner.R)
                    if (s.lps_in_inner and s.inner is not None) else R)
        # Asserted on the ZONE class, not the buec_shelf swing form: the zone is
        # what "LPS above R" names in doctrine, and the four other swing forms
        # outrank buec_shelf in the label cascade, so keying on the form left 37
        # of the 48 above-R reads unasserted (HUBB among them).
        if getattr(lps, "zone_type", None) == "OVERSHOOT_R":
            check("D5 lps-above-R", tk, float(lps.low) >= active_R - 1e-6 * active_R,
                  f"low={lps.low} R={active_R}"
                  f"{' (inner)' if s.lps_in_inner else ''}")
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

    # spy: the polarity the ENGINE's terminality repair actually used, per read
    # (EC-43 — the gate derives its key from the engine's own resolution, never
    # a re-typed twin). _cause_is_up runs inside _enforce_climax_terminality
    # once per resolve_phase_a call, so the last value before return belongs to
    # the elected Structure. Never called = the engine made NO terminality
    # claim on this frame (degenerate window) — A3 skips, exactly like an
    # undecidable direction. This replaced the root.kind spy when the climax
    # repair re-keyed polarity to the covering confirmed segment (e4471e0):
    # asserting terminality by the seed label measured 91 false violations on
    # the first post-repair run. Signature-transparent on purpose — pinning a
    # spied function's old arity broke the whole gate (250/250 read TypeError)
    # when terminal_floor was added.
    cause_seen = {"up": None}
    orig_cause = bricks._cause_is_up

    def cause_spy(*args, **kwargs):
        result = orig_cause(*args, **kwargs)
        cause_seen["up"] = result
        return result

    measured, refused, vetoed = 0, [], []
    bricks._cause_is_up = cause_spy
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
            cause_seen["up"] = None
            try:
                atr = float(daily.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
                s = read_structure(daily, atr)
            except Exception as e:
                refused.append((tk, f"read {type(e).__name__}")); continue
            if s is None:
                # A cause-before-effect abstention is an EXPECTED non-election,
                # not a coverage hole: the name fired into a pre-rule payload but
                # read_structure now abstains it. Re-run once with a trace to read
                # the engine's OWN terminal outcome (never a re-run of the veto
                # predicate) and separate it from a genuine no-structure refusal.
                # TWO outcomes carry that meaning, both cause-before-effect at
                # different seams: ``cause_absent`` (Phase B over a live trend
                # that never matured a cause) and ``lps_before_spring`` (the only
                # Phase-D evidence opens left of the Phase-C turn — invariant C6
                # asserted from the other side, 2026-08-09).
                vtrace: list = []
                read_structure(daily, atr, trace=vtrace)
                outcomes = {r.get("outcome") for r in vtrace}
                if outcomes & {"cause_absent", "lps_before_spring"}:
                    vetoed.append(tk); continue
                refused.append((tk, "no structure")); continue
            measured += 1
            _audit_setup(tk, daily, atr, s, cause_seen["up"], cd[tk], check)
    finally:
        bricks._cause_is_up = orig_cause

    n_viol = sum(len(v) for v in violations.values())
    print("=" * 64)
    print("  DOCTRINE GATE - Reading Model asserted over the live payload")
    print("=" * 64)
    print(f"setups: {len(tickers)}  measured: {measured}  "
          f"vetoed(cause-absent): {len(vetoed)}  refused: {len(refused)}")
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
    if vetoed:
        print("\nVETOED (cause-before-effect — expected non-elections, not holes):")
        print("   " + " ".join(sorted(vetoed)))
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
