# Minervini & O'Neil as Chrollo uses them — the concordance

**What this file is.** The sibling of [`wyckoff_canon.md`](wyckoff_canon.md), for the growth-stock
canon: which Minervini and O'Neil ideas Chrollo took, which it adapted, which it deliberately
left, and which of their words it reuses with a different meaning. It exists so an agent
reasoning from *Trade Like a Stock Market Wizard* or *How to Make Money in Stocks* does not
"fix" the engine toward textbook fidelity the operator does not want — and so the Power-Play
species program (`docs/power_play_program_2026-08.md`) has its vocabulary settled in one place.

**Read it before** proposing, justifying, or reviewing any change whose argument contains
*"Minervini says…"*, *"CANSLIM requires…"*, or *"the book's criteria are…"*.

Established 2026-08-17 from the verified literature sweep (criteria cross-checked against
book-quoting sources and measured against the cache), under the operator's rulings of
2026-08-14: **"Power Plays are wanted setups"** (`decisions.md`, commit `c029555`) and **"I want
to incorporate more of William O'Neil's work too into our engine as principle, same with
Minervini."**

---

## 0. The framing ruling — read this first

The Wyckoff framing transfers verbatim: **these books are a source of ideas, not a
specification.** Chrollo's prime directive stays *accurate detection of visually tight
structure*; Minervini and O'Neil enter as **principles** — named, measured, graded — never as a
checklist the engine must replicate. Three consequences:

1. **Textbook fidelity is not a success criterion.** The criterion is whether a read finds
   high-quality setups. "The book has this and we don't" is not a defect (the exact
   `wyckoff_canon.md` §0 rule).
2. **Geometry first.** Both authors lean heavily on fundamentals and volume; Chrollo's veto layer
   stays geometric. Their non-geometric ideas enter measure-first: archived, never-gating,
   graded only after an edge read (the standing measure-first law).
3. **The operator's own style is the tiebreaker.** He trades Minervini-VCP + Qullamaggie
   breakouts discretionarily; where the books disagree with each other (or with modern
   practice), his read governs, recorded as a ruling.

---

## 1. Sources of record

