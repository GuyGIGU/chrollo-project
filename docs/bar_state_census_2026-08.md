# Bar-state census — 2026-08-30

The dig the operator asked for on **symmetry**: *"I think I lean towards Symmetric? but if data
suggest other wise then.... IDK man we got to dig deeper on that."* It builds the harsher-above
rule BOTH ways and counts whom it flags — his own 35 drawn boxes, or the 98 junk framings.

This file is the **committed evidence record** (EC-16) behind the two 2026-08-30 rail-area rows in
[decisions.md](decisions.md) — *"THE RAIL AREA IS RULED: ±0.50 ATR, symmetric, both rails"* and the
three-ceiling-states row that commissioned the census. Those rows originally cited
`BARSTATES.md` / `BARSTATE-VERDICT.md` in a session scratchpad, which no fresh clone can read; the
instrument `tools/bar_state_census.py` and this record replace that pointer. The sidecar of the
reproducing run is `research/evidence/bar_state_census_2026-08-30.json`.

**Measure-first discipline: no gate, no threshold and no knob is proposed anywhere in this file.**
The 2026-08-29 guard-rail stands — a 0.5-ATR allowance is *position vocabulary only*; as a
gate/veto/rescue/junk filter it is Tested-DEAD twice.

## Population stamp

- **drawn** — every operator `CalibrationMark(verdict='box')` on HIS rails over HIS window
  (`tools.replay.drawn_box_window`, the shared EC-13 derivation, through
  `tools.calibration_harness.load_box_marks`): **35/35 measurable, 1,492 bars**,
  `marks_fingerprint 92d6a529c1ad4dc7…`.
- **junk-survived** — every negative-corpus strict candidate framing that got PAST the
  boundary-respect gate (not rescued; cascade stage not in width/window/respect), judged on
  `tools.replay.judged_window`: **98/98 framings, 2,949 bars** from 18 corpus tickers
  (stages: occupancy 69 · selection 15 · traversal 7 · passed 7).
- **engine_config_version at reproduction:** `08c981629923c30e…` (the sealed run stamped
  `0ac88199221d77be…` — see *Divergences*).
- Unit = ATR (the 2026-08-30 ruled unit); tolerance = `TOUCH_TOLERANCE_ATR` = 0.5 ATR.

## The frozen definitions

The definitions ARE the evidence; the instrument's REPRODUCIBILITY NOTE freezes each one.

**State machine** (per bar, per rail — the operator's three states plus "away"):

| state | R rail (ceiling) | S rail (floor) |
|---|---|---|
| `resting` | `low >= R` — whole bar beyond the rail | `high <= S` |
| `semi` | `high > R > low` — straddles the line | `low < S < high` |
| `at_rail` | `R - 0.5*ATR <= high <= R` — touches from inside | `S <= low <= S + 0.5*ATR` |
| `away` | otherwise | otherwise |

`resting` and `semi` are tolerance-FREE (whole-bar-beyond and straddle are exact); only `at_rail`
consumes the tolerance. ONE frame-level ATR per box.

**Census-local conventions** (none of them an engine artifact):

- a **run** = contiguous bars in any non-`away` state; `singular` = 1 bar, `short` = 2, `dwell` ≥ 3;
  its **dominant** state is the most frequent, ties resolving resting > semi > at_rail.
- **what-follows** is anchored at the run's EXTREME breach bar, never the run END (a run only ends
  when a bar goes away, which would force the answer). First close beyond ±0.5 ATR of the rail wins
  over the next 10 bars: R — `left_up`, or back inside sub-classified by whether any close in the
  horizon falls below the box MIDPOINT (`crash_back_through_box`) or not (`resumed_consolidation`,
  his "the consolidation continues normally" case); neither → `consolidating_near_rail`; too few
  printed bars → `right_edge`. S mirrored: `broke_down` / `reclaimed_into_box` /
  `held_near_support`.
- the **seller's tail** = a breach bar of spread ≥ 1.5 ATR (2.0 as the secondary cut) whose close
  crashes back below `R - 0.5*ATR` within 5 bars.
- **"mostly above/below"** = the bar MIDPOINT `(High+Low)/2` against the rail — a harshness variant
  of the census, not an engine reading.
- the **"bigger swing upwards" exclusion** uses the engine's own R-rail wave typing
  (`measure_resistance_events`): a resting run is a departure leg if any of its resting bars sits
  inside a typed `markup` zone. The second variant widens the mask to `in_progress` too.
