# Carmack Council Plan — TA Score Rework (Layered Structure/Context Score)

Companion to `specs/ta-score-rework.md`. Produced by a 6-seat council-plan
(numerical / structure / data-integrity / backend / scoring-edge / test) + Chair synthesis
(workflow `wf_1c5620fc-49f`). Branch: `engine/ta-score-rework`.

## 1. Approach summary

Land the split as a **pure additive partition inside the single `score_setup` call** — the
same term computations, regrouped into a structural bucket (which forms the tier) and a
context bucket (readout only), with `structure_total = round(total − context_total, 1)` so
flag-off byte-parity is arithmetic, not re-derived. Sequence all byte-parity scaffolding,
the one-place sub-score registry, the 5-way coupling wiring, and every behavioral test
**before** touching a single weight, so a red gate is never ambiguous about whether the
ranking moved from the re-architecture (a bug) or an intended reweight (the deliberate lever).

## 2. Phases

Every phase ends with the standing gate trio **green flag-OFF**: `pytest -q`,
`python -m tools.shadow_diff --check`, `python -m core.archive.seed_recall --check`.
Flag-ON is a separately-blessed baseline captured once (Phase 6). New flag:
`TA_SCORE_LAYERED` (default `False`).

### Phase 0 — Tripwire tests on HEAD (write first, must pass on current engine)
- `test_ta_layered_flag_off_is_byte_identical` (twin of the puzzle test): flag-off
  `score_setup` equals baseline — `total`, **every** sub-score key, **no new key**.
- Result-level twin through `_evaluate_ticker`: result dict, `_sub_scores`, **Score AND
  Tier** unchanged flag-off. The **Tier assertion is the new catcher** (tier is being re-sourced).
- Clone `test_archive_writer_columns_are_modeled_and_migrated` into a set-equality coupling
  stub (finalized P2).
- **Gate:** all three pass on **unmodified HEAD** (tripwires). Seats: Beck, McKinney.

### Phase 1 — The partition inside `score_setup` (reweight-neutral)
- Under `if settings.TA_SCORE_LAYERED:` only: `context_total = round(s_uptrend + s_rs +
  s_high + s_breadth + s_adr, 1)`; `structure_total = round(total − context_total, 1)`.
  **Subtract already-rounded parts** — do NOT re-sum from scratch (round-order can differ 0.1).
- Keep `total = round(sum(terms), 1)` byte-identical — context still adds into `total` so the
  composite ordinal sort (Finding 1, S≥A≥B) is preserved for ranking.
- Emit `ta_structure_score` / `context_score` **only inside the flag guard**.
- At the single call site (`evaluation.py:519`): `score_for_tier = structure_total if
  settings.TA_SCORE_LAYERED else total`. **Do NOT make `calculate_tier` flag-aware** (keep it
  pure scalar→letter). S-width cap stays wired to this path verbatim.
- **Gate:** flag-off byte-parity. No weight/threshold changed. Seats: Fowler, Ramírez, McKinney, Scoring-edge.

### Phase 2 — One sub-score registry + 5-way lock-step (structural-debt payoff)
- New **`core/scoring/taxonomy.py`**: one ordered list of `(name, "score_<col>", layer, present_when_flag)`.
- Route all **five** sites through it (no re-listed literals): (1) `score_setup` result dict;
  (2) `writer.py` block + `_NEW_COLUMNS`/model **and** `seed.py`'s parallel build (**two
  writers** — seed_recall runs the seed path) **and** `archive_actions.py`'s hand-copied block;
  (3) `analyze.py` `SUB_SCORES` + layer partitions; (4) calibration's `sub_score_fields`;
  (5) SQLite ALTER-on-boot.
- Fix the stale `SetupOut` schema (missing `traversal_quality`/`adr`/`puzzle_quality`).
- Finalize set-equality coupling test across all five sites (both writers).
- **Gate:** pure refactor, zero behavioral change. Seats: Fowler, Ramírez, Leach, Beck.

### Phase 3 — Persist layer totals + new-term columns (additive, nullable, NULL-aware)
- Four nullable FLOAT columns via **ALTER-ADD only, never rebuild** (DB holds the only
  bull-regime cohort): `structure_score`, `context_score`, `score_right_side_improvement`,
  `score_worked_eq_touch`.
- **Do NOT repurpose `score`/`tier`** (frozen composite ordinal). Write the structural letter
  to a **new `structure_tier`** column alongside legacy `tier` (both survive per-row for A/B).
- Writes conditional on the flag → pre-flag rows read **NULL, not 0.0**.
- **NULL semantics:** `analyze.py` + `/calibration` filter to non-null before correlating —
  kill `getattr(...) or 0.0` (it manufactures fake zero-structure winners). Backfill optional/separate.
- `engine_config_version = manifest_hash()` must include `TA_SCORE_LAYERED` + `TIER_*_STRUCT`
  (Job B needs post-flip rows queryably distinct).
- **Gate:** writer/seed upsert doesn't crash; flag-off byte-parity. Seats: Leach, McKinney, Fowler.

