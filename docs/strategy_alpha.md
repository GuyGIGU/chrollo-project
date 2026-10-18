# Strategy α — Wyckoff-Minervini Chart-Reading Reference

*(Formerly `docs/strategy_v2.md`; renamed at the 2026-07-18 Purity Pass close. Strategy α
documents the engine-α reading in its final, event-organized shape — the Reading Model
below is a catalog with **one entry per chart event**.)*

*(**Split 2026-07-27.** This file is now the **THEORY** — the operator's chart language and
what a good setup *is*. The implementation walkthrough moved to
[`engine_reference.md`](engine_reference.md), and the rulings + falsified-lever registry to
[`decisions.md`](decisions.md). The split exists so the theory can stay stable while the code
moves underneath it: **this document deliberately avoids naming files and functions**, so it
cannot rot when a module is renamed. If you need to know which function does a thing, that
question belongs in the reference.)*

> **RULE — read this before touching the reading engine.** Any change to chart-reading
> algorithm code (`engine_alpha/structure/`, `engine_alpha/scoring/`, or their
> detection/scoring knobs in `config/engine.py` / `config/scoring.py`) **starts by reading this document —
> the Reading Model section at minimum — and lands with it updated in the same change**
> when behavior moves. This file is the source of truth for *how Chrollo understands a
> chart*, not just a description of the code; letting them drift is a defect. (The rule is
> mirrored in `AGENTS.md` and the root `CLAUDE.md` so every agent session loads it.)

> **Where to go next.** *How* it is built → [`engine_reference.md`](engine_reference.md).
> *Why* it is built that way, and **what has already been tried and falsified** →
> [`decisions.md`](decisions.md). Check the latter before proposing any new knob or
> threshold — this engine has a real graveyard, and re-proposing a dead lever costs a
> full A/B cycle.

> **Companion — [`wyckoff_canon.md`](wyckoff_canon.md).** This document says what Chrollo *does*.
> Its companion says which Wyckoff ideas Chrollo **took, adapted, and deliberately left**, and
> which of his words are reused here with a different meaning. **Wyckoff is a source of ideas, not
> a specification** (operator ruling, 2026-07-26) — read the companion before proposing any change
> argued from "Wyckoff says…", and never open one whose whole justification is "canon has this and
> we don't."

This document is the **single source of truth for how we understand chart analysis in the first place** — the reading the engine is obliged to implement, not a description of what the code happens to do today. When the two disagree, this document states the intent and the code is the defect. (For what the code currently does, see [`engine_reference.md`](engine_reference.md); for the module map, [core/MAP.md](../core/MAP.md).)

The strategy combines Mark Minervini's Volatility Contraction Pattern (VCP) bias with Richard Wyckoff's Phase A/B/C/D structure. Goal: isolate **tight horizontal equilibrium bases** that have just printed an active **Last Point of Support (LPS)**, with no widening downward continuation, sitting after both R/S have been carved out by actual High/Low swing geometry.

The live structure reader is now chronological: one left-to-right daily-chart narrative, not a set of independent detectors reconciled afterward. It walks **Trend / root swing -> Phase A -> Phase B -> optional Phase C -> Phase D -> LPS**, backtracking to the next root swing when any brick fails. That single `Structure` is the shared reading object for horizontal analysis (time, cause, rail travel, compression) and vertical analysis (R/S levels, box height, undercut depth, trigger shelf).

---

## The philosophy — what Chrollo is for, and the theory behind the reading

*(Stated by the operator 2026-10-02 and 2026-10-03, and written here at his request, so this
file carries "our base philosophy for the engine and the theory that sits behind my
explanations". The Reading Model below is the chart language; this section is why that
language exists and where it sits in his decision. Each part says whether it is built. A part
marked not built is theory, and the engine must not be read as doing it.)*

### What Chrollo is for

Chrollo helps the operator **discover and prioritize strong stocks with constructive setups**
for his own review. He decides and trades by hand; Chrollo finds, measures and shows. Every
score means **observable evidence, never certainty**: not proof that accumulation is
happening, not a promise that a breakout will hold. His influences are Minervini, David Ryan,
Dan Zanger, Mark Ritchie II and Qullamaggie, and their methods differ. Never treat them as one
system, and never argue a change from "the book says" alone, the same rule as for Wyckoff
([minervini_oneil_canon.md](minervini_oneil_canon.md)).

His selection frame runs in one order: **a leading stock → constructive price and volume → a
well-formed base → a valid breakout → sustained follow-through.** It is a frame for choosing,
not a promised sequence. The principles under it, and where Chrollo stands on each:

| His principle | What it asks of a stock | Where Chrollo stands (2026-10-03) |
|---|---|---|
| Leaders, not cheap stocks | strength against the whole market comes first | the RS rating, ranked against every stock scanned; shown, never graded |
| Price leads | an uptrend, well-formed bases, orderly pullbacks, support that holds, a convincing breakout | the universe door's trend floor, and the whole Reading Model below |
| Volume is read with price, never alone | volume expanding on advances, drying up on pullbacks; heavy volume on a sharp decline is a caution | since the new reader went live (Sat 10/10/2026) volume is a fact on every event that never refuses, never elects and carries no points (his answer 10); the card shows the LPS's volume against the 50-day average, and his criterion is *under* that average (Sun 11/10/2026). Measured 2026-10-04 on the old reader's own LPS, a 2-to-7-day stretch it chose partly by volume, the quiet LPS separated the +25% moves (about 2.5 times from the loudest quarter to the quietest); measured 2026-10-12 on the new reader's own LPS days, under-the-average separates nothing and neither do a loud SOS or volume fading day by day, while the quietest 2-to-5-day stretch of the last week is a lead (its quietest quarter about 1.5 times the rest) for the live archive to confirm; up versus down volume inside the base does not, and heavy-volume declines are base length by another name |
| Accumulation is evidence, not proof | sideways trading alone is not accumulation; a base can hold distribution or stay unresolved | today a box's age earns points (Wyckoff's "cause"); the method's grade (dark) reads tightness and the event map, and age weighs nothing |
| No falling knives | strength → an orderly pullback → renewed strength → entry | the door's trend floor; the LPS is a pullback inside strength, and the buy is its high crossed |
| Group leadership is context | a strong stock can reveal a strong group, never prove one | owed: the industry and a count of peers also leading, shown only |
| Respect liquidity | the position fits what the stock trades | the 50-day dollar volume, shown, with no dollar floor until he names a size; a fire under $300M market cap leaves the scan (ruled 2026-10-03) |
| Let new listings build a record | a stock earns its place by its behaviour | the door's 200 trading days of history holds young listings out |
| Stay objective | no favourite deserves capital whatever the evidence | every chart is read fresh each scan; his stars and likes are recorded beside the read and never change it |

### Two reads, kept apart: the stock and the setup

**The stock** (is it a leader, and where is it in its life?) and **the setup** (is this a
tight base with a live LPS, and how good is the read?) are two questions with two reads. The
Reading Model below is the setup read, all of it. The stock read is the leadership read: the
RS rating, the trend template, the distance above the 52-week low, the 200-day average's
direction, the dollar volume, the market cap and the fundamentals (earnings and sales growth,
shown and archived from 2026-10-03); later the group.

His plan (2026-10-03): **two grades, one per read, built apart and used together at the end**
to find a market leader with a good setup. The stock grade is to be defined from measurement,
once a few weeks of fires carry the leadership and fundamentals reads; until then the stock
read scores and tiers nothing. Two places hold a stock trait hard: the universe door (price,
history, share volume, a close above the 50-day and 200-day averages, a one-year return of
-20% or better) and the $300M market-cap floor, checked on the fires after the read. The trend
template is context, never a hard filter (his words, the same day). The setup grade still carries two stock traits as points, the 52-week proximity
and ADR; the grade ledger (step 12 below, dark) takes them to zero, which completes the
separation. RS and the uptrend already weigh zero, by measurement (the decisions record).

So every design question starts with **which read it belongs to**. A stock trait never enters
the setup's grade, and a chart-reading trait never enters the leadership read.

### Two grades: technical and fundamental (ruled 12/10/2026)

His ruling, after the five leaders he wants at the top of the screener (SNOW, FROG, HNGE, ANET,
DDI): *"the split between technical and fundamental is correct. Technical grade is reserved for
matching the visual chart pattern which can also include some dry stats like ADR and Trend
template."* So the two grades split by **what is read**, the chart or the business, and the
price-read traits of the stock (ADR, the trend template, and by our default the RS rating and the
base count, both read off price) sit with the chart.

**The fundamental grade** reads whether the business is improving, *"not just whether its latest
quarter looks impressive"*: the last four reports and quarters (EPS and its growth, sales and its
growth, the margins), beats and misses, estimate revisions, the earnings quality, and the growth
catalyst. His reason for insisting on them: *"the price action confirms the fundamental stats"*.
The catalyst (O'Neil's "new": a new product, market, management, an industry wave) is reading,
not data, so it stays his read; its proof is measured: sales speeding up, estimates going up, and
the market's verdict on report day, a big move up on heavy volume. A quarter is read only from
the day it was reported. Nine checks, each passed, failed or not known; the letter is the share
of the known checks passed, so a stock is never marked down for data nobody has.

Beside the letter, a plain label says what kind of growth it is (accelerating, strong, a
turnaround, or mixed), and Minervini's Code 33 (EPS growth, sales growth and the margin rising
three quarters running) is awarded only when every one of its nine figures is known. Growth
off a loss is said in words, never as a percentage. The card on the board has the business as
a second page behind its chart, one key away (his idea, 12/10/2026), so the board can be read
both ways without opening a chart.

*Status (12/10/2026): built, display and archive only.* It gates nothing and moves neither the
setup grade nor the tier; its thresholds are canon defaults, to be recalibrated against the
archive. Read on his five: SNOW, FROG and ANET grade A; HNGE C (estimates cut, its latest report
missed); DDI C (flat sales), the good chart on a flat business.

**The chart outranks the business (the book, 2026-10-16).** Price turns before the earnings do.
Vicor's first flat quarter came after its stock had already lost about 70%. Crocs gapped down on
a quarter still up 144%, and its first losing quarter came only after a fall of about 73% (the
book's figures). Green Mountain Coffee topped in 2011 on a quarter up 133% with raised guidance,
and was slammed on one still up 96%. Illumina broke in July 2011 on a report that beat on both
lines. The big holders sell on what they expect, so the chart shows it first. His words on
it: *"good earnings & sales aren't the only indicators for good stocks and with out a clear
signal from the chart ( a setup) we cannot count on it being a good buy"*. The fundamental grade
confirms a business and never vouches for its chart: today it moves no fire, and a board order
that uses it should sort inside the chart's grade, never above it (ours, from the book; the
board order is still his to rule).

### The life cycle: the four stages

A stock lives through stages (Minervini, after Weinstein), and nearly every big winner made its
gain in the second:

1. **Neglect.** Sideways for months or years around a flat 200-day average, on light volume,
   often after a decline. Dead money: no buying.
2. **Advance (accumulation).** Higher highs and higher lows, the price above a rising 200-day
   average, big up weeks on volume against quiet pullbacks. Bases form *inside* the uptrend,
   and this is where he buys.
3. **Top (distribution).** Progress slows and turns erratic: wide, volatile, choppy ranges.
4. **Decline (capitulation).** Lower lows, often on heavy volume.

**No bottom picking.** A stock bought near its low sits in stage 4 or stage 1 with no momentum,
often for months. The aim is not the cheapest price but the right one, as the stock is ready
to move, so he waits for stage 2 to confirm: the price above the 150-day and 200-day averages,
the 150-day above the 200-day, the 200-day turned up, higher highs and higher lows, big up
weeks on volume against quiet pullbacks, and a rally of at least 25 to 30% off the 52-week low
before calling it stage 2. Buying later and higher, once the evidence is in, is the point.

His marks on the book's charts (2026-10-03) show where his setups live: boxes on **bases inside
stage 2**, an LPS on the late stage-1 base right at the turn into stage 2, and an X on the
wide, choppy stage-3 range. The base in an uptrend (re-accumulation) is his core setup, the
transition base is a second kind, and a wide choppy range late in a move is not a setup.

*Status: the stage is shown, never a gate.* Measured on the archive's fires, the seven-point
stage-2 checklist did not separate the moves that reached +25% (all seven 12.9%, four or fewer
13.6%), and fires taken while the 200-day still fell did as well (13.3%). The distance above
the 52-week low did separate, but only among volatile movers, and it is RS by another name,
which is Tested-DEAD to score. The transition base has its own dark lane; he has said "not yet"
to raising it, and it waits for him.

**How stage 2 ends, on the book's charts (2026-10-16).** Four more weekly charts. Citigroup
(2004 to 2009) spent three years in stage 1, poked above the range late in 2006, never turned
into stage 2, and broke down in 2007. Bank of America had a short stage 2 in 2006 that stalled
into a stage 3 of about eleven months. The book marks three points to cut the position: the
first closes under the 40-week average, a lower dip under it, then the break under the range
late in 2007. Vicor (1990 to 1993) ran about +450% in a year, topped within weeks after a
climax-like run, and crashed in March 1992. Crocs went from stage 2 to stage 4 in one gap down,
on the heaviest volume of its life. So stage 3 lasts anywhere from days to a year, and the
volume swells on the way down as the big holders leave.

**The same four charts, read by the live reader (2026-10-16).** Walked day by day on their real
daily bars through the stages the book draws (dates read off its pictures), with the call the
junk corpus makes: the door, then the reader. Days fired, of the trading days in each stage:

| | Stage 1 | Stage 2 | Stage 3 (Citigroup: the failed turn) | Stage 4 |
|---|---|---|---|---|
| Vicor 1991-1992 | too early to read | 38 of 222 | 26 of 62, mostly S | 0 of 213 |
| Bank of America 2005-2008 | 33 of 211 | 44 of 169 | 10 of 230, all S | 0 of 166 |
| Citigroup 2006-2008 | 68 of 231 | it never turned | 28 of 230, mostly S | 0 of 166 |
| Crocs 2006-2008 | too young to read | 35 of 224 | 2 of 15, grade C | 0 of 164 |

Stage 4 never fires: the door reads only a stock above its 50-day and 200-day averages and not
down 20% on the year, and that keeps every decline out. Stages 1 and 3 get through. A flat or
stalling stock spends many days above both averages, and the reader judges a box's shape in the
stock's own daily ranges, so a quiet bank's range 2 to 4% tall reads as a tight base. The trend
template on the card shows some of it (Bank of America's top fired at a median 3 of 7, the
200-day edging down) and misses the rest: Citigroup's failed turn read 6 of 7, and Vicor's top
read 7 of 7, its 200-day still climbing about 13% a month after the climax-like run. The stage-2
fires are the good side: the reader caught Vicor's run from about $4.30 in January 1991 and
Crocs' from late 2006.

His X on the stage-3 range and "no buying" in stage 1 say the other fires are not his setups.
The trend template is not the tool to keep them out: it does not separate the archive's fires
(the 332 with four or fewer checks reached +25% as often as the 7-of-7 ones, Nulls 2026-10-03),
and it cannot see a top that comes after a climax run. Telling the stages apart needs the start
of the advance and its age, the same read the base count needs (the bigger picture below).
*Not built.*

**The topping base, his reading on CMG (2026-10-16).** On the book's Chipotle chart he marked
the timeline himself: the stage-2 run, the buying climax (BC) and its automatic reaction (AR),
and the range they opened, labeled "topping base". His words: *"bases that show up after a long
up trend run (usually they are also wider then their predecessors) tend to be viable setups for
a short position"*, and *"notice the strength of sellers, even before the stock got slammed we
were already beginning to down trend."* On the daily bars (2012 dollars): the BC topped at 442
on 13 April and the AR bottomed at 401. Inside the range every rally peaked lower (424 in May,
420 in June, 405 in July) and every dip reached lower (385, then 370), and the down days carried
about 1.5 times the up days' volume in the climax week, the reaction and June. The price broke
under the range at the end of June, rallied back up to its underside (where a broker upgraded it
to a buy on 17 July), and three days later gapped to 317 on twelve times its average volume. So a
topping base opens exactly like a base in an uptrend, with a climax and its reaction. What tells
them apart is where it sits (late in a long run), its size against the bases before it, and
which side wins inside it.

*Wider than the bases before it*, measured with the base-count rule on the weekly bars of the
book's tops (the topping base from its top week to the week before the break): DECK 46% deep
against at most 26% before it, Bank of America 20% against at most 9%, AMGN 30-33% against
19-30% (2026-10-03); all three were also the widest in the stock's own weekly bars, and the
longest. Chipotle 16% against 14% for the base just before it, and the widest in its own weekly
bars, though it had deeper bases in percent in 2009-2011 (and its 16% counts the break under the
range). Vicor 27% against 26% for the one before, the same size: its top was a climax more than
a wide base. "Usually", as he says. The live reader on the same Chipotle days fired S on seven
of them inside the topping base: just after the climax (on a late-March box, 427/415) and on 20
to 25 June (a box 409/384, its trigger about 414-420, the trend template 7 of 7), the third
lower high, six trading days before the break.

**Engine β.** He reads the topping base as a short setup for a future engine: *"Engine Beta β
would focus on screening Short positions in the future after were done with Alpha"*. It confirms
his 2026-07-26 deferral of the LPSY to engine β. The rally back up to the underside of the broken
range, where Chipotle was upgraded, is the short side's mirror of Alpha's LPS: Wyckoff's last
point of supply, *"like an LPS but for distribution processes — an event that signals weak
buyers"* (his words, 2026-07-26). For Alpha the lesson is the stage-3 read above: a topping base
is not his long setup. *Nothing short-side is built.*

**The break (the book, 2026-10-16).** The book's sell signal: the largest one-day or one-week
decline since the stage-2 advance began, on the largest volume, even when it comes on a good
earnings report (Crocs fell 36% in a day on a quarter up 144%, then 99% in a year). His words:
*"Notice how after gap down the stock broke down and that gap kickstarted its long downtrend.
The largest daily decline for Crocs also came on the largest weekly decline on huge volume."*
Measured on real daily bars from each advance's start (the base count's rule):

- Crocs, Illumina and Chipotle broke on a gap far larger than any drop of their advance (36%,
  18% and 22%, against at most 8%, 5% and 8% before), each on the advance's largest volume.
- Vicor, Deckers and Stryker broke quietly, their first record drop only just past the earlier
  ones and weeks after the top.
