# Research: the layered split (trend / consolidation / swing)

**Status: research + Phase-1 design.** Sibling to
[structure_legend.md](structure_legend.md) (the shared vocabulary) and
[strategy_v2.md](strategy_v2.md) (what the code does today). This file records
*why* we're adding a swing-segmentation layer and *how* it's built measure-first.

---

## The core problem

Our structure engine already does ~95% of the job well: it finds the trend
climax, anchors R/S to BC and AR, and holds a consolidation as the root swing
even when dips breach S (MEOH is the proof case). What it **lacks** is the
*middle layer* between "here are the swings" and "find a box": **a classification
of each swing as belonging to a TREND leg or to a RANGE.**

That missing layer is the whole bug surface. ECPG is the symptom: the
consolidation's S was found later at a price that *coincided with an earlier low
inside the uptrend*, and with no concept of "that low belongs to the trend, not
the range," the engine borrowed it — dragging the root swing's origin down to the
bottom of the markup and printing a phantom "SC" that never existed.

> **The root swing is the key bridge between the trend and the consolidation.**
> It is the BC→AR swing: it *terminates* the trend (its start is the climax) and
> *births* the range (its end is the first floor/ceiling). It is owned by both.
> Segmentation is the act of finding that bridge correctly.

---

## What we already have (reuse, don't rebuild)

In `core/structure/`:

- `pivots.py::_find_pivots()` + `pivots.py::_build_zigzag()` — already produce the alternating
  peak/valley **swing skeleton** (the HH/HL/LH/LL path the whole trading world
  reads).
- `consolidation.py::find_outer_box()` — climax (BC/SC) enumeration + earliest-anchor selection.
- `box_primitives.py::phase_b_zigzag()` — range validation (boundary respect, touches, midline).
- `lps.py::detect_lps()` — the right-edge LPS, gated by `swing_complete_idx` so
  it can't predate the box.

We produce the swings. **We just never label the legs.** That's the job.

## The established frameworks this borrows from

- **Directional Change (DC):** segment price into directional legs by a
  *threshold*, event-based rather than time-based — the market gets "fragmented
  into upward and downward trends." (Springer review of DC trading; ResearchGate
  "Evolving Trading Strategies Using Directional Changes".)
- **Swing structure (HH/HL/LH/LL):** consecutive swing relationships reveal
  trend (higher highs + higher lows) vs. consolidation (oscillation in a band).

Both describe exactly the middle layer we're missing, and we already have the
swings to run them on.

## The young-base-friendly discriminator (the real ADX replacement)

ADX failed on young bases because it's a *smoothed lagging average* (~14+ bars) —
blind exactly when a base is young. Replace it with a measure computed on the
**zigzag swings, not bar-by-bar:**

