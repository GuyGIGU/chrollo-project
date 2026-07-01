# Design — Hybrid Technical Analysis Score (Chair synthesis)

Status: DESIGN v1 (Chair synthesis of 5-seat council) · Branch: `engine/ta-score-rework`
Governs: `specs/ta-score-rework.md` (locked spec v2) · Deltas: `specs/ta-score-rework-plan.md`
Evidence: `docs/archive_edge_read_2026-07-01.md` (one bull regime — tie-breaker, not objective)
Flag: `TA_SCORE_V2` (default `False`, byte-identical off)

---

## 1. Formula summary (3 sentences)

The TA Score keeps the current additive scorer as an internal **RAW structural composite** — all
structural sub-scores plus the promoted tag-reads (spring / volume-context / worked-eq / phase-D /
weekly-reaccum), each a bounded graded contribution and the two warnings as bounded soft discounts —
and then maps that raw sum to a published **0–100** grade via one deterministic, strictly-monotonic
affine transform `ta_score = clamp(raw / STRUCTURAL_CAP_SUM * 100, 0, 100)`, so the proven S≥A≥B
rank order (Finding 1) is provably preserved. **Dynamic** means present-mask neutrality (a term is
*absent*, not zero, when its measurement is None/inapplicable, and absence never adds points and never
inflates the scale) plus an optional, later, bounded per-shape weight *redistribution* that sums to
zero; the divisor stays a fixed function of config, never an empirical or per-row max. The 18 setup-tags
stop being a separate frontend layer: every tag fires off the **backend** sub-score dict / archived
flags via one registry, the backend emits a resolved `fired_tags` array, and the duplicated
`SUB_SCORE_CAPS` + `deriveTags` fire-logic are deleted so the score and its own chips have **one**
source of truth.

---

## 2. TAG DISPOSITION TABLE (all 18)

Disposition key: **POSITIVE** = promoted to a graded backend contribution (bonus-only, grades-not-vetoes);
**WARNING** = bounded soft discount, floored, never a hard reject; **DISPLAY-ONLY** = pure restatement
of a term already scored (scoring it again double-counts) → stays a chip, contributes nothing new to the
number. "Archived?" = is the read's backend input already a persisted archive column (Wave 1) or does it
need a new column first (Wave 2)? — verified against `core/archive/writer.py`.