- the junk enumeration dedupes framings by `(R, S, cand_start, stage)` and requires a ≥ 3-bar judged
  window; the sibling censuses key theirs slightly differently, so the 98-framing denominator is
  THIS convention's.

## Reproduction check — every cited number, sealed vs re-run

Run 2026-08-31 on `tools/bar_state_census.py`, against the sealed scratchpad report:

| cited number | sealed | reproduced |
|---|---|---|
| any whole-bar-above outside markup (≥1 bar/box) | drawn 17/35 · junk 26/98 | **identical** |
| mostly-above outside markup | drawn 27/35 · junk 41/98 | **identical** |
| the parity variant (+ in_progress excluded) | drawn 5/35 (14%) · junk 14/98 (14%) | **identical** |
| below-S mirror (whole-bar-below) | drawn 18/35 · junk 14/98 | **identical** |
| mostly-below | drawn 25/35 · junk 30/98 | **identical** |
| resting-dominant breach runs, drawn R | 8 left_up · 3 right_edge · 0 crash-back | **identical** |
| semi-dominant crash-backs, drawn R | 28 of 48 | **identical** |
| drawn S breach runs reclaimed | 79 of 89 | **identical** |
| markup exclusion is partial | 6/26 markup-typed; 16 of the 20 true rests overlap `in_progress` | **identical** |
| singular-semi (his forgiveness case) | drawn 4/35 R · 6/35 S; junk 20/98 R · 32/98 S | **identical** |
| seller's tail ≥1.5 ATR with crash-back | drawn 26 bars across 17/35 (1.7%) · junk 35 across 18/98 (1.2%) | **identical** |
| ceiling engagement, resting bars | drawn 8.8% · junk 2.4% | **identical** |
| bars away from the rail | drawn R 47.3% / S 46.8% · junk R 69.3% / S 76.3% | **identical** |
| sanity anchors | MSGS 10-bar rest (reach 1.1838 ATR), NOK 8-bar (1.6451), DSGN/MATX MARKUP | **identical** |

**Every headline the rulings cite reproduces exactly**, to the printed decimal, including the run
tallies, the wave-type cross-tabs, the reach distributions and the tail-carrying box lists.

## The census

Below is the reproducing run's report, unedited.

### 1. State frequencies — DRAWN

**R rail** — bars: resting 132 (8.8%), semi 311 (20.8%), at_rail 343 (23.0%), away 706 (47.3%)
  boxes containing state ≥1x: resting 22/35 (63%), semi 34/35 (97%), at_rail 35/35 (100%)
  reach beyond rail, resting bars (ATR): n=132 med=1.3048 p75=1.6129 p90=2.063 max=3.9565
  whole-bar clearance beyond rail, resting bars (ATR): n=132 med=0.3276 p75=0.6408 p90=0.9512 max=1.665
  reach beyond rail, semi bars (ATR): n=311 med=0.3609 p75=0.6019 p90=0.8126 max=2.4002
  gap inside rail, at_rail bars (ATR): n=343 med=0.2571 p75=0.3813 p90=0.4452 max=0.4982

**S rail** — bars: resting 79 (5.3%), semi 331 (22.2%), at_rail 383 (25.7%), away 699 (46.8%)
  boxes containing state ≥1x: resting 18/35 (51%), semi 35/35 (100%), at_rail 35/35 (100%)
  reach beyond rail, resting bars (ATR): n=79 med=1.1338 p75=1.5811 p90=2.1836 max=3.1715
  whole-bar clearance beyond rail, resting bars (ATR): n=79 med=0.2753 p75=0.7215 p90=1.5089 max=2.539
  reach beyond rail, semi bars (ATR): n=331 med=0.3285 p75=0.5386 p90=0.7347 max=1.8799
  gap inside rail, at_rail bars (ATR): n=383 med=0.2249 p75=0.3779 p90=0.4478 max=0.4982

### 1. State frequencies — JUNK-SURVIVED

