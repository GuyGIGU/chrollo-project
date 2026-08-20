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
> detection/scoring knobs in `config/settings.py`) **starts by reading this document —
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

> **Known gap between this model and the operator's eye (measured 2026-08-14).**
> Definition (2) above — the climax is the segment's *extreme pivot* — is not what
> the operator marks as a trend end, and the disagreement is directional rather
> than noisy. Against nine dated marks, `segment_trends` holds a terminal within
> 3 bars of his trend end on **2 of 9**, and the resolved `climax_bar` sits
> *earlier* than his trend end on **6 of 6** measurable names, never once later
> (median −50.5 bars). The mechanism follows from the definition: inside a
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
it is **not** the same shape as a Last Supper (the over-extended right side the warning
chip flags — a pullback from a run that already left the base behind). The two are
distinguished today only by the Last-Supper stretch measures; nothing grades the
after-shakeout LPS as its own form. Recorded as theory, unmeasured.

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
types each wave by its **terminal outcome**: a break above R that held near R with a
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

Above the geometry sits a second reading layer that does not move a single rail. Once the cascade has **elected** an equilibrium box, the L2 event reader ([engine_alpha/structure/box_events.py](../engine_alpha/structure/box_events.py), re-exported through [engine_alpha/structure/metrics.py](../engine_alpha/structure/metrics.py)) reads the in-box structure as *facts about a Wyckoff story* — a labeled staircase, independent rail-event zones, and their chronological assembly into the classic spring → SOS → LPS story. Like the trend model, it is **measure-only**: every function here reports what it sees and assigns no points, gates nothing, and moves no rail. It reads the box the engine **already elected** — never a re-detection — so its story is told over the same rails, start, and span everything else measures against.

The read is a pipeline of four stages. First, `read_box_staircase()` labels the in-box swing sequence: it composes the *same* calibrated significant-swing skeleton the traversal read uses (`_collapse_swings` on the order-1 zigzag, amplitude-filtered by `TRAVERSAL_NOISE_FRAC`) with the L0 labeller (`label_market_structure`), so the staircase swings *are* the worked-equilibrium swings. Each swing is annotated with its box-position (`box_pos`, 0 = S rail, 1 = R rail), a low/mid/high `zone`, and a `rail_event` (`touch_R`/`breach_R`, `touch_S`/`breach_S`, or `interior`) — one chronological HH/HL/LH/LL sequence the later events are read off.

Second, the two rails are measured **independently**. `measure_resistance_events()` walks the R-rail: every peak that turns in the high zone is a rail interaction, and consecutive higher-highs with no drop back to support between them are grouped into one *wave* that is typed by its **terminal outcome** — a break above R that held near R with a genuine mini-consolidation is an `SOS`, an advance that held far above R is `markup`, a run-up that failed back to support is a single `upthrust` (one false-break wave, not a string of SOS), and the in-between cases stay descriptive (`range` / `rejection` / `in_progress`). The Phase-D split is anchored on the structural **V** (the deepest staircase valley). `measure_support_tests()` is the S-rail sibling — deliberately *not* a mirror of the wave machinery — reporting each low-zone valley that touches S without a deep breach and then holds as a `test` (a deep breach-and-reclaim is left to the spring brick, so the two never double-emit).

Third, `read_box_events()` (over the shared chokepoint `_box_events_with_meta`) unifies these into one flat, deterministically-ordered list of independent zones, adding the calibrated **spring** brick (Phase C) and **LPS** brick (Phase D, gated purely on bar position — right of the V — never on an SOS existing). Each piece is detected on its own geometry and is never gated on another; the bricks come either from a measure-only re-detection or, when the scorer calls in, from the pieces the engine *actually elected* (including a tighter inner-box LPS), so the read describes what fired rather than a fresh parent-box guess.

Fourth, `assemble_box_narrative()` stitches the zones into the story in one linear pass. It picks the spine (`spring` → first `SOS` → `LPS`), tallies a raw `completeness` (0..4 distinct canonical pieces present — spring, SOS, LPS, held-test), reads a three-valued `chronology` (`intact` only when all three spine pieces are present *and* strictly bar-ordered spring < SOS < LPS, else `partial`/`absent`), derives the B/C/D phase spans off the shared V, and emits an explainable `trace`. Every one of these reads is descriptive — none is shaped as a pass/fail another layer could consume as a filter. A missing piece is reported, never fabricated.

The **only live consumer** is a bonus-only score term. Always on (folded 2026-07-18; formerly flag `PUZZLE_SCORE_ENABLED`), `_setup_quality()` in [engine_alpha/scoring/scoring.py](../engine_alpha/scoring/scoring.py) folds `completeness` and `chronology` into a single `[0, 1]` composite (they are correlated — an intact chronology is impossible without the full spine — so they never split into two double-counting terms), and `s_setup_quality` scales it by `SCORE_SETUP_QUALITY` (8.0) and clamps it into `[0, cap]`. It is strictly additive and `>= 0`: it can only ever *raise* a score. A missing, `None`, or malformed narrative reads a neutral `0.0`, so an absent story never demotes a setup below what its geometry already merits. Consistent with the whole reading model, **geometry is the only veto** — the Wyckoff story is graded confidence layered on top of it, never a gate.

