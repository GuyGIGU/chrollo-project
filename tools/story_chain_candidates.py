"""Story-chain specimen CANDIDATE miner (program Task 2 — the keep/junk sheet feed).

Both chains of the story-chain program (docs/story_chain_program_2026-08.md,
register rows 8-9) have ZERO named specimens, and "name 2-3 charts from memory"
is the slowest ask shape this project runs. This instrument mines the cached
panel for CHAIN-SHAPED candidates so the operator rules keep/junk off a short
sheet instead of recalling tickers cold (the species program's 40-sheet
precedent).

THIS IS NOT AN ENGINE READ. The detectors here are deliberately crude rolling
heuristics — no election, no gates, no bricks — because their only job is to
surface charts worth the operator's eyeball. The operator's keep/junk verdicts
(docs/story_chain_candidates_2026-08.md, sealed) are the ground truth; a miss
here costs nothing but a sheet row.

The two shapes:

* base-on-base — a ~60-bar rangebound stretch, a close above its ceiling, a
  run, then a compact 10-25-bar range whose LOW sits fully ABOVE the old
  ceiling (the separated young base the default read refuses standalone).
* after-shakeout recovery — a rangebound stretch, a violent undercut below its
  floor (>= ~0.75 ATR), then a tight 5-20-bar pullback window that HOLDS above
  the shakeout's low after price recovered at least half the undercut. The
  window's altitude is recorded (above the old floor vs the tactical band
  below it — both ruled valid 2026-08-23).

SIDECAR ONLY (EC-46): candidates go to --out JSON through the sealed-output
guard, pre-flight, stamped with the engine manifest hash, cache basename and
screen params. Read-only otherwise; no network, no backend, no archive writes.

Interpreter: the ChrolloDashboard venv python (bare `python` is the documented
two-installs trap).

    python -m tools.story_chain_candidates --out output/story_chain_candidates.json
    python -m tools.story_chain_candidates --tickers MAN FTNT --out ...   # bounded debug
"""
from __future__ import annotations

import argparse
import json

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ImportError:                                  # invoked as a script
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore
configure_path()

import numpy as np                                           # noqa: E402
import pandas as pd                                          # noqa: E402

from engine_alpha.freeze.manifest import manifest_hash       # noqa: E402
from tools.power_play_census import load_panel               # noqa: E402

# Screen constants — heuristic yardsticks for the CANDIDATE screen only; they
# are not engine knobs, are not registered anywhere, and the operator's sheet
# verdicts, not these numbers, are what the program calibrates against.
BOX_BARS = 60                 # the parent stretch the rolling rails frame
BOX_MAX_RANGE_ATR = 12.0      # "rangebound": parent height <= this many ATRs
CHILD_WINDOWS = (10, 15, 20, 25)     # base-on-base child lengths tried
CHILD_MAX_RANGE_ATR = 4.0     # child compactness ceiling
CHILD_SEARCH_BARS = 85        # how far past the breakout the child may end
SEP_MAX_ATR = 15.0            # a child further above its parent is not LEANING on it
SEP_SCORE_CAP = 6.0           # tightness, not distance, ranks past this
UNDERCUT_MIN_ATR = 0.75       # "violent": low below the floor by >= this
PULLBACK_WINDOWS = (5, 8, 12, 15, 20)
PULLBACK_MAX_RANGE_ATR = 3.0
PULLBACK_MIN_RANGE_ATR = 0.3  # a REAL pullback trades — dead flat = shell, not tight
PULLBACK_SEARCH_BARS = 70     # how far past the undercut the pullback may end
RECOVERY_MIN_FRAC = 0.5       # close must regain >= half the undercut first
DEDUPE_BARS = 40              # one event per ~2 months per ticker
MIN_PRICE = 5.0               # the first sweep ranked SPAC shells; floors cut them
MIN_DOLLAR_VOL = 2e6          # median close*volume over the parent stretch
MIN_ATR_FRAC = 0.008          # ATR >= 0.8% of price: zero-range tapes are not "tight"


def _atr20(df: pd.DataFrame) -> np.ndarray:
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(20, min_periods=20).mean().to_numpy(dtype=float)


def _rolling(arr: np.ndarray, window: int, fn) -> np.ndarray:
    return fn(pd.Series(arr).rolling(window, min_periods=window)).to_numpy(dtype=float)


def _date(df: pd.DataFrame, i: int) -> str:
    return str(pd.Timestamp(df.index[i]).date())


