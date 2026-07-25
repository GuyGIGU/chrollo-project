# Strategy α — Wyckoff-Minervini Chart-Reading Reference

*(Formerly `docs/strategy_v2.md`; renamed at the 2026-07-18 Purity Pass close. Strategy α
documents the engine-α reading in its final, event-organized shape — the Reading Model
below is a catalog with **one entry per chart event**.)*

> **RULE — read this before touching the reading engine.** Any change to chart-reading
> algorithm code (`engine_alpha/structure/`, `engine_alpha/scoring/`, or their
> detection/scoring knobs in `config/settings.py`) **starts by reading this document —
> the Reading Model section at minimum — and lands with this document updated in the
> same change** when behavior moves. This file is the source of truth for *how Chrollo
> understands a chart*, not just a description of the code; letting them drift is a
> defect. (The rule is mirrored in `AGENTS.md` and the root `CLAUDE.md` so every agent
> session loads it.)

This document is the **single source of truth** for what the screener actually does — and, in the [Reading Model](#the-reading-model--the-operators-chart-language) below, for *how we understand chart analysis in the first place*. It mirrors the implementation in `engine_alpha/` (the reading engine) plus `core/` (pipeline plumbing) and the parameter values in `config/settings.py` exactly. Every rule below cites the function and the module it lives in. (For the high-level map of how `core/` is organized, see [core/MAP.md](../core/MAP.md).)

The strategy combines Mark Minervini's Volatility Contraction Pattern (VCP) bias with Richard Wyckoff's Phase A/B/C/D structure. Goal: isolate **tight horizontal equilibrium bases** that have just printed an active **Last Point of Support (LPS)**, with no widening downward continuation, sitting after both R/S have been carved out by actual High/Low swing geometry.

The live structure reader is now chronological: one left-to-right daily-chart narrative, not a set of independent detectors reconciled afterward. It walks **Trend / root swing -> Phase A -> Phase B -> optional Phase C -> Phase D -> LPS**, backtracking to the next root swing when any brick fails. That single `Structure` is the shared reading object for horizontal analysis (time, cause, rail travel, compression) and vertical analysis (R/S levels, box height, undercut depth, trigger shelf).

---

## The Reading Model — the operator's chart language

Everything in this document implements ONE reading procedure — the operator's (stated
2026-07-02, AGCO dissection). This section is the canonical statement of that procedure.
The rest of the doc mirrors the implementation; *this section states the intent the
implementation serves.* When a detector and this model disagree, the model wins and the
detector is the bug (or the model gets amended here, explicitly — never silently).

### The legend (strict vocabulary)

| Term | Meaning | Reserved for |
|------|---------|--------------|
| **BC → AR** | Buying Climax → Automatic Reaction | the end of the **main uptrend** only |
| **SC → AR** | Selling Climax → Automatic Rally | the end of the **main downtrend** only |
| **Root Swing** | the climax→reaction pair *responsible for* the consolidation | whichever pair the cascade below settles on |
| **mini climax / mini reaction** | smaller fractal analogues of BC/AR — every swing peak→valley pair is one | limbs inside/after the base; **never** labeled BC/AR |
| **dead space** | the empty gap between a rail (R or S) and the consolidation's bars | a **rail-placement diagnostic only** — never a junk-chart label |

BC/AR/SC are trend-end terms, full stop. Swings are fractal — small peaks and valleys are
miniature climax→reaction pairs — but the *names* BC/AR belong to the main trend so the
story stays readable.

**Dead space (operator ruling, 2026-07-17):** too much — or plainly visible — dead space
means either the consolidation was marked wrong (a tighter, better structure exists) or no
valid setup exists there at all (no pair of limbs produces a valid structure for that
chop). Some dead space is unavoidable and acceptable depending on the structure — an SOS
shifting the base upward, a deep correction consolidating lower, a big upthrust followed
by a huge spring can all leave holes — but even then the whole structure must stay tight
and well respected. The term describes the rail-to-bars gap and nothing else; a chart the
engine must refuse gets its own honest reason (mis-framed range, trend-continuation dip,
run-up flag…), never "dead space" as a catch-all.

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

`label_market_structure()` ([engine_alpha/structure/market_structure.py](../engine_alpha/structure/market_structure.py)) tags every pivot on the shared swing skeleton HH / HL / LH / LL and tracks a running mechanical trend state. `segment_trends()` walks those labels into explicit directional **trend segments**, each with the four things that define a trend:

1. **Start** — a trend is *born* at its **change-of-character**: the first HH that breaks a prior down/range (an uptrend's CHoCH-up), or the first LL that breaks a prior up/range (a downtrend's CHoCH-down). It launched off the pivot just before that break.
2. **Climax (terminal swing)** — the trend's extreme pivot: the highest HH of an uptrend (the **buying climax**), the lowest LL of a downtrend (the **selling climax**).
3. **End (CHoCH)** — a trend *ends* at the opposite structural break: an uptrend ends when a **lower-low takes out the last higher-low** (the first LL = the CHoCH that opens the next, opposite trend); mirror for a downtrend. A segment still making trend-consistent structure at the right edge has no end yet (it is still running).
4. **Full leg** — the whole advance the climax ended: from the segment's **start** pivot up to the terminal higher-high (mirror for a selling climax). This is the retrace basis the automatic reaction is measured against. (The **terminal impulse leg** — the last higher-low into the climax — is exposed too as `impulse_start_bar`, but it is *not* the AR basis: measuring against only the final sub-leg let the reaction anchor short of the true support.)

