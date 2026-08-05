# Council Plan: Surface the Read

**Scope:** Expose the engine's already-computed chart narrative — pre-box trend, the rail-episode
tape, the electing pool and its why (election trace), spring/LPS anchors, terminal posture — to the
operator in the screener UI, so the concordance loop ("does the engine read charts the way I do?")
becomes measurable. Existing facts only; the held-through-correction strategy read is the single
flagged, measure-first exception, sequenced last.

**Context:** The engine computes the whole story today (the `event_map_*` family owned by
`engine_alpha/structure/event_map.py`, `elected_pool`, `story_admission_profile`, the L2 event
zones, and an opt-in election trace in `box_trace.py`), archives it to `setup_archive`, and
surfaces none of it — the payload's ~133 public keys carry the chart but not the read. The operator
grades setups in the `ScreenerModal`/`ScreenerStockLens` eyeball loop; `setup_reviews` holds 34
rows, all `passed` — concordance is currently unmeasurable.

**Boundaries (out of scope):** detection/scoring math, weights, tiers; the trend-terminal gate flip
and the `segment_trends` fix; rail placement; the scan_date local-date archive defect (pending
operator ruling — treated as a landmine, below); provider/fetch work; IBKR.

**Council dispatched:** mckinney (numerical), ramirez (backend), leach (data), fowler
(refactoring), dodds (frontend), saarinen (UI), friedman (UX), beck (tests), hunt (security),
performance — 10/10 returned, 62 recommendations, no empty lanes. Grounding gates green
(pytest 1229 passed; eslint clean; tree = main `a055bfb`). Advisories:
`.council/council-plan-output/2026-08-04-2059/`.

**Verified against the real code during synthesis:** `wireVocabulary.js` exists and already signs
wire keys to operator labels; `GATE_LEGS` (15 legs) exists in `box_gates.py`;
`calibration_fired.py` consumes the existing trace (and forwards raw `detail` prose — the
anti-pattern named in Task 4); the frontend test script is an enumerated file list; the
earnings lazy-fetch precedent exists in `screenerStore.js`; `activeRegion` is the modal's single
highlight channel. One worker citation was falsified and corrected: there is NO existing
`test_archive_column_parity.py` — the parity guard in Task 12 is new, not an extension.
Measured: payload 15.6 MB / ~82 KB per entry (~91% OHLCV); full narrative fact block ≈ 1 KB/entry
median, 3 KB worst; episode tape median 538 B, max 2.2 KB; evaluation ~28.5 ms/ticker; the
election trace is the ONLY unmeasured artifact.

---

## Task Sequence

### 1. Adopt the ruled architecture: capture once at scan time, artifact-borne live, archive-borne history, zero new request paths
| | |
|---|---|
| **Domain** | Ramírez × Carmack — Architecture earns its boundaries (with McKinney: grounding — the record, not a recompute) |
| **Ref** | `references/quality-backend.md` → P6; `references/quality-llm.md` → P3/P4 |
| **Depends on** | — |

