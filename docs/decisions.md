# Decisions — operator rulings, and the levers that are DEAD

**Append-only.** Rows are never rewritten or deleted; a superseded ruling gets a new row
that says so. [`strategy_alpha.md`](strategy_alpha.md) is *what we are trying to see* and
[`engine_reference.md`](engine_reference.md) is *how it is currently seen* — both describe
the present. This file is the only one that remembers what we already tried.

## Why this file exists

Measured on 2026-07-27, during the trend-terminal box gate: four designs were proposed and
falsified in one session. Two of the four were **already documented** in `strategy_alpha.md`
("the root is only a scan origin, not the box's cause"; the back-extension behaviour) and
were still missed, because they sat inside a 1700-line file in a parenthetical. Prose that
is technically present but unfindable does not prevent the bug. A short, boring registry of
*dead things* does.

**Read the Tested-DEAD table before proposing any new knob, threshold, or heuristic.**

---

## Tested-DEAD — do NOT re-propose without new evidence

| Lever | Verdict | Why it died | Recorded |
|---|---|---|---|
| **Overshoot-magnitude test for box legitimacy** (refuse a box whose trend ran N box-heights past R) | **DEAD — falsified 3×** | Anti-correlated with the operator's judgment. He ACCEPTS 47.9% (PXS), 82% (VIK), 101% (MATX) — those are upthrusts *inside* an established base; on PXS he deliberately draws R at 4.66 beneath the 4.92 spike — and REJECTS LIVN at 20.57%. A `TREND_TERMINAL_OVERSHOOT_BOX` knob was built, measured, and removed the same day. The live discriminator is **post-climax maturity** (LIVN 13 bars vs PXS 53, floor `MIN_BASE_DAYS`). | 2026-07-27 |
| **Keying the box's cause trend on `root.kind`** | **DEAD** | The root is a *scan origin*, not the box's cause. LIVN's winning root is an `SC` 420 bars away from the advance that actually swallowed its box, so a kind-keyed gate passed the very defect it was written for — silently. Derive the cause from the segment covering the bar. | 2026-07-27 |
| **Direction-blind trend-segment overlap (later segment wins)** | **DEAD** | Segments share a leg — an uptrend runs to its CHoCH, which IS the next downtrend's start. Letting the later one win lets a base's own automatic reaction (BC→AR) veto the box open at the top where it belongs. Broke 6 pinned Guided-List hits (AVT/CTOS/MATX/NGL/SYRE/VIK). Cause segment (first-write) wins. | 2026-07-27 |
| **Gating a box on its raw `cand_start`** | **DEAD** | Must judge the **back-extended** start, the bar that actually becomes `box.start_bar`. The trend floor is not monotonic: a handover bar carries the OLD (printed) terminal while the next carries the new leg's, so a legal box can sit one bar the far side of an illegal anchor (MATX). | 2026-07-27 |
| **Shelf-R overshoot re-anchoring** | **DEAD — REVERTED** | No clean rule matched the eye; the respect gate kills shelf-R framings on 16 above-rail bars, and that band is also the upthrust defense. Never loosen the respect gate to chase it. | pre-2026-07 |
| **The ATR V-arm check in the Phase-C spring detector** | **DEAD** | Superseded by the bounded-excursion model (penetration → reclaim → hold). Do not re-add. | pre-2026-07 |
| **Two-pass root walk to fix last-resort scope** | **DEAD** | Measured: it reverses CMPR's operator-accepted band election, creating a new violation while fixing another. The per-ROOT `if not pool` guard is pre-existing shared design, not a story/band regression. | 2026-07-27 |
| **Scoring `rs` / `uptrend`** | **DEMOTED to 0** | Edge read 2026-07-22 over 1977 episodes: actively harmful. Merged `fd7fe3b`; S-tier share 51%→29%. | 2026-07-25 |
| **Scoring HTF (weekly/monthly) context** | **DEAD as a score input** | Edge verdict: don't score it. Stays measure-only. | 2026-07-04 |
| **Bar-dwell gate form (EGBN class)** | **DEAD** | EGBN is a confirmed basis artifact, but the gate form breaks 10/26 identities and lets DGII/FLG fire. Merged as measurement only (`d8fd6f6`). | 2026-07 |
| **Multi-ticker `yf.download` batching to cut request count** | **DEAD — refuted at the provider** | Reads like free money (5,488 single-ticker calls → ~110 batched) and the batching code path still exists, so it invites re-proposal. It buys nothing: `yfinance/multi.py` loops **per ticker in both thread modes**, and `base.py` puts the symbol in the URL path — one HTTP request per symbol regardless of batch size. The 2026-07 docstring blaming batching for rate-limit storms is imprecise: what died was `threads=True` (uncontrolled inner threads), not batching. Per-ticker also buys real isolation — one bad symbol cannot taint a batch. | 2026-07-27 |
| **"The cold fetch is slow because it pulls 5 years"** | **DEAD — measured false** | Cold-fetch stages measured 510 s / 499 s against incremental 585–740 s; the *incremental* window is not faster. Request **count**, not payload size, sets the wall clock, and the pool is ~80% idle waiting on rate-limit tokens. Shortening `DOWNLOAD_PERIOD` would cost HTF history and save nothing. | 2026-07-27 |

