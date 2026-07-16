# Solve-the-Engine — operator flip checklist (2026-07-16)

Everything below is BUILT, tested, and proven on your marks **as dark
variants** — live defaults have not moved. Each flip is your call (EC-7/EC-8
human gates). Work top-down; run the battery between steps; one flip per
sitting per the incremental tuning loop.

Baseline context: harness policy v2 (event-window fired-walk) re-graded the
17 marks at **7/16 fired** with the engine untouched (MS + NGL were
harness-window artifacts). Everything the levers add was proven with
`scratchpad probe_combined.py`-style variant replays; the projected
full-stack scoreboard is in the session log / PR body.

## Ready to flip (in this order)

### 1. `LPS_HOLDING_SHELF_ENABLED = True`  (converts WTS, PBT; MOV/VLO grade at your rails)
- [ ] Flip in `config/settings.py` → full `pytest -q`
- [ ] Re-capture the shadow baseline (deliberate re-freeze)
- [ ] `python -m tools.marks_corpus --check` → WTS/PBT/DRTS (`holding-shelf-lps`
      stage) convert — **preview the conversions, confirm each is the marked
      shelf, then reseal.** A conversion whose stage tag does NOT match is an
      anomaly — stop and investigate, never reseal it.
- [ ] Negative corpus + hermetic seed-recall + the agreement harness re-run
      (CTOS@06-11 negative must stay upheld)
- [ ] Ledger row moves to Retired with the evidence trail

### 2. `BAND_RAILS_ENABLED = True`  (converts BODI at your exact rails; EGBN over-reaches stay dead)
- [ ] Same battery + re-freeze protocol; BODI's `band-vs-excursion` pinned
      miss converts (fires 04-10 tier A at 12.33/10.18); EGBN stays
      `under-investigation` — if EGBN converts, that is an anomaly
- [ ] EC-8 cost bound: one flag-off + one flag-on CLI scan back to back on
      the same cached frame; compare evaluation-phase seconds in
      `output/scan_metrics.jsonl` (the band pool now runs on every
      empty-window ticker — the 16-mark harness cannot see universe cost)

### 3. `LPS_OVERSHOOT_WINDOW_ATR_ENABLED = True`  (converts CTOS, with #1)
- [ ] Battery + harness; CTOS fires 07-15 tier S at your rails, span 1.0

### 4. `ELECTION_DETHRONE_ENABLED = True`  (converts MATX, with #1)
- [ ] Battery + harness; MATX fires 06-29 tier S at your rails — the evening
      before its breakout. The hermetic corpus sweep already pins zero
      non-target elections moving.

## Threshold moves (variant-proven; need their companion tests first)

### 5. `LPS_SHELF_LENGTH_MIN` 3 → 2  (converts VCTR: fires 07-13 tier S)
- [ ] BEFORE moving: the n=2 boundary audit + a still-rejected 2-bar noise
      companion test (the 529-storm ate the audit agent; this obligation is
      OPEN — plan task 11's spec is in PLAN-solve-the-engine.md)

### 6. `LPS_VOL_CONTRACTION_MAX` 0.85 → 0.87  (converts AGCO: fires 07-01 tier A)
- [ ] BEFORE moving: archive vol-ratio distribution check vs forward returns
      + a Vol_50 NaN/zero-denominator guard audit (plan task 12's spec) +
      a still-rejected companion pin at 0.88+

## Deliberately NOT flipped / parked
- **Rescued-pool arbitration — REJECTED** (killed VIK's pinned hit; recorded
  at the `box_primitives` pool seam). Do not re-attempt without new corpus
  evidence.
- **Stretch levers (EGBN dwell proximity, YPF untrimmed-tape dwell, AGCO
  SMA50 pincer)** — evidence-gated on the new `eq_respect_frac` /
  `eq_close_*_dwell` margin telemetry accumulating in the archive.
- `MIN_BOUNDARY_RESPECT_PCT` does not move — probes proved threshold moves
  useless on 4/4 marks; event-typing (lever 2) is the doctrine path.

## Standing discipline
- Mark FIRST, peek after — overlay off during re-marks; an edited mark
  changes the fingerprint and forces an explicit re-baseline.
- Every report compares only within (population, fingerprint, engine hash,
  harness-policy) — the `--prev` delta names the moved axis.
- Reseal is its own explicit act — never chained into a flip script.