- Every break came after the top, so it is a signal to sell, not a warning before the top. The
  combination of a record drop on record volume also fires in the first weeks of an advance,
  when every dip is the largest so far. The book's breaks all came six months or more into an
  advance.

The archive: 48 of 3,417 matured fires came within 65 trading days after such a break (26 weeks
or more into the advance); they reached +25% as often as the rest (12.5% against 12.1%; too few
to tell). The door already keeps most broken charts out, since they fall under their 50-day
average. ANET, one of his five leaders, broke this way in May 2026 and went on to new highs. For
Alpha nothing is built: Chrollo never manages an exit. For engine β, the break and the bounce
after it are the short side's events.

#### Bases inside stage 2, and counting them

Stage 2 does not rise in a straight line. It climbs in waves: a run, then a pause where the
stock goes sideways and builds a base, then the next run, stair-stepping from base to base. A
base inside stage 2 is a rest in an uptrend, never a return to stage 1; most last about 5 to 26
weeks. **Counting the bases** (O'Neil and David Ryan, through Minervini; sent 2026-10-03) says
how far along the advance is. The first and second bases, often coming out of a market
correction, are the best; the third is more obvious but usually still tradable; by the fourth
or fifth the trend is plain to everyone and bases fail more often. The count gives perspective
and never calls a top on its own.

His observation on the book's AMGN weekly chart (1987 to 1994, five bases marked): *"notice how
the bases get wider and wider along the stage 2 advance"*, and what he means by wider: *"the
bases structure gets to be the opposite of tight, the spread of the bars is increasing rapidly
as well as seller strength"*. Measured off that picture: each week's bar and volume lifted from
the image, the bars inside each drawn box, read at three darkness cutoffs and quoted as the
spread across them (the chart's price scale is linear, so a dollar of height means less as the
price rises):

| | Weeks | Height, % of price | Height, weekly ranges | Typical weekly bar, % of price | Down weeks against up weeks: bar size / volume |
|---|---|---|---|---|---|
| Base 1 | 27 | 26-29% | 3.7-4.8 | 6-8% | 1.0-1.7x / 1.0x |
| Base 2 | 20 | 23-30% | 4.0-4.9 | 5-8% | 0.5-1.2x / 1.4x |
| Base 3 | 30 | 28% | 4.0-5.9 | 6-8% | 1.0-1.8x / 1.1-1.3x |
| Base 4 | 20 | 19-21% | 3.0-4.3 | 5-8% | 0.4-1.1x / 0.9-1.0x |
| Base 5, the stage-3 top | 50 | 30-33% | 5.6-6.8 | 6-7% | 1.2-1.6x / 1.2x |

- **In dollars the bases do widen** (from about $0.40 high to about $3.50), as the eye sees on a
  linear chart.
- **The single bars do not widen.** The top's typical weekly bar is the same size as the
  stage-2 bases' in proportion to price, or smaller.
- **The top is the biggest base in its own ranges at every cutoff**, about one and a half times
  the stage-2 bases, and about twice as long.
- **Sellers show in the top.** It is the one base whose down weeks are bigger than its up weeks
  at every cutoff, on about 1.2 times the volume, with about half its weeks down. It is not
  unique on every count: base 2's down weeks carried even more volume (1.4x).

So on this chart "the opposite of tight" is the base as a whole (bigger in its own range,
longer, and sellers taking the weeks), not wider weekly bars. A weekly bar can hide daily
chop: a week of wide, overlapping days can still print a normal-sized weekly bar, so the bar
texture he describes is a daily read. It is one chart, read from a picture: an idea to test on
the daily bars of real bases, not a rule.

**His count, on his five (12/10/2026).** He counts only the bases of the current stage 2: *"you
counted bases not in stage 2, but stage 1 as well"* (DDI's shelves before its breakout, HNGE's
listing base). A spike over a base's top that closes back under it is inside the base (FROG's one
July-to-October base). A short pause counts (HNGE's three-week May pit stop is its base 1). On a
long advance with no visible turn from stage 1 (ANET) *"we take the last known visible pit stops
and mark them. Some look like dips/corrections and some like semi bases/bases."* His counts: SNOW
2, FROG 1, HNGE 2, ANET 3, DDI 2. A rule written from them (the count starts once the weekly
closes stop falling under a 40-week average that is not rising; a base ends only when a weekly
close clears its top) matches three of the five; the pauses it adds on FROG and ANET were the
open question (his first-leg ruling below answers most of it).

**The book's DECK and SYK (sent 2026-10-15).** Two more weekly charts from the book: DECK
2006-2008, five bases, the fifth turning into the stage-3 top, and SYK 1990-1995, five bases
from the 1990 bear-market low, a climax run (+65% in 11 weeks), stages 3 and 4, then "base 1"
again in a new stage 2 in 1994. The rule above, run on their real weekly bars, finds every
drawn base (SYK's first only by its last five weeks: the count restarts at the bear-market low
inside it), its tops and lows sit on the SYK staircase's boxes by eye, and it restarts the
count where the book does (the 1994 base reads 1). What it adds are short pauses the book
leaves inside a run, in the same places it adds them on his five: in the first leg off the
turn (DECK December 2005 to March 2006, like FROG's April shelf and June dip and ANET's 2025
pauses), just under the next base (DECK October-November 2006, like ANET's July-August 2026
pause), and in the last run into the top (DECK November 2007, SYK November 1991 inside the
climax run). No size or length separates them: the skipped pauses ran 3 to 6 weeks and 11 to
23% deep, while counted bases run as short as 4 weeks (DECK's third) and as shallow as 7%. A
pause counting only when the stock runs 20% past it fits DECK but fails SYK, whose 1991 bases
sit only about 12% apart. The widening is at the end, not base by base: DECK's bases ran 26,
8, 7, 26 and 46% deep, and the 46% one (29 weeks, under the 40-week average) is the top. The
two charts show the two endings: a late base that turns wide and loose (DECK) and a climax run
out of the last base (SYK).

**His ruling on the first leg (15/10/2026):** *"the pauses inside the first leg off the turn
don't count. Base 1 is the first rest after that leg."* It is the book's point about letting
someone else take the first leg up: base 1 comes once the first leg has shown that stage 2 is
real. It answers FROG's April shelf and June dip and ANET's 2025 pauses. Still open: the pauses
just under the next base and those in the last run into the top, and where the first leg ends
in a rule. The only simple split found (base 1 is the first rest of 8 weeks or more) fits DECK,
FROG, ANET, SNOW, DDI and SYK 1994, but it is fitted to them (ANET's skipped pause lasted 7
weeks, SNOW's base 1 lasted 8). It misses HNGE's three-week May pit stop, and it misses SYK's
1990 base, where the book counts the base that holds the bear-market low as base 1.

*Status: not built.* Chrollo's base count reads 1 on every archived fire (it counts inside the
latest short up-leg, never from the start of stage 2), so it is not shown. A real count needs
the start of the advance, which the weekly bigger-picture read below is to supply; comparing a
base with the stock's own earlier bases needs the same.

### The bigger picture: one process on every timeframe

His phrase **"bigger picture"** means *"the use of process in bigger time frames"*: the same
reading (rails, events, SOS, LPS, the buy) done on the weekly and monthly charts, so a daily
setup is seen as one piece of a bigger story. The setups he values most are **complete**: the
daily base is a step in the weekly's story, and the weekly's is a step in the monthly's. His
example is MTLS (2026-10-03):

- **Daily:** a clean base in an uptrend (re-accumulation), and its LPS.
- **Weekly:** price breaks up through a bigger, older base with strength and rising volume,
  then pulls back and contracts into a tighter base, which is the daily base.
- **Monthly:** all of it is the right side of a base begun in 2023. The daily uptrend and base
  are the monthly's SOS and LPS, in the upper half of the range, before the breakout: *"truly a
  perfect scenario"*.

The structure is fractal: the daily box, the weekly's tight base and the monthly's LPS are one
place on three charts. What carries across every timeframe:

1. **One grammar.** The words, the rails as areas, the events and the definition of a fire are
   the same on every chart; only the bar changes.
2. **Height in the chart's own range, never in percent of price** (ruled 2026-10-03: *"the
   reason I don't like the % rule it's because it's based on raw pricing which can scale up
   percentages quickly in the monthly chart"*). Measured on MTLS, the monthly base is 1.33
   monthly ranges high (43% of price) and the weekly base 1.21 weekly ranges (10% of price):
   the same size in the stock's own terms. This carries his Q7 of 12/09/2026 (no height gate in
   any unit; height is graded) to the weekly and monthly charts. The old engine keeps its
   percent caps until the method's step 7 switch goes live with steps 10 and 11.
3. **The weekly chart is the main bigger picture** (his suggestion 2026-10-03, taken: *"we can
   probably figure most of this from the weekly chart as minnervini lists his "stage" traits
   from weekly charts"*). Five years of prices hold about 260 weekly bars but only 60 monthly
   ones, so the monthly is shown when it reads and is never required.

*Open: how a count in trading days converts.* A rule counted in days (the fifteen-day minimum,
the LPS's last days) is time, and counted as bars it stretches: on the weekly chart the
fifteen-day minimum became fifteen weeks, and the read of MTLS's tight base came months late.

The bigger picture is **context for the daily setup**: is the stock in stage 2, on the right
side of its bigger base, in the upper half, after a breakout through an older base? It enters
measure-first like every read: shown and archived, then measured against outcomes and his
drawings before it weighs anything. Scoring the old weekly and monthly read is Tested-DEAD;
that verdict belongs to that read, and a new read earns or loses weight on its own
measurement. What the bigger picture can rule *out* is unknown until he draws the trades he
passed on because of it.

*Status (2026-10-03): not built.* The engine's weekly and monthly read today is the old daily
engine run on weekly and monthly bars, measure-only, and it sees no base on MTLS on either
chart. The bigger picture is to be built on the new reader of the final method (approved
02/10/2026), which, run unchanged on MTLS's monthly bars, already fires at his buy. MTLS's
weekly and monthly charts are its first test; the standard is his own drawings of trades he
takes and trades he passes, within the five years of prices the cache holds.

### The evidence: the archive and the calibration setups

Two bodies of evidence teach the engine. **The archive** holds every setup the engine fired, with
what happened afterwards: the population, what the engine finds. **The calibration setups** are
his own drawn setups (his rails, the box's dates, his trigger), 40 of them on 2026-10-03, kept
even when the vendor loses the chart: the target, what the engine should find. His ruling
(2026-10-03): *"treat calibrated setups as archived ones as well! since they are essentially
modeled archived setups made for studying high quality structures that our engine needs to
master!"*

So a calibration setup is an archived setup too, and **every study run on the archive reads the
calibration setups as well**, reported as their own group beside the engine's fires. They stay a
separate group because they were chosen for quality: blended into the fires' averages they would
flatter the engine, and side by side they show the gap between what the engine finds and what
he would take. A first instance is the base-length row of the comparison below.

*Status (built 2026-10-04, live once the backend restarts):* each calibration setup is measured
like a fire, from the trading day before his trigger, with his trigger and with his support as
the stop's rail, by the nightly outcome job; the report card, the Home edge tile and the Archive
screen show them as their own group. A setup whose prices the vendor no longer serves (SKYT) stays
unmeasured, never guessed. Measured on a copy of the archive (2026-10-04): 39 of his 40 measured;
median best gain within 60 trading days +38.6% against +5.9% for the engine's fires, and 34 of the
37 resolved hit +15% or 2.5R before the stop. They were drawn after the fact, so the gap is the
target the engine reads toward, not an edge anyone can trade.

### How it all ties to the engine: the comparison

*(Written 2026-10-03 at his request, "how it all ties to our current engine, by comparing".
"Today" is the live engine; "the method" is the final method below, built and dark until his
approval sitting; "not built" is theory only.)*

**The life cycle against Wyckoff and against Chrollo.** Minervini's four stages are Wyckoff's
cycle under other names, and Chrollo reads one part of it:

| Minervini | Wyckoff | Chrollo today | Ruled or planned |
|---|---|---|---|
<<<<<<< HEAD
| Stage 1, neglect | accumulation after a markdown (a selling climax and its automatic rally open it) | kept out by the door's trend floor only while the price is under an average: a flat stage 1 above both is read and fires (the book's Bank of America and Citigroup, measured 2026-10-16); the selling-climax pair is reserved for the end of a main downtrend | the transition base: its own lane, dark, waiting on his word |
=======
| Stage 1, neglect | accumulation after a markdown (a selling climax and its automatic rally open it) | mostly kept out by the door's trend floor; a selling climax at the end of a main downtrend would open it (an SC also names the low of a down-swing whose reaction is a stage-2 base's root: see the legend) | the transition base: its own lane, dark, waiting on his word |
>>>>>>> claude/quizzical-lewin-448381
| Stage 2, advance | markup, with re-accumulation ranges along the way | **the core.** The box's climax is the top of an up-run (the buying climax and its automatic reaction), and the box, its LPS and its buy are a stage-2 base; the trend template and the stage cells are shown | base on base (the chain grammar below, dark); the base count needs the advance's start (not built) |
| Stage 3, top | distribution | not named: the distribution side was deliberately left (the Wyckoff companion); the old reader refused a wide range by its width cap in percent of price, the live reader (since 10/10) has none, and it fires inside three of the book's four tops and his Chipotle topping base (measured 2026-10-16) | the method grades height in ranges instead of refusing (dark); the late-stage tell, a topping base wider than the bases before it, holds on four of the book's five tops (2026-10-16; not built); the short side is engine β's, after Alpha (his word, 2026-10-16) |
| Stage 4, decline | markdown | kept out by the door's trend floor | a box that fails reads "broke down", one of the method's state words (dark) |

**His sequences against the Reading Model's events.** The event chain is the same story his
selection summary tells:

| His sequence | The same story in the Reading Model |
|---|---|
| Base formation → evidence of accumulation → supply less available → upward breakout | the rails elected → turns at the rails, a spring if any, the SOS → the contraction (the LPS's receding days, the mini at the top) → the trigger crossed |
| Strength → an orderly pullback → renewed strength → entry | the SOS → the LPS → the cross of the LPS's high → the fire |
| Leading stock → constructive price and volume → well-formed base → valid breakout → sustained follow-through | the leadership read → volume facts on every event → the box and its grade → the fire → the follow-through the archive measures afterwards |

**The book's measures against Chrollo's:**

| Theory | In Chrollo | Status |
|---|---|---|
| Stage-2 criteria: price above the 150-day and 200-day, the 150 above the 200, the 200 turned up | the trend template's seven criteria, counted and shown ("7/7"), with the 200-day's one-month change | shown; measured, does not separate the +25% moves among fires |
| 25 to 30% off the 52-week low before stage 2 | "Off 52-week low" | shown; separates only among volatile movers, and is RS by another name (Tested-DEAD to score) |
| Big up weeks on volume against quiet pullbacks; more up weeks than down weeks on volume | volume is a fact only (live since Sat 10/10/2026) | measured (criteria 5 and 6): does not separate; inside the base (2026-10-04) up versus down volume does not either; the quiet LPS separated on the old reader's own LPS stretch, not on the new reader's LPS days (2026-10-12), where only the quietest stretch of the last week is a lead |
| VCP: two to six contractions, each tighter, the last one tight | today the contraction count and the last contraction's depth (in percent) earn points | the method weighs the count at zero and grades the LPS window's bar spread in ranges (dark) |
| "Tight": weekly closes in a narrow range | the box's height in daily ranges and the bar texture inside the box and the LPS window, on the daily chart | today and the method both read it; the method never in percent of price |
| Buy at the right price, as the stock is ready to move | the buy is the cross of the LPS's high; nothing fires without an LPS | today |
| Bases in stage 2 last about 5 to 26 weeks | the engine's boxes, one per base in the archive: median 46 trading days (about 9 weeks); 85% run 5 weeks or more, about 5% past 26. His 40 calibration setups, box start to his trigger: median 40 trading days (8 weeks); 90% run 5 weeks or more, none past 26 | today: both are base-sized, and the 20-day minimum (15 in the method) sits at the low end; the engine has a long tail his setups do not |
| Count the bases: 1 and 2 best, 3 tradable, 4 and 5 late | a base count, and a ratio of the box's width to the base before it | **broken:** the count reads 1 on every archived fire, and the ratio is empty on all 15,606 archived rows (it rides the same walk, and it compares in percent of price) |
| Weekly charts for the stage | the old engine's weekly and monthly read on resampled bars, measure-only | sees no base on MTLS; scoring it is Tested-DEAD; the bigger picture is to be rebuilt on the new reader (not built) |
| RS leadership | the RS rating, ranked across the scanned universe | shown; scoring it is Tested-DEAD |
| Group leadership | none | owed: the industry and a count of peers also leading |

**What the comparison shows.** The setup side lines up well: Chrollo's box, LPS and buy are
the stage-2 base and its entry, the events tell his accumulation sequence, and the boxes are
base-sized. The gaps are on the stock and the bigger picture: no read of where the stock is in
its stage-2 run (the base count is broken and the bigger picture is not built), volume measured
and shown at its key points but not graded (2026-10-04: of the Momentum Masters volume lines,
only the old reader's quiet LPS stretch separated outcomes; 2026-10-12: on the new reader's LPS
days none does), no group read, and no read of the late stage.
Every gap is a display read first, measure-first, never a gate.

### For whoever designs a change

- Name the read first: the stock or the setup.
- Every size in a structure is measured in the chart's own range, on every timeframe; no
  percent-of-price threshold decides a structure.
- A trait from the books enters as a shown, archived fact, and weighs something only after it
  separates outcomes in the archive.
- The test standard is his drawings: the calibration setups, the trades he takes and the ones he
  passes on. A study on the archive reads the calibration setups too, as their own group.

---

## The Reading Model — the operator's chart language

Everything in this document implements ONE reading procedure — the operator's (stated
2026-07-02, AGCO dissection). This section is the canonical statement of that procedure.
The rest of the doc mirrors the implementation; *this section states the intent the
implementation serves.* When a detector and this model disagree, the model wins and the
detector is the bug (or the model gets amended here, explicitly — never silently).

### The final method (ruled Sun 13/09/2026; restated in seven stages and confirmed Sun 20/09/2026; a new reader is being built to it)

The operator's own summary of what the screener is: *"we just draw 2 lines around a tight
area of a chop in a stock and display it to me so I can see it and figure out if I want to
trade it or not."* And of how the reader must work (Sun 20/09/2026): *"our main consolidation
detection method mimics 2 eyes by converting the bar data and placement into a small swing
based model -> then we place Resistance & Support to wrap the consolidation and follow said
swings ,split them into phases, we "build" the story as it unfold Left to Right as we assign
different swings different events"*.

His chain of reading, said when he put the core first (Sat 26/09/2026): *"there are 2 main
things that should be the bread and butter of every read, that's the Consolidation (Resistance
and Support lines and every thing that's related to them) aka the box generation, and the LPS.
the rest is how we interpret the inner price action in the box that leads us to the rest of the
"events" & and the way we treat the box rails since we read ohlc daily bars's High and low
values to construct the entire range of that day -> construct them into swings -> construct
swings into a drawing and then we see how it fares against our box and we can interpret said
drawing to visual patterns we can recognize aka: spring, up thrust, sos, lps, mini consolidation
and so on depending on the chronological "phase" of said setup."* So the core is two things,
the box and the LPS; the events are the drawing interpreted against the box by phase; and the
core is judged by his eye, on the bars, before anything is built on it.

The method has seven stages and the order is the point: the line comes first, the end of the
trend is found on it, the two lines are walked out from there, the box lives and ends by
swings, the story is read on the box left to right, the LPS and its trigger are read last,
and only then is anything graded or shown. Nothing in the read is a gate that can reject a
good setup on a number: *"It's hard to gate using a raw number in case we reject a valid
setups because of a small neumeric gap"* (Sat 12/09/2026). The only hard things are the
universe door, the fifteen-trading-day age floor, his own shape sentences on the LPS, and
the definition of a fire (a box, an LPS, a trigger). He confirmed the seven stages on Sun
20/09/2026 (*"1. yes 2. yes 3. okay 4. if you are reffering to mini consolidations then both
boxes live, they are a part of the same setup 5. yes 6. yes 7. Yes"*). Where a sentence below
is a builder's default and not his ruling it says so; the decisions record carries each
default as ours.

1. **The line.** Bars become one swing line. The unit is the whole bar: *"the bars
   themselves (The entire bar from High to Low) tells me everything I need to know"*
   (Thu 10/09/2026). A turn is confirmed when price backs off its running extreme by
   0.75 of the stock's daily range, high to low. The first bar and the last bar are turns by their shape: *"even with out
   "Future" Information we can deduct them as turns by their current state swing shape"*
   (Sat 12/09/2026). One bar may carry both a peak and a valley, and one rule says in which
   order: the bar is read in the direction the line came into it, that end first, so a bar
   entered rising carries its peak and then its valley, and a bar commits at most one turn of
   the line, on its close; the far view, which folds the line at a bigger floor, may make two of
   its turns on one bar wide enough to cover that floor twice over (ours). A leg's turn is the most extreme price since the turn before it, over
   every bar to the day the reversal was confirmed, the turn bar's own other end included when
   it was read after the turn (ours). A turn, once confirmed, never moves; the last one is
   marked as still forming. Every turn knows its size in daily ranges — the leg into it, in
   the range of the day it printed (ours) — and the day it became knowable, the close that
   confirmed it; the first bar's kind is known when the first leg has covered its floor. The
   daily range is built on the whole history before the chart is cut to the two years the
   reader looks at, so the first days inside the window carry a warm unit and the cut moves
   no range; the line's first turns depend on where that edge falls, for a few weeks at most,
   and are the same turns after (ours). Seen from further back the same line shows the trends:
   the far view is this line with its small swings folded away, never a second line — its
   turns are turns of the line, and a far turn is made when a day backs off it by the far
   floor in that day's own range (ours); how far back was placed at the listing gate (Sat
   26/09/2026): one and a half daily ranges, ours and provisional, the one distance at which the
   trend into his box is seen at all — and the reaction after the climax is read on the line
   itself, not on the far view, whose folded swings overshoot his support; his sitting settles both.
2. **The end of the trend, then the rule of the pair.** A run of higher highs and higher lows
   is a trend; its highest turn is the climax and the low that ends the first reaction after
   it is the automatic reaction. They are decided first: *"the swings for BC and AR are needed
   to be decided before the Root Swing, because said root swing can either be them, or a
   swing later"* (Sat 19/09/2026). The rule that places the two lines is his, settled at the
   core sitting: on Wed 30/09/2026 it was typed out to him in ten sentences, and on Thu
   01/10/2026 he answered each. The first five place the pair; six to eight are stage 3, nine
   and ten stage 4.
   (1) *A rail sits only on the end point of a swing* — *"correct"*. His ruling on the
   reader's PBT box (Mon 28/09/2026): *"we only start to anchor from the end point of
   previous swings"*; its line had come *"from the middle of a swing in the direction of the
   trend with out there being a counter move to begin with"*. The end point is the high
   where a rise stopped or the low where a fall did: a bar whose high the bar on neither side
   beats (the mirror for a low).
   (2) *A box's two rails are the two ends of one counter move; after a swing up the top
   comes first* — *"correct"*. And *"we cannot start the anchor in the same direction the
   price is going"* (Mon 14/09/2026).
   (3) *The two ends can be one wide bar's own high and low* — *"correct"*. Daily bars do
   not say which end of a bar printed first, so a one-bar pair is read in whichever order
   makes it a counter move (ours).
   (4) *The counter move is smaller than the move it comes off* — *"correct most Automatic
   rallies (AR) cover only part of the previous move if a counter move is bigger it
   contributes already to a new counter trend!"* A pair whose second end takes back the
   whole move before its first is listed and never a box. The move before is read on the
   bars alone: for a top, from the lowest low since the price was last above it (ours).
   (5) *The first pair tried is the climax and its reaction; if the bars do not come back to
   both rails, one pair to the right; one rail may stay while the other moves* — *"correct
   but ... only if a swing connects between them, we cannot allow for dismemberd anchor
   paring"*. His earlier words: *"I move one pair right until I find it, not only a single
   time. -> one line can stay on its anchor while the other moves, but they are connected
   like 2 lets placing one in front of the other"* (Sun 20/09/2026). A swing connects two
   ends when, from the first one's bar to the second's, the top is the highest high and the
   low the lowest low; a top is never paired with a low printed after a bar went over it.
   The pairs are listed in the order they open, from the first end of a trend the far view
   shows; nothing is listed before one. Where a trend end's walk starts is the first swing
   end of the climax's level in its run: a later high that pokes a little over his top does
   not move his line (his PBT: 22.71 five days after his 22.65) (ours). Each line is ONE
   anchor day's high or low, to the cent.
   His own drawings keep the rule (40 of them on Fri 02/10/2026; the standard follows what
   he draws): every one opens on the end of the swing before it, 37 on resistance after a
   rise, 3 on support after a fall. His own two anchors are a pair the rule lists on 35 of
   the 40; on the other five one of his anchors is one of two near-equal highs or lows a few
   cents apart, or the climax bar's own low, and on all five the reader's box is within
   half a daily range of his. The anchor is not always the climax: on 11 of the 37 he had
   drawn by Thu 01/10/2026 it is a swing later, and on 4 of the 40 both lines are one wide
   bar's own high and low.
3. **Answered and alive.** A pair of lines is the box when the bars come back to BOTH lines:
   *"were looking for the first instance that a consolidation is respected!"* (Sun
   06/09/2026).
   (6) *Come back: a later bar's high within half a daily range of resistance, a later bar's
   low within half a daily range of support* — *"if by "Come back" to be counted as respect
   to the respective rail that bar is closest too then yes"*. Each end of a bar counts for
   the rail it is closest to, when it is within that rail's area, on either side of it:
   *"whenever they are slightly poking out or not does not matter one bit"* (Sat
   26/09/2026). So a bar whose high touches resistance and whose low touches support
   respects both, small bars low in the box rest on support, and a bar above resistance
   whose low is close to it respects resistance. Resting on a rail is respect, the price
   need not have left it first: *"Silc supposed to work due the much respect of the
   support"* (Thu 01/10/2026, on the pictures: SILC's bars rest on his support for seven
   weeks). And a rail the base does not return to is no respected rail: *"why would DRTS
   move away as it almost perfectly respect both boundaries"* (the same day: DRTS's climax
   and its reaction low, 7.89 / 6.23, a low the bars left the day after and did not see
   again until the spring six weeks later). So the bars come back first to the rail the
   pair opened on, and to the other rail on that day or after: the price has been at the
   other rail in between. The order is ours; it is what reads both of his examples. Read as
   "any later bar", the day after a reaction low counts and DRTS's climax pair is the box;
   read as "only after the price left the rail", SILC's support is never come back to.
   (7) *The pair is a box on its fifteenth trading day, or later if the bars take longer to
   come back* — *"Correct we have to account for the bases eventual recovery when scanning
   and detecting, its looking at the base structure as whole rather and seeing that it fits
   rather then rejecting it out right"*. Fifteen days from the first anchor: *"Lets go with
   15 days"* (Sat 12/09/2026). The box is born on the later of both come-backs and the
   fifteenth day, however late, and no earlier than the day the reader could first list the
   pair (ours).
   (8) *A run past a rail never unmakes a pair by itself.* On his ALB the price stood two
   daily ranges over his resistance a week after the box opened, and he kept the lines. Of
   that breach he said: *"that breach is not an upthrust in fact there is a later on
   25/02/2026 its just that those pairs could be used to fit the box, even a later pair
   could work if that movement in 20/1 -> 27/1 and the crash afterwards could be treated as
   the place where the trend ends"*. So a run past a rail early in a box's life is not his
   upthrust (the record of Tue 29/09/2026 that called it one is corrected by him), and no
   pair is dropped for one.
   A pair shorter than one of its own daily ranges is listed and never a box (ours: from
   his huge spread being huge against the box itself). First in time stands: the first pair
   that BECAME a box is the box shown — then the earlier opening, then the earlier second
   anchor, then the tighter pair (the tie-breaks are ours). But among the pairs off ONE
   opening anchor the order of trying is his sentence 5: the climax and its reaction first,
   one pair to the right only while the bars have not come back to both of its rails. A
   sibling one swing to the right (the same top, a lower low) that was answered sooner is
   shown only until the reaction low is answered too; on that day the climax and its
   reaction take the place (his GFR, Thu 16/10/2026: *"the AR ended where I marked it (the
   red swing) the entire wave going down is already 2 swings and it's not part of the AR"*;
   the reader had shown 6.78 / 5.76 for his 6.78 / 6.04). The form is ours; a pair off
   ANOTHER anchor never comes back this way (below). The box opens on its earlier
   anchor, each line starts at its own anchor and is never extended left. The daily range
   the box is measured in is the range of its second anchor's day and is never the read
   day's (ours). An earlier, wider box is acceptable when his LPS reads against it: *"so
   nothing really disqualifies them (not until I've seen it ofc)"* (Sun 13/09/2026); the
   yardstick is concordance, never line replication.
   **Promoted by the moves that follow** (ruled Sat 10/10/2026, on his MTLS): *"we walk the
   box in pairs of swings we take one end from one swing and another from the next one. we
   anchor a rail on each one, and if the price action afterwards respect it, we can promote
   the swing between the two points to be a root swing. because that's the first swing where
   a box from that point onward that is respected by the later moves that follow"*; and of
   respect: *"if the bars keep coming back or near that area that means its in fact the
   right one"*. So the root is the first pair in time whose box the later moves respect: the
   reader's walk, with the box's life (stage 4) judging the moves that follow. On MTLS his eye
   takes the next pair, his SC 6.39 and its AR 6.83, whose lines the bars reach and turn at all
   summer, over the first pair, whose top, 7.00, the later tops approach (6.86 to 6.96) but
   never reach outside the July upthrust, and over the reader's support there, 6.60, which the
   lows run through. *Status: nothing to build.* Near stays sentence 6, within half a daily
   range, the same evening:
   *"coming within half a day's range of it? equals near and it counts as respect and i
   understand where the conflict is, because it means that less correct versions of setups
   can be detected because we excuse the margin between the bar and the rail, my corrections
   come from the fact that with my eyes I can easily pick a better fitting pair and box with
   out needing to rely on an algorithm"*. By that respect the first pair on MTLS is respected
   too (its later tops come within a third of a daily range of 7.00), so the reader's first
   respected pair stands, and picking the better-fitting box among respected ones is his eye's
   work at review, as he put it on Sun 13/09/2026: *"for the engine's sake it's probably
   better to keep it that way"*.
4. **The box's life.** A box ends only by what the bars do, and only into a new box: *"if the
   price continues to Rise/Fall with out recovering we can deduce that either that the
   consolidating structure we measured ended and the price began to trend"*, *"its tricky
   to define it with Close value we need to deduce it Swings as well"* (Sat 12/09/2026), and
   *"the child box inherit the parent as its cause"*.
   (9) *Once a box, it stays a box through dips under support and pokes over resistance that
   come back* — *"correct"*. A dip or a poke that comes back is the box's own event, a
   spring or an upthrust, never an end; a pair inside or across the shown box is its own
   leg, or a mini, and never takes its place. And a dip that comes back LATE: the reader
   reads day by day, so when the price has been under the box for fifteen days it follows
   it to the lower pair (sentence 10); on the first day the bars since then, and of the
   last fifteen days, are back at both rails of the box it gave up, that box takes its
   place back. His ROIV picture is this (Thu 01/10/2026: a red dash on each bar that meets
   one of his two lines, none on the days under the support at the end of March), and his
   word on the boxes the reader never went back to: *"go ahead with the five earlier boxes
   I think as long as the engine understand that there is a setup there I'm happy"*. The
   way back is for a dip only, and only to the box given up (ours): when the price left a
   box upward and a box above took its place, a fall back into the old box is the newer
   box's own dip (on his ST the spring under his box is at both rails of the box under it:
   giving the place back there loses his box and silences the read on his day).
   (10) *The box gives way to a newer pair only when the price left it and did not come back:
   the bars now hang on the newer rails and no longer come back to the old ones* —
   *"correct"*. As built: the newer pair is a box by the rule and lies beyond the shown one
   — its support resting on the shown resistance's area or above it, or its resistance on
   the shown support's area or below — and over the last fifteen trading days, never
   reaching back before the newer pair opened, the bars came back to both rails of the
   newer pair, and not to both rails of the shown box. Both halves of his sentence are
   read: the box never gives way to rails the bars have left (on his MTLS the pair of the
   July run became a box on a day the price was already back under it; the reader used to
   hop to it, and from it to a pair under it). It is judged on every day, not once: a
   breakout that failed keeps the box
   while the bars still come back to it, and the box gives way on the fifteenth day after
   they stopped. What "beyond" is and how long "no longer" is (his fifteen days) are ours.
   And his anchor rule: *"We can't start the anchor from the opposite direction of the trend
   if we are still inside that trend"* (Mon 27/07/2026). A box whose first anchor sat on a
   top inside a rise that had not ended — a pause on the way up — gives way to the box that
   opens on that rise's own end, once the far view says the rise ended there and that box
   is a box by the rule (the mirror for a fall; the form is ours). This is how the reader
   takes his other reading of ALB, the *"later pair"* after the run of 20/01 to 27/01/2026.
   But for that way back and the sibling tried first (stage 3), every hand-over goes to a
   pair that opened later. A pair that
   opened EARLIER does not take the shown box's place on the day it becomes a box (ours:
   measured on his 37 on Thu 01/10/2026 in three forms, it put old wide pairs in the place
   of his own box on EGBN, NTCT and ST, or moved DRTS to its first reaction low). His
   picture of ROIV says more than the reader does: a red dash on each bar that meets one of
   his two lines, none on the days under the support at the end of March or the two days
   over the resistance in May. The box is the pair the bars keep coming back to on both
   sides, visit after visit, and an extreme the price never returns to is a dip or a poke,
   however far it went (his ruling of Sat 25/07/2026 said the same of a rail: where several
   bar extremes rest, the odd poke past it tolerated). The reader shows the first pair that
   got one return on each side; on ROIV that is the pair one swing before his (30.03 /
   28.31, within half a daily range of his 30.33 / 27.92), and it now holds it through the
   dip. Choosing the box by the whole base is not built: the patch rules and the counts of
   what lies near a line that were measured are not his logic (the Tested-DEAD rows of
   2026-10-01). His bar for a drawing the reader does not read to the cent, the same day:
   the engine understands that there is a setup there. The box handed over stays in the
   record, its lines stopping where the newer pair opens; a pair the reader left for the
   box it had given up stays in the record too, its lines never running on (ours).
   The reader keeps no memory: what it records as handed over is what the day's own reading
   of its two-year window tells, and each hand-over is judged on what its own day knew, so
   a reader standing on any day tells the same history up to that day as one standing
   later. The window's left edge moves a day a night, and the OLDEST boxes of the record,
   those of the window's first months, can be told differently on a night with no hand-over
   (measured Fri 02/10/2026 on his 40 and the 16 junk charts, forty nights each, 2,240
   nights: with the same box shown, the earlier boxes were not the same list as the night
   before on 192 nights, on 98 of them only because the window had moved on past the
   oldest box, on 94 because the oldest boxes were told differently; on those nights the
   last three earlier boxes were the same on every one, and the box SHOWN moved on 94
   nights, 7 of them a place given back, each the night the read itself says so). The
   chain of boxes is a function of the first box it starts from, and nothing makes two
   chains meet: on a wider sample even the third box before the shown one was told
   differently on two nights (FRPH, read Tue 12/11/2024 and Wed 13/11/2024), the box shown
   and the box just before it unchanged. Three ways of telling the same earlier boxes
   whichever night tells them were measured and none holds on charts nobody chose (the
   Tested-DEAD record of Fri 02/10/2026). So the earlier boxes of a read are that night's
   own telling, not a record of what an earlier night showed, and the story reads the box
   shown, no earlier box and not the mini (ours). The record of what each night showed is
   the archive's.
   Measured on his 40 on his last receding day (Fri 02/10/2026, the standard following the
   three setups he drew on the evening of Thu 01/10/2026: SGHT, WAT and NET): the reader's
   box is his to the cent on 25, both lines within half a daily range of his on 11, another
   box on 4 (BODI, MATX, MTLS, NET; on the 37 before them 23, 11 and 3; the reader before
   the rebuild: 9, 15 and 13 of 37), and the read fires on his day at his trigger on 35, the
   four with another box among them. On three of those four (MATX, MTLS, NET) his own pair
   is a box by the rule and lies across a rail of the box shown when it became one, so it
   never takes its place (ours). On NET his resistance is the top of Wed 05/08/2026
   (305.00); the price ran on over it for seven days, to 332.22, and came back, and from
   then the bars met his resistance on six days and his support on eight. He kept the line.
   The reader anchors on the run's first top instead (324.73, Fri 07/08/2026): his ROIV
   logic again, a rail is the price the bars keep coming back to. No close is read anywhere: a close-dated
   hand-over is Tested-DEAD. Until a new box is born the parent keeps its lines, and a
   pullback resting above resistance is the parent's own LPS. A range price left long ago is
   no candidate because the hand-over follows the price to the box where it trades (his
   dead-space drawings, BMRN and OHI, Sat 19/09/2026); where the price has run on and no new
   box has been born yet, the old box is still the box shown, and it is the LPS's own
   refusals that keep it from firing; the state word only says where the price is, it
   keeps nothing from firing. The mini consolidation is a box
   inside the parent's right side with its own two lines, and it never replaces the parent:
   *"both boxes live, they are a part of the same setup"* (Sun 20/09/2026); *"like a small
   box, same as the regular consolidation"* (Wed 26/08/2026). It is read with the same rule of
   the pair: among the pairs that became boxes after the parent did and sit inside or across
   it (not beyond it — beyond is a new box's business, the line above), the first to become a
   box is the inner box, and it gives way inside the parent exactly as the parent would. That
   inner box is THE mini when it is a small box inside the parent: its bottom over the
   parent's support area, not the parent's own two lines again. Where it sits in the parent
   is not a rule — his ruling of Sat 03/10/2026, on the build's "at the top" question: *"we
   should gate mini consolidation by their structure its just a semi smaller base inside/in
   the vicinity of a bigger one"*. The parent's half-range area is the only width. The record carries the live mini only. The
   state word reads the parent; the story reads the parent's lines and the LPS as the record
   carries it, against whichever box the LPS named, so its LPS days are the fire's own.
5. **The story**, left to right on the box's own swings. Turns at a line are respect. A dip
   beyond the support area is a Phase C candidate until the swing after its tip recovers it
   (a high back in the area, then a higher low) or fails it (a lower low first); one Phase
   C per box, the deepest that recovered; *"Phase C = Spring"*. The spring's own days are
   the dip: from the first bar under the support area to the tip. Its recovery is the swing
   after it, never the spring (his GFR, Thu 16/10/2026: *"you marked the bars going up, aka
   the recover after the swing, not the spring it self!"*). The spring's test is the first
   valley after that recovery that holds over the spring's low and no higher than the top
   of the support area; it may sit under support (his AAPL, Fri 17/10/2026: the test of
   Tue 06/10 sat 0.55 ranges under it). It is a swing of its own: the low of the very bar
   whose high reached back into the area is the recovery, not a test (*"one of them is
   already engulfed in the other"*), and the valley THE SOS's swing rises from is the
   SOS's own, never a test (*"what you marked as the Test is already a part of the
   SOS"*). A thrust over the
   resistance area is named by the swing after it and by where it sits: THE upthrust, one
   per box, in Phase B, *"similar to a Spring but in reverse being a Resistance based
   event swing"* — price climbs quickly out of the structure, then crashes back into the
   range. The crash may take more than one swing, as long as the price is back under the
   resistance area before it makes a higher top; and a run past resistance within fourteen
   trading days of the end of the trend is the trend still ending, never an upthrust. The
   trend's end is the box's first line, or the earlier top of the trend the box took its
   place from (his ALB, Thu 01/10/2026: the run of Tue 20/01 to Tue 27/01/2026 *"is not an
   upthrust in fact there is a later on 25/02/2026"*, and *"even a later pair could work if
   that movement in 20/1 -> 27/1 and the crash afterwards could be treated as the place
   where the trend ends"*; the form of both clauses is ours). In Phase D a push that may be THE SOS, *"a push
   that's like a paradigm shift it signals local buyer strength"*; a deep correction after
   a breach of resistance in Phase D is the last supper, written only in hindsight, and a
   box carries one: *"a last supper is a noticeable deep correction that happens *usually
   only once either pre or post break out"* (Sat 03/10/2026). It is named only when it
   digs as deep as his shallowest drawn last supper less the margin the floors keep; a
   shallower pause still ends a push. When several corrections qualify, the box's last
   supper is the one off its highest top, and two tops that fall into one low are one
   correction (ours, measured on his eight: the one named is his, or on SILC THE SOS's top
   of the same correction one trading day before his; every one of his eight tops over
   resistance after the box was first breached, so no correction under resistance is
   named). Phase D
   opens at the first right-side evidence after the middle of the box, never at or before
   it. A word is either committed or provisional (ours): committed when the swing it stands
   on, and the swing that answers it, have committed on the line; provisional while one of
   them is still forming. Committed says the SWING is settled, its day and its price; the
   NAME is the reading of the box as it stands tonight, and it can move to another swing:
   there is one spring, one upthrust and one SOS per box, the middle of the box moves
   right every day, and three words lean on the pullback of the day. On his 40, over the
   ten nights up to his last receding day and on to his as-of day, committed names moved
   162 times in 470 pairs of nights, most often Phase D and THE SOS (Sat 03/10/2026). And no word ever blocks a fire: *"The up
   thrust isn't even all that important, we just got to nail down our core for detecting
   consolidations and an LPS. the rest is a nice little bonus."* The story is read after
   the LPS, because three of its words lean on the pullback, and it reads the box shown
   and no earlier box; the dependency runs one way, the LPS never reads a word. Every word
   of a box is measured in that box's own daily range, the range its two rail areas are
   measured in, frozen for the box's life, so a word never changes because today's bars
   were wide (ours). In that range the smallest push he drew as an SOS covers 1.33 ranges
   and his shallowest last supper digs 1.52; the floors sit on his side of both (ours,
   re-derived from his marked bars). No frozen range keeps every word he drew: read by
   the reader itself on his last receding day, his 40 give THE SOS on 22 of his 28, the
   spring on 9 of his 11, the last supper on 7 of his 8 (Fri 02/10/2026), each miss named
   with its cause, most of them a box that is not his.
6. **The LPS and the trigger.** He defines the pullback by the traits he wants to see:
   *"Receding Price move over time, Lowering (and low) spread below average, 2 - 5 bars"*
   (Tue 08/09/2026). One window per read day: the last run of receding days (a lower high
   or a lower low than the day before), the day before the run its top; it *"ends on the
   last receding day before the buy"*, and on where it starts, *"Lets go with the day
   after"* (Sun 13/09/2026). A pullback is read on at most five bars, so of a longer run
   only the last five are read, from their highest high down — the reading of *"the moves
   final bars being pretty shallow and in decline"* (ours; on his BMRN picture it gives his
   blue part, Tue 16/06 to Thu 18/06/2026). The trigger is that last day's high and the buy
   is the cross of it; a cross inside the pullback is a buy too. The day that crosses the
   trigger is the buy day and nothing is on the board that day; a day that crosses it and
   makes a lower low as well is a buy and the pullback goes on, its trigger now that day's
   high (ours, read off his drawings: five of them end on such a day, six were bought on
   one). The pullback is measured by highs and lows; no close is read. A pullback is
   judged on what the line had made by the evening it ended, so its verdict is the same on
   whatever later day it is read: one refused that evening put no trigger on the board, and
   no later day can have crossed it (ours). Only the freshest
   window is highlighted. An LPS is refused only by his own four sentences, read against
   the reader's own box: (1) the pullback is increasing with sellers, *"3 bars with huge
   increases in both spread and price changes"* — its last three bars widen day by day
   and fall further day by day, the last fall bigger than the whole range of the day
   before (the form is ours); (2) it is a slice of a bigger swing down, *"you cut the
   move off and it's a part of a bigger swing downwards that reaches support, we cannot
   ignore that"* (Mon 14/09/2026), *"its seems like the correction is getting to deep"*
   (Tue 08/09/2026) — the fall from the top of its swing on the line to its low is more
   than 2.5 daily ranges (the form and the number are ours: his deepest drawn pullback is
   2.43; reaching support is not asked, because his own pullbacks rest on it in a tight
   box); (3) most of it sits under the support area, read on whole bars, so a poke under it
   never refuses: *"the LPS is on the Support rather then Under it since most of the move
   is above it and only small parts of it poke out down"* (JAZZ, Sun 13/09/2026); (4) its
   low sits more than 1.35 daily ranges over resistance (*"Lets go with that ceiling 1.35
   I guess...."*, Thu 10/09/2026). The LPS is measured in the daily range as it stood five
   trading days before its last day — before the pullback, whose own days may not move
   their own yardstick — the unit his 1.35 was placed in: in it his six lows over
   resistance read what they read the day he ruled (his farthest, ST, 1.30), while in the
   box's own frozen range his ST would be refused (ours). Every other number about the
   window may be graded, never gated; none is read yet. His LPS trait *"Lowering (and
   low) spread below average"* (Tue 08/09/2026) is measured by no stage, graded by no
   rule and stored nowhere: whether it is kept as a raw value or dropped is his, at the
   approval sitting (council review, Fri 09/10/2026, finding 4). A pullback that ended before the box was a box is not
   its LPS, and the universe door stands before every read: a fire is a box, an LPS and a
   trigger on a chart the door admits (ours). The mini may carry the read: *"the LPS read
   can be against it if it is inside/near it/resting on it and the trigger is always read
   against the LPS by itself"* (asked Sat 12/09/2026, answered Sun 13/09/2026). Built: the
   pullback's low in the mini's own area — inside the band clear of both lines (in), inside
   and within the area of a line (on), outside and within the area of a line (near) — is read
   against the mini's lines and the record says which box and how; away from the mini, or a
   mini that became a box only after the pullback ended, or a fault on the mini's side: the
   parent's read (ours). The window and the trigger are the bars' and never move; the two
   position sentences read the lines of the box named.
7. **The grade, the state word, the screen.** *"grade is built from a few important traits:
   Consolidation tightness (Consolidation width + Spread Profile), Event Map, base age
   dosen't matter to me"* (Sat 12/09/2026). Height is counted in daily ranges, never in
   percent of price: *"a box is a box because of its consolidating Zig zag behavior not
   it's height"*. The junk he refuses is *"Extreme Width, Spread, Messy non tight
   structure"*, and the huge spread is huge against the box itself (his "answer a.", Sun
   20/09/2026): bars almost as tall as the gap between the lines, with no room to zigzag.
   Measured, no form of the box's SHAPE tells his setups from the junk (its height, its tall
   bars, its zigzag, its spread profile, its story count), and a box about as tall as its
   bars is fine: *"there are plenty of great setups just like it"* (Mon 05/10/2026). What
   tells them apart is his dead space in TIME: *"FRPH is total junk because the box is
   mostly dead space with no visible base insight"* (Mon 05/10/2026), the days of the base
   on which no bar is in the box. They are counted his way: a bar a hair beyond a line,
   within half a daily range, is respect (Sun 30/08/2026); a day inside a named event's own
   swing is story, *"a named event's swing is never docked, an unnamed lunge beyond a rail
   is"* (Sun 13/09/2026), and only that swing, never weeks spent outside the box (Fri
   09/10/2026). Not as a fault let pass: the event is a piece of the setup, a price pattern
   found in the box that gives it more context and makes it stronger, *"that is a good
   thing"* (Fri 09/10/2026), so its days are the box at work. And the base must hold:
   after the push tops, a fall beyond the support's
   area to a lower level than the base ever made is a base that failed, *"base dosen't hold
   and dosen't answer for an LPS anywhere"* (COLM, Thu 08/10/2026). The grade is read on the
   setup's box, S by default, falling as the base turns empty to nothing at half of it (his
   "mostly"), and nothing at all for a base that did not hold; every one of his calibrated
   setups is S (Mon 05/10/2026); the ends and the cuts are his to approve. A box the price
   leaves for a lower level of its own for weeks has failed, and its later return to the
   box's range is not tied to it, so no test and no SOS is read on that return (Fri
   09/10/2026; the box's life does not read it yet). Volume never refuses, never elects,
   and carries no points. Every chart gets one state word: fired, crossed, lines with no LPS yet, forming,
   root candidate unconfirmed, beyond resistance undetermined, under support undetermined,
   broke down, not scanned, no lines. Fired charts go on the board, the rest in a watch
   lane; nothing is on the board on the buy day. A read that failed is a fault on the
   screen, never one of the ten words (ours). The word is decided last, after the LPS:
   fired and crossed are final (an LPS over resistance fires). With no fire and no cross
   the open right edge is read, *"The bars after wards determine the meaning"*: days whose
   whole bar sits over the resistance area are beyond resistance, undetermined, days whose
   whole bar sits under the support area are under support, undetermined, and the count
   of such days rides beside the word. With no box shown, a pair of lines the bars have
   already come back to and that is younger than his fifteen days is forming, its day
   count beside it. "Root candidate, unconfirmed" and "broke down" stay on the table and
   are not said by this reader, where a box ends only into a newer box (all ours).

