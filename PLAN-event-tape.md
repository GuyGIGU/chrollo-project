# Council Plan: Event Map — whole-chart event read (name "Event Map" operator-blessed 2026-07-10; file slug kept for continuity)

**Scope:** Make the engine label every significant swing (mechanical + zone + narrative role) across
the whole chart — past the elected box's right rail and into the pre-box trend — and let detectors
consume those labels: a second flag-gated LPS completion form (holding shelf), band-vs-excursion
rail anchoring, and "Last Supper" as a typed measure-only wave. Acceptance = the operator-marks
corpus (`docs/marks/part2_2026-07.json`, 11 setups; engine currently 6.5/11).

**Context:** The engine already owns all three partial readers — the L0 HH/HL labeller +
trend segments, the worked-equilibrium box election with trace, and the L2 in-box event reader
(staircase zones, wave typing, puzzle assembly). This plan widens that machinery into one tape and
rewires the deciders (chiefly `detect_lps`) to consult it. It never adds a second skeleton (EC-3)
and never loosens boundary respect (the upthrust defense).

**Boundaries:** No scoring-weight/tier recalibration; no HTF; no provider migration; no archive-lens
chart overlay in v1 (see Risks); every behavior change is flag-gated, byte-identical flag-off,
gated by corpus + seed-recall + shadow, and amends the `docs/strategy_alpha.md` Reading Model in the
same change.

**Council dispatched:** McKinney (5), Fowler (6), Beck (6), Leach (6), Performance (5), Ramírez (6),
Dodds (5), Saarinen (6), Friedman (5); Hunt returned a clean lane (no security surface). Chair: Carmack.

**Operator clarifications (2026-07-10, post-plan — binding):**
- **BOS/CHoCH carry NO Smart-Money-Concepts semantics.** They are plain price-action reads — "the
  trend ended / a new trend started" (a low taking out the last higher-low, and its mirror). The
  Reading Model amendment and all user-facing wording say it plainly; the abbreviations survive at
  most as internal shorthand.
- **"Zoning" means each event gets its OWN drawn box/region on the chart.** The operator is
  outcome-driven ("I don't care how we do it" — mechanism is free), but the DISPLAY target for
  Tasks 13–15 is per-event boxed regions in the phase-overlay style where events have spans;
  Dodds's markers-first rule yields to the region primitive when point markers cannot express that.
- **Conventions EC-7 (corpus immutability) and EC-8 (flag protocol) are CONFIRMED** and live in
  `conventions.md`; per-flag sign-off and branch-hygiene actions are agreed.

---

## Task Sequence

### 1. Freeze the corpus into a deterministic acceptance harness with a ratchet baseline
| | |
|---|---|
| **Domain** | Beck × Carmack — The red step is the proof; Non-deterministic systems need deterministic tests |
| **Ref** | `references/quality-testing.md` → P1, P8, P10; cross-ref Leach (corpus data contract) |
| **Depends on** | — |

Commit frozen point-in-time price frames per corpus setup and replay them through the real
per-ticker evaluation, grading "fired during the LPS window / by trigger" with an explicit matcher
that handles the corpus's real quirks (NGL's two setups, null/alternate triggers, PBT's second LPS,
extraction- vs operator-sourced fields). The baseline is a ratchet: current hits pinned as
must-never-regress; each known miss recorded as an expected failure tagged with the build stage that
should convert it (shelf-LPS owns WTS/PBT/DRTS-2nd; band-vs-excursion owns BODI + VIK/WTS rails;
EGBN stays "under investigation"). The marks file is the immutable test spec — the harness must
refuse silent edits; fixing a failing case happens in the engine, never in the marks.

### 2. Write the tape causality contract before any tape code
| | |
|---|---|
| **Domain** | McKinney × Carmack — Reproducibility; no label without a knowability date |
| **Ref** | `references/quality-llm.md` → P3, P4, P5 |
| **Depends on** | — |

