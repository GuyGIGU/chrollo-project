"""Fleet exposure census for the bar-unit ceiling-engagement candidate.

Per universe-surviving ticker at the live cache edge: full pipeline OFF
(shipped) vs ON (event_map.frame_terminal_posture answered by the bar's HIGH,
in-memory), canonical-field diff. Universe refusals are skipped for the ON
pass — the patch cannot reach the universe gates by construction.

Read-only. Sidecar JSON to the scratchpad, never output/.
"""
import os, sys, json, time, contextlib
sys.path.insert(0, os.path.abspath("."))

import pandas as pd
from config import settings
from engine_alpha.evaluation import EVAL_ERROR, apply_baseline_filters_with_reason
from engine_alpha.structure.events import event_map
from core.pipeline.screening.screener import _evaluate_ticker
from tools.regression.shadow_diff import canonical_fields

_BREADTH, _SPY_6M = 0.5, 0.0        # the replay seam's frozen scoring scalars
ORIG = event_map.frame_terminal_posture

def bar_unit_posture(last_high, last_close, R, tol):
    return event_map.frame_r_engaged(last_high, R, tol)

@contextlib.contextmanager
def patched():
    event_map.frame_terminal_posture = bar_unit_posture
    try:
        yield
    finally:
        event_map.frame_terminal_posture = ORIG

data = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
tickers = sorted(set(data.columns.get_level_values(0)))
skip = {settings.SPY_SYMBOL, *getattr(settings, "INDEX_SYMBOLS", [])}
tickers = [t for t in tickers if t not in skip]

counts = {"tickers": 0, "universe_refused": 0, "eval_error": 0,
          "fires_off": 0, "no_fire_off": 0,
          "new_fires": 0, "lost_fires": 0, "changed_fires": 0}
new_fires, lost, changed = [], [], []
t0 = time.time()
session = None
for i, t in enumerate(tickers):
    if (i + 1) % 500 == 0:
        print(f"  ... {i+1}/{len(tickers)} ({time.time()-t0:.0f}s) {counts}", flush=True)
    df = data[t].dropna()
    if df.empty:
        continue
    counts["tickers"] += 1
    if session is None or df.index[-1] > session:
        session = df.index[-1]
    _, reason = apply_baseline_filters_with_reason(df.copy())
    if reason is not None:
        counts["universe_refused"] += 1
        continue
    off = _evaluate_ticker(t, df, _SPY_6M, _BREADTH)
    if off is EVAL_ERROR:
        counts["eval_error"] += 1
        continue
    with patched():
        on = _evaluate_ticker(t, df, _SPY_6M, _BREADTH)
    off_f, on_f = isinstance(off, dict), isinstance(on, dict)
    counts["fires_off" if off_f else "no_fire_off"] += 1
    row = lambda r: {"ticker": t, "tier": r.get("Tier"),
                     "score": round(float(r.get("Score", 0)), 1),
                     "pool": r.get("_elected_pool"),
                     "profile": r.get("_story_admission_profile"),
                     "R": r.get("Resistance"), "S": r.get("Support"),
                     "trigger": r.get("_trigger_price")}
    if not off_f and on_f:
        counts["new_fires"] += 1; new_fires.append(row(on))
    elif off_f and not on_f:
        counts["lost_fires"] += 1; lost.append(row(off))
    elif off_f and on_f:
        a, b = canonical_fields(off), canonical_fields(on)
        if a != b:
            counts["changed_fires"] += 1
            changed.append({"ticker": t,
                            "moved": {k: [a[k], b[k]] for k in a if a[k] != b[k]},
                            "off": row(off), "on": row(on)})

print(f"\nsession {session.date() if session is not None else None}  "
      f"({time.time()-t0:.0f}s)\n{json.dumps(counts, indent=2)}")
print(f"\nNEW FIRES ({len(new_fires)}):")
for r in sorted(new_fires, key=lambda r: -r["score"]):
    print(f"  {r['ticker']:6s} tier {r['tier']}  score {r['score']:6.1f}  "
          f"pool {r['pool']}  R {r['R']}  S {r['S']}  | {r['profile']}")
print(f"\nLOST FIRES ({len(lost)}):")
for r in lost: print(f"  {r['ticker']:6s} tier {r['tier']}  {r}")
print(f"\nCHANGED FIRES ({len(changed)}):")
for c in changed:
    print(f"  {c['ticker']:6s} moved {c['moved']}")

out = os.environ.get("CENSUS_JSON")
if out:
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"session": str(session.date()) if session is not None else None,
                   "counts": counts, "new_fires": new_fires,
                   "lost_fires": lost, "changed_fires": changed}, fh, indent=2)
    print(f"\nwrote {out}")
