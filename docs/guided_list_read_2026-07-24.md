# The Guided List — deep-dive read (2026-07-24)

**The Guided List** is the operator's curated calibration standard: **33 marked setups across 31
tickers** (NGL and ORMP carry two instances each), all `verdict='box'`, drawn on frozen
point-in-time frames in the calibration workbench. It **supersedes the seed corpus'
dates** as the engine-testing population (operator ruling, 2026-07-24: "Remove Seeded and do not
rely on those old dates, do keep the names"). Marks stay editable (EC-9); the exact set scored here
is fingerprinted `b671e056a91fc14d…` — a changed fingerprint means the ground truth moved, not the
engine.

Every number below was measured this session with read-only instruments:
`tools.calibration_stat_card` (drawn-geometry measures), `tools.calibration_harness --fired`
(full-pipeline pops-up-live replay), and two scratch probes (close-basis respect; election traces
on the 7 misses).

---

## 1. The shared signature — what all 33 have in common

Ranked by cluster tightness (normalized IQR), the operator's picks share, in order:

| trait | p25–p75 | median | reading |
|---|---|---|---|
| full occupancy / coverage | 1.0–1.0 | 1.00 | every third of the box lived in; R touched across the whole window |
| **median bar spread / ATR** | 0.80–0.92 | **0.85** | THE defining texture: individual bars stay quiet — ~0.85 ATR — even inside a wider box |
| p80 bar spread / ATR | 1.08–1.23 | 1.17 | even the *worst* bars stay ≈1.2 ATR — no violence inside the base |
| respect at drawn rails (wick) | 0.65–0.78 | 0.72 | consistent — but BELOW the 0.80 gate (see §3) |
| ATR squeeze (ATR10/ATR50) | 0.99–1.18 | 1.08 | **NOT a squeeze** — volatility roughly flat; his tightness is box-relative, not vol-contraction |
| tight-bar share | 0.61–0.74 | 0.65 | |
| contraction quality | 0.57–0.76 | 0.67 | progressive tightening present but not extreme |
| LPS shelf length | 3–4 bars | 3 | tiny terminal shelf |
| box width (ATR) | 1.47–2.22 | **1.86** | ~2 daily ranges tall |
| box width (%) | 6.1–9.7% | 8.2% | |
| base length | 29–55 bars | 43 | ~2 months |
| dist from 52w high | −7% – −2% | −3.2% | near highs, established uptrend |
| dead space (both rails) | 0.00 | **0.00** | rails drawn ON the bars — zero slack |
| full traversals / swings | 6–12 / 14–28 | 8 / 21 | genuinely worked, two-sided |
| R / S touches | 9–18 / 11–24 | 12 / 16 | constant rail engagement |
| contraction vol trend | 0.38–0.83 | 0.64 | volume drying through the pullbacks |

**In one sentence: a quiet, fully-worked, zero-slack box near highs, ending in a tiny shelf at the
rail, bought at the rail.** "Clean, simple, easy to understand" cashes out as: quiet bars
(spread/ATR), no dead space (rails at the price), constant two-sided work (touches + traversals +
occupancy). What his picks are **not** defined by: ATR squeeze (~1.0), springs (only 6/33 carry a
Phase-C mark; 1 spring-test), deep undercuts (2/33 UNDERCUT_S shelves).

Drawing conventions: **28/33 boxes drawn resistance-first** (the ceiling is pinned first);
27/33 labeled `classic`; PBT carries two LPS shelves.

### The trigger convention — the buy is AT the rail

- **12/33 buys land BELOW R** (trigger/R 0.90–0.998): the buy is the reclaim off the LPS shelf,
  not the breakout.
- 21/33 are breakout buys — and **every one is within 5% of R** (max trigger/R = 1.05). No chasing.
- LPS shelves: 2–7 calendar days (median 4), sitting late in the box (time-pos median 0.80), in the
  upper half (position median 0.62), zone INSIDE dominant.

---

## 2. Concordance baseline — the Guided List scoreboard

`tools.calibration_harness --fired`, engine `2e523e951b9085fe…`, policy v3:

- **Fired-in-window (pops-up-live): 26/33 = 79%.** This is the ratchet floor for all future work.
- Surfaced at his picks: 21/33; strict geometry-tier match: 5/33.
- **R is shared**: engine R vs his R, median offset 0.00 box-heights. The ceiling read agrees.
- **S is not**: engine S sits below his S (median −0.08, mean −0.29 box-heights; 14/26 below).
  The engine digs S to wick lows; the operator sets S at the body shelf.
- **Timing is right**: engine fire median **6 days BEFORE his buy day**; 24/26 on-or-before.
  The screener surfaces his picks in actionable time.

## 3. The wick-vs-close divergence — one physics error, three symptoms

Close-basis respect probe at the drawn rails (same `BOUNDARY_ATR_BUFFER` the gate uses):

| basis | median respect | pass ≥0.80 |
|---|---|---|
| whole-bar wick (the gate today) | 0.723 | **6/33** |
| bar body (open&close) | 0.853 | 23/33 |
| **close** | **0.886** | **25/33** |

Median wick excursion beyond the buffered rail: **0.32 ATR** — the eye lets wicks breathe about a
third of a daily range past the line. This confirms the boundary-respect eye model at n=33: the
operator reads **bodies hanging at the rail**; the gate reads whole-bar containment. The same
physics difference explains all three top-level symptoms:

1. drawn-rail respect "failures" (27/33 fail the wick gate, in a tight ~0.72 band — a convention,
   not sloppiness);
2. the engine's S-rail bias (wick-anchored S below his body-anchored S);
3. NKTR's total no-box (close-respect 0.97 — best in the set — but wicks kill every candidate).

**This is NOT a case to loosen `MIN_BOUNDARY_RESPECT_PCT`** (the upthrust defense stands, per the
shelf-R ruling). It is a case to recalibrate the *basis* of the one rail-respect primitive —
measure-first, A/B'd against the negative corpus (an upthrust closes outside or pokes far; a
close-basis read with a bounded-wick-excursion cap arguably *sharpens* that defense).