### Phase 4 — Tier-invariance behavioral tests (pins the product decision)
- Flag-ON: sweep each **context** input across its ramp → **Tier + structure_total unchanged**,
  context readout changes. Mirror: bump a structural term → structure_total + Tier **can** move.
- Keep S-width cap on the new tier path: explicit wide-box S→A demotion case.
- **Gate:** pass flag-ON with today's weights (buckets sum to same total). Seats: Beck, Scoring-edge, McKinney.

### Phase 5 — Recalibrate tier thresholds to the structural-only scale (flag-ON knob)
- Today's `TIER_S=110/A=95/B=75/C=55` are tuned to the ~122-pt composite (incl. context caps).
  Removing context lowers the max → unchanged thresholds silently empty S-tier.
- Add flag-gated `TIER_S_STRUCT/A_STRUCT/B_STRUCT/C_STRUCT`, read **only when layered** (never
  mutate live `TIER_*`). Re-solve against the structural-only distribution so S≈top quartile.
  `S_MAX_BOX_WIDTH` orthogonal/preserved.
- **Gate:** flag-off unchanged; flag-ON distribution reviewed (operator surface P6). Seats: McKinney, Scoring-edge, Fowler.

### Phase 6 — Flag-ON baseline + A/B harness (structure reproduces today's ranking)
- Re-bless a **new flag-ON shadow baseline** once (as E3 did). Flag-off stays byte-identical.
- A/B harness = faithful flag-flip clone of `tools/puzzle_ab.py`: same bar, flip only
  `TA_SCORE_LAYERED`, breadth held constant. Surface old Score/Tier vs new **structural tier +
  context as an explicit separate confluence line**. Order by tier flips first.
- Machine invariant on top of eyeball: layered ranking stays **monotonic S≥A≥B** on the fixture;
  route through eval-twins so live and seed compute the identical layered tier.
- **Gate:** flag-off green; flag-ON baseline blessed; monotonic invariant passes. **Reweight-neutral
  — flag-ON here reproduces today's ranking.** No auto-flip. Seats: Beck, Ramírez, Scoring-edge.

### Phase 7 — New structural terms (own commits, behaviorally pinned)
- Thread two new `score_setup` kwargs via a fold sibling of `score_traversal_args` (eval-twins
  byte-identical inputs). Inputs already archived — no new measurement plumbing.
  - **Right-side-improvement:** `bin_d_vs_b_support_quality_delta` is **signed** → **clamp neg→0**
    (a worse right side must never add points); pair with `1.0 − _ramp(bin_d_range_pct, …)`.
    `bin_d_range_pct` None when Phase D absent → neutral 0.0.
  - **Worked-eq touch-distribution:** `eq_s_touch_thirds/3.0` (already [0,1]) with
    `_ramp(eq_lower_dwell, …)`; 0.0 dwell is a real signal, not missing.
  - **Every None input → neutral 0.0 bonus** (a NaN reaching `round(sum)` poisons `total`).
- One test per term (monotonic in good direction, bounded, None/NaN→neutral, omitted-kwarg =
  identical pre-rework score). Flow through the P2 registry (no per-site edit).
- **Gate:** flag-off byte-parity (kwargs default-neutral); per-term tests. Seats: McKinney, Beck, Fowler, Leach.

### Phase 8 — Reweight within structure (conservative, one lever per commit)
- Single-regime corrs are **tie-breakers, not an objective**. **Cap any single-step change**
  (≈≤1 tier-gap). Prefer rank/win-rate framing over raw-mean fits.
- Promote `base_age` (+0.31) and `traversal_quality` (+0.19) by relative share. Keep
  `SCORE_BOX_TIGHTNESS` (hit-rate lever) but **add no second gross-width reward**.
- `rs_bonus` weak-harmful but **CONTEXT** — the split already removed it from the tier; keep it
  in the readout for Job B. **Do NOT zero the inert block** — trim, don't delete (operator eye arbiter).
- Fix `/calibration`'s stale re-normalizer (hard-coded 6-field `total_cap`): scope to structural
  sub-scores, re-derive `total_cap`. Read via the existing `importlib` `_cfg` — **never** add
  `from config import settings` to a backend router (config-vs-cwd boot crash).
- Each reweight = a separate `config/settings.py`-number-only commit, one-line-revertible,
  gates green between steps, fresh A/B for the operator.
- **Gate:** flag-off parity per step; flag-ON A/B interpretable. Seats: McKinney, Scoring-edge, Ramírez, Leach/Fowler.

## 3. Sub-score taxonomy (the registry's contents)