**R rail** — bars: resting 72 (2.4%), semi 350 (11.9%), at_rail 483 (16.4%), away 2044 (69.3%)
  boxes containing state ≥1x: resting 26/98 (27%), semi 77/98 (79%), at_rail 97/98 (99%)
  reach beyond rail, resting bars (ATR): n=72 med=1.2622 p75=1.5668 p90=1.9767 max=3.2327
  whole-bar clearance beyond rail, resting bars (ATR): n=72 med=0.4403 p75=0.8149 p90=1.044 max=1.7415
  reach beyond rail, semi bars (ATR): n=350 med=0.2254 p75=0.4463 p90=0.7186 max=3.4452
  gap inside rail, at_rail bars (ATR): n=483 med=0.2381 p75=0.3751 p90=0.4594 max=0.4975

**S rail** — bars: resting 63 (2.1%), semi 277 (9.4%), at_rail 358 (12.1%), away 2251 (76.3%)
  boxes containing state ≥1x: resting 14/98 (14%), semi 71/98 (72%), at_rail 90/98 (92%)
  reach beyond rail, resting bars (ATR): n=63 med=1.3227 p75=1.6025 p90=2.1637 max=2.6402
  whole-bar clearance beyond rail, resting bars (ATR): n=63 med=0.3928 p75=0.6236 p90=1.0702 max=1.8739
  reach beyond rail, semi bars (ATR): n=277 med=0.2671 p75=0.5087 p90=0.8458 max=1.6811
  gap inside rail, at_rail bars (ATR): n=358 med=0.2228 p75=0.38 p90=0.4484 max=0.4914

### 2. Singular vs run (engaged-bar runs, any non-away state)

**DRAWN R**: runs=158 len split {'short': 37, 'dwell': 78, 'singular': 43} dominant {'at_rail': 99, 'resting': 11, 'semi': 48}
  run length n=158 med=2.0 p75=6.0 p90=13.0 max=48.0; max reach ATR n=158 med=0.0008 p75=0.601 p90=1.5578 max=3.9565
  singular SEMI runs (his forgiveness case): 4 runs across 4/35 (11%) boxes

**DRAWN S**: runs=156 len split {'singular': 41, 'dwell': 85, 'short': 30} dominant {'at_rail': 94, 'semi': 61, 'resting': 1}
  run length n=156 med=3.0 p75=5.0 p90=12.0 max=36.0; max reach ATR n=156 med=0.0825 p75=0.4709 p90=1.1309 max=3.1715
  singular SEMI runs (his forgiveness case): 6 runs across 6/35 (17%) boxes

**JUNK-SURVIVED R**: runs=271 len split {'dwell': 118, 'short': 60, 'singular': 93} dominant {'at_rail': 164, 'semi': 100, 'resting': 7}
  run length n=271 med=2.0 p75=4.0 p90=8.0 max=23.0; max reach ATR n=271 med=0.0 p75=0.3488 p90=1.0823 max=3.4452
  singular SEMI runs (his forgiveness case): 21 runs across 20/98 (20%) boxes

**JUNK-SURVIVED S**: runs=237 len split {'short': 54, 'singular': 100, 'dwell': 83} dominant {'at_rail': 137, 'semi': 94, 'resting': 6}
  run length n=237 med=2.0 p75=3.0 p90=6.0 max=28.0; max reach ATR n=237 med=0.0 p75=0.2268 p90=0.9038 max=2.6402
  singular SEMI runs (his forgiveness case): 36 runs across 32/98 (33%) boxes

### 3. The "bigger swing upwards" exclusion (markup overlap, R rail)

**DRAWN**: runs containing a resting bar: 26; markup-overlapping (departure legs): 6; TRUE RESTS: 20 across 17/35 (49%) boxes
  wave types overlapping ALL resting runs: {'in_progress': 21, 'markup': 7, 'SOS': 1, 'range': 3, 'upthrust': 9, 'rejection': 6}
  wave types overlapping TRUE rests: {'in_progress': 16, 'markup': 1, 'upthrust': 8, 'rejection': 5, 'range': 2}
  true-rest max reach ATR: n=20 med=1.5511 p75=2.0655 p90=2.4097 max=3.9565; markup-leg reach ATR: n=6 med=2.1837 p75=2.3726 p90=2.7611 max=3.122

**JUNK-SURVIVED**: runs containing a resting bar: 31; markup-overlapping (departure legs): 0; TRUE RESTS: 31 across 26/98 (27%) boxes
  wave types overlapping ALL resting runs: {'SOS': 2, 'range': 11, 'upthrust': 2, 'in_progress': 15, 'rejection': 5}
  wave types overlapping TRUE rests: {'SOS': 2, 'range': 11, 'upthrust': 2, 'in_progress': 15, 'rejection': 5}
  true-rest max reach ATR: n=31 med=1.2494 p75=1.5553 p90=2.2121 max=3.4452; markup-leg reach ATR: -

