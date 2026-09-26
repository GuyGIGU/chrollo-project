# The classic Consolidation method — program record (2026-09)

The operator's ruled program (scoped 2026-09-01): the engine translates every chart into
simplified swings / moves / events, each judged by its NATURE and its RELATION to the
consolidation, the rails, and the phases — ONE language he and the engine share, in which the
two dark chart-reading flags (`CONTRACTION_RESCUE_ENABLED`, `LPS_CEILING_REST_ENABLED`)
dissolve into judgments expressed in that language. His acceptance standard, verbatim
(2026-08-31): **"we measure against the calibrated list"** — fleet drift is disclosed to him
as ruling rows, never a silent blocker and never silently accepted.

Boundaries (ruled at scoping): no read-panel UI (calibration rides the existing workbench
tab); the two universe-policy lanes (`SMA50_DIP_EXCEPTION_ENABLED`,
`BOTTOMING_BASE_LANE_ENABLED`) are out — a separate what-may-the-screener-look-at decision;
no story-chain type names; no scoring/tier changes; nothing brokerage.

---

## Task 1 — the word table extension (closed tokens, operator-signed)

**Engineering half (landed with this record):** the archived sentence is a sequence of
structured tokens — the stable word + the already-resolved verdict — drawn from the ONE
closed vocabulary the operator signed in full on 2026-08-30 (decisions.md word-table rows).
`engine_alpha/structure/event_vocabulary.py` now declares the enumerable closed sets
(`WORDS`, `VERDICTS` — DERIVED from the declared tables, EC-33, so extending a table extends
the sets by construction) and the write-time membership assert (`assert_token`, EC-55): an
unsigned word fails in the stack frame that mints it, never at a column CHECK. The archive
family (Task 8) calls it per token. Pinned by the literal closed-set battery in
`tests/test_event_vocabulary.py` (the signed sets spelled out; the retired "holding_shelf"
word and the pre-signing "gave" verdict refuse at mint time).

**The token inventory** (all signed — nothing here needs a new ruling):

| Token | Axis | Signed / ruled | Display source |
|---|---|---|---|
| `spring` / `sos` / `upthrust` / `lps` / `markup` | word | his Wyckoff vocabulary verbatim; markup signed 2026-08-30 | derived engine-side |
| `support_test` / `resistance_test` | word | signed 2026-08-30 (word + verdict shape) | derived engine-side |
| `touch_and_pivot` | word | signed 2026-08-30, widened by his screenshot ruling | derived engine-side |
| `range` | word | Phase-B cause, unjudged | derived engine-side |
| `mini_consolidation` | word | one event, position an attribute (ruled 2026-08-23) | derived engine-side |
| `held` / `breached` / `open` / `unreadable` | verdict | breached = his official term, ONE word both rails (2026-08-30) | derived engine-side |
| `at_ceiling` / `mid_range` / `on_support` / `touching_both` | position | four values ruled 2026-08-30 | `wireVocabulary.POSITION_LABELS` ("at resistance" / "middle of the base" / "on support" / touching both) |
| `contracting at resistance` / `contracting above resistance` | admission record | the behavior names, operator-named 2026-08-18 | stored verbatim (AP-12) |

**Signing sheet — SIGNED IN FULL 2026-09-01** (decisions.md signing row). The three rows below
are kept verbatim as they were put to him, so the question he answered stays readable; the
outcome is recorded under the table.

| # | Decision | Proposal (his words only) | What a YES flips |
|---|---|---|---|
| W1 | The ceiling-rest LPS form's spoken phrase — when the sentence names the rest the dark `LPS_CEILING_REST_ENABLED` exception sanctions, what does it say? | **"LPS at resistance"** — composed purely of already-signed words (`lps` + the signed `at_ceiling` display "at resistance"); his 2026-08-29 ruling already folded resting-on into the ONE "at resistance" position | The named judgment's record label (Task 6) and the later panel's chip copy. No stored cell changes — stored vocabulary stays frozen (AP-12) |
| W2 | Confirm the closure: this program mints NO new sentence words — every archived token speaks the signed table above, and any future word is a fresh signing before it serializes | **yes** (the naming doctrine applied to the language program) | **Said plainly, because the row would otherwise read as ceremony: the build ALREADY enforces this.** `assert_token` refuses an unsigned word in the stack frame that mints it, the literal closed-set battery pins the signed sets AND the signed assignment, and the vocabulary is hashed into the engine identity (`SENTENCE_VOCABULARY` in the freeze manifest) — all landed in this same changeset, before your signature. **What that hash actually guarantees, stated precisely because the first draft of this row read broader than the build was** (council review 2026-09-01 round two): it covers the MAPPING, not only the value sets — which word and which verdict each reader event means (`puzzle_type_words`, `in_progress_rail_words`, `episode_rail_words`, `episode_outcome_verdicts`, `mini_consolidation_word`), each derived from the ONE declaration per EC-33. So a re-ruling that stays entirely INSIDE the closed sets — moving `spring` from *held* to *breached*, swapping a word between two event types — rotates `engine_config_version`. It did NOT before this fix: three such re-rulings were driven through the shipped code and the manifest hash never moved. The same closure was widened once more at the round-three completeness pass: the channel BASIS block — which substrate each channel's words stand on, and the origin every archived date is measured from — rides the identity too (it was declared, it rode verbatim in every archived token, and re-declaring it rotated nothing), and the projection is now derived from a registry a guard pins against the module's own declarations, so a future table cannot slip the identity by being forgotten. One thing is deliberately NOT identity: a pure REORDERING of a declared table rotates nothing, because those tables are lookups nothing reads positionally and a spurious epoch permanently splits a cohort that could have been pooled — the same split the TA-grade block already makes between chapter ORDER (a list, ruled meaning) and the chapter MAP (a dict, registry order). Both directions are pinned. A YES makes the built state law and settles that a future word — or a re-ruling of an existing one — costs a signing plus an epoch rotation; a NO re-opens Task 1 and the Task-8 mint assert rather than confirming them |
| W3 | The bar-posture rescue's admission-record label (Task 7 — what a fire admitted by the S-test form's bar-basis ceiling leg stores in `story_admission_profile`) | **"engaged at resistance"** (the behavior seen: the right edge engaged at the rail by the bar, close anywhere; parallel to the contraction's "contracting at resistance") | The stored record string freezes at the lane's FLIP — dark, nothing archives, so a re-wording before the flip is free. Signing this is a flip precondition on the ledger row |

**The outcome (2026-09-01):** all three signed as proposed, with **one widening on W1**. He signed
"LPS at resistance" and ruled its scope to be the whole rail vicinity — *"Below (at the ceiling)/
Above (Resting on the resistance)/ or clipping through the line at self"* — which is his 2026-08-29
area ruling applied to this phrase, not new doctrine.

That widening was **checked against the build in the same sitting** rather than accepted as
satisfied: `_ceiling_rest_verdict` is a one-sided floor (`support_low >= res_avg − 0.3 × ATR`)
consulted only inside the `INSIDE` zone branch, so it already speaks for the rest **below** the
line and the rest **clipping through** it. The **above** case never reaches it — a rest whose low
sits above R types `OVERSHOOT_R` in `lps.detect_lps_candidates`' zone gate and is decided
elsewhere. So the phrase is signed
for three positions and the engine speaks it for two; the third is carried as its own ask
(`asks.md` 2026-09-01 successor row) and is explicitly NOT a razor edit — widening 0.30 ATR to the
±0.50 rail area is the measured-dead move that re-fires junk ENIC at tier A.

W2's closure is now law, and W3 satisfies the bar-posture flip precondition on the ledger row.

---

## Task 2 — the translation contract (one skeleton, causality stamps, named bases)

The sentence is a pure function of (truncated frame, rails, ATR, manifest knobs), and the
contract is now DECLARED in the projection module (`event_vocabulary.py`):

- **The skeleton contract.** Each channel declares which substrate its words stand on
  (`BASIS_CONSTANTS[...]["skeleton"]`): the puzzle channel on THE one calibrated order-1
  collapsed swing walk, the episode channel on no skeleton at all (bar-level zone visits),
  the inner-box channel on the inner election one scale down. `market_structure`'s HH/HL
  labeled points are **excluded as a sentence substrate by contract** — their pivot order
  scales with frame length, so the labels are not truncation-stable; they stay trend-model
  diagnostics.
- **Causality stamps ride every judged record.** Episode-source records now lift
  `knowable_bar` / `in_progress` from the reader's own episode record (the merge-horizon
  arithmetic stays upstream, never re-derived); puzzle records already carried them from the
  role labels; the mini-consolidation from its declared `at_right_edge`. Absent stamps read
  None — unknown, never falsely settled.