Until the new reader lands, the sections below describe the reading as the live engine
builds it today; the rulings and every measurement behind this method are in the decisions
record. The first build of this method (twelve steps, Sun 13/09 to Sun 20/09/2026, 27
switches inside the old reader, every one off) is recorded step by step in the build
reference; its proven pieces are what the new reader is made from. Flags off, the engine
reads exactly as it did.

### The legend (strict vocabulary)

| Term | Meaning | Reserved for |
|------|---------|--------------|
| **BC → AR** | Buying Climax → Automatic Reaction | the root pair's climax when the move into it went **up**: the end of the main uptrend, or of an up-swing whose reaction is the root |
| **SC → AR** | Selling Climax → Automatic Rally | the root pair's climax when the move into it went **down**: the end of a downtrend, or of a down-swing whose reaction is the root |
| **Root Swing** | the climax→reaction pair *responsible for* the consolidation | whichever pair the cascade below settles on |
| **mini climax / mini reaction** | smaller fractal analogues of BC/AR — every swing peak→valley pair is one | limbs inside/after the base that are not the root; **never** labeled BC/AR |
| **dead space** | the empty gap between a rail (R or S) and the consolidation's bars | a **rail-placement diagnostic only** — never a junk-chart label |

BC, SC and AR name the root pair and nothing else (ruled Sat 10/10/2026): **one climax per
box**, at the root's first anchor, named by the direction of the move that ended there (up: a
BC; down: an SC), and the root swing is that pair's AR, whose two ends anchor the resistance
and the support. So a BC and an SC never follow each other in one reading: when the root steps
from the first candidate to a later pair of limbs, the names move with it. His MTLS (2026):
the rise ends at 7.00 on Mon 01/06, and if that pair were the root, 7.00 would be its BC and
the fall to 6.39 its AR; his root is the next pair, so the fall to 6.39 is the move into the
climax, 6.39 (Tue 09/06) is the SC and the swing up to 6.83 is the AR, and 7.00 carries no
name. His words: *"we cannot have both BC and SC one after the other, that label is reserved
for the climax of the previous move ... an SC (selling climax) gets the label if either we came
from a downtrend or the next move in chart is downward and the "root swing" is the "AR" of
that pair. because we anchor Resistance/Support from it's ponts!"* Swings are fractal — small
peaks and valleys are miniature climax→reaction pairs — but the names stay with the root so
the story stays readable.

