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

In `core/structure/consolidation.py`:

- `_find_pivots()` + `_build_zigzag()` — already produce the alternating
  peak/valley **swing skeleton** (the HH/HL/LH/LL path the whole trading world
  reads).
- `find_outer_box()` — climax (BC/SC) enumeration + earliest-anchor selection.
- `_phase_b_zigzag()` — range validation (boundary respect, touches, midline).
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
rooting to respect **segment ownership**. Shadow-diff moves here; that diff *is*
the review artifact (ECPG snaps to the 92 climax; MEOH unchanged).

**Phase 3 — fold nesting + Last Supper** off the same segment objects.

## Open knobs (calibrate against the eye, never hard-code blind)

- The efficiency / counter-burst-ratio cutoff that separates trend from range.
- The minimum swing size (ATR displacement) that "counts" as a leg — ties to the
  ~10-bar / behavioral floor for "what is a real range."