> **Swing efficiency = |net displacement| ÷ total path length**, over a window
> of swings (Kaufman's Efficiency Ratio, run on pivots).
> - → 1.0 : every swing adds to the net move → **TREND**
> - → 0.0 : swings cancel within a band → **CONSOLIDATION**

Computed on pivots, it needs only 2–3 swings (works on young bases), is
noise-free, and has no smoothing lag.

### Magnitude, not count

Displacement is measured **ATR-normalized**, not in swing/bar count. A decisive
move can arrive in one bar or several — what marks it is the **ATR magnitude of
a continued move in one direction** (a "first big counter-burst"), not how long
it took. So the **root swing's AR leg is found as the first counter-move whose
ATR magnitude is anomalously large vs. the trend's little pullbacks.**

## Why this fixes ECPG without touching MEOH

- **ECPG:** segment it → 68→92 markup is a high-displacement TREND run; 78–85 is
  a low-efficiency RANGE. Every swing is **owned by exactly one segment**, so S
  can only be rooted by a swing *inside* the range — the earlier uptrend low
  (owned by the trend) can't be borrowed, the root origin can't drag down, and a
  selling climax inside a trend segment can't exist.
- **MEOH:** the same segmentation agrees with the engine's current (correct)
  conclusion → no regression. Agreement with the working case is the test that
  proves the layer right, not just clever.

## How it connects the puzzle pieces

Once segments are first-class objects, the rest of the legend falls out:
- **BC/AR** = the pivots of the root swing (the TREND→RANGE bridge).
- **Binding rule** ("R respects BC?") = does the range's R align with the
  trend's terminal high — a recordable boolean.
- **Parent / inner ranges** = a RANGE segment containing a tighter inner RANGE
  (the existing inner-box logic, made principled).
- **Last Supper** = the LPS swing's ATR displacement *beyond its innermost
  RANGE segment* — the stretch metric, measured "relative to the range that
  birthed it."

---

## Build path (measure-first; protects the 95%)

**Phase 1 — measure only, zero behavior change** *(this is what we're building)*.
`core/structure/segmentation.py :: segment_swings()` walks the existing zigzag and
emits, per scan, raw descriptive numbers:
- each swing's ATR-normalized signed displacement,
- window swing-efficiency (net ÷ path),
- the **candidate root swing** (climax pivot → first big counter-burst), with its
  trend displacement, counter displacement, and counter-burst ratio.

It bakes in **no trend/range cutoff** (case-dependent, calibrated later) and
**nothing consumes it yet** → shadow-diff stays frozen, MEOH untouched. We render
it on the fidelity chart and check it labels ECPG / MEOH / the 12-stock set the
way the eye does.

**Phase 2 — once the measure earns trust.** Constrain anchor selection + R/S
rooting to respect **segment ownership**.

- **Change A (shipped).** Reconnect the drifted BC anchor to the recent base
  via the segmentation root swing — display/scoping only, zero canonical drift.
- **Change B (shipped).** Outer-box candidate selection flipped from
  *global-best combined score* to **earliest good-enough range start**
  (`select="earliest"`, now the live default in `phase_b_zigzag` /
  `find_outer_box` / `find_consolidation` / `_evaluate_ticker`). The old "best"
  rule chronically truncated bases — it grabbed a tight recent *tail* with R
  often pinned to a transient spike (CGEM 19-bar tail, NMM 23-bar 2-touch
  spike) and threw the real range away. Earliest roots the box at the true
  range start near the AR low. A single quality floor
  (`PHASE_B_REACH_QUALITY_FLOOR = 0.75`) stops it reaching back into a
  *materially looser* framing (the SKT over-reach, 65% of best quality, is
  rejected → SKT keeps its tight box). The inner stage still owns
  tighter inner-range detection, so the outer box need not chase tightness.
  - **Blast radius** (frozen 198-ticker shadow fixture, best→earliest): 197
    fire (1 drop, SMFG — a quality-tied case whose truer range presents no
    LPS), **0 tier changes**, 25 scores up / 11 down, bases longer almost
    everywhere. Visually verified on CGEM/NMM/VIK/YOU/SKT/SMFG
    (`tools/phaseb_render.py`); A/B driver is `tools/phaseb_ab.py`.
- **Change C — worked-equilibrium validity (shipped).** Change B fixed *which
  valid framing* to pick but left validity loose, so the only framing that ever
  passed was the widest BC→AR box (every tighter sub-range got "broken" by later
  excursions). Symptoms: DBD/RLGT/KWR/FLG firing S/A on wide, dead-space, or
  mid-churn boxes anchored from the bottom. The fix makes validity itself encode
  the user's range test: a Resistance/Support-anchor pair is valid only if price
  **respects, touches, and zigzags through both rails constantly with no dead
  space** (`metrics.measure_dwell_balance`, formerly `measure_equilibrium`: ≥3 two-sided touches spread across the
  span + both-halves dwell + box-height coverage, and not mid-churn), box width
  ≤ 0.18, respect tightened (`MAX_CONSECUTIVE_OUTSIDE_DAYS` 30→10). Selection is
  now plain **earliest-of-valid** (`PHASE_B_REACH_QUALITY_FLOOR` retired — a
  sparse framing can no longer be valid, so no floor is needed), and **no valid
  pair → reject the stock**. This is the long-planned "constrain R/S rooting"
  Phase 2: the support anchor climbs off one-time AR lows automatically.
  Scoring rebalanced (`base_age` 35→22, `box_tightness` 15→22, oscillation
  flipped to reward rail-working) + an **S-tier width cap** (`S_MAX_BOX_WIDTH =
  0.15`) so a wide-but-worked range lands A, not S.
  - **Blast radius** (live 2y cache, full universe): daily fire 60→46, S-tier
    ~41→~24; **seed-winner recall preserved exactly** (same 28 winners re-found,
    hermetic cache probe old vs new). DBD/RLGT/KWR/FLG reject; BBVA/ABEV/COLM →
    A. Validity unit-tested in `tests/test_core_logic.py`.

**Phase 3 — fold nesting + Last Supper** off the same segment objects.
Started measure-first: the selected inner box now archives its origin
(`midpoint` vs `inner_climax`) and, when applicable, the mini-climax -> mini-AR
reaction depth/duration. This is evidence only; over-extension and staircase
behavior still wait on calibration.

## Open knobs (calibrate against the eye, never hard-code blind)

- `PHASE_B_REACH_QUALITY_FLOOR` — **retired** by Change C. Selection is now
  earliest-of-valid; a sparse framing can't be valid, so no reach floor is
  needed.
- The worked-equilibrium gates (`EQ_MIN_TOUCHES_PER_RAIL`, `EQ_MIN_TOUCH_THIRDS`,
  `EQ_MIN_HALF_DWELL`, `EQ_MAX_MID_DWELL`, `EQ_MIN_COVERAGE`) and the S-tier width
  cap (`S_MAX_BOX_WIDTH`) — starting points calibrated against seed recall; the
  width cap is the main knob for "how wide may an S setup be."
- The efficiency / counter-burst-ratio cutoff that separates trend from range.
- The minimum swing size (ATR displacement) that "counts" as a leg — ties to the
  ~10-bar / behavioral floor for "what is a real range."
