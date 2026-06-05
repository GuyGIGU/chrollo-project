# The Chrollo Structure Legend

**Status: north-star / shared vocabulary (v1).** This document describes *how a
skilled trader reads a base* and the model the structure engine is being
steered toward. It is intentionally ahead of the code. For what the engine
*actually does today*, see [strategy_v2.md](strategy_v2.md) (the
implementation-mirroring source of truth). This file is the language we agree
on first; the detector is then built to match it.

Nothing here is a gate. Every concept below is meant to become a **descriptive,
recordable measure** (measure-first), never a filter that drops a ticker.

---

## Framing principle — it's all pattern recognition

A stock's accumulation is a **story of nested processes**. Big ranges contain
smaller ranges; the smaller ones are *derivative of* the bigger ones, not
replacements for them. Some processes simply have mini-processes inside them,
and that's fine — a skilled trader reads the whole nesting at once. The engine's
job is to become a **trained pair of eyes** for that pattern, not to force every
chart into one textbook template.

**Point of view is always *now*.** We read left → right, but the thing we
*evaluate* is the **right-most actionable structure**. Everything to its left is
context (the energy-gathering history), not the setup itself.

---

## The two lego pieces

The single most important idea: **the climax pair and the trading range are two
independent pieces.** They are detected separately and *composed* — neither one
masquerades as the other.

| Piece | What it is | Rooted by |
|---|---|---|
| **A — Climax / Anchor pair** (BC/SC + AR) | the *event* where a trend exhausts and hands off to equilibrium | the terminal pivot of the advance (or decline) + the reaction right after it |
| **B — Trading Range** (R + S) | the *structure* where price is actually oscillating now | its **own** root swing pair |

Wyckoff's textbook says the range is born *at* the climax — that resistance sits
right at the Buying Climax. **That is only one case.** In real charts,
equilibrium frequently settles **below and later** than the climax. The BC is
real, the AR is real, but the consolidation you would actually trade has *its
own* R/S rooted by *its own* swing pair, somewhere else.

### The binding rule

> **R anchors on the BC only if the consolidation actually respects that
> boundary.** If it does not, the engine still records "that spike *was* the
> Buying Climax" (Piece A), but it locates the range independently with its own
> R/S (Piece B), then verifies the rest of the bars respect those lines.

"**Did the consolidation respect the BC as R? (yes/no)**" is therefore a
*recordable boolean*, not a gate — the canonical measure-first move.

---

## Relative labeling — Mini-BC / Mini-AR

Labels attach to the **current** consolidation, not to the stock's entire
history. When a larger macro climax came earlier, the swing responsible for the
*current* range's boundaries is the **Mini-BC / Mini-SC** and **Mini-AR**.

The engine only ever acts on the **operative (Mini) pair** — the local swing
that birthed the range in front of us. The macro climax is left-side context.

### The reading procedure (generalized)

1. Start at the **right edge** — the consolidation being evaluated.
2. Walk **left** to the swing that *births* that range: follow the advance up to
   its **terminal high → that peak is BC** (Mini-BC).
3. The **reaction / deep correction right after → AR** (Mini-AR), which sets the
   floor of that move.
4. *Only then* scope the consolidation (R, S, phases, LPS) **inside** the box
   those two events define.

This structurally cannot land mid-trend, because mid-trend is not a terminal
pivot and is not adjacent to the range. (Contrast the current engine, which does
a global biggest-swing / highest-volume hunt and on a stock that ran hard into
its base latches onto the *markup leg itself* — see ECPG below.)

---

## Parent ranges & inner ranges — the accumulation story

Ranges nest. A **parent range** can contain a **mini (inner) range**; the inner
one is a sub-process inside the bigger energy-gathering stage. They work
*together* and are *derivative of each other* — understanding the nesting is
understanding the whole story of the stock's accumulation.

- **Selection — which range is "the setup":** always the **freshest range at the
  right edge** (where an entry would actually fire). Older / higher ranges are
  not discarded — they are the **parent process the current range is nested
  inside**: the energy-gathering stage.
- A setup at an inner range that sits in the upper half of a parent range is
  understood as *"a process inside a bigger process"* — still the actionable
  setup, but read with the parent as context.

---

## Qualification — what counts as a range at all

There is no hard cold number. A real range is recognized **behaviorally**:

- well-respected boundaries,
- oscillation / zig-zag / repeated touches,
- width can be as tight as single-bar chop,
- working minimum **~10 bars**.