- **Decision-day = truncation, never filtering.** Stated in the module contract; enforced
  upstream by `episode_sequence_stats`' loud refusal of a sub-edge as-of (contract §1).
- **The right edge is honestly UNDETERMINED.** An unresolved engagement renders its rail
  word with verdict `open` — never a pre-typed outcome (his 2026-08-30 "the bars afterwards
  determine the meaning").
- **Named bases stay divergent facts.** The close-vs-bar divergences ride each record's
  `basis` (`breach_basis`: `close_vs_rail` vs `extremes_vs_local_swing`); "aligning" bases
  is a re-measurement with its own seam (the episode reader's pinned-yardsticks law), never
  a cleanup — EGBN is the canonical seam and stays one.

Pinned by the contract battery in `tests/test_event_vocabulary.py` (skeleton declarations,
stamp lifting, the unknown-never-settled default, the open right edge). Zero behavior moves:
the module stays dark, additive fields only.

---

## Task 3 — the three-state data law + recorded operands

The event-map family's law, restated as the sentence family's law and applied at the fold:
**NULL = not-measured-or-refused · explicit zero = measured-empty evidence · unreadable =
non-finite verdict bar** (EC-54 is this same law at the judgment layer — the rescue's
admission legs already fail closed on missing input).

Landed now (the projection layer's half): `unify_events` lifts the readability companion
from the episode reader's own output — `episode_nan_bars` / `episode_n_bars` ride the folded
stream, None when the reader never ran (an absent read can never fabricate a zero), the
reader's explicit 0 when it ran clean. Unreadable episodes already carry verdict
`unreadable` per record. Raw numeric operands ride every record by construction (`raw` = the
reader's dict by reference; `basis` = the caller's declared operands — rails, ATR, window
identity).

Deferred to Task 8 by design (the columns' physical half): nan-bar companions beside every
archived count, a refused read NULLing the whole family, the config-epoch stamp beside every
emitted word, and the LEVI zone-coverage ABSENT state inherited by every consumer of a quiet
sentence (`zone_coverage` is a measured value, so it enters as a declared operand / archived
companion — the naming layer may not compute it). The box-relative zone rebase stays
deferred to its own program (the LEVI row's Option A), untouched here.

---

## Task 6 — the ceiling-rest judgment gets a name

The ceiling-rest exception — until now anonymous arithmetic fused into the launched-above
gate inside the LPS window loop — is extracted as a **named pure judgment beside the other
LPS form verdicts**: `lps._ceiling_rest_verdict` (the `_rest_verdict` pattern). In the
signed position vocabulary it IS the "at resistance" judgment on a rest (display phrase =
signing-sheet row W1). The flag stays consulted lazily inside the function (config-shadow
rule); flag off = False = byte-identical by construction. A razor re-ruling now replaces one
function, never a hand edit inside the ~400-line window loop.

**Capture pin (the before/after the plan required):** the flag-ON leg was captured BEFORE
the edit — the full 32-ticker shadow fixture evaluated with `LPS_CEILING_REST_ENABLED`
forced on, plus NOK's ruled conversion (2026-02-13, tier B) through the real cascade — and
re-captured after: **byte-identical**, both legs. Flag-off covered by the standing suite
(full pytest 1790 · ratchet 28/33 · reader_pin zero-diff · doctrine_audit all-hold, all
green at this task's close).

**The 0.5-vs-0.3 presentation (an operator ruling to receive, never a code fold):** the
engine deliberately carries TWO named constants with two stated roles —

| Constant | Value | Role | Evidence |
|---|---|---|---|
| `TOUCH_TOLERANCE_ATR` | ±0.50 ATR | the ruled rail AREA — **position vocabulary ONLY** (2026-08-30 ruling: symmetric, both rails, ATR units) | as a gate/veto/rescue a 0.5-ATR allowance is Tested-DEAD **twice** |
| `LPS_CEILING_REST_MAX_BELOW_R_ATR` | 0.30 ATR | the ceiling-rest **admission razor** — drawn-evidence-placed | DSGN 0.010 / MATX 0.087 / MSGS 0.148 / NOK 0.241 vs junk ENIC 0.314; at 0.5 **ENIC fired tier A** and the junk guard went red |

They answer different questions — "where does a bar's position read *at the rail*" vs "how
near R must a launched-above rest sit to be *sanctioned*" — and unifying them re-fires ENIC.
The decision offered: **bless the two-constants/two-roles state as the standing law** (the
recommendation), or name the reconciliation you want and it runs the full A/B road.

---

## Task 13 — doctrine_audit hardening

The one instrument that proves the reading is RIGHT gets three defenses against going dark:

1. **The mandatory manual run-slot** — codified in AGENTS.md's verify list: `tools.doctrine_audit
   --check` after ANY change touching engine signatures or election paths. (It is deliberately not
   in pytest — it needs the live payload — which is exactly how the 2026-08 arity trap went
   unnoticed.)
2. **The hermetic plumbing leg** — `tests/test_doctrine_audit_plumbing.py`, payload-free, on every
   default pytest run: the polarity spy stays signature-transparent and delegates verbatim
   (`_make_cause_spy`, extracted); the abstention vocabulary (`_VETO_OUTCOMES`, extracted) is
   pinned against the outcomes `read_structure` actually emits by driving both veto outcomes
   through scripted fakes; the whole `_audit_setup` check table runs over a synthetic structure
   with the applied-invariant id set pinned literally.
3. **The ceiling-rest form's own invariant landed flag-aware** — `D8 ceiling-rest-on-rail`: an
   INSIDE-zone LPS whose window launched above both extension caps can only have been sanctioned
   by the ceiling rest, so its rest must sit within the razor under the owning rail. Inert while
   `LPS_CEILING_REST_ENABLED` is dark (pinned); binds automatically on the exception's first live
   payload — the flip change cannot forget it.

Verified: the hardened audit runs PASS over the live payload (289 setups, zero violations, D8
correctly absent while dark); the plumbing battery 4/4.

---

## Task 7 — the bar-unit ceiling leg, versioned dark at the full-refusal scope

**What landed.** `BAR_POSTURE_RESCUE_ENABLED` (dark) — the S-test story admission with its
ceiling leg in the operator's unit: `event_map.story_admission_bar_posture` reads
`terminal_r_engagement` (the bar's HIGH engages the rail zone — the reader's zone entry is
wick-basis already) where the S-test form reads `terminal_r_posture` (the close closing
above the rail — the one leg of the ruled form that violates the thrice-stated bar-as-unit
doctrine, and EGBN's whole miss). A VERSIONED sibling: `frame_terminal_posture` — the ONE
close-basis predicate the S-test prefilter and the episode reader both resolve through — is
untouched, its promotion counts stay pinned. Armed ONLY by the full-refusal escalation
(never in the baseline roster; the species preset cannot arm it); both escalation lanes
join ONE re-walk. Registering the flag rotated the engine epoch (the declared vocabulary
seam). New battery `tests/test_bar_posture_rescue.py` (**12 pins** — counted 2026-09-01 at
this record's seal, incl. both end-to-end conversions and the §truth-table trio); the junk
leg joined the armed-lanes negative-corpus test.

**The acceptance evidence (banked 2026-08-31, chair-verified —
`output/consolidation_evidence_2026-08-31/`):** control battery all-green; candidate
(wholesale in-memory swap) junk corpus **18/18 silent**, shadow panel **byte-identical on
all 32 fixture fires**, sealed ratchet breaks on **exactly EGBN (fires 2026-01-07 tier A) +
PKE (2026-02-18 tier B)** — both dates/tiers operator-ruled real 2026-08-19. Reproduced at
the SCOPED lane by the committed battery (same dates, same tiers, story pool, self-naming
record).

**The disclosure sheet — AS OF THE 2026-08-27 CACHE EDGE (the census the scope was chosen
from: `output/consolidation_evidence_2026-08-31/bar_posture_census.json`, 5,532 tickers,
wholesale swap). Every cell below is an as-of read, not a standing fact:**

| What moves | Names | At the shipped full-refusal scope (as of 2026-08-27) |
|---|---|---|
| Standing fires | 308/309 byte-identical, 0 elections moved | unchanged by construction (the escalation never runs on a ticker that reads) |
| New fires | **12**: KFY BIIB VTR RCUS ICLR GEO VRTS CCEP BMY MSGS CARS AMCR (MSGS is a drawn-corpus name; all legible completed-test sentences) | 12/12 were full refusals at baseline on that edge — **re-derived four days later it is 4/12; see below** |
| Lost | **QTTB** — root-steal: an older root story-admits a wider frame (same R 16.61, S 14.93→14.13), first-complete-wins ends the walk, the descent-tail gate kills the wide frame downstream | **unreachable** — QTTB reads at baseline, the escalation never runs there |

**The fleet column perishes — measured, not asserted (as of the 2026-08-31 cache edge;
`output/consolidation_evidence_2026-09-01/`, probe `probes/bar_posture_reachability.py`,
sidecar `bar_posture_reachability.json`, log `reachability.log`; population fingerprint
`1bd50279…`).** No engine stamp is quoted on this page: the probe computes it inside its own
run and writes it to the sidecar, and it rotated twice while this record was being written, so
read it out of the re-run sidecar rather than from here. The sidecar carries **two** stamps —
`engine_manifest` (the machine, read fresh at run time) and `engine_manifest_at_measurement_pin`
(the identity the printed counts were measured under) — with `measurement_identity_matches_machine`
beside them. Quote the second one beside the counts whenever they disagree, and read a
disagreement with no flag named in the advisory as a moved THRESHOLD, which no flag pin can see.

*The measurement is FLAG-PINNED, not merely taken on a quiet machine* (round three), *and the
pin is the engine's whole roster, not a hand-list of lane names* (round four): the pinned set is
DERIVED from `engine_alpha.freeze.manifest.ENGINE_SETTINGS_KEYS` — the engine's own declaration
of every constant that decides a reading, whose completeness over the eval path is proved by
`tests/test_invariants.py::test_every_scoring_settings_symbol_is_in_manifest` — which is 29
booleans, each held at this changeset's shipped value. Classification runs under that pin, the
conversion leg re-reads each reachable name with only this lane armed through the one scoped
override, the sheet asserts on the report itself that the flag set it STAMPS is the set it
COMPARES, and a differing ambient earns a loud advisory naming every moved flag plus the
`measurement_flags` block in the sidecar. A roster flag with no declared pin value aborts the
sheet at import rather than printing an unpinned count.

That pin is load-bearing at the sitting, and the hand-list it replaced was not wide enough —
measured 2026-09-01 on this cache and this population, **three flags move these counts**: with
`LPS_CEILING_REST_ENABLED` live (its own flip sits on the same asks page) KFY stops being a full
refusal and elects at baseline through THAT lane, taking the headline to 3 reachable / 3
converting; with `STORY_POOL_ENABLED` off the sheet inverts to 6 reachable / 3 electing at
baseline / **zero** conversions; with `SMA50_DIP_EXCEPTION_ENABLED` live the universe gate softens
and all three names that fail the 50-day filter (ICLR, MSGS, VTR) enter the read instead, emptying
that bucket and re-splitting the twelve across the other two — a UNIVERSE flag, which is exactly
why naming lanes was never going to be complete. Two more were already
pinned and so could not leak: with `CONTRACTION_RESCUE_ENABLED` live instead, all four reachable
names elect through the SIBLING lane at baseline with "contracting at resistance" records, so an
unpinned probe would have reported `full_refusal_reachable 0` or credited that lane's conversions
to this one. The remaining 21 measured inert HERE, on THESE twelve names, at THIS cache edge — a
null result on one population, recorded as such and pinned anyway.

**True-up, because widening a pin is a re-measurement (EC-15):** re-deriving the sheet under the
29-flag pin moved **nothing**. Population 12 · reachable 4 · cause-vetoed 0 · electing at baseline
5 · failing the universe filters 3 · converting 4 · with a chronology floor 0 — every count, every
name, every tier and every score below still reads exactly as this page and the ask rows already
state it, re-verified cell by cell against the re-run sidecar (the probe's own run additionally
compared the whole object against its pre-fix capture and found the `names` block identical).
That the numbers held is checkable rather than lucky:
all 29 declared pin values equal the shipped config values, so the pin does not perturb the basis
it makes explicit. Nothing on this page or in any ask row needed a number changed.

Four days after the census's cache edge, the same twelve names
classify four ways — the old probe could only say "reachable / not", because the public
`read_structure` returns `None` for BOTH a full refusal and a doctrinally-final
cause-before-effect abstention:

| Verdict (2026-08-31 edge) | Count | Names |
|---|---|---|
| Full refusal — the armed lane reaches it, and it CONVERTS through the shipped lane | **4** | AMCR (tier B, 93.3) · CARS (A, 100.9) · KFY (A, 107.3) · VRTS (A, 103.5) — all four elect through the story pool with the self-naming "engaged at resistance \| …" record |
| Elects at baseline — the lane cannot touch it | **5** | BIIB (elects, does not fire) · BMY · CCEP · GEO · RCUS — the last four **already fire tonight with no flip at all** |
| Cause-before-effect abstention — never reachable | **0** | none today; the property is now tested rather than assumed |
| Fails the universe filters — the chart is never read | **3** | ICLR (close 164.99 vs sma50 167.06) · MSGS (384.73 vs 394.03) · VTR (91.17 vs 92.36) |

**What "never reachable" means, pinned to the engine rather than to a vocabulary — the
predicate was wrong in the first build and is now the instrument's own first assertion.** A
read is final ONLY when the walk returns `narrative._CAUSE_VETOED`, the sentinel
`read_structure` tests by identity at step 2 and returns on before arming a single form. The
first probe classified on `doctrine_audit._VETO_OUTCOMES` instead — the frozenset that answers
a DIFFERENT question, which non-elections the coverage census EXCUSES — and that set also
holds `lps_before_spring`. An LPS chronology floor ends one root's attempt and the walk
advances to the next root, so such a name is an ordinary full refusal that the armed lane
re-walks; the wrong predicate would have printed "never reachable" over a chart the flip
converts, and skipped its conversion leg. It cost nothing HERE by luck, not by design — the
sheet now discloses that too, as `reachable_with_chronology_floor: 0` (the four refusals trace
`no_box` / `no_lps` only) — and the probe now proves both halves of the rule against the
engine, through the same scripted bricks `tests/test_doctrine_audit_plumbing.py` uses, before
it prints a single count. A drifted predicate aborts the sheet instead of colouring it.

So the honest exposure of this flip on the fleet is **4 names, not 12**, and the grades of
the four survivors have moved too (KFY S/119.9 → A/107.3; VRTS A/107.5 → A/103.5; CARS
A/101.3 → A/100.9; AMCR B/86.2 → B/93.3) — it is not only the count that perishes, it is
every cell. **Playbook line, and it is part of the flip ruling:** the fleet reachability
column is re-derived on the MORNING OF THE SITTING —
`.\.venv\Scripts\python.exe output\consolidation_evidence_2026-09-01\probes\bar_posture_reachability.py`
(~60 s; rewrites its sidecar and prints the four-way table) — and the ruling is made on
that refreshed list, never on a number banked weeks earlier.

**What does NOT churn, and it is what the flip should stand on:** the calibrated-list
conversions — **EGBN 2026-01-07 tier A** and **PKE 2026-02-18 tier B**, the dates and tiers
the operator ruled real on 2026-08-19 — are reproduced end-to-end against the SEALED
fixture by the committed battery (`tests/test_bar_posture_rescue.py`), so they are pinned
in tests and completely unaffected by cache drift. That is the acceptance evidence. The
fleet census is supporting color, and it is the perishable half (his own standard,
verbatim: "we measure against the calibrated list").

**Owed to the operator (decision-shaped, on the ledger row + asks.md):** the flip vs the
fleet eyeball — **re-derived on the morning of the sitting**, four names at the 2026-08-31
edge, not the twelve the census banked; the W3 record-label signing; the reseal (EGBN/PKE
leave the expected-miss list — SHARED with the contraction rescue: whichever lane flips
first re-seals 28/33 → 30/33 with both pinned by name); the second-walk cost bound rides
the same ScanTimer instrument as the rescue lane (Task 10), read on the ONE armed trial
night whose choreography §Task 14 proposes.

---

## Tasks 8 + 9 — the sentence archive family, measured in the one eval chain

**Task 8 (the columns).** The `sentence_*` family lands on the model-only route with its
owning declaration in `event_vocabulary.py` (`SENTENCE_COLUMN_SQL`: `sentence_tokens` — the
folded token tape, compact JSON, DATE-anchored; `sentence_n_tokens`; `sentence_nan_bars` —
the readability companion), the cell serializer (`serialize_sentence` — every token passes
the EC-55 `assert_token` at the mint; spans/knowables convert to the window ruler through
declared offsets or serialize null, never a guessed date), and the extraction
(`sentence_archive_values`) splatted by **all three writers** — live, seed, and the manual
route — with the EC-30 per-writer AST guards extended to name it. Three-state law verbatim
(Task 3): NULL = not measured or refused (whole family), explicit zero = evidence beside its
companion. No backfill ever; columns never repurposed.

**Task 9 (the measurement).** `SENTENCE_ARCHIVE_ENABLED` (dark, manifest-listed from day
one — a vocabulary-deciding knob, so the registration rotated the engine epoch): the fold
runs in the ONE shared eval chain, once per elected box, riding the elected candidate
outward — live, seed and manual rows carry identical sentences by construction. The
sentence's ONE ruler is the elected window (bar 0 = the box start), and EVERY channel handed
to the fold must already be on it: the puzzle and episode channels by construction, and
**both** df-absolute inputs — the label layer's knowable stamps and the inner-box channel's
detection bars — by an explicit rebase in the caller, because the naming layer converts
nothing (Task 4). The second half of that was applied only to the label layer in the first
build, so on a specimen whose box starts at a nonzero bar the mini consolidation landed off
the ruler and serialized `"span": null` — the operator's mini consolidation silently absent
from the sentence while every other assertion stayed green. Pinned on the corpus's one marked
fire that carries an inner box (MS 2026-06-04, `tests/test_sentence_family.py`): the shelf's
span is `["2026-04-16", "2026-05-18"]`, the box start is asserted nonzero so the pin cannot go
vacuous, and the record sorts into its chronological place in the tape instead of its tail.
Declaring the real offset
was not the smaller option available: the mint refuses a box-origin record carrying a nonzero
`box_start_in_window`, because the tape sorts on RAW spans. Flag-off spreads {}
at every surface — result rows, archive (NULL family), scan metrics, ranking order — and
flag-on is purely additive: nothing reaches score, tier, or sort keys. `read_role_labels`
now returns its chokepoint `events` alongside the labels (the fold zips them 1:1 by
construction — a second chokepoint call could re-detect and misalign).

**Additive in BOTH senses — the failure path too** (council review 2026-09-01, finding 5).
The family raises BY DESIGN (the write-time closed-set assert, the fold's vocabulary-miss
refusal), and it sits inside the one guarded eval chain whose skip-guard catches exactly
those types — so an uncontained raise would have turned every setup whose read carries a
lagging word into `EVAL_ERROR` and deleted the fire from the night AND the archive, on
precisely the nights after a re-wording. The measurement now sits in its own guard that
degrades to the family's declared NULL state (the same `{}` an unreadable read spreads —
never a fourth state) and counts the drop on its own channel
(`evaluation.SENTENCE_DROPS`, per worker process) beside a per-item stderr line, so an
error stays distinguishable from an honest refusal even though both archive NULL (EC-20).

**The signed vocabulary is engine identity, not just the flag** (finding 6). The family's
law is "rows written under a different reader vocabulary are a different epoch — no
backfill, ever", but only the FLAG rode the frozen identity, so a signed re-wording would
have minted new-worded rows under the old stamp and the mixed population could never be
partitioned again. The freeze manifest now carries `SENTENCE_VOCABULARY` —
`event_vocabulary.vocabulary_manifest()`, derived from the same declaration `assert_token`
polices (EC-33, never a second copy), hashed beside the TA-grade chapter taxonomy, the
in-house precedent for a non-settings identity block. A W-signing that re-words a table now
rotates `engine_config_version` by construction.

**And it covers the MAPPING, not only the value sets — the half-closed version of this
guarantee was caught and closed in the same review's second pass.** The first fix projected
`{words, verdicts}`, which are the sets a re-ruling INSIDE the vocabulary leaves untouched:
re-assigning `spring` from *held* to *breached*, swapping a word between two puzzle types, or
swapping the two rail words all left the manifest hash exactly where it was — three
meaning-changing re-rulings, zero rotation, verified by execution against the shipped code.
`vocabulary_manifest()` gained the four declared tables and the mini-consolidation constant as
derived projections, and each of those re-rulings moves the hash. **The completeness pass that
followed found the same class one level up and closed it as a class** (round three,
2026-09-01): the projection was still HAND-TYPED in the function body with nothing deriving
that list, and it had already swallowed a declaration — the channel BASIS block, which says
which substrate each channel's words stand on and the `span_origin` every archived date is
measured from, riding verbatim in every archived token's `basis` cell. Re-declaring a channel's
`span_origin` from box to window moved no hash at all. The projection is now DERIVED from a
declaration registry (`_MANIFEST_SOURCES`), and a guard runs first inside
`vocabulary_manifest()` pinning that registry against the module's own declarations: every
declaration is either projected into the identity or excluded from it on the record with its
reason (the archive COLUMN table is the one deliberate exclusion — column names say where a
measured cell lands, never what a sentence says), a registry row naming a vanished declaration
refuses too, and the projection is eight keys today. A future table can no longer sit outside
the identity by omission — it refuses loudly at the manifest, which is where the epoch is
decided. Row ORDER inside a table is deliberately not identity — those tables are lookups
nothing reads positionally, and minting a spurious epoch permanently splits a cohort that
could have been pooled — so a pure reordering rotates nothing; both directions are pinned in
`tests/test_event_vocabulary.py`. The mint was tightened beside it: a box-origin record must
now declare an EXPLICIT `box_start_in_window` of 0, because an ABSENT declaration used to pass
and then serialize its dates as null — the same shuffle as a wrong offset, with nothing left
to detect it by.

**And the nulling itself stopped being silent** (round three, 2026-09-01). A span that cannot
land on the elected window's ruler is archived as an honest `null`, which is right and stays —
but it used to happen with no counter and no line, and every span assertion in the family's
battery was written "if the span is not None", so a channel whose bars were never rebased was
SKIPPED rather than caught (that is how the half-applied rebase above survived a whole council
review). Two closures, neither of which widens the archive contract: the serializer now NAMES
the channel on a WARNING line (logger `chrollo.engine.event_vocabulary`, carrying word, raw
span, origin and window length in trading days — one record off the ruler is an edge read, a
whole channel off it is a broken ruler), and the battery's generic span test now DECLARES each
specimen's channel roster and asserts every declared channel is present and on the ruler. It
runs over two corpus specimens deliberately: the first fire elects no inner box at all, so a
one-specimen test is structurally incapable of catching an inner-box rebase regression.

**Round four closed the same class one axis over, and pinned the promise itself.** The WARNING
above was described here and on its flag-ledger row before anything held it: the round-four
critic deleted the whole `_log.warning` call and the suite stayed green, which is this
changeset's recurring failure shape — a fix pinned by a test that cannot fail. It is pinned now
(`tests/test_event_vocabulary.py::test_the_off_ruler_span_null_is_named_on_the_log_never_silent`,
on the house caplog precedent, with an anti-vacuity leg proving spans really nulled on that
fixture). And the span was not the only thing nulling in silence: the **knowable causality
stamp** — the reader's own "the day this became knowable" — could exist and then fail to convert
onto the elected ruler, after which a lost stamp was indistinguishable from the honest "not
knowable yet" of a record still in progress. It now gets the span line's twin: same logger, same
shape, naming the channel, and firing ONLY on a stamp that existed and was lost — pinned in both
directions, so the line cannot pass its own test by warning unconditionally. The family roster
test moved with it: a settled record whose `knowable` nulled out is now a CAUGHT lost stamp
rather than a skipped one, which is the round-three span generalisation applied to the second
axis. Neither line widens the archive contract — the cell still serializes an honest null.
Independence measured at the seam, both directions: deleting the span line leaves ONLY the span
test red with the knowable lines still on the log, and deleting the knowable line leaves ONLY the
knowable test red with the span lines still on the log. Exactly one test bites each — neither
line is riding the other's pin.

**The reader-pin baseline at this seam (EC-29/EC-51/EC-52) — stated as it actually stands,
because an earlier draft of this paragraph asserted something that had not happened.**
`tests/baselines/reader_pin_baseline.json` was recaptured inside this changeset, and what a
pin exists to record — the reader VOCABULARY — is current and clean: `tools.reader_pin
--check` passes zero-diff ("every reader says exactly what the baseline recorded") across all
three populations (marks 33 / junk 18 / shadow 37). The recapture's content diff, re-verified
mechanically at this record's sealing: **2,338 leaves compared, zero changed, zero removed,
88 added — all of them the additive `role_labels.events` passthrough key** — and
`position_grid` byte-identical. No word, verdict, span, or count moved.

What is stale is only the baseline's stamped ENGINE IDENTITY. The config epoch rotated again
after that capture (the identity widenings recorded above), and the pin RECORDS its engine
stamp without asserting it, so nothing goes red and nothing is masked; the marks-corpus seal
behaves the same way, printing an epoch ADVISORY and passing on the reading. **EC-29 permits a
recapture only in a flip/seam commit and EC-51 requires it to ship in the SAME commit as the
rotation it answers — so the re-stamp is the chair's final act at the seam, never an
intermediate agent's diff.** The earlier draft claimed "the meta stamps move to the rotated
epoch", which was false and which the flag ledger contradicted inside the same changeset
(round-three completeness critic, 2026-09-01); both now say this.

**No epoch hash literal appears anywhere in this record, deliberately:** the value may rotate
once more before the seam and a literal would be stale on arrival. Read it from the engine —
`.\.venv\Scripts\python.exe -m engine_alpha.freeze.manifest --hash` — or from the generated
Settings Quick-Reference block in [engine_reference.md](engine_reference.md), the one place a
stamp is written down — machine-generated, and kept honest by `tests/test_docs_sync.py`, which
fails the suite whenever that block drifts from the live manifest. It WAS drifting when this
pass began (the round-three identity widening rotated the epoch without regenerating the
block); the regeneration landed here, and any later rotation must regenerate it again in the
rotating change.

**Acceptance:** `tests/test_sentence_family.py` — flag-off carries no sentence keys (NULL
family); flag-on measures end-to-end on a real fixture fire with the EC-32 input-tied
identity (the sentence's episode records equal the event-map tape the same evaluation
archived, span for span) and its mutation probe (a starved fold must disagree — proven).
The battery is 9 pins today, incl. the per-channel ruler test over two specimens described
above. Gates green at this task's landing (full pytest 1,811 collected THEN · ratchet 28/33 ·
reader_pin zero-diff · doctrine_audit PASS); **the suite has grown at every later pass, so the
count that means anything is the one the seam commit records** — each completeness pass added
batteries, and a stale total in a sealed record is exactly the kind of number that reads as a
claim about today. Flip = operator, after the evaluation-phase cost reads on one
nightly scan (ledger row) — that night is the trial scan, whose choreography is proposed in
§Task 14.

---

## Task 10 — refusal-side transport + the cost instrument

The full-refusal second look now has the proven lane transport and its own cost attribution
— the instrument BOTH rescue flip rows gate their bound on:

- **The composing cost twin** — `evaluation.evaluate_ticker_with_rescue_stats`, the
  OUTERMOST rung of the one selection ladder (it wraps the species twin exactly as the
  species twin wraps the near-miss twin; flags re-checked in-worker; stable shapes at every
  layer). Returns `(species_triple, rescue_row, rescue_stats)`.
- **The in-worker channel** — a refusing ticker's eval returns None, so the escalation
  books its wall-time and outcome into the per-process sink `narrative._rescue_sink`, armed
  around the ONE evaluation and always disarmed on the way out. Dark = None = books
  nothing, byte-identical. **The sink books the PAYING walk only** (council review
  2026-09-01, finding 1): the booking is last-write-wins and sums wall-time, so the species
  lane's scoped DARK second read — which re-reads the same frame under the power-play preset
  and escalates the same armed form — now runs with the sink explicitly DISARMED, through
  the one seam that moves it (`narrative.rescue_sink`, a context manager that restores
  whatever it found). Without that scoping, the exact planned flag combination for the trial
  night (a rescue flag on, the species preset live) would have summed the dark read's time
  into `rescue_ms` and overwritten the attempt's outcome — the two numbers both flip rulings
  are read from, describing the wrong walk. A nested arm is refused loudly: the outer walk
  keeps the booking rather than the two halving each other. **The species lane is not the only
  second reader inside that arm, and the sibling is parked rather than left implicit:** the
  election-stability probe (`ELECTION_STABILITY_ENABLED`, dark) runs k backward
  `read_structure` calls inside the same evaluation, so with it and a rescue flag both live, a
  backward shift that fully refuses would escalate and book into the SAME per-process sink —
  finding 1's pathology with a different second reader. Both flags are dark, so this is a
  precondition on a future flip and not a live defect:
  [pattern_register.md](pattern_register.md) row 14 (EC-50).
- **The conductor sink + pseudo-phase** — attempt rows (`{ticker, escalated, outcome}`) and
  summed counters aggregate per scan; `rescue_lane_worker_s` records in the ScanTimer
  phases ONLY on nights the lane ran (a dark scan's persisted metrics stay byte-identical),
  and the block rides `market_context["rescue_lane"]` — the same completed-scan vehicle as
  the fires, never the archive (EC-46 intact).
- **Degradation law** — a crashed base evaluation contributes nothing (an aborted walk is
  incomplete evidence — pinned including the partial-booking case); a telemetry failure
  degrades to a counted drop (`rescue_telemetry_dropped`), never a dead scan night (EC-20).

The acceptance bound the flip rows read: measured upper bound at plan time ~1,241 refusals ×
~0.25 s ≈ 5 min single-process, divided across the pool — the pseudo-phase is what turns
that estimate into a production number on the trial scan (the one armed night, and how it is
authorized, armed, read and reverted: §Task 14's trial-scan paragraph). Battery:
`tests/test_rescue_transport.py` (**8 pins** — counted 2026-09-01 at this record's seal — incl.
the REAL conductor publishing the block + phase, the dark scan carrying neither, and the two
that pin the finding-1 disarm above: the species lane's dark read booking nothing, and a
nested arm refusing rather than the two walks halving each other).

---

## Task 11 — truth tables + the re-scoped inert contract

Every judgment the language owns now carries a **ruling-sourced truth table**, one refusing
leg at a time (EC-27), with the EC-54 fail-closed rows IN the table:

| Judgment | Table | Boundary rows stated |
|---|---|---|
| S-test story admission | `tests/test_event_map.py` (standing) | the 2026-07-25 ruled legs |
| Resistance contraction | `tests/test_resistance_contraction.py` (standing) | per-leg EC-27 |
| Bar-posture variant (Task 7) | `tests/test_bar_posture_rescue.py` §truth table | strict-superset law (posture ⇒ engagement); unreadable silence refuses |
| Ceiling-rest razor (Task 6) | `tests/test_miss_program_lanes.py::test_ceiling_rest_verdict_truth_table` | **NOK 0.241 IN · ENIC 0.314 OUT** (+ DSGN/MATX/MSGS); NaN/None/0 ATR refuse; dark refuses all |
| The signed word/verdict/position sets | `tests/test_event_vocabulary.py` literal closed-set battery | retired "holding_shelf" + pre-signing "gave" refuse at mint |

A re-ruling replaces a table WHOLE, citing its new decisions.md row — never a row-edit.

**The re-scoped inert contract** — `tests/test_inert_contract.py`, the DECLARED replacement
the dissolutions (Task 14) cite in place of the retired flag-off boom proofs: OFF-state
acceptance = canonical-field byte-identity against `shadow_diff.CANONICAL_FIELDS` (the
guard's OWN list) + a declared additive field set per lane (sentence family =
`_sentence_*`, derived from the owning declaration; the rescue lanes and the ceiling rest
declare the EMPTY set — their whole surface is the canonical fields + the fire set, owned
by the shadow guard and the ratchet). Deleting the booms without this named replacement is
the cheat the plan warned about; now it is a red test.

---

## Task 12 — the acceptance protocol (assert sealed, disclose live)

Interpreter, once (docs/deploy.md §2 — bare `python` is the documented trap):
`.\.venv\Scripts\python.exe` from the repo root.

**The instruments, and what each must say per behavior move:**

```powershell
.\.venv\Scripts\python.exe -m pytest -m "not network" -q                # the suite (MANDATORY)
.\.venv\Scripts\python.exe -m tools.marks_corpus --check                # ratchet: recall on the calibrated list
.\.venv\Scripts\python.exe -m tools.shadow_diff --check                 # shadow: canonical drift on standing fires
.\.venv\Scripts\python.exe -m tools.negative_corpus --check             # precision: the 18 must-NOT-fire (forced-ON legs live in pytest)
.\.venv\Scripts\python.exe -m tools.reader_pin --check                  # the ONLY guard that sees a rewritten sentence
.\.venv\Scripts\python.exe -m tools.doctrine_audit --check              # the reading is RIGHT (needs payload + cache)
```

**One companion step belongs beside them, because a rotation without it leaves the suite
red:** any change that rotates `engine_config_version` also regenerates the Settings
Quick-Reference block in `engine_reference.md` —
`.\.venv\Scripts\python.exe -m tools.settings_reference --write` — in the SAME change. The
generated block carries the only written-down copy of the stamp, `tests/test_docs_sync.py`
compares it to the live manifest byte for byte, and it went red on 2026-09-01 for exactly this
reason: the identity widening rotated the epoch and the block still carried the previous one.
This is the cheap sibling of EC-51's rule for baselines — the recapture (or regeneration) ships
with the rotation that invalidated it.

| Move | ratchet must say | shadow must say | negative corpus | reader_pin | census |
|---|---|---|---|---|---|
| **Contraction-rescue flip** | reseal 28/33 → 30/33, EGBN+PKE pinned by name (sealed expected-misses converting IS the red-by-design; closed only at the seam commit, EC-29/51/52) | zero drift on standing fires | 18/18 with the lane armed | zero-diff | the 32-name sheet = disclosure, not a gate |
| **Bar-posture flip** | same reseal names (EGBN+PKE — SHARED with the rescue's; whichever flips first reseals) | zero drift | 18/18 armed | zero-diff | the fleet sheet **re-derived on the day** (Task 7's probe; 4 of the census's 12 at the 2026-08-31 edge) + the QTTB unreachability note |
| **Ceiling-rest flip** | reseal +NOK (2026-02-13 tier B) | rails/box/tier hold; the ELECTED WINDOW moves on the drift set — every moved trigger DISCLOSED by name | 18/18 (the ENIC razor pin) | zero-diff | the 8-conversion + 12-drift sheets |
| **Sentence-archive flip** | 28/33 unchanged | byte-identical (additive fields only — the inert contract) | unchanged | zero-diff | none (measure-only) |
| **Any razor / form re-ruling** | per its own A/B | per its own A/B | forced-ON leg re-run | the affected table replaced WHOLE | fresh sitting, dated |

**The two laws over the table:** (1) **assertions live on sealed bases only** — ratchet,
shadow fixture, negative corpus, reader pin are all frozen artifacts; **fleet drift lives in
dated, population-fingerprint-stamped sidecars** (EC-13/EC-46) handed to the operator as
ruling rows — never a silent blocker, never silently accepted (his standard verbatim: "we
measure against the calibrated list"). (2) **Pre-flip, every instrument runs in BOTH flag
states over its whole fixture population** (the pytest forced-ON legs are the committed
half); census sittings are batched one-pass sittings off the nightly path
(`tools.miss_lane_census` is the committed instrument shape). A third law follows from
finding 9 and is stated so it is not re-learned: **a census cell is an as-of read with a
shelf life measured in days** — the fleet column of a flip sheet is re-derived on the
morning of the sitting and the ruling is made on the refreshed list, while the sealed-base
acceptance evidence (ratchet names, dates, tiers) is what the flip actually stands on. One
known defect in the census shape, carried here rather than in a ruling row because it is an
engineering fix and not a judgment: `tools/miss_lane_census.py`'s `_fire_row` fills its `resistance` /
`support` cells from `Resistance` / `Support`, keys the result dict does not carry (the
rails ride as `_R` / `_S`), so every rail in `output/miss_lane_census_2026-08-28.json` and
`…-08-29.json` is null — **446 rows carry the key, 0 carry a value** (counted 2026-09-01), and
the eyeball sheets those rows feed name no levels. The 2026-09-01 reachability probe already
reads the right keys. This is load-bearing rather than cosmetic: those two sidecars ARE the
census column of three flip rows (the contraction rescue's 32 names, the dip lane's 157, the
bottoming lane's 60), so it is parked with a kill-by rather than left as a sentence —
[pattern_register.md](pattern_register.md) row 12 (EC-50).

*Two conventions.md candidates ride the operator sheet (proposed at plan delivery, NOT
appended — his call): (a) "assert sealed / disclose live"; (b) "a basis change is a
migration".*

---

## Task 14 — seams, epochs, and the two dissolutions (the choreography)

Each flag dissolves as **THREE separate events, each parity-gated** — never blended
(blending makes WCC-class drift undiagnosable):

1. **Restructure dark** — DONE this build, capture-pinned: the roster (Task 4, byte-parity
   both legs; battery `tests/test_admission_roster_contract.py`, **41 pins** counted
   2026-09-01, of which the round-three set proves the EC-55 validation is UNCONDITIONAL —
   it raises on a read that elects no box at all, with the chart untouched, and it runs
   exactly once per read; see engine_reference "Where the roster is validated"), the ladder
   fold (Task 5, pool content + narration parity), the ceiling-rest extraction (Task 6,
   flag-ON captured before/after byte-identical).
2. **Flip by operator ruling** — HIS event: the ledger row's blocking decision answered +
   the declared ratchet reseal (EGBN/PKE/NOK are sealed expected-misses whose conversion
   turns the battery red BY DESIGN — closed only at the seam commit per EC-29/EC-51,
   newline-and-encoding-pinned per EC-52) + the Task-12 protocol run in both states.
3. **Retirement by a named `engine_config_version` rotation** — settings-key removal + the
   manifest allow-list edit in **ONE commit** (the 2026-07-18 Purity-Pass precedent; a
   half-landed removal hard-KeyErrors `collect_manifest` and kills the nightly archive at
   write time), the flag-off boom proofs replaced by the DECLARED inert contract
   (`tests/test_inert_contract.py`, Task 11), the ledger row moved to Retired with the
   evidence trail.

Standing laws carried whole: flags stay lazily read at call time (the config-shadow trap —
nothing hoisted to import); the numeric razors survive in settings after their booleans die
(`LPS_CEILING_REST_MAX_BELOW_R_ATR` among them); every ruling artifact this program mints
joins the sealed set in its creating commit (this record is in `tools._bootstrap`'s sealed
files with its EC-35 case-variant refusal test — and `conventions.md`, the AP/EC settled-law
registry, joined the same seal in this change: it lives at the repo ROOT rather than under
`docs/`, which is exactly how it stayed outside the guard while five docs-root siblings were
added one at a time. That is the class's fourth late join, so the durable fix is queued and
named — and now carries a kill-by rather than only a sentence, [pattern_register.md](pattern_register.md)
row 13 (EC-50): invert `tools._bootstrap`'s deny-list into an ALLOW-list of paths a guarded
`--out` may write, after which a new ruling artifact is protected by default instead of by
remembering); every cited sidecar is tracked in the citing change (EC-53 —
`output/consolidation_evidence_2026-08-31/` and `output/consolidation_evidence_2026-09-01/`
are both force-added in this build's change-set).

### The trial scan — the one armed night every cost precondition needs (PROPOSAL, his ruling)

Every flip row in this program cites a cost bound, and every one of those bounds comes from
an instrument that only records on nights the lane RAN: the `rescue_lane_worker_s`
pseudo-phase exists only with a rescue flag on, and the sentence fold's cost is an
evaluation-phase delta that only appears once `SENTENCE_ARCHIVE_ENABLED` is on. As written,
each flip is gated on a number only a flipped scan can produce, and nothing said who arms
the flag, whether the trial night's fires and rows are acceptable before the ruling is
final, or what a revert looks like (council review 2026-09-01, finding 7). The choreography
is therefore stated ONCE, here, and the flip rows cite it. **This shape is already house
law and was cited nowhere: `conventions.md` EC-49** — *"a live-only cost bound is measured
by ONE named trial scan with pre-agreed revert"* — codified 2026-08-22 precisely so each
future lane stops re-negotiating it or stalling dark on an unmeetable gate, naming the
trace-export flag's state since 2026-08-04 as the standing casualty. What follows is EC-49
executed for this program, and it binds the same way for the two Surface-the-Read flags
(`ELECTION_TRACE_EXPORT_ENABLED`, `STRATEGY_READ_ENABLED`), whose blocking decisions are
the identical circular precondition and now point here. **The precedent is his own:** the
`POWER_PLAY_PRESET_ENABLED` flip (2026-08-19) shipped with exactly this note on its ledger
row — *"the cost instrument only reports with this flag on — so the bound arrives with the
first live nightly scan; if it is too dear the flag is a one-word revert"* — and it held.

Proposed, one flag at a time:

1. **A flip ruling authorizes exactly ONE armed nightly scan — the trial.** A YES on a flip
   row is a YES to a trial night, not yet to a standing flip.
2. **Who arms it.** The ruling session lands the one-word `config/settings.py` flip plus its
   declared ratchet reseal in ONE commit, with the Task-12 protocol already run in both flag
   states. The operator makes it live the only way code becomes live here —
   `update_dashboard.bat` — and the next scheduled scan IS the trial. No agent ever arms a
   flag on the live machine.
3. **The bound is named BEFORE the night** (EC-15: a budget is never retro-widened). Standing
   proposals, to accept or replace at the ruling: a rescue lane ≤ **5 minutes** of summed
   `rescue_lane_worker_s` (Task 10's own measured upper bound — ~1,241 refusals × ~0.25 s
   single-process, divided across the pool); the sentence family ≤ **60 seconds** added to the
   `evaluation` phase (its expected cost is low single-digit ms per FIRE and a scan fires a few
   hundred — ~1–3 s at today's ~309 fires — so 60 s only breaks on a real surprise).
4. **It is read the next morning, and the read is spelled out because a playbook must be
   executable from this page alone** (EC-36). The persisted key is **`phases_s`**, not
   `phases` — `core/pipeline/scan_metrics.py`'s `ScanTimer.finish` emits
   `"phases_s": dict(self.phases)` and its `format_scan_metrics` reads that key back.
   Three artifacts carry that dict — use the payload for the trial night's own number, and the
   history only for the night-to-night comparison:

   - **`output/screener_data.json` → `market_context._scan_metrics.phases_s`** — the
     US-Stocks payload by construction, so nothing has to be disambiguated:
     `rescue_lane_worker_s` for a rescue lane, `evaluation` for the sentence family. The same
     file's `market_context.rescue_lane` carries the attempt rows and the summed counters
     (`rescue_telemetry_dropped` among them). `cache_meta.json["scan_metrics"]` at the repo
     root is the same block for the same universe, latest run only.
   - **`output/scan_metrics.jsonl`** — the append-only history, and the ONLY place the
     preceding nights live for an `evaluation` comparison. **It is a MIXED-UNIVERSE log and
     the record carries no universe field**, so on a full nightly run the last line is the
     29-ticker Commodities+ETFs scan, the one before it the 15-ticker Sectors+Market scan, and
     the US-Stocks record is third from the end. Pick it by `counts.universe_tickers`
     (US-Stocks ~5,900 against 15 and 29) — the shape verified against the live log
     2026-09-01, 172 records of which 83 are US-Stocks.

   **What a healthy number looks like.** `rescue_lane_worker_s` at or under **300.0** against
   the ≤ 5-minute bound, read as SUMMED IN-WORKER seconds across the pool and never as wall
   clock: on the live 2026-08-31 US-Stocks scan the sibling pseudo-phase
   `power_play_lane_worker_s` read **231.72** inside an `evaluation` phase of **145.93**
   seconds of wall clock, so a lane number LARGER than the phase containing it is the
   instrument working as designed, not a stall. For the sentence family, `evaluation` against
   the preceding nights — and the honest caveat, measured on that same log: the four most
   recent US-Stocks records (2026-08-27 morning, 2026-08-27 evening, 2026-08-28, 2026-08-31)
   read **146.82 / 215.63 / 176.97 / 145.93** seconds with no flag change at all, a
   ~70-second night-to-night spread. The ≤ 60 s bound is therefore an
   explosion tripwire, not a measurement of a ~1–3 s fold; the fold's own evidence is the
   per-fire archive cells below. **An ABSENT key means the lane never ran** — on a trial
   morning that is a redeploy that did not take, not a cost of zero.

   All three artifacts are gitignored (`.gitignore:31/37/38`), so EC-49's *"cost recorded to a
   committed sidecar"* is discharged by transcribing the measured number into the flag-ledger
   row that night (step 6, EC-15) — never by assuming the artifact will still be on disk when
   someone asks.

   Stated honestly so nobody hunts for a number that does not exist: the sentence family's drop
   counter (`evaluation.SENTENCE_DROPS`) is per worker PROCESS and never aggregates, so its
   evidence is the `[sentence drop <date>]` stderr lines in the scan log plus non-NULL
   `sentence_*` cells on the night's archive rows.
5. **The trial night's output is real, and it stays.** Its fires are ordinary picks — read or
   ignore them — and its rows carry that night's `engine_config_version`, which the flip
   itself rotates (each flag is manifest-listed, so its VALUE is part of the engine identity).
   A trial night is therefore partitionable from the dark past and from any later standing-flip
   epoch forever: nothing needs deleting, and no backfill is ever run in either direction.
6. **A broken bound reverts the flag** — the one-word settings revert plus a redeploy, the
   ledger row updated with the number actually measured (EC-15), and the trial night disclosed
   in that row as trial output rather than quietly left to look like a normal night.

This is a proposal for his ruling; it designs the choreography and decides nothing. If he
wants a different shape — two nights, a weekend, a bound named differently, or the trial run
against a manual scan rather than the scheduled one — that replaces this paragraph whole.

---

## Task 15 — the operator's tuning loop

**The refusal names its one blocking leg, in his words, at his mark.** The ONE
judgment-explaining read is `metrics.mark_refusal_read(win, R, S, atr)`: the drawn rails
judged through the ACTUAL gate helpers off the `GATE_LEGS` registry (all 15 legs, ladder
order, measured + threshold as numbers — the same predicates and lazily-read settings the
election consults, EC-18/EC-43 — the crash leg included: its verdict is the election
gate's own arithmetic, pandas' NaN-skipping `.min()` against `S × CRASH_FILTER_MULT`, with
the ratio kept as a display number only), THE single blocking leg rendered through the one
operator-language vocabulary (`leg_sentence`), and the resolved SENTENCE over his rails
(the episode read's as-of profile + counts, plus `episode_summary` — the same counts in
plain trading words). NULL whole on unreadable geometry.

The EGBN leg quoted as this loop's pattern renders, in the phrase table's own words
(`trace_export._LEG_PHRASES["lower_dwell"]`, quantum `fraction`): **"time in the lower
third 0.12 vs floor 0.15"**. Quoted from the code, not paraphrased — this record is sealed
at this merge, so a paraphrase here would become permanent spec (council review
2026-09-01, finding 4a; the earlier draft quoted "closes in the bottom third 0.118 vs the
0.15 floor", which is neither the table's words nor its precision).

**Served where he already looks:** the workbench's `/calibration/engine-read` — on a
non-election with a drawn box mark, the response's `reason` (the existing hover; zero
frontend changes) becomes "at your rails: \<blocking leg sentence\>", plus " — and N more
legs short" when other legs are also short, and closing with the episode read in plain
words (" — 2 completed tests at resistance, 1 at support", or exactly "no completed tests
yet"); the raw profile tape is machine vocabulary and never reaches the hover. The
structured block rides as `drawn_mark_refusal` for any later surface. The window derives
through the ONE shared derivation (`replay.drawn_box_window`, EC-13). Attached fresh per
request — marks are editable ground truth (EC-9), so the diagnosis is never baked into the
engine-read cache; and when the session holds several box marks (he draws an inner and an
outer) the diagnosis targets the **most recently edited** one, ties broken by highest id —
a declared pick order, so "at your rails" always names the framing he is working on now.
When every leg passes at his rails, the reason says so honestly: the miss is upstream. The
whole attach is a read-only diagnostic passenger on an already-computed response — any
failure degrades to the raw reason with one logged line, never a 500 on the read he is
looking at.

**Every surviving knob co-expressed as measured pairs:** `tools/knob_pair_table.py` — per
knob, every mark's measured value beside the live floor, hinge marks first; under
`--what-if LEG=VALUE`, the EXACT list of marks a proposed threshold flips (both
directions), derived from the leg registry's own comparison — so "two completed tests
should be enough" arrives with its own flip list. Population + fingerprint of exactly the
set scored + engine epoch stamped (EC-13); sidecar-only (EC-46), sealed-output-guarded;
unreadable marks reported loudly, never silently skipped.

**Its printing rule, added at the round-three completeness pass and stated because a
threshold ruling is read off these lines:** every number in one printed BLOCK — a floor and
the marks listed under it — renders at ONE shared precision, widened exactly as the shared
pair formatter widens a pair until no two DISTINCT numbers in that block render the same
string; count quanta stay counts. A pair formatter cannot do that job, because it only ever
compares one mark against the floor, and both failure modes were reproduced on the real print
path before being fixed: three distinct marks at 0.118 / 0.121 / 0.1249 against a proposed
floor of 0.10 all printed "(0.12)", destroying the ordering the ruling turns on; and a mark
widened to "(0.1449)" sat under a header floor formatted alone as "0.14" — a line
arithmetically impossible on its face. One helper (`fmt_block`), used by BOTH printed blocks:
the pair table above the flip list had the identical defect (two hinge marks measuring 0.105
and 0.104 both printing "0.10"), which is why the fix is a rule rather than a patch to the
one place the critic named. Scope stated honestly: the block precision is computed over the
marks actually PRINTED (the first five per leg, hinge marks first), so the same mark can
render at different precisions in two runs — deliberate, because coherence is a property of
what is printed, and the full-precision values stay in `--json`.

**Three residuals on that printed surface, found by the same audit and left unfixed on
purpose, now carried with an owner** ([pattern_register.md](pattern_register.md) row 15,
EC-50): the leg HEADER drops the operator's unit word on the two counted legs (the shared
phrase is truncated at the number placeholder and "trading days" sits after it, so a header
reads "window  (window >= 20)" while the per-mark refusal sentence at the bottom of the same
output says "window 40 trading days vs floor 20"); the flip lines print Python list repr
(brackets and quotes) on the one line a threshold ruling is read from; and `n_scored` counts
the rows that scored while the marks fingerprint stamps everything the loader returned,
unreadable marks included — disclosed rather than wrong (the UNREADABLE block prints), but the
stamp does not describe the population the numbers above it came from. Each is a wording or
stamping question rather than a defect in the read, and the first would move a phrase in the
shared vocabulary table — a re-wording, not a rendering fix.

**One verdict path, with ONE named exception:** the workbench Test/engine peek resolve through
`replay.snapped_election` + the shared `election_identity.projection` (unchanged — the
harness's own lens), and the refusal read consumes the gates' own helpers, so no threshold,
comparison, or vocabulary exists twice — **except the crash leg, deliberately and
commented in place** (the crash block inside `metrics.mark_refusal_read`, just above its
`measured_by_leg`). The exception exists because the leg registry is
the thing that does not hand the crash statistic back, so the read cannot consume a helper
that would give it: it reproduces `_validate_base_quality`'s arithmetic VERBATIM instead —
pandas' NaN-skipping `.min()` against `S × CRASH_FILTER_MULT`, the multiplication form, never
the division form — and keeps its ratio as a display number while the gate keeps the verdict.
Stating it as a reproduction rather than as "no duplication anywhere" matters, because the
reproduction is what a re-typed twin got WRONG: the twin named crash as THE blocking leg on
damaged-data windows the real ladder passes (council review 2026-09-01, finding 8), which is
why three of the eleven pins below hold this one leg to the gate. The clean fix — fold the
statistic into the registry so the helper hands it back and the reproduction disappears —
is parked with a kill-by ([pattern_register.md](pattern_register.md) row 11, EC-50), not
claimed as done. **The naming channel** stays the existing per-setup
note + the marking bar's fixed event vocabulary — the words he can cite are the same closed
set the engine emits (Task 1); no new UI (the read panel stays deferred by his ruling).

Battery: `tests/test_mark_refusal_read.py` (**11 pins**, counted 2026-09-01 at this record's
seal — registry-order legs, first-refusal blocking law, three-state NULL, the sentence riding,
the what-if derivation, the post-review five: the crash leg agreeing with the REAL gate on a
NaN low, on a real crash and at the razor edge, `episode_summary` always a closed plain-words
value, and the read serving that summary beside — never instead of — the raw tape; plus the
eleventh, that the what-if flip list prints formatted numbers and never a raw float);
`tests/test_calibration_router.py` for the served layer (the blocking-leg copy, the
"and N more legs short" clause, the all-pass branch, the most-recently-edited mark pick,
and the broken-query degradation); and `tests/test_knob_pair_table.py` (**19 pins** — 11 at
this record's first seal, 8 added at the round-three completeness pass, counted 2026-09-01)
for the tool, **eight** of which pin its PRINTED output by driving the real `main()` — leg
header, measured pair, the plain-words episode clause, the raw tape absent from a card that
HAS one, a what-if flip line, the non-finite `--what-if` pre-flight refusing before a single
character is printed, and the two the printing rule needed end to end: the what-if header
carrying the block's own floor, and the pair table never collapsing two hinge marks. Three
more pin the rule itself at the helper (distinct values never rendering as one number, a flip
entry never contradicting the floor it is listed under, and the ordinary case staying at two
decimals). **One of those pins replaced a test
that could not fail:** the "raw tape never reaches the print" assertion was made on a card
whose tape was EMPTY, so `'' not in out` held under any rendering at all — including the
tape-first rendering it was supposed to forbid. It is now two tests with two fixtures, one
carrying a real tape (five completed tests at resistance, four at support), and the split is
the round-two lesson written into the battery: an assertion that something is ABSENT is only
worth its fixture's ability to make it PRESENT.

**Two copy debts, named at this record's first draft and BOTH PAID before it sealed
(2026-09-01).** They are kept here rather than deleted, because the pair is the clearest
example this program has of the class: a rendering rule stated as an absolute while one
string still broke it. (a) `respect_share` read "share of **bars** respecting the rails" —
a noun, not a unit, and the last occurrence of the banned word in an operator-facing string.
It now reads **"share of trading days respecting the rails {m} vs floor {t}"**, and all
fifteen rendered leg phrases were then swept phrase by phrase: zero whole-word hits for
bar/bars/session/sessions, zero constant names, zero retired jargon. Pinned two ways in
`tests/test_trace_export.py`, because either alone is escapable — a whole-table banned-word
sweep (which a benign re-wording slips past) AND exact literals for the three legs that carry
a unit word. (b) `tools/knob_pair_table.py` printed the raw profile tape where the served
plain-words `episode_summary` sat one key away on the same dict; it now prints the summary,
so the machine tape reaches no operator surface anywhere — hover or tool. The scope of the
absolute is worth stating once, so a later sweep does not read it as licence: it governs the
phrases RENDERED to him, not the internal leg quantum keys (`box_gates` still keys a count as
`bars`; that key is wire vocabulary consumed by the formatter and never displayed, and
renaming it would be a re-measurement seam, not a wording fix).

---

*(Later task records append below as they land.)*