**The automatic reaction derives from this model.** Once the trend has topped at its climax, the **AR is the low of the first *continuous* reaction after the terminal swing** — the running counter-move that retraces a meaningful fraction of the *full leg* and is closed at the first **big confirmed bounce** off that low (`first_reaction_after()`). That is exactly what the drawn Phase-A overlay tightens to under `AR_FIRST_REACTION_ENABLED` (see [Phase A — First-reaction AR anchor](#phase-a--first-reaction-ar-anchor-flag-gated-default-off)).

This is **measure-only**: the trend model reads the labels the skeleton already assigns and assigns no points, moves no rails, and gates nothing. It is the geometric substrate the roadmap's richer market-structure reads (CHoCH = Phase A start, BOS = Phase D continuation, liquidity sweeps) grow from — always as graded confidence, never a veto.

#### Climax → Automatic Reaction (Phase A)

The trend-end event: the climax (an uptrend's BC, a downtrend's SC) and the automatic
reaction off it — the pair every base hangs from, and the names the legend reserves for
the main trend. The owning read is `collect_root_anchors()` (the calibrated climax→AR
anchor scan feeding the root walk). The **drawn** Phase-A overlay tells the same event
in labeled forms, never separate detectors: the canonical anchor scan; the always-on
**macro-validated bridge** (`macro_bridge_zigzag`, folded 2026-07-18 — abstains unless a
True-Root bridge validates; see "Phase A — Macro bridge read"); and the dark
**first-reaction AR refinement** (`first_reaction_after()` under
`AR_FIRST_REACTION_ENABLED`), which tightens the drawn AR to the trend model's first
continuous reaction.

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

**Commit-tail rescue — tested and REJECTED (2026-07-24, gap-breach Task 4).**
The dual of the SOS worked-window trim (re-judge a failing framing on its
window minus a bounded terminal floor-holding pullback tail — "the completing
LPS may not re-litigate its own cause") was built dark and probed on its
stage-tagged targets: **no cap (5/8/12/15 bars) restores the EGBN or YPF
elections.** Their right-edge collapses are structural, not bounded-tail
artifacts — EGBN's shelf resides ~two weeks above the creek-anchored
candidate ceilings (the creek-vs-ceiling rail-PLACEMENT family), YPF's drawn
base is 19 bars with occupancy failures — and a trim long enough to matter
re-elects stale windows (the same lesson as the rejected rescued-pool
arbitration attempt recorded under the SOS→BUEC rescue: re-judging a framing
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
A–F, verdict templates). Fire evidence (`tools.rail_margin_ab`, per-variant
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

**LPS envelope calibration — answered NO MOVES (2026-07-24, gap-breach Task
6).** The shelf-harness (`tools.shelf_harness` — the ONE detector graded over
all 34 marked shelves at the drawn basis) plus the terminal-turn envelope
settled the calibration question the Guided List raised: the operator's
shelves genuinely REST (terminal-turn median 0.0 profile-units; the p90 tail
0.18 comes from marks that already fire), so `LPS_TERMINAL_LOW_TOL_PROFILE`
(0.1) has no envelope support for widening; ORMP-2 and PKE's marked shelves
PASS this detector at the operator's drawn rails (their misses are the
elected BOX, not shelf geometry); NOK's launched-above form is a single case
(tail-fit risk — don't build acceptance forms off n=1). Every chart-readable
Guided List miss therefore belongs to ONE family — **rail placement**: the
election anchors candidate rails at wick extremes / the creek where the
operator anchors body levels / the ceiling (the S-below-drawn-S bias, EGBN's
creek-vs-ceiling, NKTR's width inflation). That family is the named next
program; no LPS geometry knob moved in this one.

#### Support Test

An S-rail hold: a low-zone valley that touches S without a deep breach, then holds.
Owned by `measure_support_tests()` — deliberately *not* the R-rail wave machinery. A
deep breach-and-reclaim belongs to the Spring; the two never double-emit.

#### Sign of Strength, Markup & Upthrust — the R-rail wave

One wave machinery, `measure_resistance_events()`, owns every R-rail interaction and
types each wave by its **terminal outcome**: a creek-jump that held near R with a
genuine mini-consolidation is an `SOS`; an advance that held far above R is `markup`; a
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
| `buec_shelf` | LPS above R (**Throwback**) | the `OVERSHOOT_R` window class — a back-up to the creek from above, matured-cause bounded (the BBVA defense) |

The freshness veto is the **Stale-Support Reject** (the `descent_tail` family): a window
still descending into its low is not an LPS yet. The full gate table lives in "Phase 3 —
LPS Detection".

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

### The measure-only reader layers

Above the event catalog sit reader layers that move no rail, gate nothing, and score
nothing (save the puzzle read's one bonus-only term):

#### The L2 event reader — Wyckoff puzzle: from rail events to a scored narrative

Above the geometry sits a second reading layer that does not move a single rail. Once the cascade has **elected** an equilibrium box, the L2 event reader ([engine_alpha/structure/box_events.py](../engine_alpha/structure/box_events.py), re-exported through [engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) reads the in-box structure as *facts about a Wyckoff story* — a labeled staircase, independent rail-event zones, and their chronological assembly into the classic spring → SOS → LPS puzzle. Like the trend model, it is **measure-only**: every function here reports what it sees and assigns no points, gates nothing, and moves no rail. It reads the box the engine **already elected** — never a re-detection — so its story is told over the same rails, start, and span everything else measures against.

The read is a pipeline of four stages. First, `read_box_staircase()` labels the in-box swing sequence: it composes the *same* calibrated significant-swing skeleton the traversal read uses (`_collapse_swings` on the order-1 zigzag, amplitude-filtered by `TRAVERSAL_NOISE_FRAC`) with the L0 labeller (`label_market_structure`), so the staircase swings *are* the worked-equilibrium swings. Each swing is annotated with its box-position (`box_pos`, 0 = S rail, 1 = R rail), a low/mid/high `zone`, and a `rail_event` (`touch_R`/`breach_R`, `touch_S`/`breach_S`, or `interior`) — one chronological HH/HL/LH/LL sequence the later events are read off.

Second, the two rails are measured **independently**. `measure_resistance_events()` walks the R-rail: every peak that turns in the high zone is a rail interaction, and consecutive higher-highs with no drop back to support between them are grouped into one *wave* that is typed by its **terminal outcome** — a creek-jump that held near R with a genuine mini-consolidation is an `SOS`, an advance that held far above R is `markup`, a run-up that failed back to support is a single `upthrust` (one false-break wave, not a string of SOS), and the in-between cases stay descriptive (`range` / `rejection` / `in_progress`). The Phase-D split is anchored on the structural **V** (the deepest staircase valley). `measure_support_tests()` is the S-rail sibling — deliberately *not* a mirror of the wave machinery — reporting each low-zone valley that touches S without a deep breach and then holds as a `test` (a deep breach-and-reclaim is left to the spring brick, so the two never double-emit).

Third, `read_box_events()` (over the shared chokepoint `_box_events_with_meta`) unifies these into one flat, deterministically-ordered list of independent zones, adding the calibrated **spring** brick (Phase C) and **LPS** brick (Phase D, gated purely on bar position — right of the V — never on an SOS existing). Each piece is detected on its own geometry and is never gated on another; the bricks come either from a measure-only re-detection or, when the scorer calls in, from the pieces the engine *actually elected* (including a tighter inner-box LPS), so the read describes what fired rather than a fresh parent-box guess.

Fourth, `assemble_box_narrative()` stitches the zones into the puzzle in one linear pass. It picks the spine (`spring` → first `SOS` → `LPS`), tallies a raw `completeness` (0..4 distinct canonical pieces present — spring, SOS, LPS, held-test), reads a three-valued `chronology` (`intact` only when all three spine pieces are present *and* strictly bar-ordered spring < SOS < LPS, else `partial`/`absent`), derives the B/C/D phase spans off the shared V, and emits an explainable `trace`. Every one of these reads is descriptive — none is shaped as a pass/fail another layer could consume as a filter. A missing piece is reported, never fabricated.

The **only live consumer** is a bonus-only score term. Always on (folded 2026-07-18; formerly flag `PUZZLE_SCORE_ENABLED`), `_puzzle_quality()` in [engine_alpha/scoring/scoring.py](../engine_alpha/scoring/scoring.py) folds `completeness` and `chronology` into a single `[0, 1]` composite (they are correlated — an intact chronology is impossible without the full spine — so they never split into two double-counting terms), and `s_puzzle` scales it by `SCORE_PUZZLE_QUALITY` (8.0) and clamps it into `[0, cap]`. It is strictly additive and `>= 0`: it can only ever *raise* a score. A missing, `None`, or malformed narrative reads a neutral `0.0`, so an absent puzzle never demotes a setup below what its geometry already merits. Consistent with the whole reading model, **geometry is the only veto** — the Wyckoff puzzle is graded confidence layered on top of it, never a gate.

#### The Event Map — the mechanical swing layer (whole-frame)

The Event Map ([engine_alpha/structure/event_map.py](../engine_alpha/structure/event_map.py), `read_swing_map`) widens the L2 staircase's calibrated swing skeleton from the elected box's window to the **whole evaluation frame**, so the pre-box trend and the box story are read on one substrate. It stands up no second skeleton: **one** order-1 pivot walk runs per frame, and each windowed view — the pre-box segment, the in-box staircase — is that walk's pivots filtered to its window and fed through the *same* staircase machinery (`_staircase_from_pivots`). The in-box view is **byte-identical** to `read_box_staircase` by construction; the widening only *adds* pre-box swings (including a pivot at the box-start bar itself, which the windowed walk's order margin masked). The two views are stitched, not re-collapsed: alternation and HH/HL/LH/LL labelling reset at the box-start seam — the price of keeping the in-box slice identical to the elected staircase — and the seam is a stated boundary, never an implicit one.

Every swing carries the **causality stamps** the Event Map contract requires ([specs/event-map-causality-contract.md](../specs/event-map-causality-contract.md), binding for all Event Map work): `describes_bar` (the pivot bar) and `knowable_bar` — the first bar at whose close the swing was *irreversibly committed*, i.e. the bar that pivot-confirms the first opposite extreme whose counter-move reaches the collapse threshold. A swing whose committing reversal has not printed is `in_progress` and satisfies nothing downstream; the frame's first swing is `edge_uncertain` (its extremity depends on bars left of the live two-year trim). The label set "as of date D" is exactly the swings with `knowable_bar ≤ D` — what makes replay honest instead of quietly clairvoyant. One stated caveat: a *view* younger than three raw pivots emits nothing yet (the staircase's own degenerate-window guard), so a swing's first appearance can lag its `knowable_bar` at view birth — labels may appear late, but never change or vanish retroactively.

Above the mechanical swings sits the **narrative-role layer** (`read_role_labels`): the L2 event zones — spring / test / SOS / upthrust / markup / range / rejection / LPS — re-emitted as stamped role labels. It consumes the *same* `_box_events_with_meta` chokepoint the puzzle read uses, **fed the engine's elected bricks** (`structure.spring` / `structure.lps`, both required arguments; an injected `None` means "the engine elected none" and is honored — the layer never re-detects). Each label carries the measurer's own tri-state `resolution` plus a `knowable_bar` derived from its real confirmation mechanics: a failed wave at its low-zone drop bar; a held wave or test at the end of its printed hold window *and* never before the wave stopped being extendable (a later higher-high with no drop to support would have absorbed it — the wave-closure rule) or the anchoring swing committed; a spring at the end of its fully-printed `BIN_C_HOLD_BARS` reclaim-hold (a window running past the last bar is `in_progress`, §2); the elected LPS at the **frame end** — its "still holding" verdict consumed every printed bar, so it is `election_dependent`: re-issued by each frame's own election, frame-scoped rather than truncation-stable (the spring's presence likewise). The chronology battery (`python -m tools.event_map_chronology --check`) replays the marks corpus with cuts stepping through each setup's LPS window and asserts, on emitted labels only, that within a stable election a committed label never mutates or vanishes as bars print.

Like the trend model and the L2 reader, both layers are **measure-only** — they move no rail, gate nothing, score nothing. On the live path they are staged behind **`EVENT_MAP_ENABLED`** (default OFF, dark-flag ledger + frozen manifest): flag-on, the readers are computed **for firing setups only** (the puzzle-read placement) and emit underscore diagnostics — the four tape-summary reads (`_event_map_n_swings` / `_pre_box_trend` / `_n_labels` / `_n_committed`; proven additive-only over the full shadow fixture, evaluation-phase cost ≈ +1ms per firing ticker) plus the **rail-episode substrate** (Event Map program Task 10): the AS-OF sentence over the elected window and rails — the SAME read the story pool consults, so a rescued fire's archived sentence is by construction the evidence that admitted it — as typed scalars (`completed_s` / `completed_r` / `alternations` / `terminal_posture` / `terminal_drift` / `story_admitted`), the readability companion (`episode_nan_bars` — an explicit zero is evidence, and it can never masquerade for unreadable bars), the sentence text, and ONE compact JSON episode tape whose anchors are dates, never bar indexes. Flag-on, the diagnostics are archived as the **`event_map_*` column family** — declared once in `event_map.py` (`EVENT_MAP_COLUMN_SQL`: names, types, row extraction; the live writer and seed both splat the one extraction function) and entering the schema as model-only nullable adds, where NULL means "not measured", never zero. **Seam discipline (Task 11):** archived sequence values are partitioned by `engine_config_version` — the flip is the family's first seam and every later episode-typing or ruled-form refinement is a NEW seam; pre-flip NULL rows are **never backfilled** by re-running a later reader over cached history (the `bin_a_*` precedent — a backfill stamps current-rule values onto rows whose replay basis may differ, destroying the seam's meaning while looking like a completeness win). Separately and unconditionally, every fire archives its **electing-pool provenance** — `elected_pool`, a closed set (`strict` / `rescued` / `band` / `story`) carried from the candidate tuple through the elected box (`EquilibriumBox.elected_pool`) into both writers — so the rescued cohort's own forward returns stay separable forever. The chart-overlay payload arrives in a later Event Map stage behind its own review; the flip is operator-gated on the scan-metrics cost A/B.

A sibling measure-only diagnostic, **election stability** (`ELECTION_STABILITY_ENABLED`, default OFF, dark-flag ledger + frozen manifest): for firing setups only, the eval-twin prep and the structure election alone are re-run at D−1..D−k (backward shifts only — nothing archived can carry lookahead) and each shifted reading is compared to the live one through the single cross-frame identity predicate (`engine_alpha/election_identity.same_election`: box-start date + rails within a scale-free tolerance). Real structures persist while junk elections flicker day-to-day. The probe measures **backward persistence of the BOX election**, not of the fire: a box can elect well before its LPS completes, so `same_frac` at a fire's first session can legitimately be anywhere in 0..1 (corpus fires measured mostly 0 — the election itself was churning into those fires — while AVT's 0.33 shows pre-fire persistence exists; a low value means election churn, never "the fire is new"). A shift where the eval-twin prep refuses (universe-gate flicker: SMA/volume/price membership, not chart structure) counts as not-same in `same_frac` and is ALSO reported separately, so calibration can tell gate-flicker from election-flicker. Diagnostics emitted raw (`_stability_same_frac` / `_streak` / `_probes` / `_refused`) — never a gate, never a score. Flag-off is byte-identical and compute-free; the flip is gated on the measured cost bound (≈2.75s per firing ticker at k=3 — see the ledger).

#### The rail-episode read — chronological completion over a rail pair (Event Map, layer 3)

Where the swing map reads *structure* and the role layer reads *the elected story*, the
rail-episode read tells a candidate window's story **chronologically, one rail engagement at
a time** — the read that separated EGBN (`S+ S+ S+ R^`) from its drift-junk statistical twins
(DGII/CHCT/COLM/FLG: zero completed episodes) when every aggregate failed (the 2026-07-25
sequence probe). It is a bar-level read over ANY rail pair — an elected box or a raw
candidate framing — using only the engine's existing yardsticks, no free knobs:

- **rail episode** — one merged visit of a rail's touch zone (zone = the touch yardstick,
  `TOUCH_TOLERANCE_ATR` × ATR; visits separated by ≤ `EPISODE_MAX_GAP_BARS` (2) inside bars
  merge into ONE episode — the band-rails same-side-span convention).
- **Outcomes (wire enums frozen; one per episode):**

  | Wire | Display | Meaning | Profile token |
  |---|---|---|---|
  | `completed` | completed support test / completed resistance rejection | the engagement resolves back inside the box: any breach beyond the respect buffer (`BOUNDARY_ATR_BUFFER` × ATR) is reclaimed and the first close after the episode confirms the rail held | `S+` / `R+` |
  | `failed` | failed episode | the engagement resolves through the rail — an unreclaimed breach, or the confirming close lands beyond the rail | `S×` / `R×` |
  | `open` | open episode | the window ends inside the engagement — no verdict printed (contract §2: `open` never satisfies a completion predicate) | `S0` / `R0` |

- **Terminal postures** (frame-scoped right-edge reads over the `open` outcome, reported
  separately from completed history — never counted as completed facts): **terminal
  resistance posture** (`R^`) — the window's last episode engages R and its final close sits
  above R: the pre-breakout stance the operator's marks end on; **terminal support drift** —
  an open S-side episode ≥ 3 bars at the window end: price lying on support with no verdict,
  the drift-junk tell.
- **The sentence** — the chronological profile string (`S+ S+ S+ R^`) — is the read's
  compact narrative form; per-window counts (completed support tests, completed resistance
  rejections, alternations between completed episodes) are its summary statistics.

Causality follows the contract: a completed/failed verdict prints at the first close after
the episode (`describes` = the episode's bar span), but the episode's IDENTITY is only
irreversible once the merge horizon has printed clean — `knowable_bar` = the last bar of the
episode + `EPISODE_MAX_GAP_BARS` + 1; an episode still inside its merge horizon at the frame
edge is `in_progress`, and the as-of sentence counts only episodes with `knowable_bar ≤ D`.
Like every reader layer, this is **measure-only**: it moves no rail, gates nothing, scores
nothing. Its two planned consumers (PLAN-event-map.md) are the story-rescue last-resort pool
(a thin, separately named admission predicate — the operator-ruled form, never baked into
this reader) and the archived sequence substrate.

**The RULED story-pool admission form (operator ruling 2026-07-25 — Option A of the census
menu; THIS paragraph is the canonical spec the pool predicate must match, pinned by test):**
a candidate window is story-admissible when its as-of episode read shows **at least 2
completed support tests AND terminal resistance posture AND no terminal support drift**
(`story_admission` in `event_map.py` — the judgment beside the reader, never inside it).
Census evidence (fingerprint `b671e056…`, engine `ab5bf340…`, run
`.council/implement-output/2026-07-25-1707/`): 22/33 marks admitted at drawn rails with
**zero live junk exposure** — every parsing junk sentence is either pool-unreachable
(ordinary election stands: KWR/NVT/GOOD) or traversal-killed in-pool; RLGT, the one
reachable junk case, is admitted by no form. **Accepted misses under the ruling** (part of
the ruling, never regressions): ALB, DLX, FOSL, MATX, NGL-2026-01, ORMP-2026-04, PKE, RGR,
SKYT, SYRE (S-poor profiles / respect-killed / universe classes). The measured in-pool
requirement: the traversal gate MUST keep running on story candidates (it kills 30 of the
69 junk occupancy deaths; the admission form is not asked to carry them alone). A re-ruling
of the form is a NEW seam (archive rule-version discipline) and re-runs the census, never a
silent predicate edit.

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
   > (live, bonus-only) event-puzzle read. Applied post-election in BOTH the live reader
   > (`bricks.validate_equilibrium`) and the diagnostic mirror (`phase_b_zigzag` →
   > `detect_boxes`), so every path frames the same box. The operator eyeballed the
   > A/B renders (`tools/fidelity/box_backext/`, `tools/box_backext_ab.py`) and the
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

### Where each step lives

| Reading step | Implementation |
|---|---|
| Trend / trend end (Phase A) | `label_market_structure()` + `segment_trends()` read the HH/HL trend model (start / climax / CHoCH — see "Trend & Change of Character") — **flag-gated: reached only via `first_reaction_after()` under `AR_FIRST_REACTION_ENABLED` (OFF in engine-α, so the trend model is inactive in the frozen base)**; `collect_root_anchors()` (the calibrated climax→AR anchor scan) for the root walk; `segment_swings()` (order-N pivot zigzag) for the drawn Phase-A bridge, upgraded first by the always-on macro-PIP read (`macro_bridge_zigzag`, folded 2026-07-18; abstains unless a True-Root bridge validates — see "Phase A — Macro bridge read"); the drawn AR tightens to the trend model's first reaction via `first_reaction_after()` (`AR_FIRST_REACTION_ENABLED`) |
| The cascade / Root Swing | `read_structure()` root backtracking × `collect_zigzag_candidates()` earliest-valid election (+ the always-on `backext_shared_rail` start refinement, folded 2026-07-18). The elected box is *emergent* — the same pair wins from nearly every scan origin — so the cascade and the election converge on the same anchors |
| "Works both rails" test | `_is_boundary_respected()` + `_validate_base_quality()` (worked-equilibrium occupancy) + the traversal gate |
| Phase C spring | `find_spring()` (bounded-excursion model: penetration → reclaim → significance → hold) |
| Phase D evidence | `resolve_phase_d_boundary()` (support_tests / sos_reclaim / rising_support / inner_box / v_tip; LPS fallback) |
| LPS (mandatory) | `detect_lps()` |

### The explainability rule

**The engine is never allowed to be blind to *why* it chose the pair it chose.**
`read_structure(df, atr, trace=[...])` narrates the whole walk: every root swing tried,
every candidate pair inside the box election with the stage that rejected it (`width` /
`window` / `respect` / `occupancy` — with the failing checks named, e.g. "dead space low" /
`traversal` / `rescue_unused`) and why the winner was elected (`selection`,
earliest-of-valid). `python -m tools.structure_case_audit <TICKER> --trace` renders it.
The trace is opt-in and free on the live path (`trace=None` = zero cost, byte-identical).
New reading logic must **extend the trace, not bypass it** — the narrated process is what
lets richer story-building (the event puzzle, graded confidence reads) trust the geometry.

**The trace speaks event language.** Every trace label, reject reason, and diagnostic
names its chart event in the catalog's vocabulary — plain chart language where humans
read, frozen keys on the wire. The catalog's third law binds here too: **a new signal
declares its event** before it ships — it enters the catalog under its event,
measure-first, as graded confidence. No event, no signal.

---

## Pipeline Overview

```
Phase 0  Universe & data acquisition          core.pipeline.data public API
Phase 1  Baseline universe filter              core.pipeline.evaluation (apply_baseline_filters)
Phase 2  Chronological structure read          core.structure           (read_structure -> bricks -> Structure)
Phase 2b Crash / extension filters             core.pipeline.evaluation (_evaluate_ticker)
Phase 3  Active LPS/Test election              core.structure           (detect_lps; latest actionable setup LPS)
Phase 3b Phase scoping + bin evidence          core.structure           (phase_d / scope_consolidation / measure_phases)
Phase 4  Scoring & tier assignment             core.scoring             (score_setup, calculate_tier)
Archive  Persist + forward-return backfill     core.archive             (writer / forward_returns / seed)
```

The code is organized as two engines plus a conductor (see [core/MAP.md](../core/MAP.md)):
**`engine_alpha/structure/`** = the Visual Structure Engine (pure geometry/measurement),
**`engine_alpha/scoring/`** = the Scoring Engine (the tunable opinion layer),
**`core/pipeline/`** = the conductor that wires them together, with **`core/archive/`** as the
measuring-stick tooling. Orchestrated by `run_screener()` in
[core/pipeline/screener.py](../core/pipeline/screener.py), running per-ticker evaluation from
[engine_alpha/evaluation.py](../engine_alpha/evaluation.py) in a `ProcessPoolExecutor`.

---

## Phase 0 — Universe & Data

### Ticker universe — `get_tickers()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/tickers.py](../core/pipeline/tickers.py))

1. Read from cached `config/tickers.csv` if it exists and is younger than `TICKER_CACHE_MAX_AGE_DAYS` (1 day).
2. Otherwise download `ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqtraded.txt`, filter rows where `Test Issue == 'N'` and `ETF == 'N'`.
3. Apply the screenable-symbol filter on both cached CSV reads and fresh FTP downloads:
   alpha-only, <= 5 chars, and excluding 5th-character `R` / `U` / `W` special
   issues (rights, units, warrants) that waste Yahoo requests while still keeping
   real 5-letter common names like `GOOGL`.
4. On fresh NASDAQ directory refreshes, also read `Security Name` and reject
   obvious non-common instruments (warrants/rights/units, preferreds, notes,
   debentures, ETNs, and closed-end funds). Rejected directory facts are persisted
   to `ticker_admission.json` as `invalid_instrument` so Yahoo never has to teach
   us the same lesson with empty history requests.
5. Exclude any one-symbol-per-line entries in `config/ticker_skiplist.txt` before
   market data is requested. This is the manual escape hatch for known delisted or
   permanently broken symbols; the runtime dead-ticker quarantine still handles
   repeated empty Yahoo responses automatically.
6. Dedupe (preserving order) and write back to the CSV cache.
7. Hard fallback to a 15-stock sample if FTP fails.

### Market data — `fetch_data()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/downloads.py](../core/pipeline/downloads.py))

- Reads from `market_data_cache_5y.parquet` and applies an **incremental refresh** policy via `cache_meta.json`:
  - `TTL_FRESH_HOURS_MARKET = 1` (RTH) / `TTL_FRESH_HOURS_OFFHOURS = 12` — under TTL the cache is reused as-is.
  - `FULL_REFRESH_INTERVAL_DAYS = 7` — at least once a week, force a cold 5y refetch regardless of TTL.
  - Between those, `_incremental_fetch()` re-downloads only the last few business days (`INCREMENTAL_OVERLAP_BDAYS = 5`), with a `SPLIT_PROBE_*` guard that detects yfinance's auto-adjust silently rescaling history and falls back to a cold refetch when > 2% of probed tickers drift.
- Cold path: downloads from `yfinance` with bounded per-ticker workers through the shared Yahoo token bucket (`YAHOO_RATE_LIMIT_*`), using `period = "5y"` (`DOWNLOAD_PERIOD`) so weekly/monthly HTF context has enough history.
- The daily structure read still trims to `DAILY_STRUCTURE_PERIOD = "2y"` before `read_structure()`, so the deeper cache feeds HTF context without changing the daily root walk.
- `_recover_missing_data()` re-downloads tickers that came back missing or with < 200 bars (skipped if more than half the universe is missing — likely rate-limit). Recovered columns replace the bad columns and the merged frame is written back to Parquet.
- SPY rides in the same parquet as the screened universe but is excluded from screening — it exists only to feed `get_market_context()` (SPY 6m return + breadth).
- `ticker_admission.json` is checked before every Yahoo fetch:
  - `active_ready` downloads normally.
  - `active_young` has live history but fewer than `ADMISSION_MIN_HISTORY_BARS`
    (200), so it cannot pass the baseline history gate yet; it is skipped until
    `ADMISSION_YOUNG_RECHECK_DAYS`.
  - `yahoo_empty` returned no usable history and is re-probed after
    `ADMISSION_EMPTY_RECHECK_DAYS`.
  - `invalid_instrument` comes from directory facts and is skipped indefinitely.
  Index symbols are never skipped by admission.
- Successful healthy fetches update the admission ledger from actual Close-bar
  counts. A current-but-short symbol is **not** treated as delisted and no longer
  gets an immediate per-ticker fallback retry; it is marked/rechecked as too young.

---

## Phase 1 — Baseline Universe Filter

`apply_baseline_filters()` ([engine_alpha/evaluation.py](../engine_alpha/evaluation.py)).

Reject the ticker entirely if any check fails. Run in this order:

| Gate | Rule | Setting |
|------|------|---------|
| History | `len(df) >= 200` bars | hard-coded |
| Price floor | `Close >= MIN_PRICE` | `MIN_PRICE = 3.0` |
| Liquidity | `Vol_50 >= MIN_VOLUME_50D` | `MIN_VOLUME_50D = 50_000` |
| Above 50d trend | `Close >= SMA_50` | hard-coded |
| Above 200d trend | `Close >= SMA_200` | hard-coded |
| 12-month return | `(Close - Close[-252]) / Close[-252] >= MIN_YEARLY_RETURN` | `MIN_YEARLY_RETURN = -0.20` (modest drawdowns OK) |

While computing baselines we attach `SMA_50`, `SMA_200`, `Vol_50`, and `Spread = High - Low` to the DataFrame for downstream use.

`_evaluate_ticker()` then attaches `ATR_10` and `ATR_50` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py): Wilder's smoothing via SciPy `lfilter`). `ADX` is implemented in `indicators.py` but **not used** by the live screener — only `backtest_watchlist.py` references it.

### Market-context broadcast — `get_market_context()` ([core/pipeline/data.py](../core/pipeline/data.py), implemented in [core/pipeline/market_context.py](../core/pipeline/market_context.py))

Before per-ticker workers fan out, the orchestrator computes two scalars once and pickles them into every worker:

- **`spy_6m_return`** — SPY close-to-close return over `RS_LOOKBACK_BARS` (126 bars). Feeds the Soft RS bonus in scoring (`excess_return_6m = stock_6m − spy_6m`).
- **`breadth_pct`** — share of the screened universe with `Close > SMA_50`. Persisted to the archive (`_breadth_pct`) and used by the market-breadth bonus in scoring; never used as a hard gate.

Cached in `market_context.json` next to the parquet with TTL 1h during market hours, 12h otherwise; invalidated when SPY's last-bar date changes.

---

## Phase 2 — Consolidation Detection

`read_structure()` ([engine_alpha/structure/narrative.py](../engine_alpha/structure/narrative.py)) is the live entry point. It assembles one Wyckoff story through pure brick validators in [engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py):

1. `find_root_swing()` — next calibrated climax -> automatic-reaction anchor, oldest-first.
2. `validate_equilibrium()` — a real worked Phase-B box, using the existing zigzag candidate and traversal gates.
3. `find_spring()` — optional Phase-C spring / shakeout.
4. `find_inner_box()` — optional tighter Phase-D mini-consolidation in the recent half of the parent.
5. `find_lps()` — mandatory active LPS/Test, inner first when a tighter inner box exists, otherwise parent.
6. `resolve_phase_a()` — reconnects the local climax -> AR bridge whose reaction lands at the validated box start.

If any required brick fails, the reader advances to the next root swing and tries again. If no complete A -> B -> (C?) -> D/LPS narrative holds, the ticker has no setup.

`consolidation.detect_boxes()` / `find_outer_box()` remain for diagnostics and low-level compatibility. The live pipeline consumes the `Structure` from `read_structure()` and adapts it into the legacy parent/inner shape internally so scoring, archive, and chart payloads stay stable.

### Setup

- `eval_df = df.iloc[:-STRUCTURE_EDGE_SKIP_BARS]` (default 5) — last 5 bars are excluded from structural anchoring as trigger/edge noise.
- Require `len(eval_df) >= MIN_BASE_DAYS + 15` = 35 bars.
- ATR snapshot: take `df.iloc[-1]['ATR_10']` from `eval_df` (which equals `df.iloc[-6]['ATR_10']`) to share one volatility frame with the LPS detector.
- **Macro gate (re-asserted):** at `eval_df.iloc[-1]`, `Close > SMA_200`. (Baseline already enforced this at the latest bar; this re-asserts at the evaluation bar so the function works standalone.)

### Phase A — Anchor Discovery

Walk bars from `scan_hi = end - MIN_BASE_DAYS` down to `scan_lo = TREND_MIN_MOVE_BARS + 5`. Each bar `i` is tested as both a possible **BC (Buying Climax)** and **SC (Selling Climax)**.

**BC qualification:**
1. `highs[i]` is the maximum over the last `LOCAL_PEAK_BARS` (30) bars.
2. Within the prior `TREND_PRIOR_LOOKBACK` (100) bars there exists a low such that `highs[i] / trough_low - 1 >= TREND_MIN_GAIN_PCT` (15%) AND the rise spans ≥ `TREND_MIN_MOVE_BARS` (20) bars.
3. **Automatic Reaction:** within `AR_MAX_BARS` (15) bars after `i`, some close drops `>= AR_MIN_DROP_PCT` (5%) below `highs[i]`. Phase B starts at the **AR low** (skips the descent so it doesn't pollute boundary respect).
4. The remaining window after the AR low must be `>= MIN_BASE_DAYS` (20).

**SC qualification:** mirror — `lows[i]` is local trough over 30 bars, fell ≥ 15% from a prior peak (≥ 20 bars), validated by ≥ 5% bounce within 15 bars; Phase B starts at the **bounce high**.

### Phase A — Anchor Selection & Backtracking

`collect_root_anchors()` is built most-recent-first; `find_root_swing()` reads it oldest-first and returns the next root swing at/after the reader's search cursor. The reader then asks Phase B and Phase D to validate the story born from that root. If the box fails, the spring/LPS path fails, or no active LPS exists, the cursor advances past that climax and the reader tries the next pair of limbs. This preserves the "earliest valid cause" bias without forcing an invalid old trend top onto a newer worked base.

### Phase A — Locality Resolution

`resolve_phase_a()` ([engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py)) repackages `segment_swings()` ([engine_alpha/structure/segmentation.py](../engine_alpha/structure/segmentation.py)) after the box is known. It returns the **local** climax -> automatic-reaction bridge whose reaction low lands within `_SEG_AR_TOL` (10) bars **at or before** `box.start_bar` (never after — Phase A ends where Phase B opens, the `ar_bar <= phase_b_start_bar` invariant); if that bridge is unavailable it falls back to the segmentation root, then to a **local synthesis**. The same worked box is reached from nearly every candidate root, so the seed root is only a *scan origin*, not the box's cause; when that seed sits more than `_SEG_LEAD_IN` (60) bars before the box — an ancient origin reaching through to a recent range — the fallback anchors the AR at the box open and the climax at the highest High in the preceding 60-bar run-up, never the stale seed climax (which would otherwise paint, e.g., a 2024 climax on a 2026 box). This fixes the "distant trend top seeds a recent box" problem: Phase A is **guaranteed local** — it belongs to the consolidation that actually validated, not the first trend climax that merely started the search. (`tools/structure_case_audit.py` is the read-only surface for confirming which root won and whether the drawn Phase A is local.)

**Climax terminality (2026-07-19).** Locality alone was not enough: a seed within the
`_SEG_LEAD_IN` window could still be a *mid-trend* pause — FLXS's 04-28 seed sat 41 bars
before the 06-26 box, so the ancient-origin synthesis never triggered, the seg bridge
found no counter-swing at the box door (the trend rips *upward* into a continuation
base), the seg root's true climax (07-02) was rightly refused for landing inside the
box, and the raw-seed fallback painted `bc + AR_MAX_BARS` — a synthetic 15-bar "AR"
while price ran +38.5% past the claimed climax. `_enforce_climax_terminality()` (wired
in `resolve_phase_a()` after the BC-down enforcement, before the AR tighten) applies
the macro bridge's True-Root rule to every calibrated path: post-climax price up to the
box open may exceed the climax by at most `PHASE_A_CLIMAX_TERMINALITY_EXCESS` (0.25) ×
bridge height (ATR floor guards degenerate heights; mirror-symmetric for SC roots;
unknown root kinds pass through). A violating pair re-anchors to the `_SEG_LEAD_IN`
run-up extreme → the box open, the same local synthesis the ancient-origin fallback
uses — terminal by construction.

This affects Phase-A scoping diagnostics (`_bars_since_BC`, `_descent_length`, chart-region labels, and Bin A). It does **not** feed R/S selection, LPS detection, scoring, tiering, or filtering.

### Phase A — First-reaction AR anchor (flag-gated, default off)

The locality resolution above answers *which* climax→reaction pair the box belongs to, but its fallbacks can pin the reaction low all the way at the box open (`phase_b_start_bar`). When the descent from the climax to the base is not a single continuous plunge — a quick reaction, a bounce/pause, then a *later* leg down to the base — that pins the drawn AR on the final leg, so the climax→AR stripe smears across half the chart even though the true automatic reaction ended much earlier.

`_first_impulse_ar_end()` ([engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py)), gated by `AR_FIRST_REACTION_ENABLED` (default off), tightens the AR to the operator's reading of it: **the low of the first continuous reaction after the trend's terminal swing.** It is a thin overlay adapter over `first_reaction_after()` ([engine_alpha/structure/market_structure.py](../engine_alpha/structure/market_structure.py)) — the AR is read from [the trend model](#the-trend-model--hhhl-runs-with-a-start-a-climax-and-a-choch) rather than a raw fixed-bar retrace. Walking forward inside the already-drawn `[climax_bar, ar_bar]` span (never beyond it):

1. **Retrace basis = the trend's FULL leg.** The reaction is measured against the whole advance the climax ended — from the elected trend segment's **start** pivot up to the terminal higher-high (`elected_trend_leg_base`; mirror: the segment start down to a selling climax), falling back to the blind `AR_UP_LEG_LOOKBACK` (40) extreme only when no confirmed segment tops at/near the climax (within `tol` bars). The reaction only "counts" once it retraces `AR_RETRACE_FRAC` (0.5) of that full leg — small wobbles while price is still rising into the top are ignored. (An earlier build measured against only the *terminal impulse sub-leg*, whose short span let the threshold trip almost immediately and anchored the AR mid-decline; the full leg is what makes "reached" mean *near the true support*.)
2. **Termination = the first big confirmed bounce.** Once the retrace threshold is met, the AR is the running reaction low, closed at the first **bounce** off it of ≥ `max(AR_BOUNCE_ATR_MULT·ATR, AR_BOUNCE_DROP_FRAC·drop)` (1.5·ATR or half the drop, whichever is larger). This is what distinguishes the *automatic reaction* from a later second leg: a real bounce off the reaction low locks the AR there (so a subsequent, deeper markdown is not mistaken for it — the AAP case), while a mid-decline pause is too small to close it (so a continuous plunge runs to the support that anchors the base — the TOL/PH case). A genuinely one-way descent with no big bounce inside the span is left anchored at the base edge (no tighten). The twitchy 4-bar *stall* terminator of the earlier build is gone — a stall is a pause, not a reaction end.

The rule is **mirror-symmetric** — a selling-climax paints the first up-reaction off its trough (retrace of the full down-leg; close on the first big give-back) — so the overlay is non-biasing across BC and SC roots. It is **tighten-only and overlay-only**: the search is bounded to the existing span and can only move the AR *earlier*, so the chronological invariant `climax_bar <= ar_bar <= phase_b_start_bar` holds by construction, and — like the locality resolution above — it feeds **no R/S, LPS, scoring, tiering, or filtering**. (It is byte-identical on the scoring/tier/canonical-shadow surface, but a flip is *not* byte-identical on the ARCHIVED `bin_a_*` Phase-A measurement columns — `ar_bar` → `measure_phases` → the winner-fingerprint archive — which no freeze gate covers; a live flip needs an archive-seam guard first. See the flag ledger.) The retarget was driven by the operator's dated BC/AR marks on PH/TOL/AVNT/AAP/AGCO/TFX (2026-07-05): raw is exact on the clean reactions (TOL/AVNT), and the flag now surgically corrects only the second-leg overshoots (AAP-class). Scan tool: `python -m tools.ar_first_reaction_diff` shows which fires re-anchor and by how much.

### Phase A — Macro bridge read (live; folded 2026-07-18)

`macro_bridge_zigzag()` ([engine_alpha/structure/phase_a.py](../engine_alpha/structure/phase_a.py), formerly `pip.py`), wired
unconditionally through `segment_swings()` ([engine_alpha/structure/segmentation.py](../engine_alpha/structure/segmentation.py))
(folded 2026-07-18; formerly flag `PIP_MACRO_PHASE_A_ENABLED`, live 2026-07-04). A multi-resolution PIP (Perceptually Important Points)
skeleton is ranked **once** (`pip_indices` — the ranking is strictly nested, so top-K is an
exact prefix of top-K+1), then walked coarse→fine from `K=4` up to `PIP_MACRO_K_MAX` (24):
the read stops at the **smallest** skeleton holding a validated climax→AR bridge, so the
macro trend-end is found before range noise can steal the climax.

`_validated_bridge` enforces the **True-Root rule** — *a bridge qualifies only if it leads
to an actual equilibrium*:

- **interior AR** — the right edge is "now", never an AR;
- **room for a base** — ≥ `PIP_MACRO_MIN_BASE_BARS` (= `MIN_BASE_DAYS`) bars after the AR;
- **AR extremity** — the AR is its own leg's extreme (no crash hiding inside the bridge);
- **climax terminality** — post-AR highs ≤ climax + `PIP_MACRO_MAX_POST_EXCESS` (0.25) × bridge height;
- **floor holds** — post-AR breakdown ≤ `PIP_MACRO_EQ_FLOOR_FRAC` (0.5) × height (spring-tolerant);
- **two-sided oscillation** — rally off the AR **and** give-back each ≥ `PIP_MACRO_EQ_OSC_FRAC` (0.3) × height.

Climax candidates are tried in descending extremity, so an unconfirmable right-edge
higher-high can't block a genuine older climax. Any failure → the macro read **abstains**
(returns nothing) and the calibrated order-N read speaks — the merge contract. On
validation the story is **truncated at the AR** (binding: downstream can never draw an
unvalidated sibling swing), the root direction comes from the bridge type (never
re-derived from window net sign), and `resolve_phase_a()` passes box-relation constraints
(bridge kind must match the canonical BC/SC root; the AR must not overrun the box birth at
all — Phase A ends where Phase B opens, the chronological invariant `ar_bar <=
phase_b_start_bar`; an earlier AR is allowed within the `_SEG_LEAD_IN` (60) lookback; AR
price must reach the box level ± touch tolerance) so a macro story can never float away from
the elected box or paint Phase A inside it. Affects the **Phase-A overlay only** — R/S selection,
LPS, scoring, tiering are untouched; both flag states are byte-identical on the canonical
shadow set. Eyeball evidence: `tools/fidelity/pip_phase_a/`; scan tool:
`python -m tools.phase_a_pip_diff --jobs N`.

### Phase B — Zigzag S/R Anchoring

`phase_b_zigzag()` ([engine_alpha/structure/box_primitives.py](../engine_alpha/structure/box_primitives.py)).

1. **Pivots** — `_find_pivots()` (vectorized; asymmetric `>=` left, `>` right so flat tops/bottoms still pivot at the rightmost — the structurally meaningful "last touch"):
   - `ORDER = PIVOT_ORDER_LONG (2)` if window ≥ `PIVOT_ORDER_THRESHOLD (40)` bars, else `PIVOT_ORDER_SHORT (1)`.
2. **Zigzag construction** — `_build_zigzag()`: merge peaks + valleys chronologically, enforce strict alternation; on consecutive same-type pivots, keep the more extreme (higher peak or lower valley).
3. **ATR reference** — use the engine-aligned snapshot from the reader if supplied; otherwise the median `ATR_10` over the last `PHASE_B_ATR_WINDOW` (30) bars; final fallback = median(High-Low).
4. **Candidate generation** — only **strictly consecutive** zigzag pairs (peak→valley or valley→peak) are tested. The peak's High = R, the valley's Low = S.
5. **Per-candidate validation — the "worked equilibrium" test.** A candidate (a
   Resistance-anchor / Support-anchor pair) is a REAL trading range only if price
   *respects, touches, and zigzags through both rails constantly, with no dead
   space*:
   - **Box width:** `(R - S) / S <= MAX_BOX_WIDTH` (0.18 — a range wider than this
     is the BC→AR extremes, not a tradeable equilibrium).
   - **Boundary respect** — `_is_boundary_respected()`:
     - Buffered band `[S - 0.5·ATR, R + 0.5·ATR]`; wicks count as breaches.
     - ≥ `MIN_BOUNDARY_RESPECT_PCT` (80%) of bars inside the band, no consecutive
       outside run longer than `MAX_CONSECUTIVE_OUTSIDE_DAYS` (10).
   - **Worked-equilibrium occupancy** — `_validate_base_quality()`:
     - In-base crash filter: `min(Low) >= S × CRASH_FILTER_MULT` (0.70).
     - **Constant two-sided touch:** ≥ `EQ_MIN_TOUCHES_PER_RAIL` (3) on each rail,
       each touched in ≥ `EQ_MIN_TOUCH_THIRDS` (2) of 3 time-thirds (not clustered).
     - **No dead space:** ≥ `EQ_MIN_HALF_DWELL` (0.15) of closes in BOTH the lower
       and upper box third, and box-height `coverage` ≥ `EQ_MIN_COVERAGE` (0.80).
     - **Not mid-churn:** middle-third dwell ≤ `EQ_MAX_MID_DWELL` (0.45).
     - **Bar-as-unit dwell — gate form tested and REJECTED 2026-07-25; kept as
       the MEASURE `_dwell_bar_basis`** (docs/bar_dwell_protocol_2026-07.md,
       sealed campaign; the operator's THIRD bar-as-unit statement). The read:
       lower/upper ENGAGEMENT — a bar whose Low/High reaches the end third has
       worked it — plus mid RESIDENCY (bars living entirely interior). It
       diagnoses EGBN exactly: at his drawn box the lower third holds 3/23
       closes but **8/23 bar-lows** (his named support tests 2025-12-24 and
       2026-01-02 are bar engagements whose closes recover — the definition of
       a support test), and the sealed fire A/B converts EGBN AT his rails on
       his bar (first_fire 2026-01-02). **But the gate form is dead:** swapped
       into `_validate_base_quality`, 10/26 ratchet hit identities break (MATX
       stops firing; FOSL/NGL/NTCT/ROIV/WTS elect displaced boxes; BWA/EWTX/
       MS/VIK re-date) and junk **DGII + FLG fire** — DGII being EGBN's
       statistical twin, now proven twin THROUGH fire level. Close-residence
       dwell is load-bearing for ELECTION STABILITY ("Phase-B rails do not
       drift" is measured fact), not merely junk defense. Do not re-request a
       basis swap; converting EGBN without breaking the fleet requires NEW
       measured information (the operator's narrative separator: SOS → Test →
       SOS 2 → True LPS; excursion→recovery-into-box) — the event-sequence
       direction, recorded for the TA-score / narrative program.
     - Public `metrics.measure_dwell_balance()` (formerly `measure_equilibrium`;
       the Equilibrium name now belongs to the rail-to-rail swing read, formerly
       `measure_traversal`) additionally reports High/Low range occupancy for
       analysis, but the box-of-record selector keeps close residence as the
       calibrated dead-space gate so Phase-B rails do not drift.
   - The old "≥2 touches + N midline crosses" gate is retired — a wide box
     mechanically racked up crosses while a one-time AR low left dead space
     beneath the real range, so the widest framing always won.
   - **Traversal gate** — `_apply_traversal_gate()` requires real rail-to-rail
     swing travel: at least `TRAVERSAL_MIN = 2` full traversals and density at
     least `TRAVERSAL_MIN_DENSITY = 0.08`. This is the swing-structural guard
     against boxes that technically touch both rails but leave one side mostly
     dead.
   - **SOS trim rescue** — a worked box whose right side has already broken out
     and held above R can be validated over the worked cause before that
     breakout tail. This rescues SOS -> BUEC structures (e.g. a valid range that
     backs up to an LPS) without moving ordinary in-range setups.
   - **Deep-excursion pair pool (`BAND_RAILS_ENABLED`, LIVE since 2026-07-16 —
     Event Map Task 11)** — a LAST-RESORT pool consulted only when the
     strict AND rescued pools are both empty, so an ordinary election can
     never move. It re-judges the SAME chronological zigzag pairs (the
     operator's rail rule: anchor R/S from the swings in chronological order,
     wick to wick) with band-leaving excursions typed as EVENTS
     (`engine_alpha/structure/rail_qualification.py`, formerly `band_rails.py`):
     a below-rail episode —
     same-side spans merged across short inside-runs, spring-then-test is
     ONE event — must penetrate, RECLAIM, and HOLD; an above-rail poke must
     fail back and never be exceeded; otherwise the pair dies as a
     breakdown/breakout, exactly as before (the operator's BODI ruling: the
     deep collapse is PHASE C inside one box, "not a box break").
     **Sequence-aware HOLD chain (2026-07-16):** successively deeper
     below-rail events that each reclaim and hold are ONE progressive
     Phase-C step-down — an earlier event's extreme may be undercut only by
     a later qualified event (the working floor steps to the most recent
     event's extreme; non-event bars must respect that standing floor), and
     the FINAL event answers the original never-undercut rule against all
     remaining tape. A pure relaxation: every single-event window judges
     exactly as before. Two hard caps bound what may be typed an event at
     all: `BAND_EVENT_MAX_DEPTH_ATR = 5.0` — an excursion digging deeper
     below the rail is a genuine breakdown, never a terminal shakeout
     (calibrated between BODI's measured chain, 0.86→3.34 ATR, and the
     EGBN 7.68–9.98 ATR over-reach class it kills) — and
     `BAND_EVENT_MAX_BARS = 20` — a run below the rail lasting months is a
     markdown leg, not an episode (EGBN's stale April framing rode a 40-bar
     "event"; BODI's real episodes run 12–18 bars). A non-finite or
     non-positive ATR refuses event-typing outright (quarantine — NaN masks
     must not silently report "no excursions"). **Flip-battery bounds
     (2026-07-16, negative-corpus regressions caught at the live flip):**
     *above* the rail the pool grants no more patience than the respect
     gate's own forgiveness horizon — an above-rail span longer than
     `MAX_CONSECUTIVE_OUTSIDE_DAYS` is a DEPARTURE (the range is not in
     force), never a poke (DBD: a 15-bar, 4.1-ATR rally above R rode the
     uncapped above loop into a tier-S election on rails that were no longer
     in force — the operator confirms DBD's consolidation itself is tight;
     the junk was the mis-framed range, 2026-07-17); and the judged
     window must be a MATURED cause — at least 2 × `MIN_BASE_DAYS` judged
     bars after excision — because a terminal shakeout ends a long Phase B,
     it does not interrupt a five-week flag (SPCB: a 34-bar high-flag whose
     left half was the +35% rally leg itself scraped every gate on 30 judged
     churn bars). Qualified event bars are
     excised from the judged window; every gate in this list runs UNCHANGED
     and full-strength on the remaining bars, except that a pair carrying a
     qualified DEEP below-rail event (multi-bar, beyond S − 2×buffer) may
     measure up to `BAND_MAX_BOX_WIDTH = 0.23` wick-to-wick — the allowance
     exists only with the event, so it can never act as a general width
     loosening. The respect gate is untouched. The qualified deep event also
     feeds Phase C as `bin_c_type = TERMINAL_SHAKEOUT` when the calibrated
     spring detector finds nothing (see the Phase C bin note). Harness proof
     at the marks (2026-07-16, flag-on variant): BODI fires tier A at the
     operator's exact rails (12.33/10.18) on 04-10; both EGBN over-reach
     fires are dead. The operator's A/B rail eyeball over
     `docs/phase_c_marks_2026-07.json` landed 2026-07-11 FAVORABLE; the
     operator granted the flip 2026-07-16 and the flip battery (full pytest,
     shadow re-capture, stage-matched BODI ratchet reseal, negative corpus,
     hermetic recall) ran green with the two bounds above.
6. **Structural-quality score:** every *valid* candidate gets
   `combined = 0.4 × box_tightness + 0.4 × touch_density(/10) + 0.2 × coverage`.
7. **Candidate selection (`select="earliest"` live default):** choose the
   **earliest** `cand_start` among the valid candidates (longest cause),
   tie-broken toward higher quality — "the earliest *of the ones that qualify*."
   There is no reach-quality floor anymore: a sparse / dead-space framing can no
   longer be valid, so the support anchor naturally climbs off one-time lows
   until the band is genuinely worked. **If no candidate is valid → no box → the
   stock is rejected.**

   > **Stale-frame dethronement (`ELECTION_DETHRONE_ENABLED`, LIVE since
   > 2026-07-16 — solve-the-engine task 13).** A rescue-propped (SOS-trim) framing whose
   > buffered R the tape has left FULLY behind for the trailing
   > `ELECTION_DETHRONE_SESSIONS = 10` sessions has stopped being the
   > operative structure: flag-on it loses the election **in favor of a
   > later valid framing** (never into an emptier read; dethroned pairs
   > narrate as `dethroned` in the cascade trace). One trailing pass over
   > the already-loaded window; pure function of the frame. Proof at the
   > marks: with the holding-shelf flag, MATX fires 06-29 tier S at rails
   > within tolerance the evening before its breakout; hermetic corpus
   > sweep shows zero non-target elections moving. The sibling
   > rescued-pool arbitration lever was built and REJECTED (it killed
   > VIK's pinned hit; no clean currency rule separates the good early
   > framing from the bad — the shelf-R lesson at election scope; the
   > counterexample is recorded at the pool seam).

`select="best"` remains a diagnostic mode (highest combined regardless of start);
`select="debug"` returns the valid-candidate landscape. The inner Phase-D
mini-consolidation runs the same worked-equilibrium validity one scale down
(mini Resistance/Support anchors) but still selects for tightness.

#### `cand_start` trim — measure on the actual chop window

Phase B begins at the AR *low* (or the bounce *high* for SC anchors), but the structural box rarely starts there — it starts at the next zigzag pivot, which is the inner "mini BC" / "mini AR" that opens the working consolidation. Bars between the outer AR and this inner pivot are the early-chop drift, not part of the box, and including them in boundary respect / base quality measurement inflates breach counts and forgives wicks that aren't really chop. To correct this, every candidate inside `phase_b_zigzag()` is measured on its own bar window: starting at `cand_start = min(r_anchor_bar, s_anchor_bar)` (the earlier of the two zigzag anchors that define R and S). Both `_is_boundary_respected()` and `_validate_base_quality()` run over `eq_df.iloc[cand_start:]`, so the boundary-respect % and the touch / midline-cross counts reflect the actual chop range, not the BC→AR span. The returned `base_length` is also the trimmed length (`base_length - cand_start`), and the r/s anchor bars are rebased to it. The outer BC anchor (`bc_anchor_bar`) remains df-positional — only the box window itself is trimmed.

`phase_b_zigzag` returns: `(base_length, R, S, box_width, r_touches, s_touches, total_outside, r_anchor_bar, s_anchor_bar)`.

The live reader returns a `Structure` object with the validated parent `EquilibriumBox`, optional `InnerBox`, optional `Spring`, winning `Lps`, phase boundaries, and Phase-D evidence. `_evaluate_ticker()` adapts that into the legacy parent tuple internally: `(base_length, R, S, box_width, r_touches, s_touches, breach_days, r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, is_inner_box)`. `bc_anchor_bar` / `phase_b_start_bar` are df-positional and feed the `_bars_since_BC` / `_descent_length` archive fields. Diagnostic `detect_boxes()` still returns `{"parent": <12-tuple>, "inner": <dict|None>}` for tools.

`r_anchor_bar` / `s_anchor_bar` are returned in **eq_df-relative** (base-relative) coordinates — the dashboard and SQLite archive consume them that way. The LPS detector translates them into df-positional indices locally.

### Phase 2b — Crash & Extension Filters

After consolidation passes, `_evaluate_ticker()` re-checks at the latest bar:

- **Crash filter:** `Close >= S × CRASH_FILTER_MULT` (0.70).
- **Extension filter:** `Close < R × EXTENSION_FILTER_MULT` (1.15) — too far above R means the move has already gone, no entry left.

---

## The Phase D Model — Reading the Right-Most Region

Phases A and B establish *where the base is* and *what its R/S are*. But everything a trade actually depends on happens in **Phase D — the right-most region of the consolidation**, where the LPS is evaluated before markup. This is the part a human reads *first* when scanning, and it is the north star the engine exists to honor: read Phase D faithfully and the rest is context.

**Phase D is defined by its Last Point of Support (LPS).** The LPS is the foundation of every setup worth considering — no LPS in the right-most region means no Phase D and no setup. This is not aspirational: `detect_lps()` is mandatory in the pipeline, and a ticker with no qualifying LPS is dropped (`_evaluate_ticker` returns `None`).

**What an LPS is (and isn't).** An LPS is **support forming and holding around the support zone, in general** — price returns to the floor and holds. It is **not** *defined* by being a higher low. A higher-low / ascending / "tennis-ball" shape is **rewarded, not required**: plenty of valid LPSs simply form around the support zone without stair-stepping up. The implementation already reflects this general definition:

- the pullback-shape gate is **graded, not binary** — `descent_frac` *multiplies* LPS quality rather than rejecting non-higher-lows (Phase 3, gate 5);
- the zone gate accepts the LPS **anywhere around the zone** — `INSIDE`, `OVERSHOOT_R` (breakout retest), or `UNDERCUT_S` (spring) — not only a clean higher low (Phase 3, gate 6);
- the ascending-support footprint is a **bonus-only** score, never a filter (see "Ascending Support / Higher-Lows Footprint");
- behind the `LPS_HOLDING_SHELF_ENABLED` flag (LIVE since 2026-07-16), a **second sanctioned completion form** — the flat holding shelf resting **high** in the structure — joins the pullback-and-rest form. This is the canon's two-form doctrine (Wyckoff: the back-up is "a simple pullback **or a new TR at a higher level**"; [lps_final_structure_canon_2026-07-10.md](lps_final_structure_canon_2026-07-10.md)), judged on geometry only (Phase 3).

**The optional tenant: a mini-consolidation.** Phase D *may* contain a second, tighter mini-consolidation — a natural development when live equilibrium shifts during accumulation and the range re-settles inside the larger process. It is **not** always present. The engine handles the "sometimes" through the `find_inner_box()` brick, which mirrors the shared inner search (`inner_box_at` + `detect_inner_root_swing`; see "Parent + Inner"). The inner box is a *structural fact to recognize*, not a requirement to impose.

**The "V" — a positioning guide, not a detected object.** The right-most action often traces a V: a final dip / shakeout / spring down into support, then a turn back up. The V is a guide for *where the trader wants to stand*:

- **before the tip** (still descending into the dip) = wrong place, wrong time — the low isn't in;
- **after the tip** (turned up off the low, demand returning) = the shakeout is done and we are walking toward launch.

The LPS *is* that turn — the last support after the reaction. The engine leans this way structurally: the active setup LPS is terminal-bar based and must sit below its trigger (Phase 3, gate 14), so a qualifying setup is biased toward the up-leg rather than a knife still falling.

**The comprehension this encodes.** Read top-to-bottom, Phase D is the bridge from *"a consolidation exists"* to *"I understand I'm in the right-most region, past the shakeout — now localize the LPS zone."* That region is resolved by `resolve_phase_d_boundary()` ([engine_alpha/structure/phase_d.py](../engine_alpha/structure/phase_d.py)) and surfaced through the narrative reader, `measure_phases()`, and `scope_consolidation()` ([engine_alpha/structure/scope.py](../engine_alpha/structure/scope.py)). It is strictly **measurement/evidence**, never a gate: it cannot drop a ticker, change R/S, or directly alter score/tier. The mandatory gate remains the active LPS itself.

The scoping layer emits best-effort chart anchors:

- **Phase A:** local root climax / automatic-reaction lead-in, from the resolved consolidation-specific climax to the reaction bar.
- **Phase B:** the whole working base / cause-building region from `phase_b_start_bar` through the setup end. In the chart validation view, Phase D is an overlapping right-side read, not a cutoff that truncates Phase B.
- **Phase D:** the right-most launch region. A true Phase-C spring recovery floors the Phase-D search; it is not itself the boundary source. Phase D starts at the earliest credible right-side evidence at/after that floor: support-test cluster, SOS reclaim, rising support, inner mini-consolidation, or recovered V-tip. If none is present, the LPS window is the mandatory fallback.
- **Phase C:** optional measured spring event in Bin B. A `SPRING` is a late Low undercut below S that stays near the box, then recovers by Close back above S within the configured recovery window. Ordinary held support tests remain part of the LPS/support-test layer, not a forced Phase C. Most bases have no Phase C and that is normal. **`TERMINAL_SHAKEOUT` (`BAND_RAILS_ENABLED`, live since 2026-07-16)** — when the calibrated detector finds nothing (its depth/linger caps are breakdown defenses and stay untouched), the box's own qualified DEEP excursion (rail_qualification: penetration → reclaim → hold, multi-bar, beyond S − 2×buffer) is typed as the Phase C at terminal-shakeout scale — the operator's BODI ruling ("the collapse is Phase C inside one box, not a box break"). Fed at the ONE detector seam (`_phase_c_candidate`), so `find_spring`, `measure_phases`, the chart's C label and the archive can never drift; a calibrated `SPRING` is never re-typed.
- **LPS zone:** a tight price-and-time box around the exact LPS candidate bars (`lps_zone_low/high` plus `lps_zone_start/end_date`), not a level stretched across all of Phase D.

All boundaries are nullable. If the engine cannot place a region confidently, it emits `None` and the frontend skips that label/box. Young bases may yield only a base body and a right edge; the model must never force four tidy quadrants.

---

## Phase 3 — LPS Detection

`detect_lps()` ([engine_alpha/structure/lps.py](../engine_alpha/structure/lps.py)). For each `(offset, length)` window in the recent tape, every hard gate below must pass; failing any hard gate disqualifies the window. Candidate swing depth is measured from the first bar's High -- the anchor peak before the pullback -- into the elected LPS valley. Normally that valley is the final bar's Low, and the trigger is the final bar's High. Two shelf patterns are also valid: a compact rising support shelf can elect its early window low as the LPS low, and a long shallow BUEC shelf can hold just above old R. Surviving candidates are filtered for actionability (`current_price < trigger`) and the latest valid setup LPS wins.

**The holding-shelf completion form (`LPS_HOLDING_SHELF_ENABLED`, LIVE since 2026-07-16).** The scan carries a second pure completion judgment, `_holding_shelf_verdict` — the two-form doctrine's flat shelf ([lps_final_structure_canon_2026-07-10.md](lps_final_structure_canon_2026-07-10.md)) — consulted only where the pullback form rejects at gate 7 (pullback depth) or gate 11 (volume floor); every other gate binds both forms. A holding shelf is judged on **geometry only**: at least `LPS_SHELF_LENGTH_MIN = 3` bars, **monotone non-rising lows** (the operator's "LPS = peak that goes down"; a rising low is the canon's wedging failure — which also means the terminal-low guard passes by construction), its low at/above the **box midpoint** (`LPS_SHELF_MIN_LOW_POS_BOX = 0.5` — the canon position test: flat finals are sanctioned only high in the structure; flat-and-low is the named failure geometry), and a dig inside the base depth envelope `[0.40, 4.50]` without the OVERSHOOT_R escalation. A shelf-saved window carries `swing_type = "holding_shelf"` and a **volume-free quality**; volume is measured truthfully (`vol_contraction` may archive negative) but never gates or rewards this form. Flag-off the judgment is never consulted — byte-identity is structural. Calibrated on the operator's marked WTS + PBT shelves (flag-ON: both convert, all pinned corpus hits and all 32 shadow fires unchanged, negative corpus clean). The shelf-length floor STAYS at 3: the 3→2 move was attempted 2026-07-17 and reverted at its flip battery — KWR + FLG (labeled dead-space) both fired via 2-bar shelves; at n=2 the monotone axis is one comparison and does not discriminate.

`offset` = bars between the LPS evaluation bar and "today" (`offset = 0` means the LPS ends today). `length` = number of bars in the LPS sequence.

| # | Gate | Rule | Setting / source |
|---|------|------|------------------|
| 1 | **Recency** | `offset` in the last 7 active LPS bars | `LPS_SCAN_OFFSET_MAX = 7` |
| 2 | **Length** | `LPS_LENGTH_MIN ≤ length ≤ LPS_LENGTH_MAX` | 2 to 7 bars |
| 3 | **Window bound** | `offset + length ≤ base_len + AR_MAX_BARS` | redundant outer guard; never lets the LPS pre-date the box |
| 4 | **Swing-complete** | `eval_idx > swing_complete_idx` where `swing_complete_idx = (len(df) - base_len) + max(r_anchor, s_anchor)` | LPS must sit *after* the swing pivots that defined R and S |
| 5 | **Pullback shape (graded)** | `descent_frac >= LPS_MIN_DESCENT_FRAC` and `high_descent_frac >= LPS_MIN_HIGH_DESCENT_FRAC`; both are pair-wise non-rising fractions over lows/highs. A fully clean downswing may span more vertical box range because it is one peak-to-valley swing, not broad chop. | shape gates + quality multipliers |
| 6 | **Zone gate** | elected LPS low lands in one of three buffered zones. Normally this is the last-bar `Low`; for a compact rising support shelf it can be the early window low. | `LPS_ZONE_ATR_MULT = 0.5` |
|   | • INSIDE | `S ≤ low ≤ R` → setup `LPS` | |
|   | • OVERSHOOT_R | `R < low ≤ R + 0.5·ATR` → setup `LPS` (backtest of breakout) | |
|   | • UNDERCUT_S | `S - 0.5·ATR ≤ low < S` → setup `REBOUND` (spring) | |
| 7 | **Pullback depth (profile-normalized)** | `pullback_profile = (first_high - elected_low) / profile_unit`, where `profile_unit = max(base_range_threshold, 0.15 × box_height)`. INSIDE/UNDERCUT_S need `>= 0.40`; ordinary OVERSHOOT_R needs `>= 1.25`; a long shallow BUEC shelf above R may use the normal `0.40` floor when price is still sitting low on R. All zones cap at `<= 4.50`. Flag-on, a window failing this gate may still complete as a **holding shelf** (see above) | `LPS_PROFILE_BOX_FRACTION_FLOOR`, `LPS_PULLBACK_PROFILE_*` |
| 8 | **Terminal-low guard** | last-bar `Low` must be within `0.10 × profile_unit` of the lowest Low in the candidate window, except for a compact multi-bar rising support shelf whose early low remains inside the support side of the box. That shelf rescue is itself rejected as a markup leg when its net advance `(last Close − first Close) / box_height > LPS_RESCUE_MAX_ADVANCE_BOX` — a genuine ascending-support coil is gradual, not a steep launch off support (OHI-class). | `LPS_TERMINAL_LOW_TOL_PROFILE = 0.10`, `LPS_RESCUE_MAX_ADVANCE_BOX = 0.21` |
| 9 | **Spread (core)** | every LPS bar's `Spread (High - Low)` must be `<= profile_unit × 1.25`; the final bar may widen over the prior bar by at most `0.35 × profile_unit` | `LPS_SPREAD_MAX_PROFILE_MULT`, `LPS_SPREAD_EXPANSION_MAX_PROFILE` |
| 10 | **Declining spread quality** | last bar spread narrower than the prior bar earns full quality; widening inside the allowed expansion cap is discounted against `profile_unit` but does not reject by itself | `LPS_SPREAD_MUST_DECLINE = True` |
| 11 | **Volume floor** | `mean(Volume[LPS]) < Vol_50[eval_idx] × 0.87`. The dry-up is the **pullback form's** judgment: a holding shelf may complete without it (volume never gates the shelf form). Moved 0.85→0.87 on 2026-07-17 against the archive (1,679 matured episodes: outcome quality flat up to the old edge, no cliff; converts AGCO); 0.88+ stays pinned rejected. A non-finite `Vol_50` refuses BOTH forms (data-integrity guard, same change) | `LPS_VOL_CONTRACTION_MAX = 0.87` |
| 12 | **Hold tolerance** | `latest['Close'] >= elected_low × 0.95` | `LPS_HOLD_TOLERANCE = 0.95` |
| 13 | **Post-LPS continuation** (only when `offset > 0`) | every bar between LPS end and current bar must hold `Low >= elected_low × 0.95` and stay profile-tight | catches support-test failures that widen after the LPS |
| 14 | **Trigger room** | candidate is actionable only when `current_price < trigger_price`; `_evaluate_ticker` keeps the same final room check | trigger = last LPS bar High |

**Setup label:** `REBOUND` if zone is `UNDERCUT_S`; otherwise `LPS`.

**Quality ranking:** pullback candidates carry `vol_contraction × (1 - tightness_ratio) × descent_frac × high_descent_frac × spread_decline_quality`; a shelf-saved candidate carries the same product **without the volume term**. Setup election is actionability-first and recency-first: latest valid `end_index`, then latest `low_index`, then (flag-on) the pullback form before the shelf form on an integer rank, then longer length, then quality — so float quality is only ever compared *within* a form. If several clean slices of the same form share the same final low, the detector reports the longest clean pullback.

> **Note on breakouts.** Despite the historical name "VCP/breakout screener," the live `detect_lps()` path is the only signal generator. A genuine breakout setup type isn't emitted from the engine right now, so the old `BREAKOUT_*` settings were removed rather than kept as false knobs.

---

## Phase 4 — Scoring & Tier Assignment

`score_setup()` ([engine_alpha/scoring/scoring.py](../engine_alpha/scoring/scoring.py)). Total score is the sum of **15 components**, each clamped into `[0, cap]` (box tightness is first scaled by the live candle-spread readability multiplier — a `[floor, 1]` grade, never additive). Maximum possible total ≈ **209**.

| Component | Formula | Cap (setting) |
|-----------|---------|---------------|
| **Box tightness** | When `TIGHTNESS_ADR_AWARE` (live): `((MAX_BOX_WIDTH_ADR - box_width_adr) / MAX_BOX_WIDTH_ADR) × 22`, where `box_width_adr = box_width·100 / ADR%` measures the range in the stock's OWN daily ranges (a flat low-ADR drift no longer reads as a coil; `corr(box_tightness, ADR) = −0.73` before the rebase). Flag-off / zero-ADR fallback: the absolute `((MAX_BOX_WIDTH - box_width) / MAX_BOX_WIDTH) × 22`. Then scaled by the always-on candle-spread readability grade `∈ [floor, 1]` (folded 2026-07-18; formerly flag `CANDLE_SPREAD_AWARE`). The absolute `MAX_BOX_WIDTH` validity gate upstream is unchanged — this only re-bases the score. | `SCORE_BOX_TIGHTNESS = 22`, `TIGHTNESS_ADR_AWARE`, `MAX_BOX_WIDTH_ADR = 4.5`, `CANDLE_SPREAD_*` |
| **Touch density** | `min(touches × 2, 15)` plus `+10` if `r_touches ≥ 3 AND s_touches ≥ 3` OR `total ≥ 6` | `SCORE_TOUCH_DENSITY = 25` (15 base + 10 bonus); `TOUCH_BONUS_INDIVIDUAL = 3`, `TOUCH_BONUS_TOTAL = 6`, `TOUCH_BONUS_POINTS = 10` |
| **Traversal quality** | `clamp((density / 0.33) × 10, 10) − clamp((dwell_asymmetry + max(0, max_swing_frac − 1)) × 8, 8)`, floored at 0, where `density = n_full_traversals / n_swings`. Rewards a box whose swing limbs genuinely run rail-to-rail; docks dead-space framings that hang off one rail (`dwell_asymmetry`) or anchor a rail on a one-off spike (`max_swing_frac > 1`). The overshoot term is zeroed for a tight box (`box_width ≤ BASE_AGE_DEADSPACE_WIDTH`) or a confirmed spring (`has_spring`) — there an oversized limb is inevitable (any real swing dwarfs a tiny range, e.g. PRA) or a bullish undercut, not dead space; the `dwell_asymmetry` dock still applies. Replaced the rail-blind **oscillation** term (which a one-sided top-hug maxed just like a true two-sided box). | `SCORE_TRAVERSAL_QUALITY = 10`, `TRAVERSAL_QUALITY_DENSITY_FULL = 0.33`, `TRAVERSAL_QUALITY_DWELL_PENALTY = 8` |
| **ATR squeeze** | `(1 - ATR_10/ATR_50 at bar -6) × 8` | `SCORE_ATR_SQUEEZE = 8` |
| **LPS tightness** | `(1 - tightness_ratio) × (20 × 2)` | `SCORE_LPS_TIGHTNESS = 20` |
| **Volume contraction** | `vol_contraction × (20 × 2)` | `SCORE_VOL_CONTRACTION = 20` |
| **Base age** (only if `base_len > MIN_BASE_DAYS`) | `sqrt(base_len / BASE_AGE_CAP_DAYS) × 22`. Hits ~50% at 30d, ~71% at 60d, 100% at 120d. **Dead-space dock:** a WIDE base (`box_width > BASE_AGE_DEADSPACE_WIDTH`) that did not work rail-to-rail (`traversal_density < TRAVERSAL_QUALITY_DENSITY_FULL`) scales its age credit by the achieved density fraction (`traversal_density / TRAVERSAL_QUALITY_DENSITY_FULL`, capped at 1) — long "cause" only counts if the base actually traversed; tight boxes are exempt. | `SCORE_BASE_AGE = 22`, `BASE_AGE_CAP_DAYS = 120`, `BASE_AGE_DEADSPACE_WIDTH = 0.06` |
| **Strong-uptrend bonus** — **DEMOTED to measure-only (weight 0) 2026-07-25, operator-authorized** | Was a linear ramp (`0` below 30% YoY return, full at 60%+). Both edge reads graded the archived sub-score HARMFUL (corr −0.19 with forward returns at n=1977, `docs/edge_read_2026-07-22.md`): momentum context was hurting the ranking. The ramp still computes (weight 0 → 0 points) and the RAW input is now archived (`yearly_return` column, model-only) so a regime-spanning revisit can re-open the question with evidence. | `SCORE_UPTREND_BONUS = 0` (was 15), `MIN_STRONG_YEARLY_RETURN = 0.30`, `MAX_STRONG_YEARLY_RETURN = 0.60` |
| **Soft RS bonus** — **DEMOTED to measure-only (weight 0) 2026-07-25, operator-authorized** | Was `min(1, excess_return_6m / 0.30) × 15`. The worst term in the book on both edge reads (corr −0.22 at n=1977). Raw signal stays archived (`excess_return_6m`). | `SCORE_RS_BONUS = 0` (was 15), `RS_LOOKBACK_BARS = 126`, `RS_MAX_EXCESS_RETURN = 0.30` |
| **52w-high proximity** | Linear ramp from `0` at −20% below 52w high to full at −5% (or higher). Bases that consolidate near recent highs hold their breakouts more reliably than ones rebuilding from deep drawdowns. | `SCORE_52W_HIGH_PROXIMITY = 8`, `HIGH_PROXIMITY_FULL_PCT = -0.05`, `HIGH_PROXIMITY_ZERO_PCT = -0.20` |
| **Market-breadth bonus** | Linear ramp on % of universe with `Close > SMA_50`. Zero below 35%, full at 60%+. Same value for every setup in a run (it's a market-wide scalar), but a strong-tape setup is structurally a better trade than the same chart in a defensive regime where most stocks are under their SMA_50. | `SCORE_BREADTH_BONUS = 8`, `BREADTH_FULL_PCT = 0.60`, `BREADTH_ZERO_PCT = 0.35` |
| **VCP contraction** | `contraction_quality × 12`, where quality ∈ [0,1] from `measure_contractions()` (see below) = `0.40·count + 0.35·progressive_tightening + 0.25·final_tightness`. Captures the Minervini VCP *process* (each pullback tighter than the last), distinct from box-tightness/ATR-squeeze which only see *static* tightness. | `SCORE_CONTRACTION = 12`, `CONTRACTION_IDEAL_MIN/MAX = 2/6`, `CONTRACTION_FINAL_TIGHT_PCT = 0.03`, `CONTRACTION_FINAL_LOOSE_PCT = 0.12` |
| **Ascending support** | `support_quality × 8`, where quality ∈ [0,1] from `measure_support_slope()` (see below) = `0.6·slope_score + 0.4·higher_low_frac`. Rewards a base whose swing lows stair-step *up* (rising support / tennis-ball action). Bonus-only — a flat or sagging floor earns 0, never penalized. | `SCORE_ASCENDING_SUPPORT = 8`, `ASCENDING_SUPPORT_FULL_SLOPE = 0.10` |
| **ADR% absolute volatility** | `adr_quality × 8`, where `adr_quality = min(ADR% / 5.0, 1.0)`. Rewards Qullamaggie-style volatile movers: stocks that travel enough each day to be worth trading. Bonus-only — low-ADR names earn 0, never a penalty. | `SCORE_ADR = 8`, `ADR_WINDOW = 20`, `ADR_FULL_PCT = 5.0` |
| **Puzzle quality** (E3, live) | `puzzle_quality × 8` — the L2 assembled-Wyckoff-puzzle completeness/chronology grade from `assemble_box_narrative()` (see [The L2 event reader](#the-l2-event-reader--wyckoff-puzzle-from-rail-events-to-a-scored-narrative)). Additive, bonus-only, clamped `[0, cap]`; grades-not-vetoes (≥ 0, can only raise a score). | `SCORE_PUZZLE_QUALITY = 8`, `PUZZLE_SCORE_ENABLED` (folded 2026-07-18) |

**Tier mapping** — `calculate_tier()`. Calibrated against the live archive distribution (mean ~95, max ~126 under the prior weights; with the new bonuses added, S now sits at roughly the top quartile rather than catching 75% of all setups):

| Tier | Threshold | Setting |
|------|-----------|---------|
| **S** | `score ≥ 110` | `TIER_S = 110` |
| **A** | `score ≥ 95` | `TIER_A = 95` |
| **B** | `score ≥ 75` | `TIER_B = 75` |
| **C** | `score ≥ 55` | `TIER_C = 55` |
| **D** | else | — |

> **S-tier width cap.** A base wider than `S_MAX_BOX_WIDTH = 0.15` cannot be S no matter how high it scores — a wide range, however long or well-touched, is not an elite setup; `calculate_tier(score, box_width)` demotes it to A on merit.

---

## VCP Progressive-Contraction Footprint

`measure_contractions()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures the **defining Minervini VCP signature** — a sequence of 2–6 pullbacks each tighter than the last (e.g. 18%→12%→6%) ending in a tight final coil. This is the *process* of tightening, which `box_width` / `atr_squeeze` (static tightness) cannot see.

It reuses the Phase B zigzag machinery over the base window: each peak→valley downswing is one contraction, `depth = (peak − valley) / peak`. The initial BC→AR descent into the base is excluded by design (it's the entry into the base, the early-chop the `cand_start` trim already removes).

`quality ∈ [0,1] = 0.40·count_score + 0.35·progressive + 0.25·final_tight`:
- **count_score** — full credit for 2–6 contractions (Minervini's range, 3–4 typical); partial for 1 or for an over-count (choppy, not a clean coil).
- **progressive** — fraction of consecutive contractions that don't widen (5% tolerance); 1.0 = textbook monotonic tightening.
- **final_tight** — ramp on the rightmost contraction depth: full ≤ 3%, zero ≥ 12%.

**Volume across the contractions (`vol_trend`).** In the same pass, the mean volume of each contraction's bars is captured and scored into `vol_trend ∈ [0,1] = 0.5·progressive_decline + 0.5·final_is_lightest` (`None` with < 2 contractions) — the Minervini nuance that volume should dry up step by step, lightest at the final coil. This is **measured only**: it is deliberately NOT folded into `quality`, so the contraction sub-score, the tiers, and the VCP-Coil tag are byte-for-byte unchanged (verified against the shadow-output guard). Archived raw as `contraction_vol_trend` to validate against forward returns before it is allowed to matter (or to surface on the tag).

Persisted to the archive as `contraction_count`, `contraction_quality`, `final_contraction_depth`, `contraction_vol_trend`, and the `score_contraction` sub-score. The frontend 🌀 **VCP Coil** tag chip currently fires when `score_contraction` reaches 80% of its sub-score cap. Scored, not gated — measure-first, like the touch-volume signature.

---

## Base Bar Compression Footprint

`measure_bar_compression()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures the **texture inside the detected box**: whether the bars themselves are quiet / low-spread, not just whether R/S are close together. This is distinct from `box_width` (range tightness) and `atr_ratio` (ATR squeeze) because a narrow box can still contain sloppy wide bars.

It reports four raw diagnostics, all persisted to the archive and not scored:

| Field | Meaning |
|-------|---------|
| `base_median_spread_atr` | median base bar spread divided by the ATR snapshot used by the LPS detector |
| `base_p80_spread_atr` | 80th percentile base bar spread divided by that ATR snapshot |
| `base_median_spread_pct_box` | median base bar spread divided by box height (`R - S`) |
| `base_tight_bar_pct` | share of base bars whose spread is no wider than the ATR snapshot |

This is **measure-first / never-gated / never-penalizing**. It gives the archive a direct way to test whether visually quiet bases outperform choppier bases with similar box width.

---

## Ascending Support / Higher-Lows Footprint

`measure_support_slope()` ([engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) measures whether the base's swing lows are **stair-stepping up** — the Minervini "tennis-ball action" / Qullamaggie "higher lows surfing the rising EMA" footprint. A flat box with a *rising floor* is a stronger coil than a flat box with a flat/sagging floor: demand is getting more aggressive into each pullback.

It reuses the same Phase B zigzag as the contraction metric, but reads the **valley** sequence. It fits a least-squares line through the `(bar_index, valley_low)` points and ATR-normalizes the slope so it's comparable across price levels and tickers.

`quality ∈ [0,1] = 0.6·slope_score + 0.4·higher_low_frac`:
- **slope_score** — linear ramp of the ATR-normalized slope from 0 (flat/descending → 0) to `ASCENDING_SUPPORT_FULL_SLOPE` (0.10 ATR/bar → 1.0).
- **higher_low_frac** — fraction of consecutive valley pairs that actually step up (consistency of the higher-lows).

Needs ≥ 2 zigzag valleys; otherwise returns neutral (quality 0). Persisted as `support_slope_atr`, `ascending_support_quality`, and the `score_ascending_support` sub-score. The frontend 📈 **Ascending Support** tag chip currently fires when `score_ascending_support` reaches 80% of its sub-score cap. **Bonus-only / measure-first** — a flat or descending floor earns 0 points and is never penalized.

---

## ADR% Absolute Volatility

`adr_pct()` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py)) measures Qullamaggie-style Average Daily Range % over the latest full tape, not just the consolidation window:

```
ADR%(20) = 100 × (mean(High / Low over the last 20 bars) - 1)
```

This captures the stock's **absolute volatility character**: a high-ADR stock resting in a tight base is a stronger momentum-continuation candidate than a low-range stock with the same visual structure. The metric is guarded at source: insufficient history, zero lows, NaN/Inf, or malformed ranges return `0.0`, so the dashboard payload never receives non-finite values from ADR.

Scoring uses `adr_quality = min(ADR% / ADR_FULL_PCT, 1.0)`, with full credit at `ADR_FULL_PCT = 5.0`. Persisted as `adr_pct` and the `score_adr` sub-score. The frontend ⚡ **High ADR** tag chip currently fires when `score_adr` reaches 80% of its sub-score cap. **Bonus-only / measure-first** — quiet names earn 0 points and are never filtered or penalized.

---

## Volume Signature Around Touches

After the consolidation passes, `_evaluate_ticker` computes two diagnostic z-scores using the base's own volume distribution as baseline:

```
touch_band = TOUCH_TOLERANCE_ATR × ATR_10
r_touch_vol_z = (mean_vol_at_R_touches − mean_base_vol) / std_base_vol
s_touch_vol_z = (mean_vol_at_S_touches − mean_base_vol) / std_base_vol
```

These don't gate anything — they're persisted to the archive (`r_touch_vol_z`, `s_touch_vol_z`) and surface as Wyckoff-classic interpretation tags on the frontend card. Those chip thresholds live in `webapp/frontend/src/components/setupTagsData.js`, not Python settings:

| z-score signature | Tag chip | Meaning |
|---|---|---|
| `r_touch_vol_z < -0.30` | 🤫 No Supply | Resistance tested on below-average volume — buyers absorbed silently, textbook precursor to a clean breakout |
| `s_touch_vol_z > +0.30` | 💪 Demand at S | Support tested on above-average volume — buyers stepping in at S, selling absorbed. **Not a spring** — a spring is the measured Phase C undercut-and-recover event (`bin_c_type = SPRING`), and an active undercut LPS still shows as `REBOUND`. |
| `r_touch_vol_z > +0.50` | ⚠️ Heavy Resistance | Resistance tested on ABOVE-average volume — supply hitting the bid every time, distribution-flavored, breakout risk |

The "Heavy Resistance" tag is the only *warning* tag in the system — designed to surface even when other positive tags would otherwise crowd it out (it carries higher `weight` in the tag-ordering than even Phase D).

These are bookkeeping (not score gates) intentionally: the volume signature at touches is a real Wyckoff axis but its predictive power needs to be measured in the archive before we make it a hard gate or a score component. Phase 2 archive analysis will tell us which thresholds actually matter and at what magnitude.

---

## Region (Bin) Features & Trend Template (Stage 2A)

Two measure-only layers. Both are **descriptive, never scored and never gated** —
every value is an underscore-prefixed result field persisted to the archive
(nullable, backward-compatible) so a later calibration pass can test whether any
of it predicts forward returns. Scoring (15 components, max ~209) and the tier
thresholds are **unchanged**.

### Bin features — "where am I in the base?"

`measure_phases()` ([engine_alpha/structure/phase_features.py](../engine_alpha/structure/phase_features.py))
slices an already-detected base into its named regions and reports raw size,
price-range, and volume character per region. It detects nothing new — it
consumes anchors the detector + LPS finder already produced.

| Region | Span | What it is |
|--------|------|------------|
| **A — climax event** | `bc_anchor_bar → phase_a_end_bar` | the BC/SC → AR trend-exhaustion lead-in |
| **B — working base** | the validated box (`base_df`) | the cause-building equilibrium |
| **D — Phase D** | the right-most region | earliest credible right-side evidence after the spring/search floor: support-test cluster, inner mini-consolidation, or recovered V-tip; else the LPS fallback |
| **LPS** | the exact LPS candidate bars | the Last Point of Support itself |

Per region: `_bin_{a,b,d}_bars`, `_bin_{a,b,d}_range_pct` ((maxHigh−minLow)/minLow),
`_bin_{a,b,d}_volume_ratio` (region mean volume ÷ trailing-50 mean). Plus:

- `_bin_lps_bars`, `_lps_position_in_box` ((lps_low − S)/(R − S): 0 = floor, 1 = ceiling);
- `_bin_d_vs_b_range_ratio` / `_bin_d_vs_b_volume_ratio` — is Phase D
  tighter / quieter than the base it sits in? (the VCP "coil into launch" read);
- `_bin_d_support_slope_atr`, `_bin_d_higher_low_frac`,
  `_bin_d_ascending_support_quality`, and
  `_bin_d_vs_b_support_quality_delta` — is the right side stair-stepping higher
  more clearly than the base as a whole?
- `_bin_d_boundary_source` — `support_tests` (a right-side support-test cluster),
  `sos_reclaim`, `rising_support`, `inner_box` (a real detected
  mini-consolidation), `v_tip` (the final recovered late-base low), or `lps`
  (the mandatory gate / fallback). Spring recovery only floors the search; it is
  not itself a boundary source.
- `_phase_d_evidence_json` — serialized evidence detail: floor marks, all
  candidate evidence signals, and the selected source/bar. The frontend overlay
  uses this when present and falls back to `_bin_d_boundary_source` otherwise.

**Phase-D boundary is single-sourced.** The Phase-D start uses the *same* rule
the narrative, bin measurement, and scoping overlay draw — all call
`phase_d.resolve_phase_d_boundary()` through thin wrappers — so the measured
Phase-D bin and the drawn Phase-D band can never drift apart. Any region the
engine can't place confidently (e.g. no LPS window) is emitted as `None`; young
bases legitimately have fewer regions.

### Last Supper stretch

**What a Last Supper is (operator's definition).** The **final run-up that traps
late buyers before the real pullback** — a last deceptive rally that lures in late
longs, after which price gives back into the *real* pullback and only then resumes.
It is a discrete **event**, can appear **before *or* after an LPS** (Phase D holds
more than one), and setups often break out *after* the Last Supper has run its
course. The engine does **not** label the run-up as a timed event — it measures the
over-extension *geometry* around the LPS (below).

**What the engine measures is the over-extension geometry.** Two raw families say
how exposed *this* entry is to a Last Supper. A precise, well-positioned LPS (near
support, off a rebound, after a Phase-C spring) survives a Last Supper; a stretched
one is the trap.

*Stretch* — how far the LPS foot sits *above the box that birthed it* (its energy source):

- `_lps_stretch_atr` = `(lps_low − R) / ATR` — distance above the ceiling, in ATR;
- `_lps_stretch_box` = `(lps_low − R) / (R − S)` — same, in box-heights.

≤ 0 means the LPS formed in or below the box (no stretch); a large positive value
flags a stretched, Last-Supper-risk LPS far from its energy source.

*Event geometry* (`engine_alpha/structure/phase_features.py` →
`_last_supper_measurements`) — the run-up-and-flush around the LPS:

- `_last_supper_pullback_from_extension_pct` = `(anchor_high − lps_low) /
  anchor_high` — depth of the pullback from the trapping run-up's high
  (`anchor_high` = the High at the elected LPS anchor bar) down to the LPS low;
- `_last_supper_reclaim_quality` ∈ [0,1] — how much of that pullback the LPS
  reclaimed (final close vs the LPS low, over the swing), averaged with the final
  bar's spread contraction (did it recover cleanly — the "popping off *after* the
  Last Supper" tell);
- `_last_supper_source_box_age` = bars from when price left the source box (rose
  above R) to the LPS low — over-extension in *time* from the energy source; set
  only when the LPS sits above R.

All raw, archived **measure-first** — never gated or scored until validated against
the durable-win vs cash-grab outcome.

### Inner-origin measurements

The selected inner Phase-D range also records how it was born:

- `_inner_source` = `midpoint` or `inner_climax`, describing which best-of-both
  search origin produced the selected inner box;
- `_inner_search_start_bar` = the df bar where that winning inner search began;
- `_inner_climax_bar` / `_inner_reaction_bar` = the detected mini-BC -> mini-AR
  swing when `_inner_source = inner_climax`;
- `_inner_reaction_pct` / `_inner_reaction_bars` = depth and duration of that
  reaction.

These are descriptive archive fields only. They let the calibration report learn
whether inner boxes born from a real mini-climax behave differently from midpoint
heuristic boxes before any later scoring or anchoring change is considered.

### Minervini Stage-2 trend template

`trend_template()` ([engine_alpha/structure/indicators.py](../engine_alpha/structure/indicators.py))
records the classic price/MA leadership template as raw context, computed
self-contained from the daily frame:

1. price > SMA_150 and > SMA_200; 2. SMA_150 > SMA_200; 3. SMA_200 rising over
~1 month (21 bars); 4. SMA_50 > SMA_150 > SMA_200; 5. price > SMA_50; 6. price
≥ 30% above the 52-week low; 7. price within 25% of the 52-week high.

Fields: `_stage2_ma_stack_pass`, `_stage2_ma200_slope_1m_pct`,
`_stage2_52w_low_pct`, `_stage2_trend_pass_count` (0–7), `_stage2_trend_pass`
(all 7). Minervini's 8th criterion (RS rating ≥ 70, a *universe percentile*) is
**deliberately omitted** — Chrollo measures relative strength SPY-relatively via
`excess_return_6m` and does not compute a universe rank — so the count is out of
7. Context only; no gate, no score.

All Stage-2A fields persist to `setup_archive` (writer + seed parity) and are
surfaced by `core/archive/analyze.py` in the fingerprint + correlation sections.

---

## Outputs

`_evaluate_ticker()` returns one dict per qualifying ticker. Public fields surfaced to terminal/dashboard: `Ticker`, `Tier`, `Setup`, `Score`, `Current Price`, `Base Len`, `Box Width`, `Touches`, `ATR Ratio`, `LPS Length`, `Breach Days`. Underscore-prefixed fields feed the chart renderer and the archive but are not displayed in the terminal.

Important structure payloads:

- Box/rail fields: `_R`, `_S`, `_r_anchor_bar`, `_s_anchor_bar`, `_phase_a_start_date`, `_phase_a_end_date`, `_phase_b_start_date`, `_phase_d_start_date`.
- LPS geometry: `_lps_offset`, `_lps_len`, `_trigger_price`, `_lps_zone_type`, `_lps_descent_frac`, `_lps_high_descent_frac`, `_lps_profile_unit`, `_lps_pullback_profile`, `_lps_first_high`, `_lps_last_low`, `_lps_window_high`, `_lps_window_low`.
- Inner/Phase-D fields: `_phase_d_inner`, `_lps_in_inner`, `_inner_*`, `_bin_d_boundary_source`, `_phase_d_evidence_json`.
- Scoring/archive helpers: `_sub_scores`, `_r_touch_vol_z`, `_s_touch_vol_z`, `_stage2_*`, `_bin_*`, `_trav_*`, `_eq_*`.

The read-only scoping payload is also underscore-prefixed: `_phase_a_start_date`, `_phase_a_end_date`, `_phase_b_start_date`, `_phase_d_start_date`, optional `_phase_c_event_date`, `_lps_zone_low`, `_lps_zone_high`, `_lps_zone_start_date`, `_lps_zone_end_date`, `_has_mini_consolidation`, `_scope_confidence`, and `_phase_d_evidence_json`. These fields are visualization/diagnostic facts only; no downstream filtering or scoring consumes them.

Pipeline returns `(results_df, market_data, tickers, market_context)` — `results_df` is sorted by `Score` descending.

Every scan also writes timing telemetry:

- `cache_meta.json["scan_metrics"]` — latest run summary.
- `output/scan_metrics.jsonl` — append-only history, one JSON record per scan.
- `market_context["_scan_metrics"]` — included in `output/screener_data.json`.

The phase timings are `ticker_universe`, `market_data_fetch`, `frame_prep`,
`market_context`, `evaluation`, and `result_assembly`; counts include the loaded
universe size, evaluated ticker-frame count, and setup count.

---

## Archive System

The screener writes every output to a SQLite-backed setup archive (`webapp/backend/trading_journal.db`, `setup_archive` table) so we can build a regression dataset of structural fingerprints + forward outcomes.

### `archive.writer.archive_scan_results()` ([core/archive/writer.py](../core/archive/writer.py))
- Called automatically after each screener run.
- Upserts on `(ticker, scan_date)` — re-running the same day updates rather than duplicates.
- `autoflush=False` on the session: avoids the "database is locked" path where a per-row existence query would auto-flush pending UPDATEs while the webapp holds a read lock.
- Attaches **market context** to every row: `spy_trend`, `vix_level`, `sector_etf`, `sector_trend` (sector ETF mapped per ticker, 50d trend pulled at scan_date). Sector lookups are cached per ticker within a run.

### `seed_archive()` ([core/archive/seed.py](../core/archive/seed.py))
- Bootstrap mechanism for known-winner setups defined in `SEED_SETUPS = [(ticker, trigger_date), ...]`.
- For each pair, scans `[trigger_date - 10d, trigger_date + 3d]` to find which day the screener actually fired (LPS is identified *before* the breakout), keeps the highest-scoring hit.
- Re-runs the full Phase 1–4 pipeline at that historical date via `_evaluate_at_date()` (a ported copy of `_evaluate_ticker` that works on a pre-sliced DataFrame).
- Computes forward returns immediately (we have the future data already).
- Tags rows with `source="seed"`, `quality_label="perfect"` to distinguish from live scans.
- CLI: `python -m core.archive.seed [--force]`.

### `update_forward_returns()` ([core/archive/forward_returns.py](../core/archive/forward_returns.py))
- Backfills outcome data for archive rows older than `--min-age` calendar days (default 5).
- For each setup, downloads OHLC after `scan_date` and computes via `_compute_returns()`:
  - **Forward returns:** `fwd_return_1d`, `5d`, `10d`, `20d`, `60d` (close-to-close from `scan_close`).
  - **MFE/MAE:** maximum favorable / adverse excursion at 20d and 60d windows.
  - **Trigger status:** `triggered = 1` if any forward `High >= trigger_price`, plus `trigger_date`.
- By default skips rows that already have `fwd_return_1d` populated; `--force` re-computes everything.
- CLI: `python -m core.archive.forward_returns [--min-age N] [--force]`.

---

## Settings Quick-Reference

<!-- BEGIN GENERATED: settings-quick-reference -->
_Generated from the frozen engine-identity allow-list
(`engine_alpha/freeze/manifest.ENGINE_SETTINGS_KEYS`) — every constant that can move a
detector decision, in manifest order, with its live `config/settings.py` value.
Regenerate with `python -m tools.settings_reference --write`;
`tests/test_docs_sync.py` fails the suite when this block drifts._

_engine_config_version: `f00560248c3b6d43289ffb254531b0bc343eb490ed6192aa3f4cc260a4ce2e7b`_

```text
DATA_DIVIDEND_ADJUSTED = False
MIN_PRICE = 3.0
MIN_VOLUME_50D = 50000
MIN_YEARLY_RETURN = -0.2
MIN_BASE_DAYS = 20
MAX_BOX_WIDTH = 0.18
CRASH_FILTER_MULT = 0.7
EXTENSION_FILTER_MULT = 1.15
PIVOT_ORDER_SHORT = 1
PIVOT_ORDER_LONG = 2
PIVOT_ORDER_THRESHOLD = 40
PIP_MACRO_K_MAX = 24
PIP_MACRO_MAX_POST_EXCESS = 0.25
PIP_MACRO_MIN_BASE_BARS = 20
PIP_MACRO_EQ_FLOOR_FRAC = 0.5
PIP_MACRO_EQ_OSC_FRAC = 0.3
PHASE_A_CLIMAX_TERMINALITY_EXCESS = 0.25
AR_FIRST_REACTION_ENABLED = False
AR_RETRACE_FRAC = 0.5
AR_UP_LEG_LOOKBACK = 40
AR_BOUNCE_ATR_MULT = 1.5
AR_BOUNCE_DROP_FRAC = 0.5
CAUSE_BEFORE_EFFECT_VETO_ENABLED = True
CAUSE_LPS_LOOSE_MAX = 0.9
BOUNDARY_ATR_BUFFER = 0.5
MAX_CONSECUTIVE_OUTSIDE_DAYS = 10
MIN_BOUNDARY_RESPECT_PCT = 0.8
TOUCH_TOLERANCE_ATR = 0.5
EQ_MIN_TOUCHES_PER_RAIL = 3
EQ_MIN_TOUCH_THIRDS = 2
EQ_MIN_HALF_DWELL = 0.15
EQ_MAX_MID_DWELL = 0.45
EQ_MIN_COVERAGE = 0.8
EQ_COVERAGE_BINS = 6
EQ_COVERAGE_MIN_FRAC = 0.03
TRAVERSAL_NOISE_FRAC = 0.15
TRAVERSAL_FULL_FRAC = 0.55
TRAVERSAL_LOW_ZONE = 0.3
TRAVERSAL_HIGH_ZONE = 0.7
TRAVERSAL_MIN = 2
TRAVERSAL_MIN_DENSITY = 0.08
DESCENT_TAIL_LSF_MAX = 0.4
DESCENT_TAIL_CFP_MIN = 0.2
SOS_TRIM_MIN_RUN = 3
SOS_TRIM_MIN_PREFIX_FRAC = 0.3
SOS_NEAR_R_MAX_BOX = 1.5
SOS_HOLD_MAX_RANGE_BOX = 0.55
TREND_MIN_GAIN_PCT = 0.15
TREND_MIN_MOVE_BARS = 20
TREND_PRIOR_LOOKBACK = 100
LOCAL_PEAK_BARS = 30
ROOT_TREND_SMA = 200
PHASE_B_ATR_WINDOW = 30
AR_MIN_DROP_PCT = 0.05
AR_MAX_BARS = 15
LPS_MIN_DESCENT_FRAC = 0.0
LPS_MIN_HIGH_DESCENT_FRAC = 0.0
LPS_MAX_WINDOW_BOX_RANGE = 0.85
LPS_OVERSHOOT_WINDOW_ATR_ENABLED = True
LPS_OVERSHOOT_WINDOW_ATR_MULT = 2.0
LPS_RESCUE_MAX_ADVANCE_BOX = 0.21
LPS_INSIDE_HIGH_EXTENSION_BOX_MAX = 0.35
LPS_INSIDE_HIGH_EXTENSION_ATR_MAX = 0.75
LPS_SCAN_OFFSET_MAX = 7
LPS_LENGTH_MIN = 2
LPS_LENGTH_MAX = 7
LPS_HOLD_TOLERANCE = 0.95
LPS_PROFILE_BOX_FRACTION_FLOOR = 0.15
LPS_PULLBACK_PROFILE_MIN = 0.4
LPS_PULLBACK_PROFILE_MIN_OVERSHOOT_R = 1.25
LPS_PULLBACK_PROFILE_MAX = 4.5
LPS_TERMINAL_LOW_TOL_PROFILE = 0.1
LPS_SPREAD_MAX_PROFILE_MULT = 1.25
LPS_SPREAD_EXPANSION_MAX_PROFILE = 0.35
LPS_HOLDING_SHELF_ENABLED = True
LPS_SHELF_LENGTH_MIN = 3
LPS_SHELF_MIN_LOW_POS_BOX = 0.5
BAND_RAILS_ENABLED = True
BAND_MAX_BOX_WIDTH = 0.23
BAND_EVENT_MIN_BARS = 2
BAND_EVENT_MAX_DEPTH_ATR = 5.0
BAND_EVENT_MAX_BARS = 20
STORY_POOL_ENABLED = False
ELECTION_DETHRONE_ENABLED = True
ELECTION_DETHRONE_SESSIONS = 10
LPS_DRAW_MIN_DESCENT_FRAC = 0.4
LPS_ZONE_ATR_MULT = 0.5
BIN_C_UNDERCUT_ATR_MIN = 0.3
BIN_C_UNDERCUT_ATR_MAX = 3.0
BIN_C_UNDERCUT_BOX_MAX = 0.65
BIN_C_RECOVERY_BARS_MAX = 8
BIN_C_LINGER_BARS_MAX = 12
BIN_C_HOLD_BARS = 3
BIN_C_HOLD_TOL_ATR = 0.5
BIN_C_SIGNIF_UNDERCUT_ATR = 0.75
BIN_C_MIN_LINGER_BARS = 2
BIN_C_LATE_BOX_FRACTION = 0.5
PHASE_D_VTIP_LATE_FRACTION = 0.35
PHASE_D_VTIP_RECOVERY_BARS = 6
LPS_RANGE_PERCENTILE = 0.5
LPS_SPREAD_MUST_DECLINE = True
LPS_VOL_CONTRACTION_MAX = 0.87
STRUCTURE_EDGE_SKIP_BARS = 5
STRUCTURE_ATR_SAMPLE_OFFSET = 6
INNER_SEARCH_FRACTION = 0.5
INNER_TIGHTNESS_RATIO = 0.75
INNER_MIN_DAYS = 15
TIER_S = 110
TIER_A = 95
TIER_B = 75
TIER_C = 55
S_MAX_BOX_WIDTH = 0.15
SCORE_BASE_AGE = 22
BASE_AGE_CAP_DAYS = 120
BASE_AGE_DEADSPACE_WIDTH = 0.06
SCORE_TOUCH_DENSITY = 25
SCORE_VOL_CONTRACTION = 20
SCORE_LPS_TIGHTNESS = 20
SCORE_BOX_TIGHTNESS = 22
SCORE_ATR_SQUEEZE = 8
TIGHTNESS_ADR_AWARE = True
MAX_BOX_WIDTH_ADR = 4.5
CANDLE_GRADE_FLOOR = 0.55
CANDLE_SPREAD_BOX_CLEAN = 0.35
CANDLE_SPREAD_BOX_MESSY = 0.6
CANDLE_SPREAD_ATR_CLEAN = 0.9
CANDLE_SPREAD_ATR_MESSY = 1.4
CANDLE_TIGHTBAR_CLEAN = 0.65
CANDLE_TIGHTBAR_MESSY = 0.3
TA_SCORE_V2 = False
FUNDAMENTALS_ENABLED = False
FUNDAMENTALS_EARNINGS_HISTORY_LIMIT = 12
FUNDAMENTALS_FILING_LAG_DAYS = 75
RS_LINE_ENABLED = False
RS_LINE_NEW_HIGH_LOOKBACK = 252
SECTOR_RANKING_ENABLED = False
SECTOR_RANKING_LOOKBACKS = (21, 63, 126)
RS_RATING_LOOKBACK = 252
SCORE_PUZZLE_QUALITY = 8.0
PUZZLE_W_COMPLETENESS = 0.7
PUZZLE_W_CHRONOLOGY = 0.3
PUZZLE_CHRONO_PARTIAL = 0.5
EVENT_MAP_ENABLED = False
ELECTION_STABILITY_ENABLED = False
ELECTION_STABILITY_LOOKBACK = 3
ENGAGEMENT_MAX_EXCURSION_ATR = 1.5
SCORE_TRAVERSAL_QUALITY = 10
TRAVERSAL_QUALITY_DENSITY_FULL = 0.33
TRAVERSAL_QUALITY_DWELL_PENALTY = 8
MIN_STRONG_YEARLY_RETURN = 0.3
MAX_STRONG_YEARLY_RETURN = 0.6
SCORE_UPTREND_BONUS = 0
SCORE_RS_BONUS = 0
RS_LOOKBACK_BARS = 126
RS_MAX_EXCESS_RETURN = 0.3
SCORE_52W_HIGH_PROXIMITY = 8
HIGH_PROXIMITY_FULL_PCT = -0.05
HIGH_PROXIMITY_ZERO_PCT = -0.2
SCORE_BREADTH_BONUS = 8
BREADTH_FULL_PCT = 0.6
BREADTH_ZERO_PCT = 0.35
SCORE_CONTRACTION = 12
CONTRACTION_IDEAL_MIN = 2
CONTRACTION_IDEAL_MAX = 6
CONTRACTION_FINAL_TIGHT_PCT = 0.03
CONTRACTION_FINAL_LOOSE_PCT = 0.12
SCORE_ASCENDING_SUPPORT = 8
ASCENDING_SUPPORT_FULL_SLOPE = 0.1
ADR_WINDOW = 20
SCORE_ADR = 8
ADR_FULL_PCT = 5.0
TOUCH_BONUS_INDIVIDUAL = 3
TOUCH_BONUS_TOTAL = 6
TOUCH_BONUS_POINTS = 10
HTF_CONTEXT_ENABLED = True
DAILY_STRUCTURE_PERIOD = '2y'
HTF_STAGE_MA = 30
HTF_STAGE_MA_SLOPE_BARS = 4
HTF_WEEKLY_WINDOWS = {'MIN_BASE_DAYS': 6, 'STRUCTURE_EDGE_SKIP_BARS': 1, 'TREND_MIN_MOVE_BARS': 5, 'TREND_PRIOR_LOOKBACK': 26, 'LOCAL_PEAK_BARS': 8, 'ROOT_TREND_SMA': 30, 'PHASE_B_ATR_WINDOW': 8, 'AR_MAX_BARS': 4, 'MAX_CONSECUTIVE_OUTSIDE_DAYS': 3, 'PIVOT_ORDER_THRESHOLD': 12, 'EQ_MIN_TOUCHES_PER_RAIL': 2, 'LPS_SCAN_OFFSET_MAX': 2, 'LPS_LENGTH_MIN': 1, 'LPS_LENGTH_MAX': 4, 'BIN_C_RECOVERY_BARS_MAX': 3, 'BIN_C_LINGER_BARS_MAX': 4, 'BIN_C_HOLD_BARS': 1, 'BIN_C_MIN_LINGER_BARS': 1, 'PHASE_D_VTIP_RECOVERY_BARS': 2}
HTF_MONTHLY_WINDOWS = {'MIN_BASE_DAYS': 4, 'STRUCTURE_EDGE_SKIP_BARS': 1, 'TREND_MIN_MOVE_BARS': 3, 'TREND_PRIOR_LOOKBACK': 12, 'LOCAL_PEAK_BARS': 4, 'ROOT_TREND_SMA': 10, 'PHASE_B_ATR_WINDOW': 6, 'AR_MAX_BARS': 3, 'MAX_CONSECUTIVE_OUTSIDE_DAYS': 2, 'PIVOT_ORDER_THRESHOLD': 8, 'EQ_MIN_TOUCHES_PER_RAIL': 2, 'LPS_SCAN_OFFSET_MAX': 1, 'LPS_LENGTH_MIN': 1, 'LPS_LENGTH_MAX': 2, 'BIN_C_RECOVERY_BARS_MAX': 2, 'BIN_C_LINGER_BARS_MAX': 3, 'BIN_C_HOLD_BARS': 1, 'BIN_C_MIN_LINGER_BARS': 1, 'PHASE_D_VTIP_RECOVERY_BARS': 1}
```

_Ops / data-fetch knobs (cache TTLs, Yahoo rate limits, admission/quarantine,
scheduler, dashboard) are deliberately NOT part of the engine identity — see
the "DELIBERATELY EXCLUDED" block in
[engine_alpha/freeze/manifest.py](../engine_alpha/freeze/manifest.py)._
<!-- END GENERATED: settings-quick-reference -->

---

## Acceptable Misses

Per the user's standing guidance: setups on **young bases that break out fast** (KEYS, BRZU, NE, CGON-style) will not be caught by this engine and that is **by design** — the base-age requirement (`MIN_BASE_DAYS = 20`, plus the sqrt-scaled scoring up to 120 days) explicitly trades early-stage breakouts for higher-cause Wyckoff setups. These should not be treated as bugs to fix.

---

## Parent + Inner — Nested Phase D Range (live)

The live reader calls `find_inner_box()` ([engine_alpha/structure/bricks.py](../engine_alpha/structure/bricks.py)) after the parent equilibrium box validates. The brick mirrors the inner-search half of `detect_boxes()` ([engine_alpha/structure/consolidation.py](../engine_alpha/structure/consolidation.py)): it tries both the mechanical midpoint (`INNER_SEARCH_FRACTION = 0.5`) and the detected inner climax (`detect_inner_root_swing`), then keeps the tighter valid inner box. The inner must be meaningfully tighter (`bw_inner < INNER_TIGHTNESS_RATIO * bw_outer`, i.e. at least 25% tighter at the default 0.75) and span `INNER_MIN_DAYS = 15`+ bars. If no qualifying inner exists, `inner` is `None`; the parent still remains the base of record either way.

`detect_boxes()` remains available for diagnostics and tools. It is no longer the live screener entry point.

Inner ⊂ outer is enforced **temporally**, not in price space — the inner can sit inside, above, or below the outer's R/S; the outer's boundary-respect gate already filters out wild outliers, so an inner found in the outer's recent half is structurally adjacent regardless. **Operator ruling (2026-07-20):** "nested" means found in the *vicinity* of the parent at a more advanced point of the accumulation, never bounded by the parent's original rails — the range's contraction naturally forms a new mini process with its **own** R and S, and a mini-consolidation forming ON the parent's Resistance, treating it as its new Support, is a common variation (8/17 live inners sit partly above parent R — measured 2026-07-19, all sanctioned).

The key difference between `inner_zigzag` and `phase_b_zigzag`: the inner version scores each candidate over **its own** bar range (from the earlier of the two anchors onward) rather than the full inner window. Bars before the inner's first anchor were forming a different structure and would unfairly fail boundary-respect.

Historical backtest snapshots are calibration inputs, not permanent truth. When a missed visual winner clusters around a hard LPS gate, the next step is to measure that gate against forward outcomes before moving it into quality/selector evidence.

### Adaptive LPS geometry

The live LPS detector no longer hard-gates raw percent pullback depth. It uses a setup-profile unit so wide/spready bases get realistic absolute wiggle room while tight bases stay precise:

```
base_range_threshold = max(base spread quantile, 1.2 * ATR)
profile_unit = max(base_range_threshold, LPS_PROFILE_BOX_FRACTION_FLOOR * box_height)
pullback_profile = (anchor_bar_high - elected_lps_low) / profile_unit
```

The ordinary LPS low is the **last bar's Low**, the trigger is the **last bar's High**, and the candidate is actionable only while current price remains below that trigger. The terminal-low guard requires the last Low to sit within `LPS_TERMINAL_LOW_TOL_PROFILE` profile units of the window low. A fully clean down-swing can exceed the broad window-range guard because the useful measurement is the individual price-action swing from anchor high to final valley. Spread decline remains quality evidence; hard rejection is only "spread expanded too much for this setup profile."

**OVERSHOOT_R window rescope (`LPS_OVERSHOOT_WINDOW_ATR_ENABLED`, LIVE since
2026-07-16 — solve-the-engine task 10).** The window-localization guard
(`window_range ≤ LPS_MAX_WINDOW_BOX_RANGE × box_height`) mis-scales for a
breakout throwback resting ABOVE a **narrow** box: above the box, box height
is the wrong yardstick (CTOS's marked shelf measures 1.06 box-heights but
only 1.42 of the stock's own ATRs). Flag-on, for OVERSHOOT_R-zone windows
only, the denominator becomes `max(box_height,
LPS_OVERSHOOT_WINDOW_ATR_MULT × ATR)` (k = 2.0; k ≥ 1.67 admits CTOS).
Gate-only — the archived `window_range_pct_box` measure is unchanged;
`max()` can only grow the denominator, so wide boxes and INSIDE/UNDERCUT_S
zones are provably untouched; a non-finite ATR refuses the rescoped path.
Proof at the marks: combined with the holding-shelf flag, CTOS fires
2026-07-15 tier S at rails within tolerance (span overlap 1.0). At the live
flip the shadow fixture admitted ONE new fire — BBVA (tier A, the rescope's
narrow-box OVERSHOOT_R class) — and the operator's eyeball (2026-07-17)
ruled it **"just incomplete"**: nothing really going on. The dissection
agreed on the numbers, via cause maturity rather than the Phase-D label
(both BBVA and CTOS select a `v_tip` boundary): BBVA sat on a bare-minimum
20-bar base with 2 full traversals and 5R/4S touches; CTOS earned its
throwback with a 50-bar cause, 10 traversals, 16R/16S. **Hardening bound
(2026-07-17):** a throwback above R claims the cause below is COMPLETE, so
the rescoped ATR denominator only engages on a **matured cause** —
`base_len ≥ 2 × MIN_BASE_DAYS`, the same floor a terminal shakeout needs in
the boundary-event pool. Immature causes fall back to the raw window gate
(the pre-flip path, which already rejected them); knob-free, no new reject
key. BBVA's fixture frame is frozen as negative-corpus case
`BBVA@2026-06-05` ("incomplete throwback — immature 20-bar cause"); the
fixture drop was exactly BBVA, zero collateral (CTOS byte-identical).

The zone tolerance still adapts for tight boxes: if box width is below 10%, `_zone_tolerance()` uses `max(0.5 * ATR, 0.5 * box_height)`. This keeps tight inner boxes from rejecting reasonable breakout retests just above R or failed-seller tests just below S.

### Current calibration frontier

The reader should stay visually strict, but the LPS gates should be audited as
separate ideas: hard geometry, quality evidence, and active-setup selection.

**Post-LPS refutation (operator ruling 2026-07-17, measure-first — no gate
yet).** On the BBVA hardening eyeball the operator went deeper than the cause:
on that freeze the trend, AR, and base election are all CORRECT — the defect is
the **LPS pick standing refuted by the frame's own remaining bars**: "even in
the same snapshot, after said LPS we continue down as one prominent
movement/Down Swing — no way we can measure off an LPS when we know for a fact
that the price action continues down, and by a large margin." Verified: BBVA's
LPS window (bars 495–497, low 22.77) was followed in-frame by a break of the
window low (bar 498), a feeble bounce, and an edge close 1.0 ATR below the LPS
low and back BELOW R — the throwback claim was dead before the fire. The
`offset` allowance tolerates a stale LPS by TIME but never checks REFUTATION.
Next lever, measure-first per doctrine: archive on every fire the post-window
excursion below `window_low` (ATR units) and, for OVERSHOOT_R, whether R was
re-lost; calibrate any threshold from the archive + marks (the vol-0.87
method). The frozen corpus case `BBVA@2026-06-05` guards this exact frame
meanwhile.
`tools/lps_gate_audit.py --matrix lps-core` is the current scoreboard for this:
it can soften descent, volume, spread, terminal-low, and pullback-profile gates
individually and report which tickers would recover/drop. Volume contraction,
descent cleanliness, and zone/range tolerances are the next places to test
against forward outcomes before loosening or hardening anything.