**Dead space (operator ruling, 2026-07-17):** too much — or plainly visible — dead space
means either the consolidation was marked wrong (a tighter, better structure exists) or no
valid setup exists there at all (no pair of limbs produces a valid structure for that
chop). Some dead space is unavoidable and acceptable depending on the structure — an SOS
shifting the base upward, a deep correction consolidating lower, a big upthrust followed
by a huge spring can all leave holes — but even then the whole structure must stay tight
and well respected. The term describes the rail-to-bars gap and nothing else; a chart the
engine must refuse gets its own honest reason (mis-framed range, trend-continuation dip,
run-up flag…), never "dead space" as a catch-all.

**Sharpened 2026-08-23 (operator):** dead space is at root a **Root-Swing selection**
diagnostic — the correct marking finds the pair of limbs (single bars up to full swings)
whose rails wrap the consolidation's zigzag most tightly, so the boundaries display the
REAL trading range where buyers and sellers actually touched, stopped and pivoted.
Perfection is rare — always take the next-best wrap. It is a rail-selection rule only,
never an argument for or against multi-structure (chain) reads.

### The rails are AREAS — the position vocabulary and the one event language

**(Operator rulings 2026-08-29/30, decisions.md; executed by the ONE-Event-Map program,
`docs/one_event_map_program_2026-08.md`.)**

A rail is a line **treated like an area — a thin area but still**. Ruled and then
measured on the drawn corpus: the area is **±0.50 ATR around the line, symmetric,
identical on R and S, in ATR units** (it does not scale with the consolidation's
height — the operator's eye and a 1.8× cross-population test agree). That is the
incumbent `TOUCH_TOLERANCE_ATR`, which this ruling finally evidences. Hard limit:
the width is **position vocabulary only** — rests and spikes do NOT separate by
distance (measured 22.3% contradiction between the readers; junk actually pierces
its rails 3.6× LESS than drawn boxes), so a 0.5-ATR allowance used as a gate,
veto, rescue or junk filter is Tested-DEAD (twice).

**Position is FOUR values, not five** — `at_ceiling` / `mid_range` / `on_support` /
`touching_both` (`inner_box.mini_consolidation_position`, tolerance = the ruled
area; display words operator-signed 2026-08-30: “at resistance” / “middle of the
base” / “on support” / touching both). At resistance, high in the range, semi
above, resting on it: ONE position. Support mirrors it — slight pokes below and
holds a little under are inside the support area and count as respect (“holding
AT the support essentialy proving that this line is infact a support line”),
with a graded preference — never a penalty — for all/most bars staying inside.
The fourth value is the honesty valve (ruled 2026-08-30): when the rest engages
BOTH rail areas at once — the base is about a bar’s worth of height, or the
rest spans it rail-to-rail — the position carries no separating information, so
it reads **touching both** rather than a fabricated “at resistance”; this is
what separates a base that genuinely holds tight in the upper vicinity from one
where that read is an artifact of the base’s own height.

**The ceiling area has three visual STATES** — resting on (whole bar above, not
part of a bigger swing upwards) · at (touch, pivot back) · semi dwelling
(straddling, poking through). None outranks another; **“the bars after wards
determine the meaning”**: pivots back into the range — including from above the
line — are respect; bars clearly continuing up are a **departure** (markup); at
the right edge, where afterwards does not yet exist, the read is honestly
**undetermined** — never pre-typed (no-lookahead). Measured on the drawn corpus:
every harshness-by-position rule flags the operator's own boxes harder than junk
(drawn boxes ENGAGE the ceiling ~2× more than junk in every state), and drawn
whole-bar-above runs resolved up or right-edge with zero crash-backs.

**One event language over two preserved geometries.** The readers keep their
deliberately different yardsticks (the episode read: ATR-fixed zones, close-basis
breach; the wave read: box-relative zones, extremes-basis breach — AP-8 stands);
what unifies them is the projection layer (`event_vocabulary.py`): one folded
tape whose records carry the shared word, the verdict axis (held / breached /
open / unreadable — "breached" is the operator's official term for price
crossing a boundary, ONE word for both rails; what a breach means is context's
job), the span's declared bar ORIGIN, and the BASIS that produced the
verdict — so two readers may still legally disagree, but never invisibly. The
projection receives reader OUTPUT only — never bars, rails or ATR — because a
naming layer that can measure becomes a fourth competing reader. The
mini-consolidation (the operator's shelf — the REST pattern; the retired term
“holding shelf” survives only as frozen stored vocabulary) rides the tape with
its position attribute and raw rail distances.

### The event catalog — one entry per chart event

The engine reads a chart as a chronological sequence of **events** — the same events the
operator names when narrating a chart. This catalog is the law of ownership:

- **Each event has exactly ONE owning detector.** Variants of an event are **labeled
  forms inside that detector**, never sibling detectors — one question, one place that
  answers it (event-domain consolidation, 2026-07-17).
- **Wire and archive keys are frozen forever.** The operator-locked display names
  (2026-07-17 sitting) apply wherever humans read — chips, lens, trace, reject reasons.
- **A new signal declares its event.** Every new measurement names the catalog event it
  reads and enters under that event's entry (or amends this catalog explicitly with a
  new one) — measure-first, as graded confidence. No event, no signal.