### 4. What-follows (context) — breaching runs, next 10 bars

**DRAWN R**: breach runs=79 outcomes {'crash_back_through_box': 45, 'right_edge': 17, 'resumed_consolidation': 2, 'left_up': 15}
  dominant=resting: {'right_edge': 3, 'left_up': 8}
  dominant=semi: {'crash_back_through_box': 28, 'right_edge': 11, 'resumed_consolidation': 2, 'left_up': 7}
  dominant=at_rail: {'crash_back_through_box': 17, 'right_edge': 3}

**DRAWN S**: breach runs=89 outcomes {'reclaimed_into_box': 79, 'broke_down': 10}
  dominant=resting: {'broke_down': 1}
  dominant=semi: {'reclaimed_into_box': 53, 'broke_down': 8}
  dominant=at_rail: {'reclaimed_into_box': 26, 'broke_down': 1}

**JUNK-SURVIVED R**: breach runs=143 outcomes {'resumed_consolidation': 27, 'crash_back_through_box': 74, 'right_edge': 35, 'left_up': 7}
  dominant=resting: {'left_up': 5, 'right_edge': 2}
  dominant=semi: {'resumed_consolidation': 20, 'crash_back_through_box': 52, 'right_edge': 27, 'left_up': 1}
  dominant=at_rail: {'resumed_consolidation': 7, 'crash_back_through_box': 22, 'right_edge': 6, 'left_up': 1}

**JUNK-SURVIVED S**: breach runs=121 outcomes {'reclaimed_into_box': 75, 'held_near_support': 18, 'broke_down': 13, 'right_edge': 15}
  dominant=resting: {'broke_down': 5, 'held_near_support': 1}
  dominant=semi: {'reclaimed_into_box': 59, 'held_near_support': 14, 'broke_down': 8, 'right_edge': 13}
  dominant=at_rail: {'reclaimed_into_box': 16, 'held_near_support': 3, 'right_edge': 2}

### 5. Seller's-tail bars (breach bar spread ≥ 1.5 ATR, crash-back within 5 bars)

**DRAWN**: big breach bars(≥1.5 ATR)=49, of which tail-crashed=26 across 17/35 (49%) boxes (1.7% of bars); at ≥2.0 ATR: 16 big, 11 crashed.
  boxes with a tail-crash: ANRO@2026-08-12[cluster], BODI@2026-04-21[classic], FOSL@2026-02-18, JAZZ@2026-02-24, NGL@2026-04-20, NTCT@2026-03-04, ORMP@2026-04-13, PBT@2026-05-11, RGR@2026-03-19, ROIV@2026-06-17[classic], SILC@2026-04-13, SKYT@2026-04-13[classic], ST@2026-04-17[classic], UNF@2026-07-10[classic], VIK@2026-06-11[classic], WTS@2026-06-12[classic], YPF@2026-05-18[classic]

**JUNK-SURVIVED**: big breach bars(≥1.5 ATR)=49, of which tail-crashed=35 across 18/98 (18%) boxes (1.2% of bars); at ≥2.0 ATR: 18 big, 16 crashed.
  boxes with a tail-crash: ABEV#411, BMRN#196, BMRN#460, BMRN#464, CHCT#439, CHCT#452, CHCT#456, CHCT#465, FRPH#342, GOOD#411, GOOD#438, GOOD#452, GOOD#494, KWR#461, KWR#463, KWR#468, OHI#401, OHI#455

### 6. THE HARSHNESS TEST — boxes flagged per rule

| rule (bars per box) | pop | n_boxes | ≥1 bar | ≥2 | ≥3 | ≥5 |
|---|---|---|---|---|---|---|
| resting_above(out-markup) | drawn | 35 | 17 | 12 | 9 | 8 |
| mostly_above(out-markup) | drawn | 35 | 27 | 21 | 20 | 10 |
| resting_above(out-markup+inprog) | drawn | 35 | 5 | 4 | 2 | 1 |
| mostly_above(out-markup+inprog) | drawn | 35 | 18 | 11 | 9 | 3 |
| resting_below | drawn | 35 | 18 | 13 | 7 | 4 |
| mostly_below | drawn | 35 | 25 | 22 | 17 | 13 |
| resting_above(out-markup) | junk | 98 | 26 | 12 | 9 | 5 |
| mostly_above(out-markup) | junk | 98 | 41 | 25 | 18 | 14 |
| resting_above(out-markup+inprog) | junk | 98 | 14 | 8 | 5 | 2 |
| mostly_above(out-markup+inprog) | junk | 98 | 28 | 16 | 10 | 6 |
| resting_below | junk | 98 | 14 | 11 | 11 | 6 |
| mostly_below | junk | 98 | 30 | 19 | 14 | 12 |

