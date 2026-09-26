"""Are the 12 new fires FULL refusals at baseline (second-look reachable),
or partial reads (only an always-on change reaches them)?"""
import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from engine_alpha import evaluation as ev
from engine_alpha.structure.events import event_map
from engine_alpha.structure.narrative import read_structure

NEW = ["KFY","BIIB","VTR","RCUS","ICLR","GEO","VRTS","CCEP","BMY","MSGS","CARS","AMCR"]
ORIG = event_map.frame_terminal_posture
def bar_unit(h, c, R, tol): return event_map.frame_r_engaged(h, R, tol)

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
full_refusals = 0
for t in NEW:
    prepared = ev._prepare_eval_frame(d[t].dropna())
    df = prepared["df"]
    atr = float(ev.structure_atr_row(df)["ATR_10"])
    base = read_structure(df, atr)                       # shipped walk
    event_map.frame_terminal_posture = bar_unit
    try:
        # second-look shape: only consulted because the shipped walk found nothing
        rescue_reachable = base is None
    finally:
        event_map.frame_terminal_posture = ORIG
    tag = "FULL refusal -> second-look reachable" if base is None else \
          f"partial read (elects {base.box.R:.2f}/{base.box.S:.2f} {base.box.elected_pool}, dies downstream)"
    full_refusals += base is None
    print(f"  {t:6s} {tag}")
print(f"\n{full_refusals}/12 reachable through the existing second-look scope")