#### Trend & Change of Character — HH/HL runs with a start, a climax, and a CHoCH

Before the reader can find *where the trend ends* (cascade step 1 below), it has to know
what a trend *is*. A trend is read off market structure — the sequence of swing highs and
lows:

- an **uptrend** prints **higher-highs and higher-lows** (HH/HL);
- a **downtrend** prints **lower-highs and lower-lows** (LH/LL).

`label_market_structure()` ([engine_alpha/structure/events/market_structure.py](../engine_alpha/structure/events/market_structure.py)) tags every pivot on the shared swing skeleton HH / HL / LH / LL and tracks a running mechanical trend state. `segment_trends()` walks those labels into explicit directional **trend segments**, each with the four things that define a trend:

1. **Start** — a trend is *born* at its **change-of-character**: the first HH that breaks a prior down/range (an uptrend's CHoCH-up), or the first LL that breaks a prior up/range (a downtrend's CHoCH-down). It launched off the pivot just before that break.
2. **Climax (terminal swing)** — the trend's extreme pivot: the highest HH of an uptrend (the **buying climax**), the lowest LL of a downtrend (the **selling climax**).
3. **End (CHoCH)** — a trend *ends* at the opposite structural break: an uptrend ends when a **lower-low takes out the last higher-low** (the first LL = the CHoCH that opens the next, opposite trend); mirror for a downtrend. A segment still making trend-consistent structure at the right edge has no end yet (it is still running).
4. **Full leg** — the whole advance the climax ended: from the segment's **start** pivot up to the terminal higher-high (mirror for a selling climax). This is the retrace basis the automatic reaction is measured against. (The **terminal impulse leg** — the last higher-low into the climax — is exposed too as `impulse_start_bar`, but it is *not* the AR basis: measuring against only the final sub-leg let the reaction anchor short of the true support.)

**The automatic reaction derives from this model — in theory.** Once the trend has topped at its climax, the **AR is the low of the first *continuous* reaction after the terminal swing** — the running counter-move that retraces a meaningful fraction of the *full leg*, closed at the first **big confirmed bounce** off that low. That reading is still what the AR *means*. An implementation of it was built and RULED DELETED 2026-09-08: measured against the operator's own dated marks it read FURTHER from his AR than the plain resolver, because the engine's climax is not yet his trend end. The drawn AR therefore sits where the plain Phase-A resolution puts it — in practice the box open, which is where he draws it too. Repairing the climax anchor is the open work; see [Phase A — First-reaction AR anchor — RETIRED](engine_reference.md).

> **Known gap between this model and the operator's eye (measured 2026-08-14).**
> Definition (2) above — the climax is the segment's *extreme pivot* — is not what
> the operator marks as a trend end, and the disagreement is directional rather
> than noisy. Against nine dated marks, `segment_trends` holds a terminal within
> 3 bars of his trend end on **2 of 9** (unchanged after the 2026-08-19 polarity
> re-key), and the resolved `climax_bar` sits *earlier* than his trend end on
> **5 of 7** measurable names, median −18 bars (re-measured 2026-08-31; it read
> 6 of 6 at median −50.5 before the re-key, which improved the anchor without
> rescuing the flag). The mechanism follows from the definition: inside a
> consolidation, a later upthrust to the box's own R is still a higher high, so it
> becomes the segment's extreme and swallows the true trend end. The operator also
> reads the pair as one **transition zone** rather than two events — the last trend
> peak, then the low 1–5 bars later where the base opens, the AR low being the root
> swing being the consolidation start (his nine spans are 1,2,2,2,3,4,5,5,5 bars).
> Bounded honestly: nine marks, on a cohort he himself called ugly and declined to
> certify. It is a direction of travel, not a specification. See
> [anchor_marks_ruling_2026-08-14.md](anchor_marks_ruling_2026-08-14.md).

This is **measure-only**: the trend model reads the labels the skeleton already assigns and assigns no points, moves no rails, and gates nothing. It is the geometric substrate the roadmap's richer market-structure reads (CHoCH = Phase A start, BOS = Phase D continuation, liquidity sweeps) grow from — always as graded confidence, never a veto.

#### Climax → Automatic Reaction (Phase A)

The trend-end event: the climax (an uptrend's BC, a downtrend's SC) and the automatic
reaction off it — the pair every base hangs from, and the names the legend reserves for
the main trend. The owning read is `collect_root_anchors()` (the calibrated climax→AR
anchor scan feeding the root walk). The **drawn** Phase-A overlay tells the same event
in labeled forms, never separate detectors: the canonical anchor scan; the always-on
**macro-validated bridge** (`macro_bridge_zigzag`, folded 2026-07-18 — abstains unless a
True-Root bridge validates; see "Phase A — Macro bridge read"). A third form, the
**first-reaction AR refinement**, was built dark and RULED DELETED 2026-09-08 — its
shape was right and its anchor was not.

**Climax terminality is law on every resolution path** (2026-07-19). The trend model
defines the climax as the trend's *extreme pivot*; a "climax" that price out-runs
before the box opens is a mid-trend pause, not the trend end. The macro bridge always
enforced this (its True-Root rule); `_enforce_climax_terminality()` now enforces the
same rule on the calibrated bridge/seed fallback paths: between the resolved climax
and the box open, price may exceed the climax by at most
`PHASE_A_CLIMAX_TERMINALITY_EXCESS` (0.25) × the bridge height (ATR floor). A
violating pair re-anchors to the box's own run-up extreme → the box open — terminal
by construction (the FLXS repair: a stale 04-28 seed painted while price ran +38.5%
into the 06-26 box; fleet-measured, 59% of setups continued >5% past their claimed
climax before the guard). The repair window **includes the box-open bar**
(2026-07-20, caught by the doctrine gate on its first run: 27 setups leaked when a
pbs-exclusive window anchored one bar short of a box that opens ON the extreme —
FLXS's 06-26 open IS its R); when the box-open bar makes the high, the pair
collapses to the sanctioned one-bar boundary form (climax == AR == box open). Overlay + Phase-A diagnostics only; the
`engine_config_version` rotation partitions the `bin_a_*`/`bars_since_bc`/
`descent_length` archive seam.

**Which end of the leg the repair takes — the polarity — comes from the trend
covering the box open, never from the seed** (re-keyed 2026-08-19). A buying
climax is the run-up's highest high; a selling climax is the run-down's lowest
low; so the repair must first know which trend ran into this box. That is the
CAUSE trend — the confirmed segment covering the box-open bar, cause-wins on the
shared handover leg — the same object the trend-terminal floor already defines.
It is **not** the scan origin the walk happened to start from: keying a box's
cause on the root's BC/SC label is Tested-DEAD (2026-07-27), the root sitting a
median ~394 bars away, and the same ruling prescribes this remedy. Measured
2026-08-19: the seed label contradicted the drawn pair on 4 of 4 live marked
names, and on CNI the mis-polarised branch took the lowest low of a lead-in that
*rose* into the box — naming the START of the advance as its climax — after the
raw resolver had already returned the operator's own pair. Re-keyed, CNI resolves
to his date exactly. Where no confirmed segment covers the box open there is no
cause to read, and the seed label remains the fallback so an unreadable frame
keeps its repair rather than losing it.

> **What the re-key did and did not fix (measured, 2026-08-19).** Against the nine
> dated marks the directional bias largely closes — the resolved climax is earlier
> than his trend end on **3 of 6** (was 5 of 6), median **−9** bars (was −36) — and
> CNI lands on his date to the bar. It is not uniform: **HTH moves the wrong way**
> (−6 → +54), and its former closeness was never agreement but two large errors
> cancelling (a −60 window term against a +54 box term). The anchor remains a
> function of where the box opens; the re-key fixes which END of the lead-in is
> taken, not the window itself. See
> [climax_anchor_diagnosis_2026-08-19.md](climax_anchor_diagnosis_2026-08-19.md).

**The one-bar climax+AR form is sanctioned (operator ruling, 2026-07-20).** A single
bar can serve as BOTH the climax and the AR — for the trend end or a root swing —
when it travels enough and carries enough spread to cover both boundaries: the bar
breaches the trend's extreme AND corrects deep enough within its own range to count
as the reaction. A zero-length pair (`climax_bar == ar_bar`) is therefore a valid
degenerate form, not a defect: a genuine single-bar climax+AR validates as a
terminal climax→AR bridge, its reaction held within the bar. The spine invariant
is `climax_bar <= ar_bar`, strict `<` not required.

**Cause before effect — a box may not predate its own climax (operator ruling,
2026-07-20; flag `CAUSE_BEFORE_EFFECT_VETO_ENABLED`, FLIPPED LIVE 2026-07-20).** Phase B has
no meaning without a Phase A: a consolidation is the *cause* worked off after a
trend ends, so an elected box must be preceded by a matured cause. The failure
class is **MIDD** (ruled "no setup at all"): price trends UP through both rails
into a blow-off (2026-07-07, ~1.8 ATR over R), then breaks down — all *inside*
the box window, so the "box" is a live trend top, not a range. The tell is NOT
the zero-length Phase-A pair — that is both the sanctioned one-bar form above AND
what `_enforce_climax_terminality` *synthesizes* (climax == AR == box open) when
no cause exists, so the two are the same output pair. The tell is **provenance**:
does the box-INDEPENDENT macro bridge (`macro_bridge_zigzag`, highs/lows only)
VALIDATE a terminal climax→AR anywhere in the lead-in, or ABSTAIN (`[]`)? A
matured base validates even far above R (a deep throwback — CTOS at 3.59 ATR
keeps its bridge); MIDD's live up-leg abstains. `bricks.cause_maturity` vetoes —
abstains the whole `Structure` with `return None` — ONLY when **all three** reads
agree the cause is absent: the macro bridge abstains AND the HH/HL staircase reads
a live up-run each side of the box open (`read_swing_map` `pre_box`/`box`
`trend_state` both `'up'`) AND **the elected LPS's final shelf candle never
tightened** (`lps.tightness_ratio > CAUSE_LPS_LOOSE_MAX`, 0.90). The shelf leg is
the discriminator that keeps the bridge+staircase pair from over-vetoing: the
separator hunt (2026-07-20, wf_8a6fdb42) found MIDD's shelf uniquely loose
(`tightness_ratio` 0.957 — the census minimum, its last shelf bar ~96% as wide as
the base) while the six tight-shelf winners it was wrongly dropping (BP/LECO/MEOH/
NTCT/VLO, all `tightness_ratio < 0.71`) had genuinely tightened. Because it is a
third AND-leg it can only *narrow* the veto — it rescues tight-shelf winners the
first two reads would drop, and can never drop a new one. Depth-free (never an
above-R cap — the fleet census killed that: 132/234 live setups sit >1 ATR above
R, CTOS blessed at 3.59), distinct from the box-geometry/rail respect gate, and
fail-OPEN (missing data or a missing/NaN shelf ratio never vetoes — recall is the
pass/fail gate). This CORRECTS the 2026-07-19 audit's misfiling of MIDD as a
*sanctioned* one-bar exemplar: MIDD is the exemplar the precondition REJECTS.

#### The Equilibrium box (Phase B) — the Root Swing election

**Equilibrium** is the operator-locked name for what a box must prove: a worked,
two-sided range price actually zigzags rail-to-rail. A climax→AR pair only *proposes*
rails; the framing must survive the worked-rails test — touches spread across the
window, boundary respect, balanced dwell, occupancy, and rail-to-rail traversal
(`_is_boundary_respected()` + `_validate_base_quality()` + the traversal gate). ONE
election owns the box: `read_structure()` root backtracking ×
`collect_zigzag_candidates()` earliest-valid election, start-refined by the always-on
shared-rail back-extension (`backext_shared_rail`, folded 2026-07-18). The elected box
is *emergent* — the same pair wins from nearly every scan origin — so the cascade and
the election converge on the same anchors. The worked example (AGCO 2026) and the
box-start divergence record live under cascade step 4 below.

**Two of those legs are read in TIME, not in bars-as-a-set (council review
2026-09-07).** "Touches spread across the window, not clustered" and "a run of
consecutive days outside the rails is a departure, not a poke" are both statements about
*where on the chart* something sat and *how many trading days in a row* it lasted. That
matters when a framing's judgment excises bars — the deep-excursion read lifts a qualified
terminal shakeout out of the window and judges what remains.

**The window's thirds stay the thirds of the *chart*.** Three touches all taken in the
first fortnight of a ten-week base are clustered, and no arithmetic on a shortened list
makes them spread. The excised days are simply days the rail was not touched, which is
true, so the anti-clustering leg cuts its thirds on the real span. Ruled 2026-09-25: this
reading stands whatever it does to any one name; the yardstick is his drawn marks.

**The departure run keeps its own jurisdiction.** A lifted-out excursion is not neutral
time and it is not a return inside: price left the rail, which is *why* it was lifted out —
but it left under the excursion's own, stricter promise (it must reclaim, hold, stay
inside a bounded depth, and last no longer than a bounded number of days). Those days
answer to that promise. The departure defence counts the outside days IT owns and runs
straight through event time: an excursion never breaks one departure into two short pokes,
and its own days are never charged to a cap set for ordinary outside days. Both errors
were measured and rejected the day they were proposed — reading the excursion as a return
turns a seventeen-day stay below support into seven and admits the junk framing; charging
its days to the ordinary cap refuses every terminal-shakeout base there is, including the
ones the operator drew himself.

Everything the same test asks as a SET (what share of bars respected the rails, how many
touches each rail took, how the dwell and the coverage sit) is a question about the judged
bars alone and is unaffected. The distinction is not cosmetic: it is the difference
between a rail proven across a base and a rail touched once and re-read by an accident of
arithmetic.

**Engagement respect — tested and REJECTED as a gate; kept as a measure
(2026-07-24, gap-breach Task 3).** The operator reads rail respect as
*engagement* — a bar poking a bounded distance past a rail and closing back
inside "hangs" (bar-basis primary, closes supplementary; his ruling: "the HIGH
and the LOW Values are the ones that matters most since Visually we use the
entire bar in Technical analysis ALWAYS"). An election-gate variant of exactly
that rule (bounded excursion + close-back-inside re-read as respect) was built
dark and A/B'd: **the negative corpus admitted FLG + BBVA at every excursion
bound ≥ 0.5 ATR** (SPCB/DBD/ENIC too at 1.5) **while converting zero Guided
List misses** — NKTR, the stage-tagged target, stays unread because its
candidate rejects are width-dominated, not respect-dominated. Ruling: the
whole-bar wick containment gate IS the upthrust/junk defense (the shelf-R
lesson, now confirmed at election scope with corpus evidence); never re-wire
an engagement read into the gate on anecdote. The engagement read survives
measure-first as two archived, never-gated columns on every fired setup —
`eq_engagement_respect_frac` (respect share when bounded close-confirmed
excursions hang; yardstick `ENGAGEMENT_MAX_EXCURSION_ATR`) and
`eq_max_excursion_atr` (deepest single-bar excursion beyond the buffered
rails) — one arithmetic home (`_engagement_hang_masks` in `box_gates`),
consumed by `measure_gate_margins`. Their live-fleet distributions are the
evidence base for any future rail-PLACEMENT work (the engine's S-below-drawn-S
bias), which is where the Guided List says the wick/close divergence actually
bites.

**The outside bars are NAMED, never judged (2026-09-05, engine-eyes Task 1).**
The operator's respect-form taxonomy (ruled 2026-08-29: touch-and-pivot ·
slight poke / semi-inside · resting above R · holding below S — "all of these
counts") is now measured per bar on the elected box, from the SAME masks the
respect gate reads, and archived as descriptors on every fire. Per bar,
exactly one form: a whole bar above the resistance LINE (Low > R) is a *rest
above resistance*; a whole bar below the support LINE (High < S) is a *hold
below support*; a bounded poke that closed back inside the buffer is the
engagement hang (*poke and close back inside*); whatever else crossed a rail
*straddled and closed out*. The whole-bar forms are judged against the line,
not the buffered rail (his wording), a bar that is both a hang and a rest
counts ONCE, and a NaN extreme is inside — never a rest. Per contiguous
outside run the engine also says how the run RESOLVED inside the window:
pivoted back (a later bar wholly under the line), hovered (back inside the
buffer, never under the line), reached the right edge (honestly undetermined
— no-lookahead), or ran past the gate's run cap. What this buys is the
VOCABULARY: on the 35 drawn boxes the 414 outside trading days are 218 pokes
that closed back inside, 127 whole-bar rests above R, 75 whole-bar holds
below S, 214 of them in the last third, and 23 of 30 drawn boxes end in a
right-edge run. What it does NOT buy is admission: re-counting the forms as
respect was benched hermetically 2026-09-04 and is DEAD as a gate in every
disguise (5 of the 18 must-not-fire junk charts fire, SILC's pinned fire is
lost, zero misses convert) — the respect floor and the run cap stay hard,
nothing consults the new numbers, and the descriptors that re-measure dead
families (rail overshoot depth = the overshoot-magnitude row; the whole-bar
early share = the harshness-by-position row) carry their graveyard tag so a
later "recalibrate against the archive" cannot walk a dead lever back in.

**Commit-tail rescue — tested and REJECTED (2026-07-24, gap-breach Task 4).**
The dual of the SOS worked-window trim (re-judge a failing framing on its
window minus a bounded terminal floor-holding pullback tail — "the completing
LPS may not re-litigate its own cause") was built dark and probed on its
stage-tagged targets: **no cap (5/8/12/15 bars) restores the EGBN or YPF
elections.** Their right-edge collapses are structural, not bounded-tail
artifacts — EGBN's shelf resides ~two weeks above the body-level-anchored
candidate ceilings (the body-level-vs-wick-extreme rail-PLACEMENT family), YPF's drawn
base is 19 bars with occupancy failures — and a trim long enough to matter
re-elects stale windows (the same lesson as the rejected rescued-pool
arbitration attempt recorded under the break-above-R-then-rest rescue: re-judging a framing
on an alternative window quietly re-litigates the election). Cause-commitment
remains open only via a genuinely CROSS-FRAME mechanism (the measure-only
election-stability probe is the calibration instrument); never via window
trims. The ratchet stage tags were corrected at this task: NKTR + EGBN →
`rail-placement`, YPF → `lps-envelope` — an interim tag SUPERSEDED by Task
6's calibration answer, which re-tagged YPF to `rail-placement` too (the
final taxonomy: every chart-readable miss is rail-placement; SKYT is
universe-gate).

**Margin calibration campaign — every lever tested and REJECTED (2026-07-25,
Rail Program Tasks 3/5).** The three hair-thin judgment margins that reject
the operator's exact drawn boxes (EGBN lower-dwell 3/23 vs the 0.15 floor;
YPF lower-dwell 2/14 + mid-dwell 7/14 vs the 0.45 cap; PKE respect 5/22
outside vs 0.80) were A/B'd against a protocol SEALED before any measurement
(`docs/rail_program_protocol_2026-07.md`: closed grids, accept conditions
A–F, verdict templates). Fire evidence (`tools.research.rail_margin_ab`, per-variant
manifest stamps, elections+rails diffed at every pinned first-fire):