### Nulls — measured, discriminated nothing

Do not re-run these as defect detectors; they describe the corpus norm, not a defect.

| Measurement | Result |
|---|---|
| Box high above R | 274/332 boxes (82%). Rails are *worked-equilibrium* levels, never climax→AR extremes, so this is design. |
| A later high exceeds the Phase-A climax high | Median +7.5% across the corpus; LIVN sits at the **39th percentile**. |
| Position of the box high within the box | Corpus median 75% depth; LIVN at 43% = 23rd percentile (i.e. *better* than typical). |
| Operator's drawn R vs the window high | His own 33 marks sit a median **+7.7% BELOW** the window high, vs the engine's +3.1% — the opposite of the expected direction. |

---

## Rulings

| Date | Ruling | Where it lives |
|---|---|---|
| 2026-08-06 | **The Event Map is the grade's frame: ONE 0-100 Technical Analysis Grade per setup**, decomposed into story chapters — Cause → Work → Turn → Finish → Trend context — with the letter tier derived from the 0-100. "Event Map shouldn't be a chip but rather a base feature… we will grade the setups by their Event Maps aka their story" (2026-08-05). Chapters are a display partition of ONE fixed-divisor affine sum, never per-chapter normalization; chapter membership is engine identity, hashed into `engine_config_version`, so a re-chaptering is a visible archive seam. The 2026-08-08 registration of this taxonomy (+ the batched v2 settings names) is the build's first deliberate no-behavior seam — scores byte-identical, hash rotated. | `engine_alpha/scoring/taxonomy.py`; flag `TA_SCORE_V2` |
| 2026-08-06 | **HTF enters the GRADE as a visual trait.** The grade's master is visual quality (the operator's charter): the Minervini base count within the current confirmed up-segment and the inter-base width comparison are graded traits — entering measure-first, weighted only at the operator's A/B eyeball. **Supersedes the 2026-07-04 "don't score HTF" edge verdict FOR THE GRADE only**; edge reads remain the separate predictive yardstick, and the demoted weekly/monthly trend-state score stays dead. | this file (supersedes the 2026-07-04 Tested-DEAD row for the grade); measurement lands via the TA-grade build |
| 2026-08-06 | **RS and uptrend stay demoted at 0** — registered, visible, zero-weight display terms (`rs_bonus`, `uptrend_bonus`); never re-inflated outside an operator A/B. | `config/settings.py` |
| 2026-07-27 | **A complete panel that is one session behind is readable, not broken.** "One bad provider day costs me nothing is better for sure." Evaluation proceeds on the cache's own last session while **archiving stays shut**; the tolerance is bounded by `MARKET_DATA_EVALUATE_MAX_LAG_SESSIONS` and requires completeness through that session, so a panel that is both behind and sparse still blocks. Prompted by 2026-07-24, where the static NYSE rule calendar called it a session and Yahoo carried **no bar for it at all**. | `engine_reference.md` "When the provider loses a whole session"; state `session_lag` |
| 2026-07-27 | **Correction, same day.** The 2026-07-24 stall was first diagnosed as "the provider published the session with OHLV and a null Close". That was **wrong**, and the way it was wrong is worth keeping: the row Yahoo served labelled `2026-07-24` (Open 738.510010, Volume 41,480,799, Close null) was the **forming 2026-07-27 bar under the wrong date** — proven when the market opened and 07-27 appeared carrying that identical Open to six decimals. An explicit-window fetch returns `07-20, 07-21, 07-22, 07-23, 07-27` for every symbol probed: 07-24 does not exist upstream. **Lesson: never conclude a bar exists from its index alone — read the values.** The first probe printed only dates and produced a confident, wrong answer that survived into four files before the market open falsified it. | this file |
| 2026-07-27 | **RESOLVED: 2026-07-24 was a normal trading day and Yahoo lost it.** S&P 500 settled 7,411.98, Nasdaq 24,975.82, Dow 51,947.25 — the NYSE calendar was correct, and the second hypothesis (an unscheduled closure a static rule calendar cannot represent) was also wrong. The real failure class is **the sole provider silently dropping a full session across the whole universe**, which no retry can fix. Leaves a permanent one-day hole in the panel (07-23 → 07-27) and no archive row for 07-24. Strongest argument yet for the parked second-provider work: one source that can lose a day has no cross-check. | `engine_reference.md` "When the provider loses a whole session" |
| 2026-07-27 | **A base may not open inside a live trend.** "We can't start the anchor from the opposite direction of the trend if we are still inside that trend" + LIVN's correction was "way too young". Encoded as: box open ≥ covering **confirmed** trend segment's terminal, and when that terminal lands inside the box, ≥ `MIN_BASE_DAYS` bars must have printed since. | `engine_reference.md` "Phase B — trend-terminal box gate"; flag `TREND_TERMINAL_BOX_GATE_ENABLED` |
| 2026-07-26 | **Wyckoff is a source of ideas, not a specification.** Textbook fidelity is not a success criterion. Never open a change whose whole justification is "canon has this and we don't." | [`wyckoff_canon.md`](wyckoff_canon.md) |
| 2026-07-26 | Retire the jargon the operator does not use — *creek*, *ice*, *BU/BUEC*, *Mini-BC*. Describe the event plainly. Frozen wire keys (e.g. `buec_shelf`) stay. | [`wyckoff_canon.md`](wyckoff_canon.md), [`structure_legend.md`](structure_legend.md) |
| 2026-07-25 | Event-Map ORDER separates the twins: drift junk shows zero completed rail-events; a mark has multiple legal forms. | [`event_map_program_2026-07.md`](event_map_program_2026-07.md) |
| 2026-07-24 | **The Guided List (33 marks) is THE engine-test standard** — the must-fire gate, checked with `python -m tools.marks_corpus --check`. | [`guided_list_read_2026-07-24.md`](guided_list_read_2026-07-24.md) |
| 2026-07-20 | Cause-before-effect: a box may not be elected over a live trend that never matured a cause. | flag `CAUSE_BEFORE_EFFECT_VETO_ENABLED` |
| 2026-07-20 | A box opening ON the trend extreme collapses to the sanctioned one-bar boundary form (climax == AR == box open). | `engine_reference.md` "Phase A — Locality Resolution" |
| 2026-07-10 | Rails anchor from the chronological swings, **wick to wick**; a deep below-rail event is Phase C inside ONE box. | flag `BAND_RAILS_ENABLED` |
| — | **Bull regime is not a validity caveat.** The bull-only corpus IS the relevant population; the surviving concern is sample SIZE, not regime. | standing |
| — | **Calibration success = concordance**, not 1:1 rail replication: the engine shares the operator's idea and his picks surface live. | standing |