def scan_base_on_base(ticker: str, df: pd.DataFrame) -> list[dict]:
    """Breakout above a rangebound stretch, then a compact range fully above
    the old ceiling."""
    n = len(df)
    if n < BOX_BARS + 40:
        return []
    atr = _atr20(df)
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    volume = df["Volume"].to_numpy(dtype=float)
    dollar = _rolling(close * volume, BOX_BARS, lambda r: r.median())
    ceil_prior = np.roll(_rolling(high, BOX_BARS, lambda r: r.max()), 1)
    floor_prior = np.roll(_rolling(low, BOX_BARS, lambda r: r.min()), 1)
    ceil_prior[0] = floor_prior[0] = np.nan
    rangebound = (ceil_prior - floor_prior) <= BOX_MAX_RANGE_ATR * atr
    tradable = ((close >= MIN_PRICE) & (np.roll(dollar, 1) >= MIN_DOLLAR_VOL)
                & (atr >= MIN_ATR_FRAC * close))
    breakout = (close > ceil_prior) & rangebound & tradable
    child_lo = {c: _rolling(low, c, lambda r: r.min()) for c in CHILD_WINDOWS}
    child_hi = {c: _rolling(high, c, lambda r: r.max()) for c in CHILD_WINDOWS}

    out, last_taken = [], -10**9
    for b in np.flatnonzero(breakout):
        if b - last_taken < DEDUPE_BARS or not np.isfinite(atr[b]) or atr[b] <= 0:
            continue
        old_r = float(ceil_prior[b])
        best = None
        for c in CHILD_WINDOWS:
            for end in range(b + c + 3, min(b + CHILD_SEARCH_BARS, n)):
                lo, hi = child_lo[c][end], child_hi[c][end]
                a = atr[end]
                if not (np.isfinite(lo) and np.isfinite(a)) or a <= 0:
                    continue
                if end - c + 1 <= b + 3 or lo <= old_r:
                    continue                       # not separated above the old ceiling
                rng_atr = (hi - lo) / a
                if rng_atr > CHILD_MAX_RANGE_ATR:
                    continue
                sep_atr = (lo - old_r) / a
                if sep_atr > SEP_MAX_ATR:
                    continue                       # too far above to lean on the parent
                score = min(sep_atr, SEP_SCORE_CAP) + (CHILD_MAX_RANGE_ATR - rng_atr)
                if best is None or score > best["score"]:
                    best = {"score": round(float(score), 2),
                            "child_start": _date(df, end - c + 1),
                            "child_end": _date(df, end),
                            "child_range_atr": round(float(rng_atr), 2),
                            "separation_atr": round(float(sep_atr), 2)}
        if best is not None:
            last_taken = b
            out.append({"ticker": ticker, "chain": "base_on_base",
                        "parent_start": _date(df, max(0, b - BOX_BARS)),
                        "parent_end": _date(df, b - 1),
                        "breakout": _date(df, b),
                        "old_ceiling": round(old_r, 2), **best})
    return out


def scan_shakeout_recovery(ticker: str, df: pd.DataFrame) -> list[dict]:
    """Violent undercut below a rangebound stretch's floor, a recovery of at
    least half the undercut, then a tight pullback holding above the low."""
    n = len(df)
    if n < BOX_BARS + 30:
        return []
    atr = _atr20(df)
    high = df["High"].to_numpy(dtype=float)
    low = df["Low"].to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    volume = df["Volume"].to_numpy(dtype=float)
    dollar = _rolling(close * volume, BOX_BARS, lambda r: r.median())
    ceil_prior = np.roll(_rolling(high, BOX_BARS, lambda r: r.max()), 1)
    floor_prior = np.roll(_rolling(low, BOX_BARS, lambda r: r.min()), 1)
    ceil_prior[0] = floor_prior[0] = np.nan
    rangebound = (ceil_prior - floor_prior) <= BOX_MAX_RANGE_ATR * atr
    tradable = ((close >= MIN_PRICE) & (np.roll(dollar, 1) >= MIN_DOLLAR_VOL)
                & (atr >= MIN_ATR_FRAC * close))
    undercut = (low < floor_prior - UNDERCUT_MIN_ATR * atr) & rangebound & tradable
    win_lo = {c: _rolling(low, c, lambda r: r.min()) for c in PULLBACK_WINDOWS}
    win_hi = {c: _rolling(high, c, lambda r: r.max()) for c in PULLBACK_WINDOWS}

    out, last_taken = [], -10**9
    for u in np.flatnonzero(undercut):
        if u - last_taken < DEDUPE_BARS or not np.isfinite(atr[u]) or atr[u] <= 0:
            continue
        old_floor = float(floor_prior[u])
        shakeout_low = float(low[u:min(u + 10, n)].min())
        depth = old_floor - shakeout_low
        if depth <= 0:
            continue
        best = None
        for c in PULLBACK_WINDOWS:
            for end in range(u + c + 3, min(u + PULLBACK_SEARCH_BARS, n)):
                lo, hi = win_lo[c][end], win_hi[c][end]
                a = atr[end]
                if not (np.isfinite(lo) and np.isfinite(a)) or a <= 0:
                    continue
                start = end - c + 1
                if start <= u + 2 or lo <= shakeout_low:
                    continue                       # must HOLD above the shakeout low
                if float(close[u:start].max()) < shakeout_low + RECOVERY_MIN_FRAC * depth:
                    continue                       # no recovery before the pullback
                rng_atr = (hi - lo) / a
                if not (PULLBACK_MIN_RANGE_ATR <= rng_atr <= PULLBACK_MAX_RANGE_ATR):
                    continue                       # dead-flat tape or too loose
                position = "above_floor" if lo >= old_floor else "tactical_band"
                hold_atr = (lo - shakeout_low) / a
                score = (PULLBACK_MAX_RANGE_ATR - rng_atr) + min(hold_atr, 3.0)
                if best is None or score > best["score"]:
                    best = {"score": round(float(score), 2),
                            "pullback_start": _date(df, start),
                            "pullback_end": _date(df, end),
                            "pullback_range_atr": round(float(rng_atr), 2),
                            "position": position}
        if best is not None:
            last_taken = u
            out.append({"ticker": ticker, "chain": "shakeout_recovery",
                        "box_start": _date(df, max(0, u - BOX_BARS)),
                        "undercut": _date(df, u),
                        "old_floor": round(old_floor, 2),
                        "shakeout_low": round(shakeout_low, 2),
                        "undercut_atr": round(depth / atr[u], 2), **best})
    return out