#### The Event Map — the mechanical swing layer (whole-frame)

The Event Map ([engine_alpha/structure/event_map.py](../engine_alpha/structure/event_map.py), `read_swing_map`) widens the L2 staircase's calibrated swing skeleton from the elected box's window to the **whole evaluation frame**, so the pre-box trend and the box story are read on one substrate. It stands up no second skeleton: **one** order-1 pivot walk runs per frame, and each windowed view — the pre-box segment, the in-box staircase — is that walk's pivots filtered to its window and fed through the *same* staircase machinery (`_staircase_from_pivots`). The in-box view is **byte-identical** to `read_box_staircase` by construction; the widening only *adds* pre-box swings (including a pivot at the box-start bar itself, which the windowed walk's order margin masked). The two views are stitched, not re-collapsed: alternation and HH/HL/LH/LL labelling reset at the box-start seam — the price of keeping the in-box slice identical to the elected staircase — and the seam is a stated boundary, never an implicit one.

Every swing carries the **causality stamps** the Event Map contract requires ([archive/specs/event-map-causality-contract.md](archive/specs/event-map-causality-contract.md), binding for all Event Map work): `describes_bar` (the pivot bar) and `knowable_bar` — the first bar at whose close the swing was *irreversibly committed*, i.e. the bar that pivot-confirms the first opposite extreme whose counter-move reaches the collapse threshold. A swing whose committing reversal has not printed is `in_progress` and satisfies nothing downstream; the frame's first swing is `edge_uncertain` (its extremity depends on bars left of the live two-year trim). The label set "as of date D" is exactly the swings with `knowable_bar ≤ D` — what makes replay honest instead of quietly clairvoyant. One stated caveat: a *view* younger than three raw pivots emits nothing yet (the staircase's own degenerate-window guard), so a swing's first appearance can lag its `knowable_bar` at view birth — labels may appear late, but never change or vanish retroactively.

Above the mechanical swings sits the **narrative-role layer** (`read_role_labels`): the L2 event zones — spring / test / SOS / upthrust / markup / range / rejection / LPS — re-emitted as stamped role labels. It consumes the *same* `_box_events_with_meta` chokepoint the story read uses, **fed the engine's elected bricks** (`structure.spring` / `structure.lps`, both required arguments; an injected `None` means "the engine elected none" and is honored — the layer never re-detects). Each label carries the measurer's own tri-state `resolution` plus a `knowable_bar` derived from its real confirmation mechanics: a failed wave at its low-zone drop bar; a held wave or test at the end of its printed hold window *and* never before the wave stopped being extendable (a later higher-high with no drop to support would have absorbed it — the wave-closure rule) or the anchoring swing committed; a spring at the end of its fully-printed `BIN_C_HOLD_BARS` reclaim-hold (a window running past the last bar is `in_progress`, §2); the elected LPS at the **frame end** — its "still holding" verdict consumed every printed bar, so it is `election_dependent`: re-issued by each frame's own election, frame-scoped rather than truncation-stable (the spring's presence likewise). The chronology battery (`python -m tools.event_map_chronology --check`) replays the marks corpus with cuts stepping through each setup's LPS window and asserts, on emitted labels only, that within a stable election a committed label never mutates or vanishes as bars print.

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
only inside the species lane's own election — the **resistance contraction** (the
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

**The RULED story-pool admission form (operator ruling 2026-07-25 — Option A of the census
menu; THIS paragraph is the canonical spec the pool predicate must match, pinned by test):**
a candidate window is story-admissible when its as-of episode read shows **at least 2
completed support tests AND terminal resistance posture AND no terminal support drift**
(`story_admission` in `event_map.py` — the judgment beside the reader, never inside it).
Census evidence (fingerprint `b671e056…`, ruled at engine `ab5bf340…`; committed record:
[event_map_program_2026-07.md](event_map_program_2026-07.md); standing gate `python -m
tools.event_map_census --check` pins the fingerprint AND the headline): 22/33 marks
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
   > A/B renders (`tools/fidelity/box_backext/`, `tools/box_backext_ab.py` — tool
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

### The explainability rule

**The engine is never allowed to be blind to *why* it chose the pair it chose.**
`read_structure(df, atr, trace=[...])` narrates the whole walk: every root swing tried,
every candidate pair inside the box election with the stage that rejected it (`width` /
`window` / `respect` / `occupancy` — with the failing checks named, e.g. "dead space low" /
`traversal` / `rescue_unused`) and why the winner was elected (`selection`,
earliest-of-valid). `python -m tools.structure_case_audit <TICKER> --trace` renders it.
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
