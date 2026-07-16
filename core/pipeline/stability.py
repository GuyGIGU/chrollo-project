"""Election stability under backward eval-day shifts (Calibration at Scale,
Task 14) — flag-dark, measure-only.

The evidence (2026-07-10/11 calibration work): real structures persist while
junk flickers — BODI's band-pool pair exists at 2026-04-15 and dies at 04-16;
VLO's read exists 07-07 and dies 07-08. "The elected reading survives shifting
the eval day" is the algorithmic form of the operator's "anchor the rails and
see if the structure holds" — and it needs no threshold to mean something.

Discipline:
* BACKWARD shifts only (D-1 … D-k). The +j frames do not exist at the live
  right edge, and a lookahead-contaminated archive cannot be cleaned
  retroactively (the bin_a seam lesson). Forward persistence may exist as an
  offline research view but is never archived as scan-time knowledge.
* ELECTION stage only: one prep + one ``read_structure`` per shift — nothing
  after the election (LPS resolution, bins, HTF, puzzle, scoring) informs
  "did the same structure elect", so none of it is re-run.
* Identity via the ONE cross-frame predicate
  (``core.pipeline.election_identity.same_election``): calendar dates +
  scale-free rail tolerance — an epsilon wobble never reads as flicker.
* Fires only, on frame slices the worker already holds — no refetch.
* Never gates, never scores: raw values surface as underscore diagnostics.
"""
from __future__ import annotations

from config import settings
from core.pipeline.election_identity import projection, same_election


def election_stability(raw_df, reference_structure, reference_df) -> dict:
    """Probe the elected reading at D-1 … D-k on slices of ``raw_df``.

    ``raw_df`` is the SAME unprepared frame the live evaluation received —
    each shift re-runs the full eval-twin prep (never a lightweight copy that
    measures a subtly different engine). ``reference_structure``/
    ``reference_df`` are the LIVE election and its prepared frame at D.
    Returns raw measured values:
      * ``same_frac``  — fraction of probes electing the SAME reading
      * ``streak``     — consecutive same-reading days walking back from D-1
      * ``probes``     — shifts attempted (the k actually available)
      * ``refused``    — probes where the eval-twin PREP refused the shifted
        frame (universe-gate flicker — SMA/volume/price membership, not chart
        structure). Refusals count as not-same in ``same_frac`` ("the engine
        read nothing yesterday" is not persistence) but are reported apart so
        calibration can tell gate-flicker from election-flicker afterward.
    A shift where a different/no structure elects also counts as not-same.
    """
    from core.pipeline.evaluation import _prepare_eval_frame  # noqa: PLC0415 — sibling seam, lazy to avoid an import cycle
    from engine_alpha.structure.narrative import read_structure

    reference = projection(reference_structure, reference_df)
    lookback = int(settings.ELECTION_STABILITY_LOOKBACK)
    same_flags = []
    refused = 0
    for shift in range(1, lookback + 1):
        if len(raw_df) <= shift:
            break
        prep = _prepare_eval_frame(raw_df.iloc[:-shift])
        if prep is None:
            same_flags.append(False)
            refused += 1
            continue
        df_j = prep["df"]
        atr_j = float(df_j.iloc[-settings.STRUCTURE_ATR_SAMPLE_OFFSET]["ATR_10"])
        structure_j = read_structure(df_j, atr_j)
        if structure_j is None:
            same_flags.append(False)
            continue
        same_flags.append(same_election(reference, projection(structure_j, df_j)))

    probes = len(same_flags)
    streak = 0
    for same in same_flags:
        if not same:
            break
        streak += 1
    return {
        "same_frac": (sum(same_flags) / probes) if probes else None,
        "streak": streak,
        "probes": probes,
        "refused": refused,
    }
