# Spec — Technical Analysis Score (the Visual half of the scoring system)

Status: DRAFT v2 (reframed by operator 2026-07-01) · Branch: `engine/ta-score-rework`
Evidence basis: `docs/archive_edge_read_2026-07-01.md` · Plan: `specs/ta-score-rework-plan.md`
· **Design: `specs/ta-score-hybrid-design.md`** (the buildable formula/tag-fold synthesis)
(the plan predates this reframe — its engineering spine holds; buckets + formula phases are
superseded by §3–§5 here and the hybrid-design doc).

## 1. Purpose & the two-half system

The scoring system is split into two halves:

- **Technical Analysis Score (Visual / chart-reading)** — THIS rework. A single **0–100**,
  **hybrid + dynamic** number that scores the *entire visual read* of a setup from its chart.
- **Fundamental Score** — a separate future half (to be continued). Out of scope here.

We **ditch the old "visual vs market" framing.** Market **regime is no longer a score input**
— it becomes a small informational **label** (§4). The letter tier / grade derives from the
Technical Analysis Score alone.

Two jobs remain distinct (unchanged from v1):
- **Job A — define & grade what a good setup *is*** (this rework): a regime-agnostic
  descriptive quality grade of the chart. The operator's discretionary eye
  (Minervini/VCP + Qullamaggie + Wyckoff) is the spine.
- **Job B — measure its *edge* across regimes/eras** (deferred): needs an adverse cohort we
  don't have yet. The edge read is **input/tie-breaker, not the objective function.**

## 2. What "hybrid + dynamic" means

- **Hybrid** — the score fuses the **quantitative sub-scores** with the **qualitative
  setup-tags** (today's "why ranked" chips: worked-equilibrium, touch-volume, HTF re-accum,
  spring/LPS reads, etc.). Tags stop being display-only and become **graded scoring inputs**,
  folded/rewritten into one coherent formula.
- **Dynamic** — the formula **adapts to the structure actually present** rather than a rigid
  fixed additive sum: features that don't exist for a given setup don't dilute it, and
  setup-shape (e.g. spring vs flat coil vs LPS) can weight its own relevant reads. Exact
  mechanism is a plan/design question (§7).

## 3. Architecture — the layers ✅ LOCKED (operator, 2026-07-01)

- **Technical Analysis Score (0–100)** — built from **every single-chart, chart-readable
  signal**, folding in the tags. Its distribution is normalized to a **0–100** grade, and the
  **letter tier derives from it.**
- **Regime label** (§4) — universe breadth + SPY trend; **annotation only, never scored.**
- **Fundamental Score** — future half; not built here.

**New formula, reweighting everything** (§5) — not a conservative cap-nudge. Still
**flag-gated, byte-identical when off**, and gated by the standing guards.

### Term taxonomy (locked)

| Signal | Home | Notes |
|---|---|---|
| box_tightness, touch_density, traversal_quality, atr_squeeze, lps_tightness, vol_contraction, base_age, contraction, ascending_support | **TA Score** | core structure |
| right_side_improvement, worked_eq_touch (new) | **TA Score** | promoted structural reads (edge §4) |
| puzzle_quality (E3) | **TA Score** | L2 Wyckoff narrative, its own flag |
| uptrend_bonus, high_proximity, adr | **TA Score** | single-chart trend / position / volatility |
| **rs_bonus** (relative strength vs SPY) | **TA Score** | leadership is a technical read (operator-locked) |
| setup **tags** ("why ranked" chips) | **TA Score** | folded in as graded inputs (hybrid) |
| **breadth** (universe % > SMA50) | **Regime label** | market state, not chart |
| **spy_trend** | **Regime label** | market state, not chart |
| fundamentals | **Fundamental Score** | future half |

## 4. Regime label (replaces the old context layer)

Breadth + SPY-trend (and any market-state facts) render as a compact **label on the setup**:
"found in a {bullish/…} tape, breadth {n}%." It informs the reader where/when the setup was
found and feeds **Job B** later, but it **does not move the number or the tier.**

## 5. Reweighting — the new formula (Job A)

- **Fold the current 14 sub-scores + tags** into one hybrid formula normalized to **0–100**.
- **Promote** the edge-supported, operator-core reads: `base_age` (+0.31), `traversal_quality`
  (+0.19), and the new `right_side_improvement` + `worked_eq_touch` terms.
- **Reframe tightness as a consistency lever** (tight boxes win 90% @1.91R; the raw-mean
  "contradiction" is a fat-tail artifact), located on the right side of the base.
- **Weak/inert terms are down-weighted, not deleted** — "inert over one bull regime" ≠ "not
  part of good structure." The operator's eye is the arbiter; the edge read is a tie-breaker.
- `rs_bonus` was weak-harmful on the bull sample → **low weight, but kept** (it's a technical
  leadership read the operator wants visible in the number).

## 6. Constraints & guards (unchanged)

- Flag-gated (e.g. `TA_SCORE_V2`), **default-off byte-parity** (mirror CANDLE/PUZZLE containment).
- Gates green every step: `pytest -q`, `tools.shadow_diff --check`, `core.archive.seed_recall --check`.
- Small evidence-driven steps; **A/B surface on live fires for operator eyeball before flip.**
- One sub-score/tag **registry** feeds the 5 coupled sites (writer + seed writer + archive_actions
  + analyze + calibration); a set-equality invariant test guards it.
- Geometry/validity **gates untouched** — scoring only (grades-not-vetoes).

## 7. Decisions

**Resolved (operator, 2026-07-01):**
1. ✅ System split = **Visual (this) + Fundamental (future)**; ditch visual-vs-market.
2. ✅ TA Score = **hybrid + dynamic**, folds current sub-scores **+ tags**, 100% visual.
3. ✅ **Scale = 0–100**; tier derives from it.
4. ✅ **Regime → label only** (breadth + SPY); never scored.
5. ✅ **Relative strength stays IN the TA Score** (technical leadership read).
6. ✅ **Reweight everything with a new formula** (not a cap-nudge).
7. ✅ **Flip gated on operator eyeball** of the A/B set, never an aggregate edge number.

**Still open (plan/design phase):**
- The exact **hybrid/dynamic mechanism** (how tags combine with sub-scores; how the formula
  adapts to present features / setup shape).
- **Per-tag + per-term weights** and the 0–100 normalization anchors (calibration + eyeball).
- Whether the regime label also drives any **secondary sort** (default: no).

## 8. Validation plan

- Flag-off byte-parity + gates (mechanical correctness).
- A/B the new 0–100 TA Score vs the current tier on live fires; operator eyeballs the
  calibration set; **flip is a human decision.**
- **Job B (regime/era/setup-variety edge)** deferred until a corrective cohort matures under
  the now-reliable tick.