## 4. The 7 misses — full taxonomy (election traces on frozen frames)

| miss | trace verdict | cluster |
|---|---|---|
| NOK | box ELECTS every session; `no_lps` ×6 | **LPS blindness** |
| ORMP@05-08 | box elects; `no_lps` everywhere | LPS blindness |
| PKE | box elects near trigger; `no_lps` | LPS blindness |
| SKYT | `no_lps` on the one readable session; **prep REFUSED 5/6 sessions** (universe gate) | LPS blindness + gate-flicker |
| EGBN | `no_lps` early → **`no_box` at as_of** | right-edge election collapse |
| YPF | `no_lps` 05-11/12 → `no_box` 05-13..18 | right-edge election collapse |
| NKTR | `no_box` ×6, width+respect kill all candidates | wick texture (see §3) |

Two structural findings:

- **LPS blindness is the dominant blocker (5/7).** A box elects; `detect_lps` never blesses the
  shelf the operator marked. We now hold the empirical envelope of 34 marked shelves (length 2–5
  bars, tightness_ratio median 0.66, position median 0.62, INSIDE dominant, pullback_profile
  0.86–1.61) to calibrate the ONE detector against. Note VIK/VLO fail the overshoot
  pullback-profile band at 1.17–1.23 vs the 1.25 floor — the boundary sits right on his cases.
- **The effect can kill its own cause.** EGBN/YPF (and PKE at one session) were electable days
  before as_of; the completing LPS pullback bars retroactively break the box election
  (respect/occupancy shift at the right edge) exactly when the setup completes. The eye freezes
  the box once established and reads the LPS *against* it; the engine re-elects from scratch every
  session. The election-stability diagnostic already measured this churn on the corpus fires.
- SKYT's prep refusals are Phase-1 baseline-filter flicker — invisible today; needs named telemetry.

## 5. What this directs (the gap-breach program, one code per event)

> **PROGRAM EXECUTED 2026-07-24** (branch `engine/gap-breach`) — this section is the point-in-time
> plan, kept for the record; the OUTCOMES live in `docs/strategy_alpha.md` (Tasks 3/4/6/7 records).
> #1 shipped as measures only — the election-gate variant was tested and REJECTED (the junk corpus
> admits FLG/BBVA at every bound). #2 tested and REJECTED (no tail cap restores EGBN/YPF — their
> collapses are structural). #3 answered NO MOVES (the shelves genuinely rest; ORMP-2/PKE pass at
> the drawn rails — their gap is the elected box). #4 SHIPPED (REFUSED(universe) telemetry; it
> re-classified SKYT as an sma50 universe exclusion). Do not re-request #1–#3 from this list —
> the doctrine records exist to prevent exactly that.

Ground truth = this list; gate = fired-in-window ≥ 26/33 ratchet + rail-tol diagnostics. Then, in
order of evidence weight:

1. **Rail physics** — ONE rail-basis primitive (close/body + bounded wick excursion), owning
   respect, S-anchoring, and the LPS shelf judgment. Measure-first, negative-corpus-guarded.
2. **Commit the cause** — the box election, once persistent, is not re-litigated by its own LPS
   bars (the dual of the cause-before-effect veto). One election with one commitment rule.
3. **LPS envelope calibration** — recalibrate `detect_lps` geometry against the 34 marked shelves
   (a shelf-harness: run the detector on every marked window, log verdict + failing margin).
4. **Universe-gate telemetry** — name every prep refusal so gate-flicker is visible.

Seed corpus: names retained, dates retired. The must-fire ratchet (`tools.marks_corpus` sealed
fixture) should be re-frozen FROM the Guided List marks — a deliberate EC-7 re-freeze event, not a
casual edit.