| # | Tag (group) | Disposition | Read it grades (backend field) | Archived? | Edge-grounding |
|---|---|---|---|---|---|
| 1 | 📐 phase_d (Structure) | **POSITIVE** | `phase_d_inner` present + inner-vs-outer tightness delta | ✅ col `phase_d_inner` | Right-side-of-base tightening; `bin_d_range_pct −0.39` (Finding 2/4) |
| 2 | ⚖️ worked_equilibrium (Structure) | **POSITIVE (headline)** | `traversal_density` (from `trav_n_full_traversals`/`trav_n_swings`); this IS the new `worked_eq_touch` term | ⚠️ derive from 2 cols; `eq_s_touch_thirds`/`eq_lower_dwell` ✅ cols | **Strongest correlate:** `eq_s_touch_thirds +0.39`, `eq_lower_dwell +0.34` (Finding 4) |
| 3 | 🪝 phase_c_test / spring (LPS) | **POSITIVE** | `bin_c_present` + `bin_c_undercut_atr` (+ recovery bars, spring vol-z) | ✅ cols | Effort/result at the floor; **not in score today** — a promotion |
| 4 | 🤫 no_supply (Volume) | **POSITIVE** (signed R-rail term, light side) | `r_touch_vol_z` below no-supply threshold | ✅ col `r_touch_vol_z` | Light supply at ceiling = constructive; touch-volume is the effort/result axis Finding 4 blesses; **not in score today** |
| 5 | 💪 demand_at_s (Volume) | **POSITIVE** (S-rail term, heavy-demand side) | `s_touch_vol_z` above demand threshold | ✅ col `s_touch_vol_z` | Demand absorbing supply at floor; **not in score today** |
| 6 | ⬆ weekly_reaccum (Trend) | **POSITIVE** | `htf_w_reaccum` (+ nested/monthly flags) | ✅ via `htf_archive_values` | HTF alignment = real confluence; Stage-2 trend context (Finding 4) |
| 7 | 🏛 old_base (Structure) | **POSITIVE** (feeds existing `base_age`) | `base_age` sub-score cross | ✅ col `score_base_age` | **Top earner** `score_base_age +0.31` (Finding 3) — promote by share |
| 8 | 🌀 vcp_coil (Structure) | **POSITIVE** (feeds existing `contraction`) | `contraction` sub-score cross | ✅ col | Inert on this regime → keep LOW weight, trim not delete |
| 9 | 📈 ascending_support (Structure) | **POSITIVE** (existing `ascending_support`) | `ascending_support` sub-score cross | ✅ col | Inert-block → keep, low weight |
| 10 | 🪶 tight_lps (LPS) | **POSITIVE** (route via `right_side_improvement`) | `lps_tightness`, reframed to right-side | ✅ inputs archived; new term col Wave 2 | Tightness pays on the RIGHT side (Finding 2); `bin_d_vs_b_support_quality_delta +0.40` |
| 11 | 🚀 uptrend (Trend) | **POSITIVE** (low weight) | `uptrend_bonus` sub-score cross | ✅ col | Single-chart trend; operator wants visible, edge-inert → small weight |
| 12 | ⚡ high_adr (Trend) | **POSITIVE** (low weight) | `adr` sub-score cross | ✅ col | Tradeability (operator-locked); inert → small |
| 13 | ⚠️ Last Supper (Warning) | **WARNING-discount** | `lps_stretch_box` / `lps_stretch_atr` magnitude | ✅ cols | Valid-looking LPS stretched from its energy source; bounded soft discount only |
| 14 | ⚠️ heavy_resistance (Warning) | **WARNING-discount** | `r_touch_vol_z` above heavy-R threshold | ✅ col `r_touch_vol_z` | Sellers defending ceiling; **mirror of no_supply on the same z** → one signed R-rail term (see §3), not a second add |
| 15 | 🔒 tight_box (Structure) | **DISPLAY-ONLY** | already `box_tightness` | ✅ col | Promoting it double-counts `box_tightness` and re-inflates tight-clean setups |
| 16 | 🥇 strong_rs (Trend) | **DISPLAY-ONLY** | already `rs_bonus` | ✅ col | `score_rs_bonus −0.17` weak-harmful (Finding 3); kept in readout, LOW weight, never a second add |
| 17 | 🌊 vol_dryup (Volume) | **DISPLAY-ONLY** | already `vol_contraction` | ✅ col | Restatement of `vol_contraction`; scoring twice double-counts |
| 18 | (tight_lps raw-box duplicate) | **DISPLAY-ONLY** if consumed | if `right_side_improvement` already consumes lps tightness, chip is display-only | — | Avoid double-counting lps tightness across `lps_tightness` + `right_side_improvement` |

**Highest-value promotions** (currently INVISIBLE to the number): the two touch-volume rail reads
(no_supply / demand_at_s) and the **spring** read — these are exactly the worked-equilibrium /
effort-result signals Finding 4 says carry the forward-return correlation.

**Rail double-count guard:** no_supply, demand_at_s and heavy_resistance all read the same
`r_touch_vol_z` / `s_touch_vol_z` columns. Implement each rail as **one signed volume-context term**
(positive-bounded when light, negative-bounded-and-floored when heavy) — never two independent adds
off the same z-score.

---

## 3. The hybrid formula

### 3a. Two-stage architecture

```
RAW  = Σ (structural sub-scores)  +  Σ (promoted tag-reads, bonus-only)
       [warnings applied later, on the bounded value — see 3d]
ta_score = clamp( RAW / STRUCTURAL_CAP_SUM * 100 , 0, 100 )
```

