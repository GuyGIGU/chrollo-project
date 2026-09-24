"""The full guard battery, A/B, for ONE candidate change judged in memory only:

    'is this bar engaging the ceiling?'  ->  answered by the bar's HIGH
    (event_map.frame_terminal_posture := frame_r_engaged; close ignored)

Nothing on disk moves. Control pass first (unpatched — proves the ground is
green), then the identical three guards patched:
  1. tools.regression.negative_corpus.check_corpus()   must-NOT-fire, 18 frozen frames
  2. tools.regression.marks_corpus.check_corpus()      sealed must-fire ratchet
  3. tools.regression.shadow_diff.check_baseline()     canonical drift, firing cohort
"""
import os, sys, time, contextlib
sys.path.insert(0, os.path.abspath("."))

from engine_alpha.structure.events import event_map
from tools.regression import negative_corpus, marks_corpus, shadow_diff

ORIG = event_map.frame_terminal_posture

def bar_unit_posture(last_high, last_close, R, tol):
    """The operator's unit: the bar engages the ceiling zone; close anywhere."""
    return event_map.frame_r_engaged(last_high, R, tol)

@contextlib.contextmanager
def patched(on):
    event_map.frame_terminal_posture = bar_unit_posture if on else ORIG
    try:
        yield
    finally:
        event_map.frame_terminal_posture = ORIG

def battery(tag, on):
    print(f"\n{'='*70}\n  {tag}\n{'='*70}", flush=True)
    out = {}
    for name, fn in (("negative_corpus", negative_corpus.check_corpus),
                     ("marks_corpus",    marks_corpus.check_corpus),
                     ("shadow_diff",     shadow_diff.check_baseline)):
        t0 = time.time()
        print(f"\n----- {name} ({tag}) -----", flush=True)
        with patched(on):
            try:
                ok = fn()
            except SystemExit as e:          # some mains sys.exit; keep going
                ok = (e.code in (0, None))
        out[name] = ok
        print(f"----- {name}: {'PASS' if ok else 'FAIL'}  "
              f"({time.time()-t0:.0f}s) -----", flush=True)
    return out

control = battery("CONTROL - engine as shipped", on=False)
candidate = battery("CANDIDATE - ceiling engagement judged by the bar's HIGH", on=True)

print(f"\n{'='*70}\n  SUMMARY\n{'='*70}")
for k in control:
    print(f"  {k:18s} control {'PASS' if control[k] else 'FAIL':4s}   "
          f"candidate {'PASS' if candidate[k] else 'FAIL'}")