- `EQ_MIN_HALF_DWELL` 0.15→0.125 converts EGBN (tier B) with 26/26 hits kept
  and 18/18 junk rejecting — but fails the sealed separation condition: ten
  junk candidates (KWR ×3, BBVA-throwback ×2, BMRN/OHI/NVT/RLGT/GOOD) newly
  cross the dwell leg at 0.125, so the marks and junk populations overlap at
  the boundary with zero bars of gap. The floor stays. (Converting EGBN is
  one operator RULING away — amending condition D via the protocol changelog
  — but it is a ruling, never a default.)
- 0.15→0.10 additionally breaks the ratchet (MS fires early; NTCT/ROIV
  elections displaced) and converts NKTR unpredicted — dead.
- `EQ_MAX_MID_DWELL` 0.45→0.50/0.55 is the widest blast radius of the
  program: 4–6 pinned hits break (BWA/EWTX/MS/VIK fire on different days,
  WTS's election displaced, **MATX stops firing entirely**), PKE/YPF/ORMP
  convert unpredicted via different elected boxes, and at 0.55 the DGII junk
  case FIRES. The cap stays; YPF (which needs BOTH dwell and mid moves) is
  therefore unconvertible by calibration — a correct miss.
- `MIN_BOUNDARY_RESPECT_PCT` 0.80→0.75 admits FLG + BBVA-throwback junk
  fires, displaces FOSL/NTCT elections — and PKE still misses: its respect
  leg passes and the candidate then dies at occupancy (upper-third dwell
  1/22). The "one bar short" diagnosis is SUPERSEDED: PKE is respect AND
  upper-third dead space — structural, not hair-thin. The one-bar tolerance
  reframing (allowance identical to rate-0.75 at PKE's n=22) therefore
  converts nothing and was answered NO without an EC-8 build. The respect
  gate remains never-loosened (shelf-R doctrine, now with campaign evidence).

Net: **zero moves; the ratchet stays 26/33; every gate floor is already
sitting exactly where the junk begins** (the margin instrument's headline:
converting marks pass candidate floors with zero bars to spare while the
nearest junk candidate sits one bar away). The named junk counter-cases
carrying lever names are existing negative-corpus members: DGII (mid cap
0.55), FLG + BBVA-throwback (respect 0.75), and the ten dwell-leg crossers
(dwell 0.125). Do not re-request these levers; a re-proposal must beat the
sealed protocol as written.

**Cluster-anchored rail statistic — tested and REJECTED (2026-07-25, Rail
Program Task 6).** The operator's ruling reframed the rail-placement family:
rails DO sit at bar High/Low (never a wick-vs-body question); the question a
wick-inflated window poses (NKTR: 1900+ width rejects, no candidate within
0.5 box-heights of the drawn box) is WHICH bars' extremes define the rail.
The candidate statistic — `cluster_rails` in `rail_qualification.py`, a pure
counting rule (R = the highest high with ≥ `EQ_MIN_TOUCHES_PER_RAIL`
bar-highs resting within `TOUCH_TOLERANCE_ATR` ATRs; S mirrored; no new
knobs) — was validated against ALL 33 Guided List boxes under an acceptance
sealed BEFORE the run (`docs/cluster_rail_validation_2026-07.md`), and
**failed decisively: 20/66 rails within 0.5 ATR (needed 60), median 0.88
ATR; on NKTR the cluster level EQUALS the wick anchor** (the "outlier" has
three resting neighbors at the touch tolerance). A (k, tol) sensitivity
sweep caps the whole family at 34/66; the one cell that nails NKTR (k=5,
tol=0.1) collapses to 33/66 — the tail fit the sealed guard rejects. The
real finding: the operator's rail is a **representative interior bar's
extreme**, not the outermost level with k resting neighbors — where his rail
IS the clustered extreme the statistic matches to 0.000 (PKE R, SKYT R,
EGBN S). Tested-DEAD: never re-propose an outermost-level/order-statistic
rule for rail placement; future placement work must model the anchor-BAR
choice. The function + validation tool stay in the tree as the mechanical
tripwire (measure-only, no live caller); the dark cluster-width form and its
flip (planned Tasks 7–9) were NOT built — their premise failed.

**Anchor-bar study — the eye model, measured (2026-07-25,
`docs/anchor_bar_study_2026-07.md`).** All 33 marks carry declared anchor
bars; the study made three reading-model claims into measured fact: (1)
drawn rails are EXACT bar extremes (fidelity 0.000 on 66/66 rails — the
rails-at-H/L ruling); (2) the box is born at its first swing — R = the
window's first bar's high (drawn first 28/33), S = the first reaction low a
few bars later, i.e. the operator's own climax→AR; (3) the drawn rails then
tolerate heavy later overshoot (window extreme median 1.6 ATR above R,
~12 bars beyond R inside his own box) and are proven by re-touch (median
11–15 later touches), not redrawn. The engine's candidate anchors already
land on his exact bar 27/64 (median 2 bars apart; misses median 0) — rail
placement is NOT the eye gap. **Bounded compensation over the gate margins
is tested-DEAD in the same study:** EGBN's fail-one-leg-by-one-bar-with-
big-surplus profile has exact junk twins (DGII/BMRN surplus 14, GOOD 49; 15
junk candidates fail narrow-but-rich), so no compensation rule on the
worked-equilibrium/respect legs separates them. The residual eye-gap is
separable only by NEW measured information (why a third is empty; what
story an excursion tells), entering measure-first as always.

#### Spring (Phase C)

The turn-conductor event: penetration below S → reclaim → hold (the bounded-excursion
model). ONE detector, `find_spring()`, owns it; the terminal-shakeout scale is typed at
the same single seam (`_phase_c_candidate`, live since 2026-07-16), so the chart's C
label, the phase read, and the archive can never drift — a calibrated `SPRING` is never
re-typed. Downstream reads **inject** the elected spring rather than re-detecting. Most
bases have no Phase C and that is normal (see "The Phase D Model").

**A spring is MARKED, never graded (operator ruling 2026-08-12).** "There is no telling
whether a setup that has one will win or not. A setup is more complete if a clear Phase C
occurs and then recovers nicely into a Phase D, but that's about it — it's more important
for the engine to *find* Phase C (spring) or the 'V' tip structure, just to put a mark on
where the right-most side of the consolidation is, to understand the order of how the
setup played out." So Phase C is not a chapter of the grade and carries no points; the
spring term rides a `marker` layer that is outside the grade's arithmetic entirely, so the
ruling holds by construction rather than by a weight anyone could raise. The *completeness*
a clean turn buys is graded where completeness is graded — inside the consolidation's story
terms — not as a bonus for the event itself.

**Shakeouts read the same way, and the LPS that follows one is its own shape.** A shakeout
is a later, deeper correction whose purpose is literally to shake buyers out; it is typed
at the same Phase-C seam and marked, not scored. The operator's read: the smaller,
contracting seller pullback that forms *after* a shakeout is often a very good setup, and
it is **not** the same shape as a Last Supper (the deep, fast giveback of a preceding
up-move, described in the chain grammar below; descriptive, never a warning, per the
2026-08-26 ruling). The two are distinguished today only by the Last-Supper stretch
measures; nothing grades the after-shakeout LPS as its own form. Recorded as theory,
unmeasured.

**Cause before effect, Phase C → Phase D (operator ruling 2026-08-09, KYMR): the LPS
may not predate the spring.** "By chronological order the actual LPS comes in Phase D
— the right side of the stock's V — after either a dedicated Phase C or just natural
price-action progression." When a spring is elected, it conducts the turn, and the
last point of support is the rest that follows it; a support test that completed
BEFORE the shakeout is a prior test, never the terminal evidence. The elected LPS
window therefore may not OPEN left of the spring tip — opening ON the tip bar stays
legal (the sanctioned undercut-rebound form: the window resting on the spring low
itself). The failure class this closes (KYMR, live payload 2026-08): the LPS elector
takes the latest window whose trigger is still overhead, so once the true post-spring
LPS has triggered it reached BACK past the spring and painted support that had
already broken — the "last point of support" read 8 bars before its own cause,
tripping doctrine invariant C6 (`spring.tip <= lps.start`, the same ordering law the
gate asserts from the other side). A story whose only Phase-D evidence predates its
spring is refused on ORDER (a doctrinal non-election, like a cause-absent veto), not
on missing evidence. No-spring bases are untouched — natural progression needs no
floor.

**LPS envelope calibration — answered NO MOVES (2026-07-24, gap-breach Task
6).** The shelf-harness (`tools.calibration.shelf_harness` — the ONE detector graded over
all 34 marked shelves at the drawn basis) plus the terminal-turn envelope
settled the calibration question the Guided List raised: the operator's
shelves genuinely REST (terminal-turn median 0.0 profile-units; the p90 tail
0.18 comes from marks that already fire), so `LPS_TERMINAL_LOW_TOL_PROFILE`
(0.1) has no envelope support for widening; ORMP-2 and PKE's marked shelves
PASS this detector at the operator's drawn rails (their misses are the
elected BOX, not shelf geometry); NOK's launched-above form is a single case
(tail-fit risk — don't build acceptance forms off n=1). Every chart-readable
Guided List miss therefore belongs to ONE family — **rail placement**: the
election anchors candidate rails at wick extremes where the operator anchors
BODY levels (the S-below-drawn-S bias, EGBN's body-level-vs-wick-extreme
placement, NKTR's width inflation). That family is the named next
program; no LPS geometry knob moved in this one.

#### Support Test

An S-rail hold: a low-zone valley that touches S without a deep breach, then holds.
Owned by `measure_support_tests()` — deliberately *not* the R-rail wave machinery. A
deep breach-and-reclaim belongs to the Spring; the two never double-emit.

#### Sign of Strength, Markup & Upthrust — the R-rail wave

One wave machinery, `measure_resistance_events()`, owns every R-rail interaction and
types each wave by its **terminal outcome**: an advance that held with a genuine
mini-consolidation is an `SOS`, and an actual breach of R is not required (whether
the top decisively cleared R is recorded on the event as data — operator ruling
2026-08-26). The operator's full model (recorded 2026-08-26, decisions.md): an SOS
is a **decisive Phase-D swing, not a shallow climb** — it need not end at R at all —
and where the swing ends is a **graded quality, never a gate** (nearer R, above it,
or back near the prior high after a shakeout reads higher). The current machinery
implements the hold-confirmation form only (typed from high-zone waves, no
decisiveness requirement, ending location split binary at the markup cap); the
decisiveness and ending-quality dimensions are recorded rulings awaiting
measurement. **Decisiveness is SHAPE, not a number, and volume is not part of it**
(ruling 2026-08-28, from the drawn corpus: "it's in the shape of the thing rather
than the numbery measurement"): an SOS is an immediate up-surge of buyers — read in
span, travel, speed, one-way-ness, launch position and the ground kept afterwards —
that comes in many variations with one role, strong buyers before the breakout.
Volume is recorded as data only; the measured shape envelope of the 22 drawn
specimens lives in the Corpus Study record ([corpus_study_2026-08-28.md](corpus_study_2026-08-28.md)),
whose fitted floors are proposal input for the operator's eyeball, never a
classifier on their own — election and story context stay load-bearing. An advance that held far above R is `markup`; a
run-up that failed back to support is a single `upthrust` (one false-break wave, never a
string of SOS); the in-between cases stay descriptive (`range` / `rejection` /
`in_progress`).

#### Phase D — the right-most region

Where the base turns. `resolve_phase_d_boundary()` places the Phase-D open from labeled
evidence variants — support-test cluster / SOS reclaim / rising support / inner
mini-consolidation / recovered late-base low (`v_tip`) — with the LPS window as the
mandatory fallback; the variants' floor policies are labeled and behavior-frozen.
Measurement only, never a gate — see "The Phase D Model — Reading the Right-Most
Region".

#### Last Point of Support — the mandatory terminal event

No LPS in the right-most region means no Phase D and no setup. ONE detector,
`detect_lps()`, owns the event; its sanctioned completion geometries are **labeled swing
forms inside it**, never sibling detectors (wire enums frozen forever):

| Form (wire enum) | Display | Geometry |
|---|---|---|
| `terminal_valley` | LPS | the classic pullback that rests on its low |
| `holding_shelf` | LPS — flat hold | the two-form doctrine's flat shelf, sanctioned only high in the structure |
| `buec_shelf` | LPS above R | the shallow-shelf form of the `OVERSHOOT_R` window class — an LPS that forms ABOVE the old resistance, after price broke out and came back to rest on it; matured-cause bounded (the BBVA defense). The wire key is frozen; read it as "LPS above R" |

**Which R is "the old resistance"? The one belonging to the range the LPS rests on**
(2026-08-13). An LPS is located INSIDE / above R / below S — its **zone class** — and that
class is read against the rails of *the range that owns it*. When the right side tightens
into a nested mini-range and the LPS is elected there, the nested range is a range in its
own right: its own resistance is the level price broke out over and came back to rest on,
so its rails are the ones the zone class means. The parent's rails are a different fact
about a different object. This is a corollary of nesting being **temporal, not
price-bounded** — a nested range may sit above the parent's R (treating it as its new
support) or entirely inside the parent, and in the second case an LPS that is genuinely
above the nested resistance sits *below* the parent's. Reading the class against the
parent's rails there is a category error, not a violation: the two levels answer different
questions, and only the owning range's answer types the event. The zone class is therefore
never comparable to a rail the read was not taken against.

The freshness veto is the **Stale-Support Reject** (the `descent_tail` family): a window
still descending into its low is not an LPS yet. The full gate table lives in "Phase 3 —
LPS Detection".

**The ceiling rest — the drawn corpus's most common terminal shape, sanctioned dark
(operator ruling 2026-08-29, NOK).** The Corpus Study measured what the catalog had
under-modeled: 30 of 36 drawn LPS windows rest at the CEILING — the after-advance
giveback landing ON the rail, wick pokes above R included. The detector's launch gate
refused exactly this straddle (an INSIDE window that "launched above resistance"),
reading it as a late off-structure pullback. The dark exception sanctions it ONLY when
the rest itself sits on the rail (within 0.3 ATR under R — the bar placed by the drawn
class: DSGN/MATX/MSGS/NOK rest at 0.010–0.241, the nearest labeled junk at 0.314); a
launch-above window resting any deeper stays refused as before. This is a completion-
form refinement inside the one LPS detector, never a sibling detector; flip and the
razor's eyeball are the operator's.

**One LPS per setup (operator ruling 2026-08-09).** A setup has a SINGLE last point of
support — the chronological terminal one, in Phase D, right of the V (see the spring
entry's cause-before-effect rule). The earlier support-test staircase the chart used to
paint ("prior LPS/TEST behavior checks", requested while the engine's multi-test read
was being proven) is retired from the DRAWN chart: the engine is judged strong enough
that only the elected LPS is marked, alongside the other events that may appear. The
staircase itself survives as measurement — it feeds the Phase-D boundary evidence and
the LPS-shrink read — it is just never drawn as an LPS.

#### Cross-event measures — graded context, never events

Some reads grade events rather than being one. **Dwell Balance** — how the box's time
splits between the rails — docks one-rail hangs. **Resistance/Support Volume**
(`r/s_touch_vol_z`) is ONE statistic — event volume as a z-score against the base
window's own distribution — living in TWO guarded homes (the touch families in
`metrics`, the event families in `bin_features`) kept separate **by design**: each
home's guards and NaN routing differ, and what they share is the question, not code
worth merging (event-domain audit C14). Bar spread likewise carries TWO statistics by
design — the readability texture and the LPS yardstick — pinned apart. All of these are
graded confidence or archived measures; **geometry is the only veto**.

#### Where the graded reads land — the one number (live 2026-08-09)

Every graded read above rolls up into **ONE 0-100 Technical Analysis grade**, and that
grade — not the raw sum of components — **is the read's number**. It is a single affine
sum over a FIXED divisor, so absence is neutral: a chart missing an input grades against
the same denominator as a complete one, and no read is punished for a measurement the
engine could not take.

The grade is read as three **story chapters** — **Consolidation → Phase D → Trend** —
left→right like the chart. The chapters are a *display partition* of the one sum: their
subtotals add up exactly to the grade, with no per-chapter divisor, floor, or clamp (any
of those would recreate the tested-DEAD present-cap denominator one level down).

- **Consolidation** — the base itself: is it tight, mature, two-sided, contracting, on a
  floor that stair-steps up, and did its story complete? Wyckoff's *cause* and the work
  inside the range are ONE question about ONE object, and were fused as such (operator
  ruling 2026-08-12: "a two-sided zigzag price action can be folded into one of the
  quality traits we look for in a consolidation as a whole").
- **Phase D** — the right side into the pivot: the LPS's tightness, its volume dry-up, the
  terminal squeeze.
- **Trend** — the chart around the base: trend, RS, 52-week proximity, ADR. Hopefully the
  *result* of said cause.

**Some events are marked, not graded.** Phase A and Phase C carry no points at all. The
engine finds them, types them, archives them and draws them — and stops there, because
locating them is the whole job: a mark says *where* the base's right side begins and in
*what order* the setup played out, not how good it is. Grading them would claim an edge
nobody has measured (see the Spring entry). A read is never punished for lacking a mark,
and never rewarded for having one. What a clean shakeout-and-recovery genuinely buys is
already graded where it belongs — in the consolidation's *completeness*, which reads the
whole story rather than the presence of one event in it.

Two rules keep it honest against the model above:

- **The letter follows the number.** The tier is derived from the grade, so what the
  operator reads as "S" and the number beside it can never disagree. The one thing that
  overrides the grade is the operator's own width rule: a base wider than the S cap is
  never elite, however well it grades.
- **Warnings discount, never veto.** A warning multiplies the bounded grade against a
  floor; a missing warning input reads exactly neutral. Geometry remains the only veto —
  a warning can dim a read, never refuse it.

Market regime (breadth, the index trend) sits **outside** the grade entirely, as an
informational label: the tape is context for the operator, not evidence about this chart.

### The measure-only reader layers

Above the event catalog sit reader layers that move no rail, gate nothing, and score
nothing (save the story read's one bonus-only term):

#### The L2 event reader — Wyckoff story: from rail events to a scored narrative

Above the geometry sits a second reading layer that does not move a single rail. Once the cascade has **elected** an equilibrium box, the L2 event reader ([engine_alpha/structure/events/box_events.py](../engine_alpha/structure/events/box_events.py), re-exported through [engine_alpha/structure/metrics/base.py](../engine_alpha/structure/metrics/base.py)) reads the in-box structure as *facts about a Wyckoff story* — a labeled staircase, independent rail-event zones, and their chronological assembly into the classic spring → SOS → LPS story. Like the trend model, it is **measure-only**: every function here reports what it sees and assigns no points, gates nothing, and moves no rail. It reads the box the engine **already elected** — never a re-detection — so its story is told over the same rails, start, and span everything else measures against.

The read is a pipeline of four stages. First, `read_box_staircase()` labels the in-box swing sequence: it composes the *same* calibrated significant-swing skeleton the traversal read uses (`_collapse_swings` on the order-1 zigzag, amplitude-filtered by `TRAVERSAL_NOISE_FRAC`) with the L0 labeller (`label_market_structure`), so the staircase swings *are* the worked-equilibrium swings. Each swing is annotated with its box-position (`box_pos`, 0 = S rail, 1 = R rail), a low/mid/high `zone`, and a `rail_event` (`touch_R`/`breach_R`, `touch_S`/`breach_S`, or `interior`) — one chronological HH/HL/LH/LL sequence the later events are read off.

Second, the two rails are measured **independently**. `measure_resistance_events()` walks the R-rail: every peak that turns in the high zone is a rail interaction, and consecutive higher-highs with no drop back to support between them are grouped into one *wave* that is typed by its **terminal outcome** — a break above R that held near R with a genuine mini-consolidation is an `SOS`, an advance that held far above R is `markup`, a run-up that failed back to support is a single `upthrust` (one false-break wave, not a string of SOS), and the in-between cases stay descriptive (`range` / `rejection` / `in_progress`). The Phase-D split is anchored on the structural **V** (the deepest staircase valley). `measure_support_tests()` is the S-rail sibling — deliberately *not* a mirror of the wave machinery — reporting each low-zone valley that touches S without a deep breach and then holds as a `test` (a deep breach-and-reclaim is left to the spring brick, so the two never double-emit).

Third, `read_box_events()` (over the shared chokepoint `_box_events_with_meta`) unifies these into one flat, deterministically-ordered list of independent zones, adding the calibrated **spring** brick (Phase C) and **LPS** brick (Phase D, gated purely on bar position — right of the V — never on an SOS existing). Each piece is detected on its own geometry and is never gated on another; the bricks come either from a measure-only re-detection or, when the scorer calls in, from the pieces the engine *actually elected* (including a tighter inner-box LPS), so the read describes what fired rather than a fresh parent-box guess.

Fourth, `assemble_box_narrative()` stitches the zones into the story in one linear pass. It picks the spine (`spring` → first `SOS` → `LPS`), tallies a raw `completeness` (0..4 distinct canonical pieces present — spring, SOS, LPS, held-test), reads a three-valued `chronology` (`intact` only when all three spine pieces are present *and* strictly bar-ordered spring < SOS < LPS, else `partial`/`absent`), derives the B/C/D phase spans off the shared V, and emits an explainable `trace`. Every one of these reads is descriptive — none is shaped as a pass/fail another layer could consume as a filter. A missing piece is reported, never fabricated.

The **only live consumer** is a bonus-only score term. Always on (folded 2026-07-18; formerly flag `PUZZLE_SCORE_ENABLED`), `_setup_quality()` in [engine_alpha/scoring/scoring.py](../engine_alpha/scoring/scoring.py) folds `completeness` and `chronology` into a single `[0, 1]` composite (they are correlated — an intact chronology is impossible without the full spine — so they never split into two double-counting terms), and `s_setup_quality` scales it by `SCORE_SETUP_QUALITY` (8.0) and clamps it into `[0, cap]`. It is strictly additive and `>= 0`: it can only ever *raise* a score. A missing, `None`, or malformed narrative reads a neutral `0.0`, so an absent story never demotes a setup below what its geometry already merits. Consistent with the whole reading model, **geometry is the only veto** — the Wyckoff story is graded confidence layered on top of it, never a gate.

#### The Event Map — the mechanical swing layer (whole-frame)

The Event Map ([engine_alpha/structure/events/event_map.py](../engine_alpha/structure/events/event_map.py), `read_swing_map`) widens the L2 staircase's calibrated swing skeleton from the elected box's window to the **whole evaluation frame**, so the pre-box trend and the box story are read on one substrate. It stands up no second skeleton: **one** order-1 pivot walk runs per frame, and each windowed view — the pre-box segment, the in-box staircase — is that walk's pivots filtered to its window and fed through the *same* staircase machinery (`_staircase_from_pivots`). The in-box view is **byte-identical** to `read_box_staircase` by construction; the widening only *adds* pre-box swings (including a pivot at the box-start bar itself, which the windowed walk's order margin masked). The two views are stitched, not re-collapsed: alternation and HH/HL/LH/LL labelling reset at the box-start seam — the price of keeping the in-box slice identical to the elected staircase — and the seam is a stated boundary, never an implicit one.

Every swing carries the **causality stamps** the Event Map contract requires ([archive/specs/event-map-causality-contract.md](archive/specs/event-map-causality-contract.md), binding for all Event Map work): `describes_bar` (the pivot bar) and `knowable_bar` — the first bar at whose close the swing was *irreversibly committed*, i.e. the bar that pivot-confirms the first opposite extreme whose counter-move reaches the collapse threshold. A swing whose committing reversal has not printed is `in_progress` and satisfies nothing downstream; the frame's first swing is `edge_uncertain` (its extremity depends on bars left of the live two-year trim). The label set "as of date D" is exactly the swings with `knowable_bar ≤ D` — what makes replay honest instead of quietly clairvoyant. One stated caveat: a *view* younger than three raw pivots emits nothing yet (the staircase's own degenerate-window guard), so a swing's first appearance can lag its `knowable_bar` at view birth — labels may appear late, but never change or vanish retroactively.

Above the mechanical swings sits the **narrative-role layer** (`read_role_labels`): the L2 event zones — spring / test / SOS / upthrust / markup / range / rejection / LPS — re-emitted as stamped role labels. It consumes the *same* `_box_events_with_meta` chokepoint the story read uses, **fed the engine's elected bricks** (`structure.spring` / `structure.lps`, both required arguments; an injected `None` means "the engine elected none" and is honored — the layer never re-detects). Each label carries the measurer's own tri-state `resolution` plus a `knowable_bar` derived from its real confirmation mechanics: a failed wave at its low-zone drop bar; a held wave or test at the end of its printed hold window *and* never before the wave stopped being extendable (a later higher-high with no drop to support would have absorbed it — the wave-closure rule) or the anchoring swing committed; a spring at the end of its fully-printed `BIN_C_HOLD_BARS` reclaim-hold (a window running past the last bar is `in_progress`, §2); the elected LPS at the **frame end** — its "still holding" verdict consumed every printed bar, so it is `election_dependent`: re-issued by each frame's own election, frame-scoped rather than truncation-stable (the spring's presence likewise). The chronology battery (`python -m tools.audits.event_map_chronology --check`) replays the marks corpus with cuts stepping through each setup's LPS window and asserts, on emitted labels only, that within a stable election a committed label never mutates or vanishes as bars print.

Like the trend model and the L2 reader, both layers are **measure-only** — they move no rail, gate nothing, score nothing. On the live path they run behind **`EVENT_MAP_ENABLED`** (**LIVE since 2026-07-25** — Event Map program Task 13, operator grant; frozen manifest — the flip is the family's first `engine_config_version` seam): the readers are computed **for firing setups only** (the story-read placement) and emit underscore diagnostics — the four tape-summary reads (`_event_map_n_swings` / `_pre_box_trend` / `_n_labels` / `_n_committed`; proven additive-only over the full shadow fixture, evaluation-phase cost ≈ +1ms per firing ticker) plus the **rail-episode substrate** (Event Map program Task 10): the AS-OF sentence over the elected window and rails — the same READER the story pool consults but a **different basis** (elected window + zone ATR, vs the admission's candidate window + candidate ATR), so the substrate and the admission may legally disagree: YPF fires story-elected while `event_map_story_admitted` reads 0. The evidence that ACTUALLY admitted a story fire is archived separately in `story_admission_profile`; this substrate is what a later TA-score calibration grades, never the admission record — as typed scalars (`completed_s` / `completed_r` / `alternations` / `terminal_posture` / `terminal_drift` / `story_admitted`), the readability companion (`episode_nan_bars` — an explicit zero is evidence, and it can never masquerade for unreadable bars), the sentence text, and ONE compact JSON episode tape whose anchors are dates, never bar indexes. Flag-on, the diagnostics are archived as the **`event_map_*` column family** — declared once in `event_map.py` (`EVENT_MAP_COLUMN_SQL`: names, types, row extraction; the live writer and seed both splat the one extraction function) and entering the schema as model-only nullable adds, where NULL means "not measured", never zero. **Seam discipline (Task 11):** archived sequence values are partitioned by `engine_config_version` — the flip is the family's first seam and every later episode-typing or ruled-form refinement is a NEW seam; pre-flip NULL rows are **never backfilled** by re-running a later reader over cached history (the `bin_a_*` precedent — a backfill stamps current-rule values onto rows whose replay basis may differ, destroying the seam's meaning while looking like a completeness win). Separately and unconditionally, every fire archives its **electing-pool provenance** — `elected_pool`, a closed set (`strict` / `rescued` / `band` / `story`) carried from the candidate tuple through the elected box (`EquilibriumBox.elected_pool`) into both writers — so the rescued cohort's own forward returns stay separable forever. The chart-overlay payload arrives in a later Event Map stage behind its own review; the flip is operator-gated on the scan-metrics cost A/B.

A sibling measure-only diagnostic, **election stability** (`ELECTION_STABILITY_ENABLED`, default OFF, dark-flag ledger + frozen manifest): for firing setups only, the eval-twin prep and the structure election alone are re-run at D−1..D−k (backward shifts only — nothing archived can carry lookahead) and each shifted reading is compared to the live one through the single cross-frame identity predicate (`engine_alpha/election_identity.same_election`: box-start date + rails within a scale-free tolerance). Real structures persist while junk elections flicker day-to-day. The probe measures **backward persistence of the BOX election**, not of the fire: a box can elect well before its LPS completes, so `same_frac` at a fire's first session can legitimately be anywhere in 0..1 (corpus fires measured mostly 0 — the election itself was churning into those fires — while AVT's 0.33 shows pre-fire persistence exists; a low value means election churn, never "the fire is new"). A shift where the eval-twin prep refuses (universe-gate flicker: SMA/volume/price membership, not chart structure) counts as not-same in `same_frac` and is ALSO reported separately, so calibration can tell gate-flicker from election-flicker. Diagnostics emitted raw (`_stability_same_frac` / `_streak` / `_probes` / `_refused`) — never a gate, never a score. Flag-off is byte-identical and compute-free; the flip is gated on the measured cost bound (≈2.75s per firing ticker at k=3 — see the ledger).