- **RAW** is an internal number, never published. It keeps the current additive machine
  (`score_setup` in `core/scoring/scoring.py`) and adds the promoted tag-reads as new bounded
  `_clamp(...)`-ed terms. Every term is computed and summed at **full float precision** (the
  per-term `round(...,2)` in the result dict is DISPLAY-only and must not feed the sum — it already
  doesn't; keep it that way).
- **CONTEXT terms** (`rs_bonus`, `uptrend_bonus`, `high_proximity`, `adr`) are computed but stay LOW
  weight; **`breadth` and `spy_trend` are EXCLUDED entirely** — they go to the regime **label**, never
  the tier basis. (Taxonomy §3 locked.)

### 3b. 0–100 normalization — the math shape (be concrete)

- **Divisor** = `STRUCTURAL_CAP_SUM`, the **fixed** sum of the `SCORE_*` caps of exactly the terms in
  the TA-Score taxonomy (all structural + promoted tag-read caps + the two new terms; `breadth`
  excluded). Derived **once** by iterating the Phase-2 `taxonomy.py` registry filtered to `layer==TA`,
  reading `settings.SCORE_*` lazily — a pure function of config, zero lookahead, zero fitting.
- **Transform** = a positive-slope **affine map** `raw * (100 / STRUCTURAL_CAP_SUM)`, then a defensive
  lower clamp at 0. **No upper clamp needed** (raw < divisor by construction, since no real setup fires
  every cap at once), but keep a defensive `min(…,100)`.
- **FORBIDDEN:** sigmoid / logistic / percentile-rank / any cohort-relative "spread across 0–100"
  transform. Percentile-rank is lookahead (depends on the cohort, non-reproducible in `shadow_diff`);
  a sigmoid compresses the tails where S-tier lives and would destroy the very rank order Finding 1
  validated. A monotone affine map is the guardrail that lets the operator trust the rebrand did not
  move the ranking.
- **A missing term contributes 0 to the numerator and keeps its FULL cap in the fixed denominator** —
  that is the correct "this setup lacks this quality" semantics. **Do NOT** copy the frontend's per-row
  present-cap denominator (`scoreBucket` sums only measured keys' caps): a data-dependent divisor makes
  the scale non-monotonic across rows and is exactly the second-source-of-truth this rework kills.
- Because raw tops out well below the divisor, the live 0–100 distribution occupies roughly the
  lower-mid band. **That is fine and expected** — tier thresholds get re-solved against THIS
  distribution (plan Phase 5, `TIER_*_STRUCT`), anchored to 100, never *at* 100.
- **Round exactly once**, at the very end, on the scaled value (`round(...,1)`). Never round the raw
  then divide (round-before-divide injects magnitude-dependent scale error that can flip adjacent
  ranks near a tier boundary).

### 3c. The DYNAMIC / feature-adaptive mechanism

Two deterministic mechanisms; ship (1) first (bigger correctness win, simpler), (2) later behind the
same flag:

1. **Present-mask neutrality (ship first).** A term is *absent* — not zero — when its measurement is
   `None`/`NaN` or structurally inapplicable (no Phase D → `right_side_improvement` absent; no inner
   box → puzzle absent; no spring → spring-read absent). Every promoted flag-read maps a missing input
   to a **neutral 0.0 contribution** *before* it enters the sum, reusing the exact
   `isinstance/None/pd.isna` guard already proven in `_puzzle_quality` / `_candle_readability`. Absence
   never adds points and — because the divisor is fixed — never inflates the scale. This is the spec's
   "features absent must not dilute" requirement: a clean flat coil with no spring is scored against the
   max achievable *and never rewarded for lacking a feature it was never going to have*.
2. **Bounded per-shape weight redistribution (later increment).** Classify setup shape from
   already-archived facts (spring present via `bin_c_present`; flat-coil via low `traversal_density` +
   tight box; LPS-continuation via lps zone). A **fixed lookup table** keyed by shape shifts a small
   bounded fraction (e.g. ≤ ±15% of a term's cap) toward that shape's relevant reads (spring →
   up-weight spring/demand-at-S/worked-eq; flat VCP coil → up-weight contraction + candle readability).
   **Constraints:** static table (no learned/continuous/cohort function — determinism + byte-parity
   demand it); **each shape's reallocations MUST sum to zero** so `STRUCTURAL_CAP_SUM` (the divisor)
   is stable per shape and the same structure can't score differently just by tripping a classifier
   boundary. Redistribution moves a fixed budget; it never changes total scale.

### 3d. Warnings — bounded, floored, applied AFTER normalization

- Each warning is a factor in `[WARN_FLOOR, 1.0]` (heavy_resistance ramped from `r_touch_vol_z` above
  its threshold; last_supper from `lps_stretch_*` magnitude). Multiply the factors, clamp the **product**
  to one global floor (e.g. `0.85` — one warning shaves ≤ 15%, two stacked can't drive below the floor),
  then multiply the **final 0–100** value by it.
- **Two hard rules:** (1) apply on the bounded 0–100 number, **not** the raw sum (discounting raw then
  re-normalizing double-applies the scale — a rescale trap); (2) a missing/`None` warning flag →
  factor **1.0** (perfect neutrality), never `0.0` (a `0.0` factor would zero an otherwise-strong
  setup). `WARN_FLOOR` is a named config knob so the operator tunes "how much a warning bites" without
  code. Floored + multiplicative-on-a-bounded-value → monotonic-preserving among setups with the same
  warning profile, and grades-not-vetoes is structural (a warning can never bury a geometrically-sound
  setup, never reject).

### 3e. Machine invariants (Phase-0-style tripwires, first-class tests)

Because the formula now adapts per setup, pin these across ALL shapes and present-masks:
- **(a) Output bound:** `ta_score ∈ [0,100]` for every input incl. all-absent and all-present.
- **(b) Warning monotonicity:** raising a warning read only lowers-or-holds; raising any positive read
  only raises-or-holds.
- **(c) Absence-neutrality:** a term flipping present→absent must never raise the score (the classic
  "game the score by lacking a feature" failure of a present-cap denominator — forbidden here by the
  fixed divisor).
- **(d) Shape-sum-zero:** each shape's reallocation sums to 0 → divisor stable.
- **(e) Rank preservation:** normalized ordering == raw-sum ordering, exactly, on a fixture (the
  guardrail that proves the rebrand didn't reorder).
- **(f) NaN safety:** an all-None/all-NaN flag set yields a **finite** score equal to the geometry-only
  baseline (one unguarded NaN reaching `round(sum)` poisons `total` and every downstream tier/sort).
- Route all of this through the **eval-twins fold** so live `_evaluate_ticker` and seed
  `_evaluate_at_date` compute a byte-identical layered score.

---

## 4. Single source of truth (score / tag / caps duplication)

**The disease:** caps live in TWO places — backend `_clamp` args in `scoring.py` and a literal
`SUB_SCORE_CAPS` in `setupScoreMath.js`; `deriveTags.firesAt` reads the frontend copy, so a cap change
in `config/settings.py` silently mis-fires chips. Several reads (spring, no_supply, demand_at_s,
worked_eq, weekly_reaccum, phase_d_inner, both warnings) aren't in the score at all — the frontend
threshold-tests raw flags with hard-coded constants (`TOUCH_VOL_Z_NO_SUPPLY=-0.30`,
`TOUCH_VOL_Z_SPRING=0.30`, `TOUCH_VOL_Z_HEAVY_R=0.50`, `traversalDensity>=0.33`, etc. — none exist on
the backend). `ScreenerCard.jsx` also hand-maps a ~30-line `flags={{…}}` literal (a silent 4th source),
and `setupScoreMath.js` carries a whole `deriveScoreBreakdown` with its own VISUAL/MARKET partition (a
5th, contradictory math).

**The cure — backend registry is the one producer:**

1. **`core/scoring/taxonomy.py` is the ONE home for caps + fire-rules.** Each entry:
   `(canonical_name, "score_<col>", cap, firesAt_fraction | flag_predicate, group, tag_id, layer)`.
   `scoring.py` reads the cap **from the registry** (resolved via lazy `settings` lookup at call time —
   never a module-level constant, to dodge the config-vs-cwd backend-cwd shadow), so the score and its
   fire-threshold share ONE literal.
2. **The fire predicate and the grading term are the SAME object.** Because tags become graded inputs,
   the predicate that fires a chip and the predicate that grades the term are evaluated **once, on the
   backend**, off the sub-score dict + the raw flags `_build_live_result` already computes
   (`_traversal_density`, `_bin_c_present`, `_r_touch_vol_z`, `_phase_d_inner`, `_lps_stretch_box`,
   `_htf_w_reaccum`, …). This makes "score for a read whose chip doesn't fire (or vice-versa)"
   structurally impossible.
3. **Backend emits `fired_tags`** as `[{id, group, <numeric fields the tooltip interpolates>}]`, plus
   `ta_score` and a sibling `regime_label` object. `dashboard.py` serializes them into
   `chart_data[ticker]` exactly as it already conditionally serializes the puzzle key;
   `archive_actions.py` / `seed.py` persist the same via the registry.
4. **Frontend consumes, never derives.** `deriveTags` / `firesAt` / `SUB_SCORE_CAPS` / the JS
   thresholds / `deriveScoreBreakdown`'s VISUAL/MARKET key-lists are **deleted**; `deriveTags` shrinks
   to an `id → {label, tone, copy}` presentational lookup. `explainTip()` copy stays on the frontend
   (presentation, keyed by tag id) — the backend ships only the numeric fields tooltips interpolate.
   `ScreenerCard`'s hand-assembled `flags` literal is retired (card receives resolved tags).
5. **Regime label on a strictly separate branch.** Drop `breadth_bonus` from the scored sub-score set;
   surface `breadth` + `spy_trend` only under `regime_label` (a sibling object, never among
   `sub_scores`, so no bucketing helper can sum it). **Re-point or retire `useScreenerFilters.sortTickers`'s
   `market`-pill sort** (currently `deriveScoreBreakdown(...).market.score`) — or removing breadth either
   crashes (missing key) or silently keeps influencing a user-visible "quality" sort. Default: regime
   label drives **no** secondary sort.
6. **Wire contract = versioned envelope.** Flag-off, `chart_data[ticker]` + the archive row carry the
   SAME keys + values as today; `ta_score` / `fired_tags` / `regime_label` appear ONLY when the flag is
   on (conditional add, mirror the puzzle key). A contract test snapshots the flag-off key set for a
   fixture ticker (mirror `test_result_adapter.py`) and a second asserts flag-on is a strict superset —
   so byte-parity is proven at the **serialization boundary**, not just inside the scorer (shadow_diff /
   seed_recall run on the scorer, not the serializer).

---

## 5. Updated phase plan (delta to `specs/ta-score-rework-plan.md`)

The plan's **scaffolding / registry / tests / A-B-first, weights-last discipline HOLDS**. Its
**buckets + formula phases are superseded** by the two-stage 0–100 + tag-fold here. Flag renamed to
match spec: **`TA_SCORE_V2`** (plan said `TA_SCORE_LAYERED`). Deltas by phase:

| Plan phase | Change |
|---|---|
| **P0 Tripwires** | KEEP. Add a tripwire that the backend-emitted `fired_tags` set == today's `deriveTags` set on a fixture (the tag-layer analogue of flag-off byte-identical), and a **contract-boundary** flag-off key-set snapshot on `chart_data` (not just the score dict). |
| **P1 Partition** | **REPLACE** the structure/context *subtraction* partition with the **two-stage RAW→0–100** shape: emit `ta_score` (normalized) + internal `raw` only inside the flag guard; `total` stays byte-identical; tier sources from `ta_score` when flag-on. `STRUCTURAL_CAP_SUM` derived from the registry, lazily. Affine transform only. |
| **P2 Registry** | KEEP + **WIDEN**. `taxonomy.py` now also carries per-term `cap`, `firesAt` fraction, `group`, `tag_id`. Extend the set-equality coupling test to cover the tag entries across all 5 sites **+ the frontend `TAG_CATALOG` id list**. Fix stale `SetupOut`. |
| **P3 Persist** | KEEP + **ADD Wave-2 columns**: `score_worked_eq_touch`, `score_right_side_improvement`, the 3 puzzle grades (`puzzle_completeness` INT, `puzzle_chronology` TEXT, `puzzle_upthrust_terminal` INT — currently dropped at `evaluation.py:504`), and `ta_score` raw + normalized as their own columns (so normalization anchors are re-derivable off history without a re-scan). ALTER-ADD only; pre-flag rows read NULL. Manifest hash includes `TA_SCORE_V2` + `TIER_*_STRUCT`. |
| **NEW P3.5 Tag-fold (Wave 1)** | **ADD.** Promote the reads whose inputs are ALREADY columns into graded backend terms: phase_d_inner, spring (`bin_c_*`), the two signed rail volume-context terms (`r/s_touch_vol_z`), worked_eq (`traversal_density` from `trav_n_full/trav_n_swings`), weekly_reaccum (`htf_w_reaccum`), + the two warning soft-discounts (`lps_stretch_*`, `r_touch_vol_z`). These A/B and back-test against the 998-episode archive immediately. Each term: None→neutral, bounded, monotonic-in-good-direction, omitted-input == pre-rework score. |
| **P4 Tier-invariance** | KEEP; retarget to the new tier basis: sweeping a CONTEXT input (`rs`, `uptrend`, `high`, `adr`) leaves tier unchanged; a structural/promoted term can move it. Keep the S-width cap (`S_MAX_BOX_WIDTH`) verbatim on the new path + explicit wide-box S→A test. |
| **P5 Recalibrate thresholds** | KEEP. `TIER_*_STRUCT` re-solved against the 0–100 distribution (S ≈ top quartile), read only when flag-on, live `TIER_*` never mutated. |
| **P6 Flag-ON baseline + A/B** | KEEP + **UPGRADE the A/B surface**: per live fire show old tier, new 0–100, **AND the signed per-term contribution delta** (which reads moved the number and by how much — so the operator distinguishes "jumped on worked_eq_touch" from "rs_bonus leaked in"), the tier-flip count, and the max single-fire swing. Read puzzle/worked-eq/spring on the engine's OWN elected box (object-identity, as E3 does by injecting `structure.spring`/`structure.lps` at `evaluation.py:461`). Seed the calibration set from **live screener fires** (971/998 episodes), not seed winners. Machine invariant: normalized ordering == raw ordering; monotonic S≥A≥B. |
| **NEW P6.5 Frontend cutover** | **ADD, sequenced after eyeball, LAST.** Frontend reads `fired_tags`/`ta_score` when present, falls back to `deriveTags` when absent (thin adapter at the 3 call sites: ScreenerCard TagRow, `useScreenerFilters.buildTagMap`, ScreenerStockLens) so cards render through flag-off, A/B (mixed v1/v2 rows), and pre-v2 archive rows. Only AFTER the operator flips + re-seed do you delete the JS fire-logic + `SUB_SCORE_CAPS` + `deriveScoreBreakdown` — cut the card + filter-map derivation **together** so grid and tag-filter never disagree. |
| **P7 New structural terms** | KEEP (`right_side_improvement` = `bin_d_vs_b_support_quality_delta` clamp neg→0 + `1−ramp(bin_d_range_pct)`; `worked_eq_touch` = `eq_s_touch_thirds/3 + ramp(eq_lower_dwell)`). None→neutral; per-term tests; flow through the P2 registry. |
| **P8 Reweight** | KEEP the discipline verbatim: anchor weights to **reproduce today's ranking first** (Finding 1 ordering is doing real work), THEN edge read as **tie-breaker only** — promote `base_age`(+0.31)/`traversal`(+0.19)/worked-eq/right-side by **relative share not absolute refit**; cap any single term change ≈1 tier-gap/commit; trim-don't-delete the inert block; `rs_bonus` LOW weight kept; require sign-stability (20d vs 60d agree) before any corr-nudge; one lever per config-number-only commit. Hard-cap each promoted term's max contribution to a bounded slice of the 0–100 so one bull regime can't set magnitudes. |

**Sequencing guarantee (unchanged):** P0–P6.5 are reweight-neutral (scaffolding / registry / tag-fold
plumbing / tests / A-B / frontend adapter). The **first weight change is P7/P8**. A red gate always
localizes to the one lever that moved. Every phase ends with the standing trio green **flag-OFF**:
`pytest -q`, `python -m tools.shadow_diff --check`, `python -m core.archive.seed_recall --check`.

---

## 6. Still-open operator decisions (SURFACED, not invented)

1. **Per-tag / per-term weights + the 0–100 anchors.** The exact caps for the promoted tag-reads and
   the two new terms, `STRUCTURAL_CAP_SUM`'s resulting value, and the `TIER_*_STRUCT` thresholds are
   **calibration + eyeball** decisions (spec §7 open; plan P5/P7/P8). Chair does not set numbers.
2. **Dynamic mechanism scope.** Ship present-mask (3c-1) for sure; **whether to ship the bounded
   per-shape redistribution (3c-2) at all**, and if so its shape taxonomy + reallocation table, is
   open — recommend deferring it to a later flag-gated increment after present-mask is eyeballed.
3. **`WARN_FLOOR` value** — how hard a warning bites (default proposal 0.85; operator tunes).
4. **Regime label secondary sort** — spec default is **no**; confirm the `market`-pill sort is retired
   vs re-pointed to `ta_score`.
5. **The flip itself** — gated on **operator eyeball** of the A/B set (live screener fires), never an
   aggregate edge number. Human decision after P6/P8.
6. **DATA-seat acceptance (deferred, separate from the flip).** The promoted terms (`base_age`,
   `traversal`, `worked_eq_touch`, `right_side_improvement`) must be re-checked on `durable_win` once a
   **non-bull cohort** matures under the reliable tick (re-run `core.archive.analyze` filtered to the
   new columns when matured@20d in a corrective tape crosses the adequacy gate, n≈343/minority≈158).
   Until then the fold is hypothesis-confirming; keep weights conservative enough that an adverse-cohort
   sign flip is a **re-weight, not a rebuild**.
7. **Rebrand naming** — public label + archive column names ("TA Score" / `ta_score`). Plan used
   working `structure_*`; spec locks "Technical Analysis Score" 0–100.
