# Solve-the-Engine — operator flip checklist (2026-07-16)

> **STATUS 2026-07-17: EXECUTED.** The operator granted the flips ("if
> everything proved to be working then I don't mind flipping it"); each item
> below ran the full battery in its own commit on `engine/solve-the-engine`.
> Four flips are LIVE, the volume threshold moved with its evidence, and the
> shelf-length move was **attempted and REVERTED** at its own battery — the
> negative corpus vetoed it (details below). This file stays as the record.

Baseline context: harness policy v2 (event-window fired-walk) re-graded the
17 marks at **7/16 fired** with the engine untouched (MS + NGL were
harness-window artifacts). Every step below re-ran: full pytest, shadow
guard, marks ratchet, negative corpus, hermetic seed-recall, and the
agreement harness with `--prev` delta attribution.

## Executed flips (in order)

### 1. `LPS_HOLDING_SHELF_ENABLED = True` — DONE (commit 5b46823)
- WTS (06-08 tier B) + PBT (04-30 tier S) converted stage-matched; ratchet
  resealed at 8 pinned hits; DRTS stayed red exactly as the ledger predicted.
- Shadow byte-identical (no re-capture needed). Harness 7/16 → 9/16, delta
  named ENGINE as the moved axis, zero collateral rows.

### 2. `BAND_RAILS_ENABLED = True` — DONE (commit aed76e2)
- **The battery caught two junk leaks** invisible to the 16-mark harness,
  both closed with knob-free bounds BEFORE the reseal:
  - **DBD** (dead-space, tier-S leak): a 15-bar 4.1-ATR rally ABOVE R rode
    the uncapped above loop as a "poke" → above-rail spans now bounded by
    `MAX_CONSECUTIVE_OUTSIDE_DAYS` (the respect gate's own horizon).
  - **SPCB** (run-up junk, tier-A leak): a 34-bar high-flag whose left half
    was the +35% rally leg scraped every gate on 30 judged bars → the judged
    window must be a matured cause (≥ 2 × `MIN_BASE_DAYS` bars).
- BODI converted at the operator's exact 12.33/10.18 rails (04-10 tier A);
  EGBN stayed dead; ratchet resealed at 9 pinned hits.
- EC-8 cost bound (full 5,487-ticker cache, 3 passes): +8–19% eval-phase
  (~2–3 min per nightly scan); universe fires 317 → 331 (+14, +0.26%).
- Harness 9/16 → 10/16, exactly BODI moved.

### 3. `LPS_OVERSHOOT_WINDOW_ATR_ENABLED = True` — DONE (commit fcf7727)
- CTOS converted to **match** + fired 07-15 tier S at his rails (span 1.0).
- Shadow re-captured with ONE new admission: **BBVA** (tier A, the rescope's
  narrow-box OVERSHOOT_R class; its labeled negative-corpus frame still
  rejects). ⚠ **OPEN: operator eyeball on BBVA** — if junk, freeze its frame
  as a new negative case and the rescope gets a hardening pass.
- Harness 10/16 → 11/16, exactly CTOS moved.

### 4. `ELECTION_DETHRONE_ENABLED = True` — DONE (commit 2672122)
- MATX converted to **match** + fired 06-29 tier S at his rails, the evening
  before its breakout. Shadow byte-identical; the hermetic zero-collateral
  sweep held. Harness 11/16 → 12/16, exactly MATX moved.
- The rejected rescued-pool arbitration lever stays rejected (VIK
  counterexample pinned; guard test enforces it never quietly returns).

## Threshold moves

### 5. `LPS_SHELF_LENGTH_MIN` 3 → 2 — **ATTEMPTED, REVERTED** (the battery vetoed)
- The n=2 audit ran (crash-safe; monotone axis = one comparison, near-vacuous
  as the plan warned) and the companion noise pins were written and pass.
- **At the flip battery: KWR (tier B) and FLG (tier S) — labeled dead-space
  must-NOT-fires — both fired via 2-bar shelves.** Attribution probe: shelf-2
  alone leaks both; vol-0.87 alone is clean. The move reverted on the spot.
- VCTR stays unconverted. **Do not re-attempt** without a shelf predicate
  that actually discriminates at n=2 — the negative corpus is the arbiter.
  (The shelf-R lesson, confirmed again at a new scope.)

### 6. `LPS_VOL_CONTRACTION_MAX` 0.85 → 0.87 — DONE (this commit)
- Archive distribution check (1,679 matured episodes): outcome quality FLAT
  up to the old edge (0.80–0.85 band n=174, +6.7% mean 20d, 80% win) — no
  cliff at the boundary; deeper dry-up is not better in this archive.
- `Vol_50` non-finite refusal guard added in the same change (a NaN
  denominator used to pass both ratio comparisons silently).
- Companion pin: 0.88+ stays rejected (tests/test_lps.py). Negative corpus
  17/17, marks ratchet 9/11 held. Shadow re-captured: two LPS re-elections
  (PLPC, TRS — windows in the newly-admitted ratio band now compete), no new
  fires, no tier/rail moves. AGCO converts in the harness.

## Standing items
- **BBVA eyeball** (from flip 3) — see above. The one open judgment call.
- Stretch levers (EGBN dwell proximity, YPF untrimmed-tape dwell, AGCO SMA50
  pincer) stay evidence-gated on the `eq_respect_frac` / `eq_close_*_dwell`
  margin telemetry now archiving on every fired box.
- `MIN_BOUNDARY_RESPECT_PCT` does not move — probes proved threshold moves
  useless on 4/4 marks; event-typing is the doctrine path.

## Standing discipline (unchanged)
- Mark FIRST, peek after — overlay off during re-marks; an edited mark
  changes the fingerprint and forces an explicit re-baseline.
- Every report compares only within (population, fingerprint, engine hash,
  harness-policy) — the `--prev` delta names the moved axis.
- Reseal is its own explicit act — never chained into a flip script.
