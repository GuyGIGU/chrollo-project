# Chart framing census — 2026-09-02

Evidence for the [`decisions.md`](decisions.md) ruling *"the card and the modal frame by a fixed
reference time scale that only a long base stretches; the vertical proportion trim is retired."*

Reproduce every figure below in one command (~2 s, read-only, boots nothing):

```
node tools/chart_framing_census.mjs
```

It imports the **shipped** framing math (`webapp/frontend/src/components/chartGeometry.js`) for the
"after" column, so that column can never drift from what the app draws; the "before" column is a
transcription of the retired model, kept inside the census because the code it describes was
deleted in the same change. The artifact it reads (`output/screener_data.json`, 230 setups) is
gitignored per EC-53, so the numbers below **are** the record — the script re-derives them whenever
an artifact is present.

Run of record: `output/screener_data.json`, scan 2026-09-01, 230 setups, 231–300 daily candles
carried per setup (median 300 ≈ 14 months).

---

## The complaint

> *"the mini charts are showing the consolidation much wider (horizontally) then they are making
> them appear much much tighter when they actually are making me confuse wide choppy setups for
> cute tight ones … + when looking at the close up chart, I always got to zoom out to see the real
> stock."* — operator, 2026-09-02, with two screenshots of MSEX (the card, and the same stock in
> TradingView at ~190 trading days).

## The cause

Each card chose its own window, then ran a pass that bought **vertical** box height with a
**horizontal** knob: delete the oldest trading days until the box owns 40% of the visible price
range (`minBaseHeightFrac`), bounded by a 55-day floor (`trimFloorBars`). The pass carried an
escape hatch — *if even the most-trimmed window cannot reach the target, trim maximally anyway.*

| | measured |
|---|---|
| trim fired | **179 / 230** cards |
| of those, **futile** (target proved unreachable, trimmed to the floor for nothing) | **140** |
| trim succeeded (reached its own 0.40 target) | 39 |
| modal: futile trims | **167 / 230** |

`trimFloorBars = 55` shipped in the Finviz UI program and was never ruled by the operator.

## Before → after

Card plot widths are the real ones, measured in the running app at 1536×864 effective, scale 1.00:
435px inside the old 480px-minimum card, 687px inside the new 620px-minimum one.

### Mini card

| | BEFORE (480px card, 435px plot) | AFTER (742px card, 687px plot) |
|---|---|---|
| window, trading days | min 56 · **med 62** · p90 131 · max 300 | min 140 · **med 140** · p90 220 · max 300 |
| px per trading day | 1.45 – **7.02** – 7.77 | 2.29 – **4.91** – 4.91 |
| base % of card WIDTH | med **51.9** · p90 83.0 | med **26.4** · p90 43.2 |
| cards with the base over 45% of width | **136 / 230** | **17 / 230** |
| cards with the base over 60% of width | **97 / 230** | **3 / 230** |
| cards under 3 px per trading day | 8 | **8** |
| boxes cropped off-pane | 0 | 0 |
| **longer rest drawn NARROWER than a shorter one** | **2,275 / 25,904 pairs = 8.8%** | **37 / 25,904 = 0.1%** |

The last row is the complaint as a number: roughly one side-by-side comparison in eleven actively
lied about which consolidation had lasted longer. It is now 0.1% — and **every one of the 37
survivors involves a base of at least 96 trading days**, i.e. the monster tail, never a
normal-length rest. Below the cap crossover (base ≈ 44 days) every card is drawn at the same
140-day scale, so there width *is* duration, exactly.

### The monster tail — the ceiling yields (operator ruling, same day)

The first cut of this change left seven cards with the base still owning 61–100% of the pane at the
220-day ceiling. Ruled: *"for monster bases simply zoom out the base."* So the ceiling now **yields
to a base it cannot frame**: if the base would still own more than `ceilingYieldShare` (0.60) of the
pane at the ceiling, the window opens as far as the cap wants and the carried history allows.

It is a TAIL rule, not a raised ceiling, and the difference was measured:

| | over 60% of width | cards under 3 px/day |
|---|---|---|
| ceiling 220, no yield | **7** | 2 |
| ceiling raised to the full history | 3 | **47** |
| **ceiling 220 + yield at 0.60 (shipped)** | **3** | **8** |

Simply raising the ceiling fixes the same four cards (7 → 3) and drags **45 medium-base cards**
below 3 px per trading day — from the ceiling's 3.12 down to 2.31–2.96, and 17 of them all the way
to 2.29 — a legibility regression on cards that read fine. The yield buys the same result at a cost
of 8 cards instead of 47: CRSP · GNE · REXR · AM · STRA · TTC · XRN · CHD.