Write this ruling into the plan as a constraint every later task inherits: the narrative is
computed once in the scan subprocess, projected into the payload for the live grid, persisted to
the archive for history, and NO endpoint recomputes or joins narrative facts on demand — a
display-time recompute runs on a fresher frame and is a lookahead wearing the record's clothes
(the archive chart endpoint's adjustment-ratio hack is standing proof recompute drifts). Payload
size is settled by measurement, not argument: ~1 KB against an 82 KB median entry — record a
per-entry narrative budget (low single-digit KB) so future additions inherit the discipline. Each
rendered story sources all its facts from ONE store per render (payload or archive, never a silent
blend), and carries a visible as-of; see Risks for the temporal-skew and second-basis watchpoints.

### 2. Measure the election trace on real fires before deciding its transport
| | |
|---|---|
| **Domain** | Performance × Carmack — Measure before you claim |
| **Ref** | `references/quality-performance.md` → P1/P4 |
| **Depends on** | — |

The trace narrates the whole candidate cascade, so its size scales with the enumeration space —
it is the only piece of this feature with no number attached. Use the existing offline tooling to
request traces on a representative set of real firing tickers and record the size distribution;
until those numbers exist, plan the trace as detail-view material (fetched/rendered on one
operator action), never multiplied ×332 into the bulk artifact. This ruling gates Task 4's
transport decision and nothing else — do not block Tasks 3/5 on it.

### 3. The narrative fact block: one engine-side projection feeding both surfaces
| | |
|---|---|
| **Domain** | Leach × Carmack — Schema choices compound; one producer, N consumers (with McKinney: date anchors, tri-state) |
| **Ref** | `references/quality-postgres.md` → P4/P5; `references/quality-llm.md` → P2 |
| **Depends on** | Task 1 |

Derive the payload's narrative block from the same owning declaration that already feeds both
archive writers (`event_map.py`'s single column-and-extraction source) — never a re-declared field
list in screener assembly, router, or frontend. Every anchor crosses the wire as a DATE, converted
once at payload-assembly while the eval frame is in hand (the narrative layers speak three
different bar origins — a bar index on the wire is frame-relative data pretending to be a fact).
The tri-state travels as one unit: JSON null = never measured, explicit zero = measured-and-empty
(the junk separator IS zero), with the NaN-bar readability companion alongside — never
default-filled (EC-26). Each payload row also carries its archive identity verbatim
(ticker, scan_date, universe_type + engine_config_version) so verdicts bind to the exact row;
publish only the chosen field set — the `_`-prefix boundary holds (Hunt). Where a story-pool
election renders beside substrate columns, the two AP-8 bases stay two labeled facts (see Risks).

### 4. Election-trace export: same-run capture, one outbound artifact, operator-language summarizer
| | |
|---|---|
| **Domain** | Fowler × Carmack — State is the source of bugs; published interfaces that shouldn't be (with McKinney: reproducibility; Leach: archive-what-was-shown) |
| **Ref** | `references/refactoring.md` → P3/P4/P5/P6; `references/quality-postgres.md` → P1 |
| **Depends on** | Tasks 1, 2, 3 |

Capture the trace inside the same scan-time election that produced the fired box (the no-op-when-
unrequested guarantee survives; flag-off stays byte-identical) — never a second "narrate" pass at
request or payload time, which can elect a different box and explain an election that never fired.
The raw trace dicts stay unpublished internals: one exporter beside the trace's owner module emits
the deliberate outbound shape — date-anchored, closed-set coded, honest about not-measured — and
BOTH payload and archive consume that one artifact (archived additively via the documented
model-only column route, raw at write time, measure-first). Two functions live here and nowhere
else: the terminal-verdict summarizer ("which stage/leg killed it, or passed" — already re-derived
three times in offline tools; the new surface must be a consumer, not a fourth copy) and the
sentence renderer that reads leg records + the `GATE_LEGS` registry and emits plain operator
language — internal `detail` prose never reaches the UI. Trace capture cost becomes visible in
the existing ScanTimer phase telemetry with a measured bound before it rides every nightly scan.

### 5. The serve boundary: contract-validated payload block; archive endpoints widened, no new router
| | |
|---|---|
| **Domain** | Ramírez × Carmack — Validate at the boundary (with Hunt: closed-set inputs, fail-safe; Leach: the tape as pinned wire contract) |
| **Ref** | `references/quality-backend.md` → P3/P6; `references/security.md` → P7/P9 |
| **Depends on** | Task 3 (Task 4 for trace fields) |

Give the narrative block the health-board treatment at GET time: a closed, extra-forbidding
contract mirroring the archive's CHECK vocabularies, every field nullable so NULL-vs-zero survives
the wire, absent served as absent. Historical fires ride the EXISTING archive response models —
add the fourteen `event_map_*` columns (nullable) to them rather than minting a narrative
endpoint; the episode-tape JSON cell is parsed and shape-checked server-side exactly once, so the
wire carries structure and one malformed cell degrades that setup to the honest "unreadable"
state (never a 500 across the surface, never schema/path detail in responses). Decide the slim
summary-endpoint seam deliberately: the tape does not ride the light wire the Home tiles poll.
No new mutation endpoint exists anywhere in this feature.

### 6. Vocabulary: every new label operator-signed in the one registry, shipped as data
| | |
|---|---|
| **Domain** | Saarinen × Carmack — Build tokens, not one-offs (with Fowler: vocabulary crosses the language seam as data, not a hand-mirrored map) |
| **Ref** | `references/quality-ui.md` → P8; `references/refactoring.md` → P5 |
| **Depends on** | Tasks 3, 4 |

Every operator-facing word this feature introduces — episode outcomes, pool names, posture,
trace verdicts, stage names — lands in the existing `wireVocabulary.js` registry as an
operator-signed plain name before any surface renders it (retired jargon can never reach the eye;
keep the render-verbatim fallthrough). Sentences and display labels are emitted engine-side inside
the payload fields themselves (the exporter speaks words, not codes) — the repo's own history
shows hand-synced JS mirrors outlive their registries (`SUB_SCORE_CAPS` still re-types settings
values today). JS keeps only code→visual-treatment maps (glyph shape, ink weight), confined to
the Task-7 formatter.

### 7. Frontend formatter module + the narrative status enum
| | |
|---|---|
| **Domain** | Dodds × Carmack — Derive, don't sync; impossible states impossible (with Fowler: formats, never judges; Beck: registered pure-logic tests) |
| **Ref** | `references/quality-frontend.md` → P2/P3/P7; `references/quality-testing.md` → P6 |
| **Depends on** | Tasks 5, 6 |

One pure, component-free module (the `setupScoreMath.js` precedent) owns all tape/trace display
shaping — glyph-list assembly, date formatting, truncation — and never re-derives an engine
judgment; if a display needs a fact, the engine publishes the fact. It exposes a single derived
status enum the render switches on — not-measured (NULL), measured-but-empty (explicit zeros),
ready (plus loading/error only if a live detail fetch exists) — and falsy checks on tape data are
forbidden (0 completed S-tests is a load-bearing engine statement; `fx`-guard discipline
throughout). Its test file is APPENDED to the enumerated `test` script list in
`webapp/frontend/package.json` in the same change — an unregistered test is theatre.

### 8. The lens narrative section: glyph strip, disclosure ladder, recessed trace readout
| | |
|---|---|
| **Domain** | Friedman × Carmack — Structure complexity at the moment of judgment (with Saarinen: instrument form; Dodds: composition + local disclosure state) |
| **Ref** | `references/quality-ux.md` → P1/P2/P4; `references/quality-ui.md` → P1/P2/P3/P4/P8; `references/quality-frontend.md` → P5 |
| **Depends on** | Task 7 |

The full story enters `ScreenerStockLens` as a sibling section beside the phase panel — the
concordance judgment forms in the modal, not the grid. Form: the tape is a JetBrains-Mono glyph
strip (data, not prose; columns held for vertical scanning), outcomes encoded by glyph shape and
ink weight on the neutral ramp — no red/green semaphore, no mythril, no tier hues. The disclosure
ladder is card cue → sentence + tape visible by default → election trace collapsed, explicitly
labeled, LAST, rendered as the system's recessed-well readout that opens within the panel's own
scroll (the chart never reflows). The two absences are designed loudly: "not measured" says why in
plain words (the row predates the event-map flip); measured-and-empty says "no completed events" —
same treatments wherever the narrative appears. Disclosure depth is plain local state with a
deliberate, decided reset-on-cycle behavior (the operator pages Prev/Next; an accidental reset or
persistence is felt on every keypress).

### 9. One-gesture verification: tape spans ride the existing activeRegion channel
| | |
|---|---|
| **Domain** | Dodds × Carmack — One highlight channel, derived not synced (with Friedman: verifiable in one gesture; Saarinen: nothing draws at rest) |
| **Ref** | `references/quality-frontend.md` → P2/P3; `references/quality-ux.md` → P9 |
| **Depends on** | Task 8 |

Hovering/focusing an episode highlights its date-anchored span on the modal chart through the
SAME `activeRegion` value the phase-bin panel already drives (extend its id vocabulary; spans
derived during render from the one Task-7 parse) — never a second parallel highlight state, and
nothing new draws on the chart at rest. Concordance is a visual comparison; a claim the operator
cannot locate on the chart within a second is a claim he stops consulting.

### 10. The card face: at most one compact, signed, stateless chip
| | |
|---|---|
| **Domain** | Saarinen × Carmack — Density is designed (with Dodds: effect-free render; Performance: memoization holds) |
| **Ref** | `references/quality-ui.md` → P4; `references/quality-frontend.md` → P2; `references/quality-performance.md` → P4 |
| **Depends on** | Tasks 6, 7 |

If the narrative appears on the card face at all, it is ONE compact mark in the existing tag-chip
vocabulary and height — computed from the payload during render with zero state, zero effects, no
second measuring loop — because the card is the triage unit and anything added multiplies ×332 and
shrinks charts-per-viewport at 1536×864 (denser-over-bigger is the operator's standing rule). The
facts travel inside the per-ticker data object the card already receives, so React.memo economy
holds; the full read lives in the lens.

### 11. The concordance verdict: a third axis riding the existing reviews write path
| | |
|---|---|
| **Domain** | Friedman × Carmack — Make disagreement as cheap as agreement; the verdict must not collide with the two existing marks (with Hunt: no new write surface; Leach: bind to the identity key) |
| **Ref** | `references/quality-ux.md` → P6/P9; `references/security.md` → P5; `references/quality-postgres.md` → P1 |
| **Depends on** | Task 8 |

The feature's success metric is recorded verdicts on the READ, so the lens story carries a one-tap
agree/disagree at the exact point judgment forms — optimistic, never blocking, recordable without
breaking Prev/Next rhythm, with an optional structured reason whose vocabulary is about the read
(rails, story, posture), not recycled setup-skip reasons. This is a THIRD axis — it judges the
read, not the setup — so wording/placement must not reuse "considered" (card checkbox) or the
archive's "pass" language; a correct read of junk and a wrong read of a winner are both legal.
It writes through the EXISTING `setup_reviews` path with its established validation, binding to
the payload row's verbatim identity key (never a client-derived date — the scan_date landmine),
and no new mutation endpoint is minted.

### 12. The guard battery: contract, parity, and honesty proofs
| | |
|---|---|
| **Domain** | Beck × Carmack — The red step is the proof; behavioral, structure-insensitive (with McKinney: basis honesty; Leach: NULL fidelity) |
| **Ref** | `references/quality-testing.md` → P1/P2/P5/P11 |
| **Depends on** | Tasks 3, 5, 7 |

Four families, all with independently specified expected values (never pasted from a first run):
(a) a payload-contract guard evaluating a committed fixture through the real cascade, asserting
exact narrative values per flag state, with the flag-off leg byte-identical per identity and
unmeasured facts asserted ABSENT, never defaulted; (b) a NEW per-field archive↔payload parity
test through ONE real evaluation — including the tape cell surviving the round trip — asserted on
the two outputs so it survives assembly refactors (no existing parity file to extend; verified);
(c) the NULL-vs-explicit-zero pair on every layer that renders the story, the two outputs
asserted UNEQUAL; (d) EC-27 leg-distinguishing tests on every read-path conjunction ("row
missing" vs "pre-flip" vs "trace never requested" must be distinguishable in observable output).

### 13. LAST: the strategy read — held-through-correction, dark, measure-first
| | |
|---|---|
| **Domain** | McKinney × Carmack — No lookahead, never-gating (with Beck: EC-17 real-cascade happy path; Performance: ScanTimer cost bound) |
| **Ref** | `references/quality-llm.md` → P3/P4; `references/quality-testing.md` → P3; `references/quality-performance.md` → P1/P4 |
| **Depends on** | Tasks 3, 12 |

The only new measurement in the plan: the held-through-correction strategy judgment ships behind
its own flag with the FULL EC-8 protocol (manifest + ledger + inert test + flag-off byte-parity +
cost bound), output never-gating and never-penalizing, raw value archived. Its happy-path test is
cut to the `test_story_pool_guards.py` template — a committed fixture through the real evaluation
entry point, production values, only this flag forced on. It runs only over fired setups (~191–332),
and its cost bound is specified as a measured flag-on/flag-off delta in the existing ScanTimer
phase telemetry — the bound exists to catch a per-universe leak (work accidentally running on all
~5,471 evaluations), the one way this gets expensive.

---

## Risks & Watchpoints

- **McKinney — the scan-night record:** any future "re-read this chart today" feature is a SECOND
  basis and must be labeled as such, never substituted for the fire-night story. Applies the day
  someone proposes "refresh the story" on an open modal.
- **McKinney — AP-8 dual bases:** a story-pool election beside `event_map_story_admitted=0` is
  LEGAL (YPF). Wherever both render, they are two labeled facts (admission profile = the why;
  substrate = the calibration read) — one collapsed panel would look self-contradictory and
  discredit the surface.
- **Leach — temporal skew:** payload and archive are non-atomic stores; during/after a scan a
  blend would show this scan's rails with last scan's tape. One store per render (Task 1) is the
  rule; watch it at every new render site.
- **Leach — the scan_date landmine:** ~28% of archive episode-pairs are byte-identical weekend
  duplicates (ruling pending, out of scope). Until ruled, identity comes verbatim from the payload
  row; nothing client-side constructs a date.
- **Fowler — the three existing trace-summary copies** (`calibration_fired.py`,
  `near_miss_census.py`, `rail_margin_evidence.py`): migrating them onto the Task-4 summarizer is
  cheap follow-up once it exists — not required by this plan, but the next council-review should
  flag any NEW copy as shotgun surgery.
- **Dodds — disclosure reset-on-cycle:** decide it where the modal already resets `activeRegion`
  on ticker change; an unconsidered default is felt on every keypress of the fastest loop.
- **Ramírez — the slim summary endpoint** strips heavy keys by denylist, so every new field rides
  it BY DEFAULT; the Task-5 seam decision must be explicit or the tape silently fattens the light
  wire every poll touches.
- **Hunt — the rebinding gap:** until the pending TrustedHost one-liner lands (separate item), the
  localhost API is reachable by hostile web pages; this plan adds no write surface, which is
  exactly why Task 11 must stay on the existing reviews path.
- **Saarinen — color discipline:** the tape describes, it does not judge — any red/green coding
  turns "what transpired" into P&L and biases the concordance read the feature exists to collect.
- **Performance — the keypress budget:** any on-demand deep fetch (trace detail) must degrade
  gracefully during rapid Prev/Next cycling — chart and card facts render immediately, the
  narrative panel fills when data lands; a synchronous per-keypress fetch is the one way to make
  the fastest loop stutter.
- **Beck — deliberately NOT specified:** no tests for thin router pass-throughs (route
  registration is the existing subprocess import check's job), no JSX snapshot tests (logic lives
  in the extracted formatter), no re-testing of `event_map` internals (owned by `test_event_map.py`).

## External Setup Required

No external setup required. All tasks can be implemented within the codebase.

## Summary

| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Rule the architecture: capture once, no recompute, zero new request paths | Ramírez | — |
| 2 | Measure the election trace on real fires | Performance | — |
| 3 | Narrative fact block: one engine-side projection, dates + tri-state + identity | Leach | 1 |
| 4 | Election-trace export: same-run capture, one exporter, operator-language summarizer | Fowler | 1, 2, 3 |
| 5 | Serve boundary: validated contract; archive models widened; no new router | Ramírez | 3 (4) |
| 6 | Vocabulary: operator-signed labels in wireVocabulary.js, words on the wire | Saarinen | 3, 4 |
| 7 | Frontend formatter module + narrative status enum | Dodds | 5, 6 |
| 8 | Lens section: glyph strip, disclosure ladder, recessed trace readout | Friedman | 7 |
| 9 | Tape→chart one-gesture verification via activeRegion | Dodds | 8 |
| 10 | Card face: one compact signed stateless chip | Saarinen | 6, 7 |
| 11 | Concordance verdict: third axis on the existing reviews path | Friedman | 8 |
| 12 | Guard battery: contract, parity, NULL/zero honesty, EC-27 legs | Beck | 3, 5, 7 |
| 13 | LAST: strategy read, dark flag, full EC-8 + EC-17 + ScanTimer bound | McKinney | 3, 12 |

## Verdict

The single most important decision in this plan is Task 1, and it is already made: the story the
operator grades is the record of the fire-night run — captured once, projected everywhere, never
recomputed. Every seat independently hit some corner of the same truth: a narrative surface that
can disagree with itself (payload vs archive, card vs lens, trace vs rails, zero vs NULL) doesn't
degrade — it dies, because its only product is trust. That makes McKinney's lane the critical one:
date anchors converted once, the tri-state carried intact, the two AP-8 bases labeled, the trace
captured from the election that actually fired. Start with Task 3 — it's the spine every surface
hangs off — and keep Task 2 cheap and early so the trace's transport is decided by a number, not a
guess. The frontend work is deliberately boring: one formatter, one status enum, one highlight
channel, one chip; boring is what the Instrument Panel wants. Have McKinney on hand as the pair
agent through Tasks 3–5, and Beck's independent-expectation rule enforced ruthlessly in Task 12 —
a guard pasted from first-run output would bless the exact drift this feature exists to expose.
The size argument is dead (1 KB against 82 KB); don't let anyone resurrect it to justify a live
endpoint. Build the record, show the record, let the operator argue with the record — that's the
whole feature.