Flag RATES at ≥1 bar (drawn should be LOW if the rule is safe):

- resting_above(out-markup): drawn 17/35 (49%) vs junk 26/98 (27%)
- mostly_above(out-markup): drawn 27/35 (77%) vs junk 41/98 (42%)
- resting_above(out-markup+inprog): drawn 5/35 (14%) vs junk 14/98 (14%)
- mostly_above(out-markup+inprog): drawn 18/35 (51%) vs junk 28/98 (29%)
- resting_below: drawn 18/35 (51%) vs junk 14/98 (14%)
- mostly_below: drawn 25/35 (71%) vs junk 30/98 (31%)

### 7. Symmetry closure — R vs S, drawn population

| measure | R (ceiling) | S (floor) |
|---|---|---|
| resting bars | 132 (8.8%) | 79 (5.3%) |
| boxes with resting | 22/35 (63%) | 18/35 (51%) |
| semi bars | 311 (20.8%) | 331 (22.2%) |
| boxes with semi | 34/35 (97%) | 35/35 (100%) |
| at_rail bars | 343 (23.0%) | 383 (25.7%) |
| boxes with at_rail | 35/35 (100%) | 35/35 (100%) |
| resting reach median (ATR) | 1.3048 | 1.1338 |
| semi reach median (ATR) | 0.3609 | 0.3285 |
| runs | 158 | 156 |
| run length median | 2.0 | 3.0 |

### Sanity anchors — known ceiling-rest chapters

- **DSGN@2026-03-31[classic]** (79 bars): … [31-78] 48b dom=semi states={'semi': 33, 'resting': 10, 'at_rail': 5} reach=1.5454ATR **MARKUP**
- **MATX@2026-07-01** (39 bars): … [17-38] 22b dom=resting states={'at_rail': 3, 'semi': 5, 'resting': 14} reach=3.122ATR **MARKUP**
- **MSGS@2026-05-22** (67 bars): … [57-66] **10b dom=resting** states={'semi': 5, 'resting': 5} reach=1.1838ATR
- **NOK@2026-02-17[classic]** (27 bars): … [19-26] **8b dom=resting** states={'semi': 3, 'at_rail': 1, 'resting': 4} reach=1.6451ATR

The two departure legs are correctly typed MARKUP; the two genuine right-edge rests are not — which
is the whole of finding 3. Full run lists are in the instrument's stdout and the sidecar.

## What the numbers say (the verdict the rulings cite)

1. **Harshness-by-position is ANTI-predictive on every variant tried** — it flags the operator's own
   boxes 1.8–3.6× harder than junk. Raising the bar count (≥2, ≥3, ≥5) never reverses the ordering.
   The one variant reaching parity (14% = 14%) gets there by also excluding `in_progress` waves,
   which swallows his genuine right-edge ceiling rests (MSGS's 10-bar, NOK's 8-bar) — i.e. it reaches
   parity by refusing to look at exactly the bars he drew the box for.
2. **A whole bar above his rail is a departure announcing itself, not a failure.** Of the 11
   resting-dominant breach runs in his boxes, 8 left upward and 3 hit the window edge — ZERO crashed
   back. It is the SEMI straddlers he is most inclined to forgive that crash back through the box
   (drawn 28/48, junk 52/100).
3. **The engine's markup typing implements the "bigger swing upwards" clause only partially.** Only
   6 of 26 drawn resting runs overlap a typed `markup` wave; 16 of the 20 "true rests" overlap
   `in_progress` instead — no-lookahead typing cannot type a wave that has not finished, and in his
   marks the rest usually IS the right edge. Markup overlap is a SUFFICIENT but not NECESSARY
   exclusion; a clean mechanical test of the clause needs an outcome that does not exist yet at the
   right edge.