**Three cards cannot be fixed by framing at all** — the payload does not carry enough history:

| ticker | rest lasted | history carried | window the cap wants | best possible |
|---|---|---|---|---|
| STRA | 344 days | 300 | 872 | **100% of width** |
| XRN | 263 days | 300 | 766 | 87.7% |
| CRSP | 189 days | 300 | 555 | 63.0% |

`DASHBOARD_CHART_DAYS` is 300 for every setup. Raising it globally would add ~6.3 MB to a 17.8 MB
artifact; a per-setup floor (carry `max(300, base_len + context)` for the ~14 setups with a base
over 120 days) would cost well under 1 MB. **Not built — it is a scan-pipeline change and the
operator's call.**

### Modal (daily pane ~1050px)

| | BEFORE | AFTER |
|---|---|---|
| window, trading days | min 81 · **med 81** · p90 160 · max 300 | min 231 · **med 252** · p90 286 · max 300 |
| windows pinned at the 81-day floor | **140 / 230** | — |
| px per trading day | 3.50 – **12.96** – 12.96 | 3.50 – **4.17** – 4.55 |
| base % of width | med **40.7** · p90 75.3 | med **14.7** · p90 33.2 |
| base over 60% of width | 50 | 3 |
| history shown, of what the payload already carried | **27%** | **84%** (the rest is one scroll away) |

`DASHBOARD_CHART_DAYS` stays at 300 — deliberately out of scope. The payload already carried 3.7×
what the modal was showing; the defect was entirely in the framing.

### Hover glance (~330px plot) — improved, still the worst surface

| | BEFORE | AFTER |
|---|---|---|
| base % of width | med **61.6** · p90 87.2 | med **35.2** · p90 78.1 |
| base over 60% of width | 118 | **48** |
| px per trading day | 1.10 – **5.69** – 7.17 | 1.10 – **3.14** – 4.71 |
| glances under 3 px per trading day | 20 | **20** |

Better, and still bad: a 330px pane cannot show seven months of trading at a legible bar width.

**The glance yields at 1, not at the card's 0.6 — and that is deliberate.** The first cut of the
monster zoom-out reused 0.60 on every profile. Against the glance's 105-day ceiling that is not a
tail rule at all: it trips at a 59-day rest and fires on **66 of 230 setups (29%)**, dropping those
glances to **1.1–1.8 px per trading day**. Measured alternatives on the live 230:

| glance `ceilingYieldShare` | base over 60% of width | glances under 3 px/day |
|---|---|---|
| 0.6 (the card's) | 3 | **66** |
| 0.8 | 23 | 43 |
| **1 (shipped)** | **48** | **20** |
| no yield at all | 63 | 20 |

At 1 the glance yields only when the rest does not *fit* the pane, which costs nothing against no
yield at all (the same 20, and those are the never-crop clamp's doing, not the yield's) while still
pulling bases over 60% of width from 63 to 48. The glance is a **recognition** surface by ruling,
and 1.1 px/day serves recognition worse than a wide base does.

**RULED the same day — the glance is a preview, never a verdict** (operator: *"oh yeah that's fine"*).
Its job is recognition — *which row is this* — and the card is where tightness is judged. **The standing
consequence: the glance's 380px constraint may never be used as an argument to lower the card's or the
modal's span.** If a future session finds the glance dishonest, widen the glass (`GLANCE_WIDTH` in
`glanceMath.js`) — never retune `CHART_FRAMING.mini`. Placement was re-ruled in the same exchange: the
glass now opens beside the cursor rather than against the row's ticker cell. See
[`decisions.md`](decisions.md) 2026-09-02.

### The two cards he screenshotted

| ticker | rest lasted | BEFORE | AFTER |
|---|---|---|---|
| **MSEX** | 33 trading days | 56-day window, base **58.9%** of card width | 140-day window, base **23.6%** |
| **NP** | 24 trading days | 56-day window, base **42.9%** | 140-day window, base **17.1%** |
| **TECH** | 25 trading days | 56-day window, base **44.6%** | 140-day window, base **17.9%** |
| **SBUX** (the cap-bound case) | 82 trading days | 100-day window, base **82.0%** | 220-day window, base **37.3%** |

MSEX at 23.6% and SBUX at 37.3% now differ *because their rests lasted different lengths of time*.
That is the property that was missing.

---

## The model