This stays **descriptive / confidence**, never a hard gate (consistent with the
current directive: no new gates in this stage).

---

## Last Supper (LS) — the stretch measure

The **Last Supper** is a post-LPS shakeout that fires when the LPS forms
stretched too far from its energy source — it takes out the stops sitting at the
obvious LPS trap.

**Stretch = the move from the LPS, measured relative to the range that birthed
it** — where "the range that birthed it" is the **last energy-gathering stage
before the move**, i.e. the *innermost* range the LPS sits in (not automatically
the parent).

Two measurable components:

- **a. raw move from the LPS** — how far price extended off the LPS itself.
- **b. distance from the last consolidation** — how stretched the LPS is from
  its birthing range.

> Rule of thumb: **measure the move from an LPS relative to the range that
> birthed it.**

Example: parent range, a mini range nested in its upper half, the LPS sitting at
the mini range → the stretch is measured **from the mini range**, because that
is the last energy source that set the move off. This falls straight out of the
nesting model: "the range that birthed it" is simply *whichever range is
innermost at the LPS*.

LS becomes a raw archived measure first (an "LPS stretch" field), validated
against accruing outcomes (especially the durable-win vs cash-grab label) before
it ever influences ranking.

> **Shipped (Stage 2A).** The stretch is now a raw archived measure:
> `_lps_stretch_atr` and `_lps_stretch_box` — the LPS foot's distance above the
> box ceiling R, in ATR and in box-heights — from
> [bin_features.py](../core/structure/bin_features.py). Component **b**
> ("distance from the last consolidation") is the box-relative form; the
> innermost range *is* the operative box the detector returned. Measure-first:
> archived, never yet scored.

---

## Engine implications

1. **The fix is two detectors, not one tweak.** Today the engine fuses Piece A
   and Piece B — the anchor it finds *defines* where R/S get carved (see
   strategy_v2.md, "Phase A — Anchor Discovery/Selection" → "Phase B — Zigzag
   S/R Anchoring"). Splitting them so the range can be rooted by its **own**
   swing pair, independent of the climax, is the real correction.
2. **Nesting = energy source = Last Supper.** The parent/inner-range model and
   the LS stretch measure are the *same axis*. Once nesting is represented,
   LS is "distance from the innermost birthing range" and comes almost for free.
3. **Everything here is a measure, not a gate.** BC-respected-as-R, range
   qualification confidence, LPS stretch — all raw archived fields, recalibrated
   later against the live outcome archive.
4. **Read the range from its earliest valid start, not its best-scoring
   sub-window (shipped — Change B).** The outer box now selects the *earliest
   good-enough* candidate pair (`select="earliest"`), so the consolidation is
   rooted at the true range start near the AR low. The old "pick the
   highest-scoring pair" rule kept grabbing a tight recent *tail* and discarding
   the real base — "a random pair that scored better" starting the box mid-
   equilibrium. A single quality floor (`PHASE_B_REACH_QUALITY_FLOOR`) keeps it
   from reaching back into a materially looser framing. See
   segmentation_research.md → Build path → Change B.

5. **Regions are now measured (Stage 2A).** `measure_bins` records each region's
   (A / B / D / LPS) size, range, and volume as raw archived fields — the
   "where am I in the base?" layer — alongside the Minervini Stage-2 trend
   template. The Phase-D boundary is single-sourced with the scoping overlay
   (`scope._resolve_phase_d_start`). Still measure-first: nothing here gates or
   scores. See strategy_v2.md, "Region (Bin) Features & Trend Template".

---

## Worked example — ECPG (the case that motivated this legend)

- The stock **ran hard up into its base.** The terminal high of that advance
  (~92 spike) is the **BC** (the climax event). The deep correction after it is
  the **AR**.
- The actual consolidation is the box price oscillates in afterward
  (~78–85), with **R drawn at the range's repeated-touch ceiling (~85)** — which
  sits *below* the BC spike — and **S at ~78**.
- **The engine's error:** it fused A and B, did a global biggest-swing hunt, and
  anchored on the **rising markup leg** (and even at the *bottom* of that leg,
  labeling an uptrend low as a Selling Climax — a semantic inversion). A wrong
  anchor is a coordinate-system error: every phase downstream inherits it and
  the real R/S box gets buried.
- **The legend's fix:** still mark the ~92 spike as BC (Piece A), but **do not
  force R onto it** — detect that the bars oscillate in the ~78–85 box and root
  R/S on *that* box's own swing pair (Piece B); record "BC respected as R? → no."
