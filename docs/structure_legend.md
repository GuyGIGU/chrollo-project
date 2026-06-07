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

**The whole job, stated plainly.** We read, detect, and compare **staircases**
(swing sequences) to locate **boxes** (consolidations) — and those boxes contain
*inner* boxes with their own staircases. That recursion is the entire structural
task. The general reading we play toward is one clean layered layout:

> **Trend → Climax → Base → Inner Climax → Inner Base**

— *not* a template forced onto every chart (many setups, especially young ones,
show only part of it), but the spine of how price action is read here. This is a
system that **solves price-action puzzles** from boring OHLC + volume: no flash,
just disciplined reading, followed to the letter.

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

## Last Supper (LS) — the over-extension axis

**"Last Supper" is our own coined term** (not a published TA term) — the *last*
shakeout before the trend resumes. It names a real pattern: a deep correction,
sometimes sharp (a day or two) or drawn-out (several days), that **punishes an
over-extended entry** — it flushes the stops behind the obvious LPS, then pivots
and continues the move, often without you. Keep two things separate:

- **The event** — the flush itself. We do **not** detect or alarm on this
  everywhere; that is not the engine's job.
- **The condition** — *over-extension*: how far the LPS sits from the range that
  fed it. This is what we measure, because it tells you whether a Last Supper
  would hurt *you at this entry*. A precise, well-positioned entry (near support,
  off a rebound, after a Phase-C spring) survives a Last Supper; a stretched one
  is the trap.

It can appear **before *or* after an LPS** — Phase D holds more than one LPS (see
"Phase D is a sequence"), so a flush can sit between two of them.

**The good case has a name:** an LPS resting *just above* freshly-breached
resistance (R flipped to support) is close to its energy source and *not*
over-extended — the Wyckoff **Back-Up to the Edge of the Creek (BUEC)**, which
the engine already classifies as the `OVERSHOOT_R` zone.

**Stretch = the move from the LPS, measured relative to the range that birthed
it** — where "the range that birthed it" is the **last energy-gathering stage
before the move**, i.e. the *innermost* range the LPS sits in (not automatically
the parent).

Two measurable components:

- **a. raw move from the LPS — "% past the pivot."** How far price has extended,
  in percent, above its energy source — the trader-intuitive form (also
  Minervini's "don't buy extended past the pivot"). *Planned add.*
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

## Phase D is a sequence — the staircase

Phase D is **not a single LPS** — canonically it is a *staircase*: an advance
(**SOS** — sign of strength, wide spread + expanding volume) into a reaction
(**LPS** — narrow spread + drying volume), repeated, each LPS a higher low and a
valid add point, until markup. There can be **multiple LPSs** in one Phase D
(Wyckoff: *"despite the ostensibly singular precision of this term, there may be
multiple LPSs"*).

**SOS is a certainty-booster, not a prerequisite.** Theory says wait for a clean
SOS before trusting the LPS — but in practice the best entries are the *early*,
well-positioned ones (an LPS near support, off a rebound, right after a Phase-C
spring), because you catch the fish before the stream. Waiting for the SOS to
confirm = late to the party = the move is gone. So the engine must **never**
demand an SOS or drift toward later, more-confirmed setups. The SOS lives
*inside* the staircase (it is the advance leg between two LPS steps), never as a
"wait for it" gate.

**The staircase as a Phase-D maturity read.** How developed Phase D is — the
number of SOS→LPS steps, together with rising support and progressive volume
dry-up — is a real measure of *where we are* in the setup. It is to be **scored
as a bonus, never hard-gated** (same shape as ascending support / ADR: 0 for
absence, raw measure archived, tiers untouched).

---

## Engine implications

1. **One unified mechanism: climax → root swing → range — run at every scale.**
   The detector's real job is a single move: *given a window, find its climax
   (Phase A) and root the range (R/S) on the counter-swing that climax births.*
   The **outer** box is already largely decoupled in practice — the `cand_start`
   trim + earliest-valid-start selection (Change B) root R/S on their own zigzag
   pair, so the box sits at a healthy length (archive: `base_length` median ~31
   bars) even while the macro-climax label sits ~459 bars back, and that BC
   anchor does **not** feed R/S, LPS, scoring, or tiering. So the outer split is
   mostly *diagnostic* (a clean local Mini-BC + a "BC-respected-as-R?" boolean).
   **The real win is applying the same mechanism to the *inner* base.** Today the
   inner search starts at a **mechanical midpoint** (`_INNER_SEARCH_FRACTION` —
   the recent 50% of the outer) and grabs the tightest box: *no* inner climax,
   *no* root swing. Anchoring the inner box on a *detected* **Inner Climax**
   (inner Phase A) + its root swing — exactly how the eye reads it — is the
   upgrade, and it sharpens the inner range → Phase D → LPS → the actual trade.
   The machinery half-exists: `segment_swings._find_root_swing` already finds
   "climax → first big counter-burst (AR)"; today it runs once, on the outer,
   for chart labels only. Generalize it to the inner window. (The falsified v5
   experiment was *outer anchor preference* — a different lever; inner-climax
   anchoring is untested.)
2. **Nesting = energy source = Last Supper.** The parent/inner-range model and
   the LS over-extension axis are the *same axis*. With the inner range anchored
   on its own climax, "% past the pivot" is measured from the innermost birthing
   range automatically — the layout **Trend → Climax → Base → Inner Climax →
   Inner Base** falls straight out.
3. **Everything here is a measure, not a gate.** BC-respected-as-R, range
   qualification confidence, LPS stretch — all raw archived fields, recalibrated
   later against the live outcome archive.
4. **The box is the earliest WORKED equilibrium, or there is no box (shipped —
   worked-equilibrium rewrite).** Terminology: **BC / SC / AR** name the Phase-A
   *trend* (climax + automatic rally) — where the search begins; the box's rails
   are the **Resistance anchor / Support anchor** (mini-anchors for inner bases),
   which may coincide with BC/AR but usually sit later/tighter. A candidate pair
   is valid only if price *respects, touches, and zigzags through both rails
   constantly with no dead space* (`measure_equilibrium`: constant two-sided
   touch + both-halves dwell + coverage, not mid-churn). Selection keeps the
   **earliest** pair that passes every constraint — "the earliest *of the ones
   that qualify*." Because a sparse/dead-space framing can no longer be valid,
   the support anchor climbs off a one-time AR low until the band is genuinely
   worked (this is what finally fixes "anchored from the bottom"). If no pair
   qualifies anywhere, the stock is rejected. This supersedes the earlier
   "Change B / `PHASE_B_REACH_QUALITY_FLOOR`" earliest-good-enough rule (retired).
   See segmentation_research.md → Build path → Phase 2.

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

---

## Parent + Inner: the nested range model (draw both)

Decided 2026-06-06. When an inner box is found we **keep both** — the parent is
never thrown away:

- **Parent (outer) is the base of record.** Drawn R/S, base length, Phase A/B/D
  regions and the vertical bins all anchor on the parent, always. The inner no
  longer replaces it.
- **Inner box is detected (inner climax → root swing) and drawn** as a child R/S
  inside the parent.
- **The inner is a nested Phase D range, not a second base:**
  - the parent's **Phase D bin extends to span the inner** — no separate inner
    bins;
  - if the **LPS lands inside the inner box, the LPS is scored against the
    inner's tighter R/S** (trigger / tightness / zone); an LPS outside the inner
    scores against the parent.
- Net: it **keeps the base of record (parent) separate from the nested Phase D
  range (inner)**. The climax → root-swing → range mechanism (the "A/B split")
  sharpens *both* anchors. Phase C stays unbuilt.

**Inner-climax selection — best-of-both (measure-first verdict, 2026-06-06).**
`_detect_inner_phase_b_start` (core/structure/box_candidates.py) finds the
most-recent qualifying inner climax — a ≥ `AR_MIN_DROP_PCT` reaction leaving
≥ `INNER_MIN_DAYS` bars. But on the 197-ticker fixture a *pure* climax anchor
regressed inner detections 32 → 12 (it grabs late minor peaks on long bases). So
the inner search runs from **both** the detected climax and the old midpoint and
keeps the better box — 35 vs 32 today, never worse, and it captures the
earlier / longer inner bases the midpoint structurally can't see.

**Staging.** Stage 1: draw both (parent + best-of-both inner), firing unchanged
(shadow-clean) — eyeball the inner anchor on charts. Stage 2: the flip — parent
becomes primary, the LPS routes to the inner when it sits inside it, the Phase D
bin extends over the inner; validated (shadow-inspect + seed_recall + backtest +
before/after firing-diff).

## Agreed build order (measure-first, no new gates)

Distilled from the engine-strength review. All enrichment — none add a gate:

- **`_contraction_vol_trend`** ✓ *measured + archived* — volume drying up *across*
  the contractions, lightest at the final / tightest one (the VCP canon).
  `measure_contractions` now reads volume per contraction into `vol_trend ∈ [0,1]`
  and archives it raw; it is **not** folded into `quality`, so ranking is
  byte-unchanged (shadow-guard verified, 197 tickers). *Remaining:* surface it on
  the 🌀 VCP Coil chip — the one UX choice.
- **% past the pivot** — the raw-% over-extension form (Last Supper component a);
  measured from the inner-climax-anchored birthing range.
- **SOS→LPS staircase** — the Phase-D maturity read; **scored as a bonus, never
  gated** (ascending-support / ADR shape).
- **Base count / stage** (O'Neil) — trend maturity on the weekly frame; reset on
  a deep decline; late-stage (3rd/4th+) = higher-risk *context*, archived raw.
  Its own lane.

Structural prerequisite for the middle two is the **Inner-Climax** unification
(engine implication #1). Sequence: inner-climax mechanism → over-extension +
staircase; volume-trend anytime; base-count in parallel. The binding limit on
*detection* remains the LPS detector (the v5 anchor-preference experiment was
falsified) — left ringfenced under quality-over-recall.