#### The rail-episode read — chronological completion over a rail pair (Event Map, layer 3)

Where the swing map reads *structure* and the role layer reads *the elected story*, the
rail-episode read tells a candidate window's story **chronologically, one rail engagement at
a time** — the read that separated EGBN (`S+ S+ S+ R^`) from its drift-junk statistical twins
(DGII/CHCT/COLM/FLG: zero completed episodes) when every aggregate failed (the 2026-07-25
sequence probe). It is a bar-level read over ANY rail pair — an elected box or a raw
candidate framing — on the engine's touch/buffer yardsticks with TWO layer-local
conventions, stated: **zone entry reads wick extremes** (the touch convention) while
**breach-and-reclaim read closes** — a deliberate divergence from the respect gate's
extreme-basis buffer (a deep intrabar flush that closes back inside is a worked test to
this read, a breach to respect) — and `EPISODE_DRIFT_MIN_BARS` (3) is this layer's own
drift floor. The promotion counts are pinned on exactly these bases; "aligning" them with
the respect yardsticks later is a re-measurement (a new archive seam), never a cleanup:

- **rail episode** — one merged visit of a rail's touch zone (zone = the touch yardstick,
  `TOUCH_TOLERANCE_ATR` × ATR; visits separated by ≤ `EPISODE_MAX_GAP_BARS` (2) inside bars
  merge into ONE episode — the band-rails same-side-span convention).
