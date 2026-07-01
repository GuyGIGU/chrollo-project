# Spec — Technical Analysis Score (regime-agnostic structural quality grade)

Status: DRAFT (framing lock before council-plan) · Branch: `engine/ta-score-rework`
Evidence basis: `docs/archive_edge_read_2026-07-01.md`

## 1. Purpose & reframe

There are **two different jobs**, and the current scorer conflates them:

- **Job A — define & grade what a good setup *is*** (this rework). A **regime-agnostic,
  descriptive quality grade of the chart's bar/structure characteristics.** It does not
  know or care what the market regime is. This is "read the picture."
- **Job B — measure that grade's *edge*** (deferred). How the grade's realized returns
  hold up across regimes, eras, and setup varieties. This is where the "bull-only sample"
  caveat lives — and it needs an adverse cohort we don't have yet.

The edge read is therefore **input and sanity-check, not the objective function.** The
spine of the score is the operator's discretionary theory of good structure
(Minervini/VCP tightness + contraction, Qullamaggie momentum containment, Wyckoff
worked-equilibrium / LPS). Data tells us which characteristics co-move with outcomes and
flags freight that grades nothing — it does not get to *define* "good," because one bull
regime can't.

## 2. The core problem in today's scorer

`core/scoring/scoring.py::calculate_score` sums **14 sub-scores** into one `total`, mapped
to a letter tier by `TIER_*` thresholds. That single total mixes two categories:

| Category | Sub-scores |
|---|---|
| **Structural** (chart bar characteristics) | `box_tightness`, `touch_density`, `traversal_quality`, `atr_squeeze`, `lps_tightness`, `vol_contraction`, `base_age`, `contraction`, `ascending_support` (+ `puzzle_quality`, flag-gated) |
| **Context / regime** (NOT chart structure) | `uptrend_bonus`, `rs_bonus`, `breadth_bonus`, `high_proximity`, (`adr` = tradeability) |

Two independent reasons this is wrong for Job A:
1. **Conceptual (operator):** context terms describe the market/instrument, not whether
   the base is well-formed. They contaminate "what is a good setup."
2. **Empirical (edge read, live cut):** those context terms are the dead weight —
   `rs_bonus` weak-**harmful** (−0.17 vs durable-win), `uptrend`/`breadth`/`high_proximity`
   **inert** — while the structural earners `base_age` (+0.31) and `traversal_quality`
   (+0.19) are buried in the same sum.

## 3. Proposed direction — the key architectural decision  ✅ LOCKED (operator, 2026-07-01)

**Decision: FULL SPLIT, tier derives from the structural layer ONLY.** Context terms
become a separate confluence readout; they never enter the letter grade. ADR is grouped
with context (tradeability), not structure.

**Split the single total into two transparent layers:**

- **(A) TA Structure Score** — regime-agnostic; built ONLY from chart-structure terms.
  This is the grade of "what a good setup is," and the **letter tier derives from this.**
- **(B) Context layer** — trend / RS / breadth / 52w-proximity / tradeability, kept as a
  **separate, explicit readout (confluence)**, never folded into the structural grade.
  Preserved for Job B (regime study) and optionally for a *capped* ranking nudge, but it
  cannot move the definition of good structure.

This is a **re-architecture into layers + a reweight, not a rebuild.** The composite's
ordinal ranking already works (S +8.6% > A +5.5% > B −3.3%, monotonic), so we keep the
mechanism and clean its inputs. Flag-gated; **byte-identical when the flag is off.**

## 4. Reweighting *within* the structural layer (Job A)

- **Promote** the edge-supported, operator-core terms: `base_age`, `traversal_quality` /
  worked-equilibrium, and add/strengthen a **right-side-improvement** term
  (`bin_d_vs_b_support_quality_delta` +0.40, `bin_d_range_pct` −0.39 — currently unscored)
  and a **worked-equilibrium touch-distribution** term (`eq_s_touch_thirds` +0.39,
  `eq_lower_dwell` +0.34).
- **Reframe tightness as a consistency lever, not a magnitude one,** and locate it on the
  right side of the base — that's where it pays (tight boxes win 90% @1.91R vs loose 74%
  @1.64R; the raw-mean "contradiction" is a fat-tail artifact). Keep tightness; stop
  over-rewarding gross box width.
- **Audit the inert block** (`touch_density`, `atr_squeeze`, `lps_tightness`,
  `vol_contraction`, `contraction`, `ascending_support`): reweight so they don't dilute
  the earners — but **inert ≠ delete.** "Inert on durable-win over one bull regime" is not
  "not part of good structure." The operator's eye is the arbiter for the structural
  terms; the data is a tie-breaker, not a veto.

## 5. Non-goals (explicit)

- **No regime conditioning** of the score — that is Job B.
- **No edge-maximization as the objective** — single-regime data would overfit the tape.
- **No blind rebuild** — keep the working ordinal composite; incremental, flag-gated steps.
- **No change to geometry/validity GATES** — vetoes stay geometric; this touches SCORING
  only (grades-not-vetoes, per the reading roadmap).

## 6. Constraints & guards

- Flag-gated (e.g. `TA_SCORE_LAYERED`), **default-off byte-parity** (mirrors the
  CANDLE_SPREAD / ADR / PUZZLE containment pattern).
- Gates green every step: `pytest -q`, `tools.shadow_diff --check` (engine byte-parity),
  `core.archive.seed_recall --check` (firing invariant).
- Small evidence-driven steps; A/B surface on live fires for operator eyeball before flip.
- Archive writer + `/calibration` + analyze.py sub-score lists kept in lock-step (the
  archive's 5-way coupling — see the blindspot audit).

## 7. Decisions

**Resolved (operator, 2026-07-01):**
1. ✅ Structure/context **SPLIT** — yes (§3).
2. ✅ **Tier derivation** — structure layer ONLY.
5. ✅ **ADR** — grouped with context (tradeability), not structure.

**Still open (resolve during plan):**
3. **Rebrand** — the "Technical Analysis Score" name/label in UI + archive columns.
4. **Context terms' role** — pure display, or a capped secondary input to *ranking/sort*
   (never to the tier)?
6. **New structural terms** — exact definition/weights for the right-side-improvement and
   worked-equilibrium touch-distribution terms (plan + calibration work).

## 8. Validation plan

- Flag-off byte-parity + gates (mechanical correctness).
- A/B the layered score vs current on live fires; operator eyeballs the calibration set.
- **Job B (regime / era / setup-variety edge) is deferred** until a corrective cohort
  matures under the now-reliable tick — that is the test that separates "grades good
  structure" from "rode a bull market."