---

## How a change to this engine should go

The order below is what actually caught mistakes, in the order it caught them.

1. **Read the theory first** ([`strategy_alpha.md`](strategy_alpha.md)), then this file's
   Tested-DEAD table. Most bad proposals die here for free.
2. **Measure before building.** State the discriminator you expect, then test it against the
   corpus *and* against the operator's marks. Four of this engine's most plausible ideas
   were nulls; finding that out costs minutes, and finding it out after implementation costs
   a day.
3. **Build it behind a default-off flag**, with a row in [`flag_ledger.md`](flag_ledger.md)
   in the same change. Flag-off must be byte-identical.
4. **A/B against the sealed marks ratchet** (`python -m tools.marks_corpus --check`) with the
   flag on. A regressed pinned hit is a design falsification, not a threshold to tune —
   diagnose the specific name before touching a constant.
5. **Run the invariant gate** (`python -m tools.doctrine_audit --check`) and the full suite.
6. **Land the docs in the same change.** Theory → `strategy_alpha.md`; implementation and
   its reasoning → `engine_reference.md`; the ruling and anything falsified → here.
7. **The flip is the operator's**, on eyeball evidence. Renders go to `tools/fidelity/`.

**Put the gotcha where the hands are.** The facts that unblocked the 2026-07-27 session came
from *docstrings* at the point of use, not from any document. If an invariant can be stated
next to the code that depends on it, state it there and let these files carry the model.

**Prefer a machine-checked invariant to a paragraph.** `tools/doctrine_audit.py` is the
highest-leverage artifact in the repo: prose tells the next session the rule, the gate proves
they did not break it. When a ruling is expressible as an invariant, add it.