- **Outcomes (wire enums frozen; one per episode):**

  | Wire | Display | Meaning | Profile token |
  |---|---|---|---|
  | `completed` | completed support test / completed resistance rejection | the engagement resolves back inside the box: any breach beyond the respect buffer (`BOUNDARY_ATR_BUFFER` × ATR) is reclaimed and the first close after the episode confirms the rail held | `S+` / `R+` |
  | `failed` | failed episode | the engagement resolves through the rail — an unreclaimed breach, or the confirming close lands beyond the rail | `S×` / `R×` |
  | `unreadable` | unreadable episode | a verdict-relevant close (the confirming close, or the run's last close when a breach needs its reclaim read) is not finite — no verdict printed on unreadable bars (contract §5; refined 2026-07-26: a NaN confirm previously printed a false `failed`) | `S?` / `R?` |
  | `open` | open episode | the window ends inside the engagement — no verdict printed (contract §2: `open` never satisfies a completion predicate) | `S0` / `R0` |

- **Terminal postures** (frame-scoped right-edge reads over the `open` outcome, reported
  separately from completed history — never counted as completed facts): **terminal
  resistance posture** (`R^`) — the window's last episode engages R and its final close sits
  above R: the pre-breakout stance the operator's marks end on; **terminal support drift** —
  an open S-side episode ≥ 3 bars at the window end: price lying on support with no verdict,
  the drift-junk tell.
- **The sentence** — the chronological profile string (`S+ S+ S+ R^`) — is the read's
  compact narrative form; an identity-UNFIXED verdict (merge horizon still open at the
  frame edge) carries a `~` suffix (`S+~`), so a sentence can never appear to contradict
  the as-of counts beside it (which rightly exclude it). Per-window counts (completed
  support tests, completed resistance rejections, alternations between completed episodes)
  are its summary statistics.

Causality follows the contract: a completed/failed verdict prints at the first close after
the episode (`describes` = the episode's bar span), but the episode's IDENTITY is only
irreversible once the merge horizon has printed clean — `knowable_bar` = the last bar of the
episode + `EPISODE_MAX_GAP_BARS` + 1; an episode still inside its merge horizon at the frame
edge is `in_progress`, and the as-of sentence counts only episodes with `knowable_bar ≤ D`.
An as-of read is taken on a frame that ENDS at D: because the terminal flags and the
profile are right-edge reads of the frame as printed, the stats layer REFUSES a sub-edge
as-of over a longer frame (a replay that wants "admission as of D" truncates the frame at
D — contract §1; the refusal is the tripwire). Like every reader layer, this is
**measure-only**: it moves no rail, gates nothing, scores nothing. Its two consumers (both
live in the code) are the story-rescue last-resort pool (a thin, separately named admission
predicate — the operator-ruled form, never baked into this reader) and the archived
sequence substrate.

**The stated geometric limit (2026-08-10) — and the zone-coverage companion.** The zones
are ATR-fixed while the boxes this screener elects are the market's tightest, so the two
yardsticks collide at the bottom of the width range: the S and R touch zones together
consume `2 × TOUCH_TOLERANCE_ATR` ATRs of box height, and on a box shorter than ~2 ATR the
neutral middle left between them is thinner than one average bar — price cannot stay out
of both zones long enough for the merge horizon to print clean, distinct tests fuse into
ONE unresolved visit, and the read prints all-zero counts on a chart that consolidated
cleanly (LEVI, the discovering case: a 1.45-ATR box read as one R episode spanning the
whole base; scan-wide, the sub-2-ATR cohort averages 2.57 completed events vs 4.72+
above — monotone in coverage). The read is therefore honest only WITH its geometry
companion: every substrate row carries **zone coverage** (`2·tol/(R−S)`, raw, unclamped,
NULL only when the read itself was refused), and the story-input law carries a fourth
state — **all-zero counts at coverage ≥ the unreadable floor read ABSENT, never zero**
(the NaN-bars leg's sibling; the display caveats the same rows in the same words). Nonzero
counts stay evidence at any coverage — a story loud enough to print through starved
geometry is real (FXNC: 5 completed at 0.66). Re-basing the zones themselves
(box-relative tolerance) is deliberately NOT done: the promotion counts and the ruled
admission form are pinned on these exact bases, so that change is a re-measurement — a
new archive seam plus a census re-run and re-pin — reserved for its own program if story
pricing ever needs it.

**The two named ruled forms of the story admission (2026-08-17, Power-Play species
program; renamed by operator ruling 2026-08-18 — the record says the BEHAVIOR it saw,
never an invented umbrella word).** The admission stays a thin predicate OUTSIDE this
reader, and it now carries TWO named forms, each an operator-ruled judgment with exactly
one implementation: the **S-test form** (the 2026-07-25 ruling: ≥ 2 completed support
tests + terminal resistance posture + no terminal support drift) and — dark, consulted
only inside the contraction rescue's re-walk since the species lane's deletion (build
step 12, Sat 19/09/2026) — the **resistance contraction** (the
Power-Play species; ruling `c029555`, theory in `minervini_oneil_canon.md` §2). A young
continuation base after an explosive leg contracts at or above resistance: its story is
the HOLD, not completed support tests — it is S-poor **by virtue**, so the S-test form
can structurally never read it. The form asks the same episode vocabulary the question
that fits the species: the floor never FAILED, the frame is not bleeding on the floor (no
terminal support drift), and the right edge is ENGAGED at the ceiling — an open
resistance episode (a terminal `R^` bar produces the same open episode, so the
post-breakout stance is covered by construction). The admission record names the behavior
it measured, derived from the terminal posture: **`contracting above resistance`** (the
last bar closes above the rail — the post-breakout stance) or **`contracting at
resistance`** (engaged at the rail's zone, close still below it), stamped
`<behavior> | <profile>` as the admitting sentence; the S-test form's record is
unchanged. The support-side sibling — price contracting ON support after a shakeout
recovery — is the LPS, which keeps its own name and its own detection path. The
contraction form is PROVISIONAL until the operator's species ruling sheets calibrate it;
the species' trend-side theory (the transition zone — trend end and base open as one
short zone) enters with the trend-state layer, not here.

**The bar-unit ceiling leg — the S-test form's posture judged by the bar,
sanctioned dark at the same scope (consolidation method, 2026-09-01).** The
S-test form's ceiling leg reads the CLOSE (terminal resistance posture: the
last close above the rail) — the one leg of the ruled form that violates the
operator's thrice-stated bar-as-unit doctrine ("the HIGH and the LOW Values
are the ones that matters most"). The measured fix — the right edge counts as
at the ceiling when the bar's HIGH engages the rail zone, close anywhere — is
sanctioned as a VERSIONED second form of the same admission, never an edit of
the close-basis leg (its promotion counts are pinned, and the wholesale basis
swap is Tested-DEAD). It is consulted only where the whole walk has already
refused everything — the contraction rescue's scope — so it can only add a
read where there was none: the banked A/B converts exactly EGBN and PKE on
their operator-ruled dates with the junk corpus silent, and the fleet drift
the wholesale swap would cause (the QTTB root-steal) is unreachable by
construction. Flip and the record-word signing are the operator's.

**The contraction rescue — the form's one sanctioned road into the paying read
(dark; miss program 2026-08-28).** The 2026-08-19 refusal of the global form flip
named its own successor: converting EGBN/PKE (both conversions operator-ruled
real) "needs its own program with a real A/B", because the global flip also
re-elected WCC into a 2.2×-wider box and moved pinned fire dates. That program's
answer is a SCOPE, not a threshold: the form is consulted only when the whole
walk has already refused everything — a second walk on full refusal, never after
a cause-before-effect abstention. At that scope a rescued fire can only ever ADD
a read where there was none; no existing election, framing, or fire date is
reachable. The admission stays the same thin ruled judgment outside the reader,
and a rescued fire records itself through the story pool with the
behavior-naming profile. Dark until the operator's flip (which re-seals the
must-fire ratchet for EGBN/PKE); the evidence record is
[miss_program_2026-08.md](miss_program_2026-08.md).

**The RULED story-pool admission form (operator ruling 2026-07-25 — Option A of the census
menu; THIS paragraph is the canonical spec the pool predicate must match, pinned by test):**
a candidate window is story-admissible when its as-of episode read shows **at least 2
completed support tests AND terminal resistance posture AND no terminal support drift**
(`story_admission` in `event_map.py` — the judgment beside the reader, never inside it).
Census evidence (fingerprint `b671e056…`, ruled at engine `ab5bf340…`; committed record:
[event_map_program_2026-07.md](event_map_program_2026-07.md); standing gate `python -m
tools.research.event_map_census --check` pins the fingerprint AND the headline): 22/33 marks
admitted at drawn rails with **zero live junk exposure** — every parsing junk sentence is
either pool-unreachable (ordinary election stands: KWR/NVT/GOOD) or traversal-killed
in-pool; RLGT, the one reachable junk case, is admitted by no form. **Accepted
ADMISSION-misses under the ruling** (part of the ruling, never recall regressions — "miss"
here means the FORM does not admit the mark, NOT the Guided-List must-fire sense; most of
these fire through ordinary election, where the last-resort pool is never consulted, so
non-admission costs them nothing): ALB, DLX, FOSL, MATX, NGL-2026-01, ORMP-2026-04, PKE,
RGR, SKYT, SYRE (S-poor profiles / respect-killed / universe classes).

> **Scope correction (measured 2026-07-27).** "The last-resort pool is never consulted"
> above is true **per root**, not per engine. `read_structure` walks root swings
> oldest-first and returns the FIRST root that completes, so a last-resort box on an
> EARLY root can end the walk before a later root's ordinary box is ever reached — the
> election moves even though no *window* preferred the last-resort candidate. Measured
> over the 332-setup payload: exactly **1 of 332** moves under the story pool (AMCX,
> strict→story). This is **pre-existing design shared with the rescued pool** (same
> per-root scope, not even flag-gated) and with `BAND_RAILS` (live since 2026-07-16 —
> CMPR band-elects this way *inside the payload* and passes the doctrine gate). **Do not
> "fix" it with a two-pass walk:** simulated over the 12 live last-resort elections, that
> reverses 2 of them — including CMPR's operator-accepted band election — so the
> "strict superset of recall" claim is false.

The measured in-pool
requirement: the traversal gate MUST keep running on story candidates (it kills 30 of the
69 junk occupancy deaths; the admission form is not asked to carry them alone). A re-ruling
of the form is a NEW seam (archive rule-version discipline) and re-runs the census, never a
silent predicate edit. **Executed fire-level A/B (Task 14, 2026-07-25):** pool ON converts
**26→28/33** — NKTR@2026-04-09 and YPF@2026-05-06 elect via the story pool, their admitting
sentences riding `story_admission_profile`; the negative bench stays clean and all 26
existing hit elections are per-identity byte-identical. **EGBN itself does NOT convert** —
the honest headline: its framing is never PROPOSED at a story-passing shape (rail
PLACEMENT, upstream of any pool), so the flagship is admission-certain at drawn rails and
conversion-blocked at proposal. **LIVE since 2026-07-26:** the operator's per-fire chart
eyeball of both conversions passed (rails confirmed correct on both; YPF ruled
early-but-right — post-window breakout → LPS 05-12..05-15 → true breakout; NKTR's pre-base
gap ruled irrelevant to the box's traits), and the ratchet was deliberately resealed
**26→28/33** with the two story-caused hits pinned by name as the only legally
flag-off-silent identities (`test_story_pool_guards`). The flip rotated
`engine_config_version` → `53c208dc…` (the story pool's archive seam; fires archive
`elected_pool='story'` + `story_admission_profile` from that seam forward). Evidence:
[event_map_program_2026-07.md](event_map_program_2026-07.md) §flip.

### The Root-Swing cascade (the linear narrative)

The reader walks the chart left to right and anchors by descent:

1. **Find where the trend ends** — the true BC & AR (or SC & AR). This is **Phase A**.
2. **Seed R and S from that pair** and test the framing: does price actually *work* both
   rails — touch, respect, and zigzag between them constantly, with no dead space?
3. **If there is dead space, advance to the next pair of limbs.** Keep descending pair by
   pair until you reach the pair that is *responsible for the earliest actual worked
   consolidation*.
4. **That pair is the Root Swing**, and the consolidation it births is **Phase B**. Often
   the Root Swing *is* the BC/AR; after a one-way climax leg it is a later, smaller pair.
   (Worked example — AGCO 2026: BC 02-12 @143.11 → AR 03-20 @107.44 is the true Phase-A
   read, but rails at those extremes leave permanent dead space; the cascade settles on
   the 04-02 low 111.30 → 04-10 rebound 123.32 pair — 12 R-touches / 21 S-touches and
   8 full rail-to-rail traversals by the engine's own measure.)

   > **Known divergence — box-start pinning (RESOLVED: lever built 2026-07-02, flipped
   > LIVE 2026-07-03 after operator eyeball).** On the same AGCO base the operator reads the
   > earlier **03-25 → 03-30 pair** (H 119.24 → L 111.83) as the Root Swing. Dissection
   > agreed with the *start* while keeping the engine's rails: the ELECTED rails
   > (123.32/111.30) are **fully valid by every engine gate from 03-25** — but that
   > framing is *unproposable*, because candidate starts are pinned to the anchor pair
   > (`cand_start = min(r_anchor, s_anchor)`); the earliest-valid election cannot reach
   > an earlier start its own gates would bless. The census confirmed this is systemic
   > (as-traded re-run: 94% of fires extend under raw band-conformance, median +5 bars)
   > but the pre-cutover adjusted-price run also showed raw conformance is too loose
   > (WDI +80 swallowed its descent leg; BYD +26 was mid-band chop). **The built lever
   > = shared-rail back-extension** (`box_primitives.backext_shared_rail`, unconditional
   > since the 2026-07-18 fold; flipped live 2026-07-03): after election the start walks left to the
   > earliest zigzag pivot that re-touches an elected rail within touch tolerance
   > (peak≈R / valley≈S), with every intervening bar inside the buffered band. The
   > rail re-touch requirement is the drift filter: AGCO extends onto the 03-30
   > S-touching valley (3 bars shy of the proven 03-25 validity — the 03-25 peak never
   > re-touches R); on as-traded data WDI no longer fires at all, and BYD's extension
   > *survives* (44→41 bars) because a genuine S re-touch anchors it — the lever keeps
   > worked cause, it does not veto wide boxes. A/B over the live universe: 42/140
   > fire starts move (median 6 bars, max 49), **0 fires gained/lost, 0 re-storied**.
   > Rails, gate verdicts and the election are untouched — but every read anchored to
   > the box start re-measures over the extended span: the base-window suite (base-age,
   > traversal quality, contractions, support slope, dwell, touch-volume, bar
   > compression), the spring / inner-box / LPS windows, bin evidence, and the
   > (live, bonus-only) event-story read. Applied post-election in BOTH the live reader
   > (`bricks.validate_equilibrium`) and the diagnostic mirror (`phase_b_zigzag` →
   > `detect_boxes`), so every path frames the same box. The operator eyeballed the
   > A/B renders (`research/fidelity/box_backext/`, `tools/box_backext_ab.py` — tool
   > retired 2026-07-18, 44f8293) and the
   > flag went LIVE 2026-07-03; the shadow baseline was re-captured at the flip; a
   > seeded backtest over cherry-picked setups remains the planned deeper validation.
   > The trace annotates the elected pair with
   > `backext_bars`. Secondary lever (the operator's shelf-R read —
   > R at the touch-cluster mode with April pushes as tolerated overshoot): parked
   > separately; the respect gate kills shelf-R framings on 16 above-R bars, and that
   > band is also the upthrust defense.
5. **Decide the right side — are we past the tip of the final 'V'?** A box alone is not a
   setup; the reader must see evidence the base has turned:
   - a **Phase C spring** that *conducts* the turn (undercut below S → reclaim → hold), OR
   - direct **Phase D evidence**: an SOS, a mini-consolidation (inner box), rising
     support / a support-test cluster.

   Either way the **LPS is the mandatory terminal evidence** — no LPS in the right-most
   region means no Phase D and no setup.

### The chain grammar — stories with sequels (ruled 2026-08-23; program open, engine reads DARK)

The linear cascade above tells ONE story and refuses whatever its box cannot contain. The
operator's 2026-08-23 rulings extend the model: **a chart may be a chain of structures**, and
the read does not end when a structure resolves. A resolution — breakout above R, shakeout
below S — is a **displacement**, and after any displacement the reader's next job is always
the same:

1. **Freeze the parent.** The resolved structure's identity — rails, start, resolution day —
   is captured at that moment and never re-framed by later bars. (Re-electing the parent on
   the longer chart is the WCC defect: a wider frame elected a 2.2×-wider box.)
2. **Read the re-stabilization.** After a shakeout: did it recover at all — in one sharp
   swing, staircase-like with a couple of tests, or by building a new base altogether — and
   where did it land: back inside the old range, sitting a little below, or stuck at the
   bottom? After a breakout: did price run, then pause into a new smaller consolidation above
   the old ceiling?
3. **Hunt the contraction family** — SOS, LPS, contracting lower pullbacks,
   mini-consolidation — positioned against the PARENT's levels. Every piece of a chain must
   individually satisfy the same tightness laws as ever; what a chain relaxes is only the
   demand that one box hold the whole story. Chains never loosen floors (occupancy
   relaxation is Tested-DEAD).

Two ruled chains open the grammar:

- **Base on base** (the operator: a "mini consolidation that appeared after the bigger one
  broke out"): a separated young base above a resolved box. Standalone it has no trend-end
  and no cause of its own; in the chain it inherits the parent's cause through the breakout.
- **After-shakeout recovery** (the operator: "a violent shake out maybe the spring and its
  our key to mapping out the Phase C of that Setup. what happens next though is what's truly
  important"): the shakeout's DEPTH never disqualifies it — it may be the spring; what forms
  afterwards adjudicates. The terminal contracting pullback is the LPS — and it may legally
  sit BELOW the old floor while above the shakeout's low: the **tactical long**, paying if
  price recovers into the base and later breaches it. A **Last Supper** is the operator's
  BU: a deep, fast seller reaction to a preceding up move — the SOS, the push off an LPS,
  the breakout itself — "the last trap before buyers take over and the long continues"
  (ruling 2026-08-28; the corpus's 10 drawn specimens all follow an SOS, but that is
  sample fact, not definition). It is a normal chapter of a *winning* chain, descriptive
  and never a warning (ruling 2026-08-26; Corpus Study 2026-08-28: all 10 drawn specimens
  preceded +17% to +134%). The same what-forms-afterwards test adjudicates it: a rest at
  a defended level — the conquered rail, or the tactical long's higher-low above the
  shakeout — continues the chain; a giveback after which no constructive rest ever forms
  is the failure branch, and only that branch is a defect.

The mini-consolidation unification rides the same rulings: the inner mini-consolidation and
the tightening shelf at the ceiling are **one event, one mechanism** — "no need to give it a
new name, just acknowledge its position" — with position a graded attribute (at the top =
slightly higher quality). Its right-side power is VCP logic: tighter, smaller, less bar
spread, developing later in the consolidation ("over time = right side").

Setups carry a **type**: the same trait family everywhere, graded per type, with traits a
type declares absent costing nothing. A grade is comparable only WITHIN its type. (Per-row
"normalize by what's present" stays Tested-DEAD; a type's trait set is declared, never
derived from the row.)

*Status: theory ruled; the engine does not read chains yet. The program runs dark,
measure-first — [story_chain_program_2026-08.md](story_chain_program_2026-08.md) is the
program record.*

### The explainability rule

**The engine is never allowed to be blind to *why* it chose the pair it chose.**
`read_structure(df, atr, trace=[...])` narrates the whole walk: every root swing tried,
every candidate pair inside the box election with the stage that rejected it (`width` /
`window` / `respect` / `occupancy` — with the failing checks named, e.g. "dead space low" /
`traversal` / `rescue_unused`) and why the winner was elected (`selection`,
earliest-of-valid). `python -m tools.audits.structure_case_audit <TICKER> --trace` renders it.
The trace is opt-in and free on the live path (`trace=None` = zero cost, byte-identical).
New reading logic must **extend the trace, not bypass it** — the narrated process is what
lets richer story-building (the event story, graded confidence reads) trust the geometry.

**The gate legs speak from one registry (near-miss lane Task 1, 2026-07-26).** The
validity judgment's fifteen legs — width, window, the respect share/run pair, crash, the
eight-check occupancy family, the traversal count/density pair — have ONE machine-readable
home, `box_gates.GATE_LEGS`: each leg's identifier, the statistic it reads, its settings
binding (resolved lazily at call time), its native quantum (fraction / bars / touches /
thirds / traversals / ratio), and its exact comparison form. A gate rejection record now
carries structured `legs` — leg id + measured statistic + threshold as NUMBERS — with the
prose `detail` derived from the same values, so a downstream instrument (census, near-miss
telemetry) reads the numbers and never re-parses a sentence. A `measured` of `None` is a
declared kill-site unknown (crash's min-low ratio, respect's run maximum): the cascade
short-circuits, so those numbers are only knowable to a post-hoc completion read, never to
the refusal record itself.

**The trace speaks event language.** Every trace label, reject reason, and diagnostic
names its chart event in the catalog's vocabulary — plain chart language where humans
read, frozen keys on the wire. The catalog's third law binds here too: **a new signal
declares its event** before it ships — it enters the catalog under its event,
measure-first, as graded confidence. No event, no signal.

**And in a phrase he reads, the unit beside a number is his own word: trading days — never
"bars", never "sessions".** This binds wherever a refusal is RENDERED for him, which now
includes the refusal named at his OWN drawn rails: the same fifteen legs judged on the
framing he drew, the single blocking one spoken in that vocabulary, and the episode
history stated in plain words ("two completed tests at resistance") rather than as the
internal profile tape. Machine notation stays machine-side; a surface he reads carries
only language he uses. The scope is the rendered phrase, and saying so is not a hedge — the
engine still keys some measurements internally in units nobody displays, and a sweep that
read this rule as covering those keys would be changing what is measured, not what is said.
Renaming a measurement is a re-measurement with its own seam; renaming a phrase is free.