Specify, as a Reading Model amendment draft: every role label carries two bar stamps (the bar it
describes, the bar it became knowable) and "labels as of date D" means exactly those confirmed ≤ D;
states whose definition needs future bars (shelf hold, Last Supper, wave outcomes) are tri-valued
held/failed/**in-progress**, never binary; and the tape is a pure function of the frame under the
exact live two-year trim (the audit tool's 5y-vs-2y parity defect is the cautionary case). This
contract is what Beck's truncation tests (Task 5) assert.

### 3. Fold `detect_lps` into machinery + completion predicate, byte-identical
| | |
|---|---|
| **Domain** | Fowler × Carmack — Two Hats: refactor first, add behavior second |
| **Ref** | `references/refactoring.md` → P8, P2 |
| **Depends on** | Task 1 |

Separate the form-agnostic machinery (window enumeration, tightness/volume gates, zone typing,
trigger derivation, reject counting) from the single form-specific judgment (rests-on-terminal-low +
overshoot pullback floor), and prove the fold byte-identical — outputs AND reject counters — over
the corpus, seed-recall set, and shadow baseline before any shelf logic exists. Same
capture→fold→parity discipline as the eval-twins fold.

### 4. Build the mechanical tape layer by widening the one skeleton
| | |
|---|---|
| **Domain** | Fowler × Performance — One decoration layer; one bar-level swing walk per ticker |
| **Ref** | `references/refactoring.md` → P5, P6; `references/quality-performance.md` → P3; cross-ref McKinney (NaN quarantine) |
| **Depends on** | Task 2 |

The in-box stretch of the tape must BE today's staircase — widen its window left of the box and
right of the rail rather than standing up a second skeleton; the in-box slice stays byte-identical
(capture it over the corpus + a broad panel first). One bar-level swing walk per ticker; the
staircase, traversal, and any new windowed view become slices of that one computed result; only the
cheap amplitude-collapse re-runs where a different significance basis is genuinely needed. Coerce
highs/lows/volumes once at entry and make every new gate explicitly NaN-rejecting. New reader gets
its `core/MAP.md` row.

### 5. Add the narrative-role layer over the elected bricks
| | |
|---|---|
| **Domain** | Fowler × McKinney — role labels fed the election, never re-detecting; causal by construction |
| **Ref** | `references/refactoring.md` → P6; `references/quality-llm.md` → P3; cross-ref Beck (chronology tests) |
| **Depends on** | Tasks 2, 4 |

Role labels (spring / test / SOS wave / upthrust / LPS / markup) are computed after `read_structure`
elects, consuming the elected box, spring, and LPS the same injected way `box_events` already does —
never a parallel spring/LPS read (the EC-3 cycle-escape trap). Every label carries the Task-2
confirmation stamp and tri-state resolution. Ship with Beck's behavioral chronology tests:
label-truncate-relabel invariance with cuts stepping through each corpus setup's LPS window and
trigger, asserted on emitted labels only, never on machine internals.

### 6. Stage the tape on the fire path behind its flag, with the full flag protocol
| | |
|---|---|
| **Domain** | Performance × Beck × Leach — fire-path only; flag inert-proof; manifest registration |
| **Ref** | `references/quality-performance.md` → P4, P6, P1; `references/quality-testing.md` → P5; `references/quality-postgres.md` → P1 |
| **Depends on** | Tasks 4, 5 |

Phase one has no scan-time consumer, so the full tape is computed only for fires (dozens/night, the
puzzle-read placement) with zero compute flag-off; later stages promote up-funnel only the minimal
facts their consumer reads. The flag protocol applied here and to every later flag: register in the
frozen settings manifest and the dark-flag ledger in the same change; unit-level inert test plus one
frozen-fixture pipeline replay with only that flag off, equal to the shadow baseline; scan-metrics
A/B of the evaluation phase with an agreed acceptance bound before the operator flips it.

### 7. Establish the archive column families with one owning module per family
| | |
|---|---|
| **Domain** | Leach × Carmack — EC-4 upheld structurally, not by discipline |
| **Ref** | `references/quality-postgres.md` → P5, P3, P4 |
| **Depends on** | Task 5 |

Each new column family (tape summary now; shelf-LPS form and Last-Supper wave fields when their
tasks land) is declared once — names, types, row-value extraction — in an owning module consumed by
the live writer, seed, and forward-returns (the HTF-columns precedent), entering as model-only
ADD-only nullable columns so the boot-time model-diff migration and the writer-columns-are-modeled
guard cover them automatically. NULL means "not measured," never zero; EC-2 NaN-scrub at the pandas
boundary; booleans on the 0/1-or-NULL convention.

### 8. Land the holding-shelf completion predicate, flag-gated
| | |
|---|---|
| **Domain** | Fowler × McKinney — second predicate in the one scan; deterministic cross-form election |
| **Ref** | `references/refactoring.md` → P2; `references/quality-llm.md` → P4; cross-ref Performance (tape indexed, never recomputed per window) |
| **Depends on** | Tasks 3, 5, 6 |

The shelf is a second pure completion judgment consulted inside the one window scan — never a
sibling detector — discriminated through the existing `swing_type` field so every downstream
consumer keeps reading one shape; the flag gates only whether the predicate is consulted, making
flag-off byte-identity structural. Election precedence between forms settles on integer/categorical
keys with float quality compared only within a form; window-interval and rounding conventions match
the staircase's emitted values. The shelf consults tape facts computed once per ticker before the
scan — no per-window label derivation. Converts the WTS / PBT / DRTS-2nd corpus stages red→green.

### 9. Guard the two forms: attribution, pinned precedence, negative corpus, shelf archive fields
| | |
|---|---|
| **Domain** | Beck × Leach — assertions are the test; form provenance is queryable |
| **Ref** | `references/quality-testing.md` → P6; `references/quality-postgres.md` → P5 |
| **Depends on** | Tasks 7, 8 |

Every fire carries which form completed it, archived as a plain value (the zone-type/swing-type
precedent) alongside wave type/placement when Task 12 lands. Three day-one assertions: flag-on, every
previously-firing shadow ticker still fires identically and stays pullback-attributed; corpus shelf
cases fire without any pullback-form gate moving; engineered both-forms-qualify frames pin the
precedence choice. Replay the committed negative corpus flag-on — a second completion form must not
make labeled junk fire while every existing guard stays green.

### 10. Extend the one trace and the one narrative, form-tagged
| | |
|---|---|
| **Domain** | Fowler × Carmack — the trace is the instrument the misses were diagnosed with |
| **Ref** | `references/refactoring.md` → P7 |
| **Depends on** | Task 8 |

Reject counters tag which form refused which window; the elected form is named in the LPS brief;
tape/role summaries ride the existing per-root trace records; `assemble_box_narrative` grows new
typed steps inside its one chronological list, never a parallel narrative. Trace stays opt-in and
free on the live path.

### 11. Band-vs-excursion rail anchoring consuming the mechanical layer
| | |
|---|---|
| **Domain** | Fowler × McKinney × Carmack — excursions become typed events; respect gate untouched |
| **Ref** | `references/refactoring.md` → P6; `references/quality-llm.md` → P3; corpus stages from `references/quality-testing.md` → P1 |
| **Depends on** | Tasks 4, 8 |

Derive candidate rails from the worked band the mechanical tape exposes (where price actually
dwells and turns), with below-S / above-R excursions modeled as typed events carrying their own
reclaim requirements — tolerated as events, never absorbed into the rails and never excused by
weakening boundary respect. This is the hardest read in the plan (the reverted shelf-R lever is the
cautionary tale); it enters dark, A/B-rendered for operator eyeball, and owns the BODI width-reject
and VIK/WTS rail-placement corpus stages.

### 12. Type the "Last Supper" inside the existing R-rail wave machinery
| | |
|---|---|
| **Domain** | Fowler × Leach — a new wave outcome typing, measure-only |
| **Ref** | `references/refactoring.md` → P1; `references/quality-postgres.md` → P5 |
| **Depends on** | Tasks 4, 11 |

The resistance-wave reader already groups higher-high rail reaches and types waves by terminal
outcome; Last Supper (operator definition: the final run-up trapping late buyers before the real
pullback, occurring before OR after the LPS) becomes a new outcome typing positioned relative to
the LPS — not a fresh detector. Archive its type and placement as plain values; document its
relationship to the near-twin `_lps_stretch_*` measure at the taxonomy registry.

### 13. Overlay payload: labels ride the scan artifact
| | |
|---|---|
| **Domain** | Ramírez × Carmack — precomputed file serving; the backend stays dumb and flag-blind |
| **Ref** | `references/quality-backend.md` → P2, P3, P6 |
| **Depends on** | Task 6 |

Labels are written at scan time into each chart-tier ticker's existing `chart_data` block of
`output/screener_data.json` and served through the existing mtime-cached route — no new endpoint, no
request-time structure read. Labels anchor by candle time + price (never eval-frame bar index — the
inner-box offset defect, times forty labels), use short stable role codes, cover only the visible
window, and the label key is stripped from `/screener-summary/` in the same change. The key is
conditionally present (puzzle precedent): flag-off artifacts stay byte-identical and old artifacts
must keep serving. v1 is the live screener path only.

### 14. Chart overlay: one marker collection, one pure builder, one style spec
| | |
|---|---|
| **Domain** | Dodds × Saarinen — compose the onReady seam; narration takes context colors |
| **Ref** | `references/quality-frontend.md` → P1, P2, P3, P7; `references/quality-ui.md` → P1, P2, P3, P5, P8 |
| **Depends on** | Task 13 |

Labels enter through the shared `useLightweightChart` onReady seam as their OWN series-marker
collection (never merged with trigger/MFE/MAE marks), toggled imperatively via a stored handle —
excluded from chart-rebuild deps. One pure payload→label builder shared by card and modal, colocated
and unit-tested, tolerating absent tapes and dropping invalid labels whole (one bad time blanks the
chart). One event-style spec beside the shared chart palette: context colors only (never mythril,
tier hues, or the trigger green), position + glyph carry the classification with ~2 muted hues,
both LPS forms wear the existing gold identity, chart-mono type never louder than the axis, minis
get mute glyphs or nothing. Per the operator's zoning read, events with spans render as their own
boxed regions (the phase-overlay primitive contract) where point markers cannot carry the meaning.

### 15. Detail-lens UX: progressive disclosure, evidence, and honest empty states
| | |
|---|---|
| **Domain** | Friedman × Carmack — labels aid, never command; one structure story |
| **Ref** | `references/quality-ux.md` → P2, P3, P4, P7, P9 |
| **Depends on** | Task 14 |

The tape lives in the detail lens only — card faces stay chart-first. The overlay toggles as a
layer (state persists across a review session) and the lens gains a chronological event list where
hovering one entry spotlights that one swing (the phase-region interaction the operator already
knows). Every label carries its mechanical basis one hover away, with mechanical facts visually
distinct from narrative interpretations. The tape must tell the SAME story as the phase panel and
tag chips — divergence is a defect. "No tape computed" and "tape found little" are designed as
distinct, calm states; a missing tape degrades nothing.

---

## Risks & Watchpoints

- **McKinney — frame left edge:** a swing near the two-year trim boundary can have its confirmation
  depend on trimmed-away bars; the contract must state how boundary swings resolve, or replay/live
  divergence returns through the side door.
- **Beck — the implementer is an AI:** the cheapest path to green is nudging a mark by a day. The
  corpus-edit refusal (Task 1) must be enforced mechanically and re-stated in the implementation
  brief when `council-implement` runs.
- **Performance — agree the cost bound up front:** before each flag flip, the operator signs off an
  explicit evaluation-phase delta from the scan-metrics A/B — "should be cheap" is not a bound.
- **Ramírez — archive lens is deferred, deliberately:** the archived-setup chart route rescales
  prices by an adjustment ratio at request time; scan-time price-anchored labels would need the same
  rescale. Bolting labels onto that path without it teaches distrust of the whole overlay.
- **Dodds — no custom pane primitive on day one:** series markers carry the v1 design; build a
  primitive only if Saarinen's spec is proven inexpressible as markers, and then on the
  phase-overlay's handle contract.
- **Fowler — near-twin measures:** Last-Supper wave typing vs the archived `_lps_stretch_*` stretch
  measure must be cross-documented at the taxonomy registry or they will accrete independently.
- **Friedman/Saarinen — naming gate:** "Event Tape" and every on-chart term/abbreviation need
  operator blessing before they appear in UI or docs (naming doctrine).
- **Branch hygiene:** `engine/ta-score-v2` is unmerged (rebase-first per its own note) and the
  audit-tool parity fix sits uncommitted on worktree branch `claude/quirky-volhard-990138` — merge
  or consciously sequence both before implementation starts.
- **EGBN stays open:** its ratchet tag is "under investigation"; dissect it (fixed audit tool, Dec-2025
  roots now visible) before assigning it to any stage.

## External Setup Required

| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | ~~Feature name~~ RESOLVED 2026-07-10: **"Event Map"** operator-blessed. On-chart terse terms/abbreviations still need blessing when Task 14 reaches them | Naming doctrine: no invented jargon in UI/docs without blessing | Task 14 |
| 2 | Operator eyeballs A/B renders + signs the scan-cost bound, then flips each flag | Flags are operator-gated by design | Tasks 6, 8, 11, 12 (go-live only) |
| 3 | Merge (or consciously defer) the audit-tool parity worktree branch and settle ta-score-v2 rebase order | Avoids building on a shifting base | Task 1 |

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Corpus acceptance harness + ratchet | Beck | — |
| 2 | Tape causality contract | McKinney | — |
| 3 | `detect_lps` machinery/predicate fold (byte-identical) | Fowler | 1 |
| 4 | Mechanical tape layer (widen the one skeleton) | Fowler/Performance | 2 |
| 5 | Narrative-role layer over elected bricks | Fowler/McKinney | 2, 4 |
| 6 | Fire-path staging + flag protocol | Performance/Beck/Leach | 4, 5 |
| 7 | Archive column families (owning modules) | Leach | 5 |
| 8 | Holding-shelf completion predicate | Fowler/McKinney | 3, 5, 6 |
| 9 | Two-form guards + shelf archive fields | Beck/Leach | 7, 8 |
| 10 | Trace/narrative extension, form-tagged | Fowler | 8 |
| 11 | Band-vs-excursion rail anchoring | Fowler/McKinney | 4, 8 |
| 12 | Last Supper wave typing | Fowler/Leach | 4, 11 |
| 13 | Overlay payload seam | Ramírez | 6 |
| 14 | Chart overlay (markers + style spec) | Dodds/Saarinen | 13 |
| 15 | Detail-lens UX integration | Friedman | 14 |

## Verdict

The one decision everything else hangs on is the causality contract: a role label with no
knowability stamp makes every downstream stage — the shelf LPS, the corpus grade, the eventual
calibration — a lookahead artifact that replays better than it screens. Write Task 2 before any
tape code and let Beck's truncation tests enforce it forever. McKinney is the critical seat here,
not because the math is exotic but because this feature's failure mode is invisible: everything
runs, the corpus goes green, and the labels are quietly clairvoyant. Start with Tasks 1 and 2 in
parallel — they are cheap, independent, and every later task is graded by them — then do the Task 3
fold while the harness is fresh. The display track (13–15) is genuinely parallel after Task 6; don't
let it block engine work or vice versa. Keep the corpus harness running as the pair agent for every
stage: red before, green after, pinned hits never regress. And resist the urge to start with the
band-vs-excursion read because it feels most profound — it is the hardest and least specified; let
the shelf form pay for the tape first.