One reference time scale per surface, stretched only by a long base:

```
capWindow = ceil((visibleBase + rightPad) / baseWidthCap)
window    = max(referenceBars, min(legibilityCeilingBars, capWindow))
            // ...and the ceiling YIELDS to a base it cannot frame:
            if (capWindow > ceiling && (visibleBase + rightPad) / window > ceilingYieldShare)
              window = max(window, min(capWindow, carriedHistory))
from      = min(rightEdge - window + 1, baseStart - minContextBars)   // never-crop outranks both
```

| profile | referenceBars | ceiling | baseWidthCap | ceilingYieldShare | minContextBars |
|---|---|---|---|---|---|
| `mini` | 140 (~7 months) | 220 | 0.35 | 0.60 | 18 |
| `modal` | 252 (one trading year) | 300 | 0.35 | 0.60 | 25 |
| `popover` | 70 (~3.3 months) | 105 | 0.35 | **1** (see the glance section) | 14 |

`baseWidthCap` is deliberately **identical** across the three, so the card, the modal and the glance
can never disagree about how much pane a rest owns. The cap crossover is base ≈ 44 trading days, so
it is a tail rule: 62% of setups never touch it. Measured (live 230, `tools/chart_framing_census.mjs`):
the cap moves only the **middle** of the distribution — base % of card width p75 30.0 / 32.5 / 37.1
at cap 0.30 / 0.35 / 0.40, with the median (26.4) and p90 (43.2) unchanged across all three, because
p90 is owned by ceiling-bound and yielded cards whose share is cap-independent. **The tail knee is at
0.50**: p90 43.2 → 47.5 and cards over 45% of width 17 → 63.

`minContextBars` is the 2026-08-09 approach-leg ruling and is the **only** rule that survives the
rewrite. It outranks the legibility ceiling: a 280-day base over 300 candles is drawn at 298 days,
past the ceiling, rather than losing the bar where the box opened.

### Vertical proportion is a consequence now, not a target

The retired trim existed to stop a base being drawn flat. That job moves to the chart well, which
had **never grown**: `clamp(180px, 11vw, 240px)` resolves to 168.96px at a 1536px viewport and so
sat permanently on its 180px floor, at every UI-scale step (CSS `zoom` does not rescale `vw`). The
well is now `clamp(200px, calc(26vh / var(--ui-scale)), 300px)` = **225px** at 1536×864 (measured
224.625px), and the mini chart's date axis is hidden (the card header already carries the as-of
date), so the price band goes 123px → **180px, +46%**. Net: the box is drawn at essentially the same
pixel height as before while the card shows **2.3× the history**.

The 225px figure is scoped to Scale 1.00 and viewport heights ~770–1153px. Only the clamp's *middle*
term carries the `/ var(--ui-scale)` correction; its bounds are ordinary px and render at
`bound × scale`. So the well is physically constant only while `200 ≤ 26vh/scale ≤ 300` — at 864px
that is every step up to 1.10, and from 1.15 the 200px floor binds and the well grows with the zoom
(230 / 240 / 250 / 260px at 1.15 / 1.20 / 1.25 / 1.30). Below a ~770px-tall window the floor binds
even at Scale 1 (a 720-tall window gets 200px, +11% over the old 180 rather than +25%). The
behaviour is benign — the well only ever gets bigger — but do not build on "constant at every step".

---

## Tested-DEAD, measured here

**1. A log price scale instead of the vertical trim.** Intuitive — a percentage-honest axis should
give a base at the top of an advance a fairer share. Measured on identical windows: box share of the
visible price range **linear med 0.227 / p10 0.104 vs log med 0.203 / p10 0.085**; log is better on
only **18 of 230** charts. Structural, not incidental: these bases sit at the *top* of an advance,
which is exactly where a log axis compresses them.

**2. "Just match his TradingView density."** The most intuitive proposal in this space, and
measurably wrong. Pinning the card to a fixed px-per-day, in the same 687px plot:

| fixed density | window | base % of width, median | over 45% | over 60% |
|---|---|---|---|---|
| 7.0 px/day (his TradingView) | 98 days | 37.8 | 88 / 230 | 66 |
| 5.0 px/day | 137 days | 27.0 | 65 / 230 | 38 |
| **shipped (140-day reference)** | **140 days** | **26.4** | **17 / 230** | **3** |

Density is a legibility budget; the **span** is the invariant. Matching his TradingView px/bar in a
half-width pane matches the wrong thing — he reads at that density *because his pane is 1389px wide*.
