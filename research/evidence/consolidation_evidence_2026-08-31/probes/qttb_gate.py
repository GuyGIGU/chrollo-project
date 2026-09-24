import os, sys
sys.path.insert(0, os.path.abspath("."))
import pandas as pd
from config import settings
from engine_alpha import evaluation as ev
from engine_alpha.structure.events import event_map

ORIG = event_map.frame_terminal_posture
def bar_unit(h, c, R, tol): return event_map.frame_r_engaged(h, R, tol)

d = pd.read_parquet(settings.CACHE_FILENAME, engine=settings.PARQUET_ENGINE)
df = d["QTTB"].dropna()

event_map.frame_terminal_posture = bar_unit
try:
    prepared = ev._prepare_eval_frame(df)
    sc = ev._resolve_structure_context(prepared["df"], prepared["latest"])
    print("structure_ctx:", "OK" if sc else "REFUSED")
    if sc:
        lc = ev._resolve_lps_context(prepared["df"], prepared["latest"], sc)
        print("lps_ctx:", "OK" if lc else "REFUSED")
        if lc:
            m = ev._measure_base_context(sc["base_df"], sc["res_avg"], sc["sup_avg"],
                                         sc["atr_for_zone"],
                                         sc["structure"].box.equilibrium)
            drop = ev.descent_tail_drops(prepared["df"], m["equilibrium"],
                                         sc["box_width"], sc["inner"],
                                         lc["lps_in_inner"], sc["atr_for_zone"])
            print("descent_tail_drops:", drop)
finally:
    event_map.frame_terminal_posture = ORIG