| Source | Standing |
|---|---|
| Minervini, *Trade Like a Stock Market Wizard* (2013) | The Power-Play/SEPA source. Criteria verified 2026-08-17 via near-verbatim book-quoting notes (rgarg333 MinerBook2; whatheheckaboom review carries the "dearth of fundamentals" passage) |
| O'Neil, *How to Make Money in Stocks* | The HTF + CANSLIM source. HTF passage verified against a scanned book page; IBD articles carry the house rules (buy point +$0.10, breakout volume ≥40% above average) |
| Bulkowski, thepatternsite.com (`htf.html`, `HTFStudy.html`) | The measured-statistics source — cite BOTH eras (§2), never the early billing alone |
| qullamaggie.com, "My 3 timeless setups" | The modern-practice source (the operator's style); the broad continuation-base numbers |

None is a target to reproduce.

---

## 2. The Power Play / High Tight Flag — the species

**One pattern, two names.** Minervini's **Power Play** is O'Neil's **High Tight Flag**
(Minervini's own coinage is "velocity pattern"). **Chrollo's name for the species is Power
Play** — the operator adopted it 2026-08-14, and it is Minervini's real term
(naming-doctrine-safe). "High tight flag" is acceptable in prose as the O'Neil synonym. The
structure INSIDE the pattern keeps Chrollo's Wyckoff vocabulary: the pause after the climax leg
is named by the BEHAVIOR measured — **contracting above resistance** (post-breakout stance) or
**contracting at resistance** (pressing from below) — never "Mini-BC" (retired per
`wyckoff_canon.md` §5) and never "holding shelf" (retired by operator naming ruling
2026-08-18, `decisions.md`: the behavior already has a name — say it).

**The verified book criteria:**

| Criterion | Minervini | O'Neil / IBD | Bulkowski (measured) |
|---|---|---|---|
| Prior advance (the pole) | ≥100% within 8 weeks, huge volume, from a quiet Stage 1 — late-stage bases usually disqualify | 100–120% in 4–8 weeks | ≥90% in ≤2 months |
| Flag depth | ≤20% (low-priced stocks up to 25%) | 10–25% (some IBD articles 10–20%) | winners retrace 10–34% of the pole |
| Flag length | 3–6 weeks; **"some can emerge after only 10 or 12 days"** | 3–5 weeks | winners are 10–29 **calendar** days (~7–20 trading bars) |
| Tightness | VCP required **unless** total correction ≤10% ("already tight enough") | volume dries up in the flag | "trade tight flags, not loose ones" |
| Fundamentals | **his ONLY dearth-of-fundamentals entry** — the velocity IS the institutional signal | n/a in the passage | n/a |
| Rarity | "rare bird" | "one or two in a bull market" | 2,588 in 552/1,018 stocks over 14.5 years |

**Bulkowski's two eras — cite both, never the first alone.** Early Encyclopedia billing:
best-performing pattern, 69% average rise, 0% break-even failure (253 bull-market HTFs). His own
2009 restudy (2,588 patterns): **27% average post-breakout gain, 33% combined failure, only 6%
double**; current site: rank 30/39, 39% average rise, 15% break-even failure, 67% throwback.
The lesson is the census's law too: small flattering samples do not survive scale — Chrollo
measures its own forward returns and trusts nobody's billing.

**The two-tier taxonomy (measured on our own cache, as-of 2026-08-13):**

- **Tier 1 — the strict textbook species:** pole-qualified AND shallow AND short. Of the six
  specimens measured, only **MAN** qualifies (best-40-bar pole +111.9%, correction 12.2%, shelf
  20 bars) — and it is exactly the one the engine missed.
- **Tier 2 — the broad continuation base** (Qullamaggie's flag: 30–100%+ move in the past 1–3
  months, orderly tight pause, higher lows, no hard depth cap): FTNT (+123.9% over 13 weeks,
  40-bar pole only +40.9%), HELE, AVTX — all of which the engine already fires. The strict HTF
  is the extreme tail of this distribution.

**The clock collision** (why the species program exists): the textbook flag's duration
(~7–20 trading bars for Bulkowski winners; Minervini's floor 10–12 days) sits almost entirely
inside the engine's 25-bar effective reading clock (`MIN_BASE_DAYS` 20 +
`STRUCTURE_EDGE_SKIP_BARS` 5). The clock does not occasionally miss the species — it excludes
it by construction. The remedy is the declared species preset
(`docs/power_play_program_2026-08.md`, Task 1), never a global loosening.

**MRVL/ARM are not counter-examples.** Their poles qualify (+124.6% / +135.6%) but their −50%
corrections are double the book maximum — by the literature the original flag FAILED, and their
play is the next base. Note the books agree with our universe gate here: Minervini's own trend
template requires price above the 50-day (criterion 5 below), so a −50% mid-correction name is
out of the population for him too. The sma50 wall is not anti-Minervini; it is his own floor.

---

## 3. What Chrollo took, adapted, and deliberately left

| Canonical idea | Chrollo | Status |
|---|---|---|
| **Stage-2 trend template** (Minervini/Weinstein) | `indicators.trend_template` — the 7 price/MA criteria, measure-only; HTF twin `htf.htf_stage2` (Weinstein MA-30). Criterion 8 (RS rating ≥70) deliberately omitted from the pass count; the count is shown on the card's leadership read since 2026-10-02 | **TAKEN** (measure-only; two labeled forms by design) |
| **VCP — volatility contraction** | The engine's whole tightness family: `MAX_BOX_WIDTH`, contraction sequence scoring (`SCORE_CONTRACTION`, `CONTRACTION_IDEAL_*`), ADR-aware tightness (`TIGHTNESS_ADR_AWARE`), candle-spread grade, `atr_squeeze` | **TAKEN** — as geometry, Chrollo's own measures; never the book's %-retrace arithmetic |
| **VCP volume nuance** (each pullback lighter, final coil quietest) | `metrics._vol_trend_from_contractions` — bonus-only | **TAKEN** (measure, never a gate — wyckoff §0.3) |
| **Power Play / High Tight Flag** | The species program: preset clock + pole qualifier + the resistance-contraction story form, all dark | **ENTERING** (this program; §2) |
| **Stage analysis** (Weinstein/Minervini: the four stages, read on the weekly chart) | `engine_alpha/stock.py`, `read_stage` (2026-10-16): the stage from the 40-week average's slope and the 52-week low on completed weekly bars, and the week the stage-2 advance began (the start of the base-count rule written from his counts, 12/10/2026); shown in the detail panel, archived on every fire of the live reader | **ADAPTED** — measure-only, never a gate; the book's real-time checks, so a top reads 3 only once the average stops rising (Vicor's and Chipotle's tops read 2) |
| **Base counting** (bases 1–4; later bases fail more) | `market_structure.measure_trend_bases` — count within the covering confirmed up-segment, saturating at `TREND_BASE_COUNT_CAP`, + inter-base width ratio | **ADAPTED** — counted inside ONE confirmed up-segment, not across a lifetime; measure-only |
| **Buy near the 52-week high** (O'Neil) | `SCORE_52W_HIGH_PROXIMITY` ramp | **TAKEN** (graded, never a floor) |
| **RS line at new highs** (O'Neil/IBD) | `core/regime/rs_line.py` (`RS_LINE_ENABLED`, dark; `rs_line_new_high`) | **TAKEN, dark** — flip is an operator decision after an edge read |
| **RS rating** (IBD universe percentile) | `rs_rating` — in-house percentile of twelve-month strength (four quarters, the latest counted double, IBD-style) over every stock the scan reads with a year of history at or above `MIN_PRICE`; LIVE since 2026-10-02, no flag, shown 1–99 on the card and archived | **ADAPTED** — our own universe, our own formula; never IBD's number. Display only: scoring RS is the Tested-DEAD row (§6) |
| **CANSLIM C/A** (quarterly earnings + acceleration) | `core/fundamentals/metrics.py`: `eps_growth_yoy`, `sales_growth_yoy`, `eps_growth_accel`, `earnings_surprise` (`FUNDAMENTALS_ENABLED`, live 2026-10-03, display and archive only); since 2026-10-12 the fundamentals sheet (`core/fundamentals/sheet.py`: four reports, four quarters, margins, beats, revisions, earnings quality) and the fundamental grade (`grade.py`, nine checks, A-D) | **ADAPTED, live** — measures and a display grade, never gates or scores the setup; annual (A) reduced to the last four quarters + acceleration; the 25% floors are canon defaults, recalibrated later |
| **CANSLIM L** (leader vs laggard) | `rs_rating` (live, display) + the leadership read (`core.regime.leadership`, live 2026-10-26, shown on the Watchlist until 2026-10-28, when its table became the operator's list; written by every scan, shown nowhere now): groups and sectors ranked by the median RS of their stocks, the top quarter leading, and each stock's place in its group (#1 = Minervini's market leader, the next places his top competitors); the SPDR-ETF sector ranking (`SECTOR_RANKING_ENABLED`) stays dark | **ADAPTED** — the RS half and the group/sector half shown, never scored or gated |
| **Six kinds of company** (Minervini: market leaders, top competitors, institutional favourites, turnarounds, cyclicals, past leaders and laggards; the money is made on the market leader) | the leader's chart half = `rs_rating`; its business half = the fundamental grade, whose label names the kind of GROWTH (accelerating, strong, turnaround, mixed), not the six kinds | **ADAPTED in part** — no kind is named; the leader's "first into new high ground after the market's low" measured 2026-10-17 = the RS rating by another name (decisions Nulls row); the book's 20% leader floor beside the grade's 25% |
| **Valuation and expectations** (Minervini: a leader in its fast growth always looks expensive and is cheap for its growth; a fast grower lives by beating the estimates, each beat raising the bar until a miss) | no valuation read anywhere; the fundamental grade's beats check (3 of the last 4, the latest included) and estimate revisions, display only | **LEFT** (valuation, in step with the book; his ruling 2026-10-17: *"correct no need"*); the beats **TAKEN as display** and measured 2026-10-17 to separate nothing in the 60-day tail, nor the growth's level; the growth speeding up on an RS 80+ stock does (decisions Nulls row) |
| **CANSLIM M** (market direction) | O'Neil **distribution days** on the index (`regime_distribution_days`, `REGIME_DISTRIBUTION_DAY_*`) + the market/sector health board | **ADAPTED — context only, NEVER a gate** (regime is observability; see wyckoff_canon §5 "distribution") |
| **Code 33** (Minervini: EPS, sales and margins accelerating three quarters) | `core/fundamentals/grade.py` `code33` (2026-10-12): EPS growth, sales growth and the net margin each rising three quarters running, every figure known | **ADAPTED, strict** — a display badge, never awarded on missing history or two good quarters |
| **CANSLIM N** (new products/management) | the catalyst's PROOF only, in the fundamentals sheet (2026-10-12): sales speeding up, estimates rising, the report-day reaction (daily ranges on 50-day volume) | **ADAPTED as proof** — the story itself is qualitative and stays his read |
| **CANSLIM S** (supply/float) | — | **DROPPED** |
| **CANSLIM I** (institutional sponsorship) | the volume footprint on the chart is the only proxy | **DROPPED** as data — no holdings source |
| **Follow-through day** (O'Neil) | — | **DROPPED** — the health board's 7-state cycle is Chrollo's own market read |
| **Cup-with-handle / saucer / double-bottom taxonomy** | — | **DROPPED** — Chrollo reads emergent Wyckoff boxes, not named pattern templates |
| **Entry mechanics** (pivot +$0.10, 40%-volume breakout, cheat entries, stops) | — | **DROPPED** — Chrollo generates ideas and keeps books; the operator trades by hand |
| **Fundamentals as GATE** (O'Neil: EPS growth ≥25% required) | measure-first law: archived, graded later, never gating | **REFUSED as a gate, taken as a measure** — and the Power Play is Minervini's own exception: the species must NEVER be blocked on absent fundamentals |

---

## 4. False friends — words that will mislead you

| Word | The books | Chrollo | The trap |
|---|---|---|---|
| **Power Play** | Minervini: strictly the ≥100%-in-8-weeks velocity pattern | the species program's name for the wanted young continuation base; the census + operator rulings decide how far below the book pole the boundary sits | assuming Chrollo's species preset must enforce the book's exact 100% — the boundary is RULED from sheets, not transcribed |
| **correction** (flag depth) | peak-to-low % from the flagpole top | `box_width` = (R−S)/S between ELECTED rails — a different measure on different anchors | "the book allows 25%, our MAX_BOX_WIDTH is 0.18, loosen it" — the two numbers are not comparable; MAN's 12.2% depth elected a much tighter box |
| **base count** | lifetime count across a stock's whole advance | `trend_base_count` counts inside the covering confirmed up-segment only, saturating at the cap | reading `trend_base_count=1` as "first base ever" — it means first in THIS segment; measured 2026-10-03 it is 1 on 8,804 of 8,804 archived fires (the segment is weeks long), so it carries no information yet |
| **RS rating** | IBD's 1–99 universe percentile | in-house percentile over Chrollo's scanned universe (archived 0–100, shown 1–99) | quoting IBD thresholds ("RS ≥ 70") against our column — different universe, different scale |
| **relative strength** | O'Neil: vs the whole market, ranked | `SCORE_RS_BONUS` was SPY-relative excess return — **demoted to 0 on evidence** (n=1977, corr −0.22) | "the books demand RS, restore the bonus" — see Tested-DEAD below |
| **distribution days** | O'Neil: index down-days on higher volume | exactly that, on the INDEX, as regime observability | wiring it into a per-stock read (the wyckoff_canon §5 trap, restated here) |
| **tight** | Minervini: weekly closes in a narrow range | Chrollo: box width, ADR-aware tightness, candle-spread grade — daily, elected-rail-relative | porting weekly-close arithmetic into the daily reader |
| **high tight flag** | the pattern name | acceptable prose synonym for the species; the in-box structure is **price contracting at/above resistance after the climax leg** | inventing HTF-specific structure vocabulary — the Wyckoff names stay |

---

## 5. The point-in-time law (the McKinney rule — binding)

**Current-snapshot fundamentals never join a historical replay.** yfinance serves the CURRENT
revision of every income-statement line: restated, amended, re-split — not what a trader could
read on the historical date. The filing-lag gate (`FUNDAMENTALS_FILING_LAG_DAYS = 75`,
`core/fundamentals/metrics.py`) disciplines **WHICH quarter** was knowable at `as_of`; it cannot
discipline **WHOSE REVISION** of that quarter is served. Therefore:

- Fundamentals attach only to **live, forward archives** (the scan's own `as_of`, explicitly
  passed — the `as_of=None` fail-open path never feeds an archived write; see
  `power_play_program_2026-08.md` Task 12).
- **The SEC fill is the first as-reported source (2026-10-12, on: his email is the contact):**
  `core/fundamentals/sec.py` takes each quarter's sales as FIRST filed on or before the day. It
  covers US filers' sales only; every yfinance line still falls under the law below.
- **Any fundamentals backtest against historical dates is BLOCKED** until a genuine
  point-in-time source (as-reported filings) exists. A "backtest the O'Neil layer against the
  archive" proposal is lookahead by construction — the data is fiction regardless of the lag
  gate. The honest corpus is built forward, scan by scan, measure-first.

---

## 6. Do not propose these — already tested or ruled

| Tempting move | Why it is wrong here |
|---|---|
| Restore `SCORE_RS_BONUS` / `SCORE_UPTREND_BONUS` because "the books demand RS/trend" | Demoted to 0 on evidence (corr −0.22 / −0.19, n=1977) — the wyckoff_canon Tested-DEAD row, restated because these two are the most book-endorsed terms in the engine |
| Score the HTF context because "M matters" | The HTF edge verdict was DON'T score (measure-only stands) |
| Gate the species on fundamentals | Inverts Minervini's own dearth-of-fundamentals exception AND the measure-first law |
| Enforce the book's 100%-pole / 25%-depth as hard species gates at add time | The boundary is ruled from the census sheets (the FTNT/MAN evidence says the wanted species is broader than the strict book tier); constants enter dark, thresholds only after rulings |
| Bump the yfinance pin to get better fundamentals surfaces | AP-4: the pin is a supply-chain + byte-parity control; if Yahoo's endpoints die, the answer is the parked provider swap |
| Loosen `MAX_BOX_WIDTH` toward the 25% book depth | Wrong units (§4 "correction") and a junk-defence relaxation |

---

## 7. Open questions for the operator

1. **MRVL/ARM marking guidance:** when they build their NEXT base (post −50% correction), do they
   enter the species corpus as ordinary continuation bases, or carry a "failed prior flag"
   annotation? (The books say the prior flag failed; the census can carry either.)
2. **The species boundary:** tier 1 only (strict pole ≥~90–100%) or the broad tier-2 species the
   engine already reads at maturity? The census sheets (program Tasks 3–4) are built to put this
   exact fork in front of you with evidence.

**Handled by design — and since DONE:** the species' theory (the resistance contraction as a
positive concept, the transition-zone note) entered `strategy_alpha.md` **in the same
change as the behavior that implements it** (program Task 6 landed the "two named ruled
forms" paragraph in the rail-episode read, 2026-08-17), per the reading rule — theory
and engine move together, so this concordance carries no strategy_alpha delta of its own.