def mine(frames: dict, top: int) -> dict:
    """Best candidate per ticker per chain, ranked, trimmed to ``top`` each."""
    per_chain: dict[str, list] = {"base_on_base": [], "shakeout_recovery": []}
    for ticker in sorted(frames):
        df = frames[ticker]
        for cand in scan_base_on_base(ticker, df) + scan_shakeout_recovery(ticker, df):
            per_chain[cand["chain"]].append(cand)
    ranked = {}
    for chain, rows in per_chain.items():
        best_per_ticker: dict[str, dict] = {}
        for r in rows:
            cur = best_per_ticker.get(r["ticker"])
            if cur is None or r["score"] > cur["score"]:
                best_per_ticker[r["ticker"]] = r
        # Deterministic full ordering: score desc, then the event's violence
        # (undercut depth / separation) desc, then ticker — a saturated score
        # must never leave the tail ranked by dict-insertion accident.
        ranked[chain] = sorted(
            best_per_ticker.values(),
            key=lambda r: (-r["score"],
                           -(r.get("undercut_atr") or r.get("separation_atr") or 0.0),
                           r["ticker"]))[:top]
    return ranked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="sidecar JSON path (guarded)")
    ap.add_argument("--cache", default=None, help="panel parquet (default: live cache)")
    ap.add_argument("--tickers", nargs="*", default=None, help="bounded debug run")
    ap.add_argument("--top", type=int, default=20, help="candidates kept per chain")
    args = ap.parse_args(argv)

    refuse_sealed_output(args.out)          # pre-flight, before the expensive pass
    frames, cache_name = load_panel(args.cache, args.tickers)
    print(f"scanning {len(frames)} tickers for the two chain shapes...")
    ranked = mine(frames, args.top)

    report = {"instrument": "story_chain_candidates",
              "engine_config_version": manifest_hash(),
              "cache": cache_name, "tickers_scanned": len(frames),
              "params": {"box_bars": BOX_BARS, "box_max_range_atr": BOX_MAX_RANGE_ATR,
                         "child_max_range_atr": CHILD_MAX_RANGE_ATR,
                         "sep_max_atr": SEP_MAX_ATR, "sep_score_cap": SEP_SCORE_CAP,
                         "undercut_min_atr": UNDERCUT_MIN_ATR,
                         "pullback_range_atr": [PULLBACK_MIN_RANGE_ATR,
                                                PULLBACK_MAX_RANGE_ATR],
                         "recovery_min_frac": RECOVERY_MIN_FRAC,
                         "min_price": MIN_PRICE, "min_dollar_vol": MIN_DOLLAR_VOL,
                         "min_atr_frac": MIN_ATR_FRAC, "top": args.top},
              "candidates": ranked}
    with open(refuse_sealed_output(args.out), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)

    for chain, rows in ranked.items():
        print(f"\n{chain} — top {len(rows)}:")
        for r in rows:
            when = r.get("breakout") or r.get("undercut")
            print(f"  {r['ticker']:<6} {when}  score {r['score']}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