4. **The seller's tail is real, detectable with the existing ATR yardstick, and NOT junk-specific** —
   it appears slightly more often inside his own boxes (17/35, 1.7% of bars) than in junk (18/98,
   1.2%). Context to weigh around a breach, never a standalone fatal.
5. **His forgiveness case is real but not the norm and not a signal** — a lone straddling bar sits in
   11% (R) / 17% (S) of his boxes versus junk's 20% / 33%. Junk has it MORE. Forgive it, never reward
   it.
6. **The rails mirror.** Drawn R vs S: semi 20.8% vs 22.2% of bars, at_rail 23.0% vs 25.7%, resting
   reach medians 1.30 vs 1.13 ATR, semi reach 0.36 vs 0.33, runs 158 vs 156. The one asymmetry —
   more whole-bar-above (8.8%) than whole-bar-below (5.3%) — is the departure legs leaving upward.
   Support behaves as he described: drawn S-side breach runs reclaimed into the box 79/89 times.
7. **The loud negative, stated plainly:** being above the rail does not separate junk from his marks
   in either direction as a standalone position read. Junk's defining behavior at the ceiling is
   ABSENCE (69% of junk R-side bars are away from the rail vs 47% of his), not breach.

## Caveats (named, not hidden)

- Junk n=98 framings come from only 18 tickers, so box-level flag rates cluster by ticker; the
  bar-level denominators (1,492 vs 2,949) are the robust ones.
- The markup/`in_progress` numbers BOUND — they do not settle — the "bigger swing upwards" clause,
  because no-lookahead typing cannot type the right edge.
- What-follows and tail horizons truncate at the window edge (drawn R: 17/79 runs right_edge; junk R:
  35/143), so crash / left-up rates are lower bounds inside the drawn window, not forward returns.

## Divergences from the sealed run

One, and it is a stamp, not a number:

- **`engine_config_version` moved**: `0ac88199221d77be…` when the evidence was sealed (2026-08-30 on
  `claude/zen-satoshi-d1122d`, pre-merge) → `08c981629923c30e…` at reproduction (post-merge main,
  which carries the miss-program dark lanes and the ONE-Event-Map epoch). Every census number is
  unchanged, which is the expected result: the rotating constants are dark flags (default off) and a
  fire-rule/tag addition, none of which touches box geometry, wave typing or the state machine.
  Recorded rather than re-stamped — the sealed hash is what the ruling was made under.

No measured value diverged. Nothing was re-fitted.

## What the port deliberately left out

The exploratory instrument was ~32 KB written fast; the committed one reproduces the cited headlines
and drops the rest:

- **the per-bar record dump** (`bar_states`: one dict per bar per box, the bulk of the old 860 KB
  JSON). The per-bar distance values are still measured and pooled into the reported distributions;
  only the per-bar rows are gone. The sidecar carries the population summary plus one row per box
  (state counts, harshness counts, run tallies, tail counts) — 108 KB.
- **the box-fraction courtesy columns** (`max_reach_boxfrac`, `box_height_atr` per run). The ruled
  unit is ATR; the box-fraction column existed only as a courtesy read and no cited number uses it.
- **`min` and `p25`** from the distribution summaries — the report only ever printed
  n / median / p75 / p90 / max.
- **the markdown writer**: the exploratory wrote `BARSTATES.md` itself. The committed instrument
  prints the report to stdout and this file is the committed record; a tool that writes a docs file
  is a write path into the evidence record we do not want.
- **the silent skips**: a junk case with a missing frame or a refused prep used to `continue`. It now
  aborts loudly naming the case — a silently skipped case shrinks the 98-framing denominator every
  cited rate divides by.

## Reproducing it

```powershell
.\.venv\Scripts\python.exe -m tools.bar_state_census --json output\bar_state_census_2026-08-30.json
```

Read-only and offline: it reads the calibration marks DB, the frozen frame store and the committed
negative-corpus fixture; it writes a sidecar only (EC-46) through the sealed-output guard (EC-14).
**Runtime ~22 s** on the operator's machine — no scoping flags needed, so none were added. The run
is deterministic: two consecutive runs printed byte-identical reports.

`output/*.json` is gitignored, so the sidecar is committed with `git add -f`, exactly as its
committed siblings `research/evidence/miss_lane_census_2026-08-29.json` and
`research/evidence/shape_profile_2026-08-29.json` are — an EC-16 evidence file that a fresh clone cannot read
is not an evidence trail.
