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

> **Revised 2026-10-02** — the card and the glance now cap the base at 0.45 (the modal stays at
> 0.35), the card's price band is 88% of a well locked to 1.9:1 by width, and the census lives at
> `tools/research/chart_framing_census.mjs`. Everything above the
> [2026-10-02 revision](#2026-10-02-revision--the-close-up-on-his-two-screens) is the 2026-09-02
> record and is left as measured.

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
**435px inside the 490px card**, three-up, before and after. (A two-up 620px minimum shipped for a
few hours between these two measurements and was reverted the same day — see "What the first cut got
wrong" below.)

### Mini card

| | BEFORE (490px card, 435px plot) | AFTER (490px card, 435px plot) |
|---|---|---|
| window, trading days | min 56 · **med 62** · p90 131 · max 300 | min 55 · **med 121** · p90 220 · max 300 |
| px per trading day | 1.45 – **7.02** – 7.77 | 1.45 – **3.60** – 7.91 |
| base % of card WIDTH | med **51.9** · p90 83.0 | med **30.6** · p90 43.2 |
| cards with the base over 45% of width | **136 / 230** | **19 / 230** |
| cards with the base over 60% of width | **97 / 230** | **6 / 230** |
| cards under 3 px per trading day | 8 | 82 |
| boxes cropped off-pane | 0 | 0 |
| **longer rest drawn NARROWER than a shorter one** | **2,275 / 25,904 pairs = 8.8%** | **6 / 25,904 = 0.0%** |

The last row is the complaint as a number: roughly one side-by-side comparison in eleven actively
lied about which consolidation had lasted longer. It is now **0.0%** — 6 pairs of 25,904, and every
one involves a rest of **130+ trading days**, i.e. the monster tail, never a normal-length rest.

The cost is bar thickness on long rests: 82 cards draw under 3 px per trading day, against 8 before.
That is the honest price of the cap — a 90-day rest shown at a third of the pane needs a 270-day
window, and 270 days do not fit thickly in 435px. The cards the operator actually triages are not
among them: a 24-day rest gets 83 days at **5.24 px/day**, a 33-day rest 109 days at **3.99**.

### What the first cut got wrong

The first version of this change used a **fixed 140-day span for every setup** and widened the card
to 620px (two-up). Both were reverted the same day, on the operator's ruling:

> *"you made that only 2 cards are visible per row, return it back to 4 [3 at his width]. Return it
> to the original width, I asked for a more accurate representation of the price data bars and the
> stock rather then a streched out version … by focusing on the consolidation area and then some
> room behind it for added context before the consolidation (this is way way too much). I'm
> requesting for a dynamic scaling based on the found consolidation."*

He is right on both counts. A fixed span makes the window a property of the **surface** instead of
the **setup** — the same mistake as the retired trim, pointing the other way: 140 days is far too
much room behind a 24-day rest. And two-up made the chart wide and short (3.1:1), so a stock's whole
run was squeezed into a strip with the rest as a sliver in the corner. **The card's spare room was
vertical, not horizontal.** Three-up at 490px with the 225px well is a **2.17:1** chart — within a
rounding error of Finviz's own screener charts (2.1:1), which is the reference he pointed at.

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
| **MSEX** | 33 trading days | 56-day window, base **58.9%** of card width | **109**-day window, base **30.3%**, 3.99 px/day |
| **NP** | 24 trading days | 56-day window, base **42.9%** | **83**-day window, base **28.9%**, 5.24 px/day |
| **TECH** | 25 trading days | 56-day window, base **44.6%** | **86**-day window, base **28.9%**, 5.06 px/day |
| **SBUX** (the long-rest case) | 82 trading days | 100-day window, base **82.0%** | **220**-day window, base **37.3%**, 1.98 px/day |

NP gets 83 days and MSEX 109 *because their rests lasted different lengths of time* — the window is
the setup's, not the surface's. That is the property that was missing, and a fixed span did not have
it either.

---

## The model

One reference time scale per surface, stretched only by a long base:

```
capWindow = ceil((visibleBase + rightPad) / baseWidthCap)   // the rest sets the scale
window    = max(minWindowBars, min(legibilityCeilingBars, capWindow))
            // ...and the ceiling YIELDS to a rest it cannot frame:
            if (capWindow > ceiling && (visibleBase + rightPad) / window > ceilingYieldShare)
              window = max(window, min(capWindow, carriedHistory))
from      = min(rightEdge - window + 1, baseStart - minContextBars)   // never-crop outranks both
```

| profile | minWindowBars | ceiling | baseWidthCap | ceilingYieldShare | minContextBars |
|---|---|---|---|---|---|
| `mini` | 55 (a floor, not a span) | 220 | 0.35 | 0.75 | 18 |
| `modal` | 252 (one trading year — here the floor IS the span) | 300 | 0.35 | 0.60 | 25 |
| `popover` | 55 | 105 | 0.35 | **1** (see the glance section) | 14 |

**`minWindowBars` is a floor, not a span.** It only binds for a rest short enough that the cap would
leave no approach leg (under ~15 days); it is inert on all 230 live setups, and exists so a 5-day
rest cannot produce a 43-day window.

**`legibilityCeilingBars` has to sit HIGH, and that is counter-intuitive.** A low ceiling reads like
a legibility win — hold the bars thick — but it makes the window stop growing while the rest keeps
growing, so past the ceiling a *longer* rest starts drawing *narrower* than a shorter one. Measured
at a 110-day ceiling: the lie returns on rests as short as **37 trading days** and the
order-inversion rate goes to **9.7% — worse than the 8.8% this whole program exists to remove.** At
220 it is 0.0%. Legibility on the long tail is bought with the yield, never by lowering the ceiling.

`baseWidthCap` is deliberately **identical** across the three, so the card, the modal and the glance
can never disagree about how much pane a rest owns. It is now the PRIMARY lever — it sets the window
for every setup, not just the long ones. Measured (live 230, `tools/chart_framing_census.mjs`):
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

---

## 2026-10-02 revision — the close-up, on his two screens

> *"I'm still interested in increasing the real state each setup gets in the mini chart cards
> (look at the screenshot) + I want more close up on the setups themselves (meaning in exchange of
> some information from the left side) + Very important to keep an ACCURATE view of how each setup
> looks in the big advanced chart/trading view/finviz or other websites and tools"* — operator,
> 2026-10-02, circling the card's two-row header.

This is his explicit **close-up** ask, not a box-height target: the retired vertical trim stays
retired. The window is still the setup's (`ceil((rest + pad) / baseWidthCap)`); it is just framed
closer, and nothing deletes trading days to make a box look taller. The same day the card grid was
capped at three per row on every monitor (his main screen is 2560x1440 and had been drawing five
493px cards) — see [`decisions.md`](decisions.md) 2026-10-02.

Reproduce: `node tools/research/chart_framing_census.mjs` (section "2026-10-02 — the close-up").
Run of record: the live artifact of 2026-10-02, 109 setups, 208–300 candles (median 300). Plot
widths are the card less its borders and the ~53px price scale: **563px** for the 618px three-up
card at 1920x1080 and **776px** for the 831px card at 2560x1440 (the 2026-09-02 figures above are at
435px, 1536 effective). "The big chart" is the modal's daily pane at 1920x1080, measured at
**1318x672px**.

### The model, revised

| profile | minWindowBars | ceiling | baseWidthCap | ceilingYieldShare | minContextBars | price band (margins) | volume from |
|---|---|---|---|---|---|---|---|
| `mini` | 55 | 220 | **0.45** (was 0.35) | 0.75 | 18 | **88%** (0.04 / 0.08; was 80%, 0.06 / 0.14) | **0.92** (was 0.86) |
| `modal` | 252 | 300 | 0.35 (unchanged) | 0.60 | 25 | 78% (unchanged) | 0.84 |
| `popover` | 55 | 105 | **0.45** (was 0.35) | 1 | 14 | 77% (unchanged) | 0.88 |

`baseWidthCap` is **no longer identical** across the three: the card and its preview (the glance)
agree, and the modal may frame wider but never closer — the card is the close-up, the modal is the
stock. 0.45 stays below the 0.50 tail knee measured above. At 0.45 `minWindowBars` is no longer
inert: it binds on rests under 20 trading days.

### The well is width-locked now

The 2026-09-02 well was keyed to the viewport's **height** (`clamp(200px, 26vh / scale, 300px)`).
That made the card's shape a property of the **screen**: 281px tall in a 618px card at 1920, but
capped at 300px in a card of any width at 1440 tall — so on his main screen the same setup drew in
different proportions than on his secondary. The well is now **`aspect-ratio: 1.9`** of the card's
own width (`--card-chart-aspect`, floor `--card-chart-min-h` 200px, which never binds at the 480px
card minimum): **324px at 1920, 436px at 2560**, "slightly more a cube like" (2026-09-02) than the
~2.2:1 well it replaces. A ratio is unitless, so the UI-scale `zoom` scales it with its card and the
whole correction paragraph above no longer applies. The header and the tag strip fold to one row
each (30px and 28px), so at 1920 the card stays ~384px tall (was 390) while the well grows 15%.

### Before → after (live 109)

| | BEFORE (cap 0.35, band 80%, 26vh well) | AFTER (cap 0.45, band 88%, 1.9:1 well) |
|---|---|---|
| window, trading days | med **106** · p90 212 | med **83** · p90 165 |
| base % of card WIDTH | med **30.2** · p90 32.5 | med **38.8** · p90 41.8 |
| bases over 45% / 60% of width | 5 / 1 | 5 / 1 |
| boxes cropped off-pane | 0 | 0 |
| **1920 three-up** — well | 281px | **324px** |
| median box drawn (w x h) | 170 x 48 px | **218 x 70 px** |
| squareness vs the big chart, median | 0.58 | **0.65** |
| px per trading day, median | 5.31 | 6.78 |
| cards under 3 px per trading day | 14 | **7** |
| **2560 three-up** — well | 300px (capped) | **436px** |
| median box drawn (w x h) | 234 x 51 px | 301 x 94 px |
| squareness vs the big chart, median | 0.45 | **0.64** |
| 2560 **five-up** (before the three-card cap) | 493px card, squareness **0.80** | — |

**Squareness** is the box's height/width on the card divided by the same box's height/width on the
big chart; 1.00 is the same shape. The card still draws boxes flatter than the big chart, but less
than before — so the closer view is **not** a tighter-looking view. And it is now the same shape on
both monitors (0.65 / 0.64), where before it was 0.58 on the 1920 three-up card and 0.80 on the 2560
five-up one: **the shape no longer depends on the monitor.**

**Order inversion, with a pixel tolerance.** Strict, it goes 1 → 38 of 5,772 pairs (0.7%). Almost
all of that is the cap's `ceil()` step: a 32-day rest earns an 83-day window and a 31-day rest 80, so
the longer one is drawn ~1.1px narrower at 563px (~1.5px at 776). No eye sees it. Counted only when
the longer rest is drawn more than **1px** narrower: 1 → **15** (1920) and 1 → **27** (2560); more
than **2px**: **1 → 1** on both. The one real inversion is TTC (171 days) against FLNG (136), the
monster-tail yield, and it was there before.

**The glance** moves with the card (med base share 30.5% → 38.8%; over 60% unchanged at 9; glances
under 3 px/day unchanged at 5). **The modal** is untouched (median 252 days, base share med 12.7%).

### Found on the way: the one-row chip strip needed an honest fit

`TagRow` decides how many chips fit before its `+N` by comparing chip widths from
`getBoundingClientRect` — screen px, already multiplied by the `--ui-scale` zoom — against the
row's `clientWidth`, which is layout px and **includes its padding**. On the old two-row strip the
error hid in the second row; on one row it lets the last chip or the `+N` wrap out of sight. Both
sides are now layout px inside the padding. Swept over 205 grid widths on the live cards: the old
measure spilled at **31 widths at Scale 1 and 163 at 0.85**; the fixed one at **0 and 0**.

## 2026-10-03 revision — one card size, one big-chart size, on both screens

> *"Okay now cards look huge, I want them to retain the original size so the scaling looks the
> same, with the extra monitor space I could just you know..... see more of the website. same goes
> for the big charts"* — operator, 2026-10-03, with a screenshot of three 831px cards at 2560.

The 2026-10-02 three-card ceiling read "the clean 3 Charts per row" as a COUNT; his rule was the
1920 card. The grid is now `minmax(590px, 1fr)` with no ceiling: **three 618px cards at 1920, four
620px cards at 2560** (Watchlist: 607 and 612). The well is still 1.9:1 of the card's width, so the
card, its ~563px plot and every setup drawn in it are now the same on both screens — the
"1920 three-up" rows above describe the 2560 screen too, and the "2560 three-up" rows are history.
On the 2560 screen 12 cards sit above the fold instead of ~6.

The big charts hold their 1920 size the same way: the lens's chart band at **567px** tall (its
daily pane **1318x566** on both screens, where the 2560 screen had drawn it 1318x926, every setup
64% taller), and the Watchlist D/W/M band at **1850x805** (daily pane 1247x770 on both, against
1714x1130 at 2560), with the card grid rising into view below it. The lens first went in as a
centered 1760x921 box; the same day he asked for it to *"strech more down so we could see more,
even put the entire big chart higher"*, so it fills the screen's height again from the top and
its read panel takes the room the band no longer does (300px at 1920, 660px at 2560 — the whole
read without scrolling). No framing knob moved: `CHART_FRAMING` is unchanged and the window is
still the setup's. Measured live at 1920x945 and 2560x1305; pinned in `uiScale.test.js`.