| canonical name | `score_` column | layer | in tier? | notes |
|---|---|---|---|---|
| box_tightness | score_box_tightness | STRUCTURAL | yes | reframe (consistency lever), keep S-width cap |
| touch_density | score_touch_density | STRUCTURAL | yes | inert block — trim not delete |
| traversal_quality | score_traversal_quality | STRUCTURAL | yes | **promote** (+0.19) |
| atr_squeeze | score_atr_squeeze | STRUCTURAL | yes | inert block |
| lps_tightness | score_lps_tightness | STRUCTURAL | yes | inert block |
| vol_contraction | score_vol_contraction | STRUCTURAL | yes | inert block |
| base_age | score_base_age | STRUCTURAL | yes | **promote** (+0.31) |
| contraction | score_contraction | STRUCTURAL | yes | inert block |
| ascending_support | score_ascending_support | STRUCTURAL | yes | inert block |
| puzzle_quality | score_puzzle_quality | STRUCTURAL | yes (when its own flag on) | E3, conditional key |
| right_side_improvement | score_right_side_improvement | STRUCTURAL | yes (P7) | signed delta, clamp neg→0 |
| worked_eq_touch | score_worked_eq_touch | STRUCTURAL | yes (P7) | eq_s_touch_thirds + eq_lower_dwell |
| uptrend_bonus | score_uptrend_bonus | CONTEXT | **no** | readout only |
| rs_bonus | score_rs_bonus | CONTEXT | **no** | weak-harmful; keep, don't delete |
| high_proximity | score_high_proximity | CONTEXT | **no** | readout only |
| breadth_bonus | score_breadth_bonus | CONTEXT | **no** | readout only |
| adr | score_adr | CONTEXT | **no** | tradeability (operator-locked) |
| ta_structure_score | structure_score | — (tier basis) | forms tier | new nullable column |
| context_score | context_score | — (readout) | never | new nullable column |
| structure_tier | structure_tier | — | new letter | alongside frozen `tier` |

## 4. Risks + mitigations

| # | Risk | Mitigation (phase) |
|---|---|---|
| 1 | Re-derived structural sum drifts from `total` by rounding → shadow_diff red even flag-off | `structure_total = round(total − context_total, 1)`; new keys/tier-switch only inside flag guard (P1) |
| 2 | Tier re-sourced but proven only for the Score number, not the letter | Result-level tripwire asserts **Tier** unchanged flag-off (P0); tier-invariance test flag-ON (P4) |
| 3 | Old `TIER_*` reused against smaller structural max → S empties, reads as regression | New flag-gated `TIER_*_STRUCT`; live `TIER_*` never mutated (P5) |
| 4 | S-width cap dropped → wide ranges reach S (the operator-flagged bug) | Cap stays verbatim on new tier path; explicit S→A wide-box test (P4) |
| 5 | New key writes to dict but not column / seed writer / analyze list (recurring coupling failure) | One registry → five sites; set-equality test covers **both** writers (P2) |
| 6 | Pre-flag NULLs zero-coalesced → fake zero-structure winners poison correlations | Null-aware readers; kill `getattr(...) or 0.0`; NULL correct, no backfill (P3) |
| 7 | `/calibration` re-normalizer divides by stale 6-field `total_cap` → nonsense weights | Scope to structural sub-scores, re-derive `total_cap`, via `importlib` `_cfg` (P8) |
| 8 | Signed delta term lets a worse right side add points; None poisons `total` | Clamp neg→0; None→neutral 0.0; `_clamp` bounds; per-term tests (P7) |
| 9 | Weights fit to beta + fat-tail winners → score encodes "rode a bull market" | Corrs are tie-breakers; capped single-step; episode-deduped; sign-stability 20d vs 60d; one lever/commit (P8) |
| 10 | Config-collision boot crash from naive `from config import settings` in a router | Read via existing `importlib` `_cfg`, never top-level backend import (P8) |
| 11 | Bundling split + reweight makes a red shadow_diff ambiguous | Restructure first (P1–6 neutral), reweight second (P7–8), one lever/commit |

## 5. Still-open operator decisions (surfaced, NOT answered)

1. **Rebrand:** public name/label in UI + archive columns ("TA Structure Score"? "Technical
   Analysis Score"?). Plan uses working columns `structure_score`/`structure_tier`.
2. **Context role in ranking:** pure display, or a **capped secondary sort input** (never the
   tier)? Plan preserves the composite `score` ordinal for sort + renders context separately.
3. **New-term weights:** exact ramp anchors + `SCORE_*` caps for the two new terms (P7/8 calibration).
4. **The flip itself:** gated on **operator eyeball of the A/B set**, never an aggregate edge
   number (single bull regime; Job B deferred). Human decision after P6/8.

**Sequencing guarantee:** Phases 0–6 are reweight-neutral scaffolding/registry/tests/rebase/A-B.
The **first weight change is Phase 7/8**, after every gate + behavioral pin is in place — so a
red gate always localizes to the one lever that moved.

**Key files:** `core/scoring/scoring.py`, `core/scoring/taxonomy.py` (new),
`core/pipeline/evaluation.py:519`, `core/archive/writer.py`, `core/archive/seed.py`,
`webapp/backend/routers/archive_actions.py`, `core/archive/analyze.py`,
`webapp/backend/routers/archive_calibration.py`, `config/settings.py`, `tools/puzzle_ab.py`,
`tools/shadow_diff.py`, `core/archive/seed_recall.py`.
