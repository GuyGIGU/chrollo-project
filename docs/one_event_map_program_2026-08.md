# The ONE Event Map — program record (2026-08)

Program 1 of the breathing-reader architecture (operator commission 2026-08-29:
*"we got to fuse everything into one. I don't want to have a bunch of peices of
code competing for solving the same problem"*). Fold the engine's rail-event
readers into ONE vocabulary with ONE position attribute over TWO deliberately
preserved geometries, plus one new positioned-shelf event. **Zero behavior
change**: every task proves itself by byte-parity or a committed pin; geometry
unification stays the operator's deferred Option A (decisions.md 2026-08-10).

The working plan (13 tasks, full expert attribution) lives at repo-root
`PLAN-one-event-map.md` — gitignored by design; THIS file is the committed
record (EC-16). Council-plan run: `.council/council-plan-output/2026-08-29-2154/`
(brief F1–F10 + ten seat files). Implement run: `.council/implement-output/
2026-08-30-1313/session-state.md`.

## The rulings this program executes (decisions.md, verbatim rows)

- **2026-08-29 — rails are AREAS**: position is THREE values (`at_ceiling` /
  `mid_range` / `on_support`); "above resistance" refused as a blanket rule —
  context (LPS · recovering upthrust · rest-on-R · new base) decides, and the
  engine cannot dispatch on a context it never named.
- **2026-08-30 — the rail area is ±0.50 ATR, symmetric, both rails, ATR units**
  (evidenced onto the incumbent `TOUCH_TOLERANCE_ATR`; no number moves).
  Position vocabulary ONLY — a 0.5-ATR allowance as a gate is Tested-DEAD twice.
- **2026-08-30 — the three ceiling STATES** (resting on / at / semi dwelling)
  are visual descriptors, never a ranking; *"the bars after wards determine the
  meaning"* — a departure is bars clearly continuing up; the right edge is
  honestly UNDETERMINED (no-lookahead).

## The census evidence (committed instrument: `tools/correspondence_census.py`)

Measured 2026-08-29 on the operator's 35 drawn marks, chair-verified: a true
FUSE is falsified (387 puzzle events vs 184 episodes; strict agreement
251/323 = 77.7%, 22.3% contradiction, from the `EPISODE_MAX_GAP_BARS` merge
horizon and the two "failed" referents); ADOPT-ONE moves elections (the episode
layer feeds two election gates + four TA terms); the readers already share
their swing skeleton, so all disagreement lives in the episode layer. Hence
NAMES-ONLY over two preserved geometries, with per-record basis provenance.

## Task record

| # | Task | Status | Proof |
|---|------|--------|-------|
| 1 | Pre-fold full-output baseline (`tools.fold_parity --capture`) | **DONE 2026-08-29** | Clean engine tree at `0f607fd`; 37 tickers / 32 fires / 220 fields; immediate `--compare` byte-identical; provenance stamp in the council-plan run dir. Not committed by design (deterministic from the committed fixture; SHA+manifest is the seal). |
| 2 | Per-event reader pin (`tools/reader_pin.py` + committed baseline + plumbing tests + AGENTS.md line) | **DONE 2026-08-30** | 88 charts (33 sealed marks / 18 junk / 37 shadow incl. the 5 rejects), ~5s, deterministic. RED-proven on BOTH layers (runtime-perturbed `EPISODE_MAX_GAP_BARS` and `_EVENT_HOLD_MIN_BARS` → FAIL naming chart/surface/event/field). Gate: pytest 1,755 green. |
| 3 | Census promoted to a committed instrument | **DONE 2026-08-30** | `tools/correspondence_census.py`; reproduces the sealed evidence exactly (387/184/362/167/293/160, 35 cards, fingerprint `92d6a529…`). Three adaptations only (house bootstrap, EC-14 guard, provenance docstring with the two frozen census conventions). |
| 4 | The vocabulary as a pure projection (`engine_alpha/structure/event_vocabulary.py`) | **DONE 2026-08-30** | Reader OUTPUT dicts in, nothing else (the load-bearing constraint). Declared word tables (one dict per axis; unknown value raises, never coins). DARK — zero live importers. 9 literal-fixture tests; pin PASS; pytest 1,764 green. |
| 5 | Basis + origin provenance on every folded record | **DONE 2026-08-30** | `BASIS_CONSTANTS` per channel (the census's two mechanisms as values); declared caller operands (F9-preserving); `window_span` refuses without a declared offset. Design catch: emit-seam stamping would leak fields into the ARCHIVED tape — basis rides the projection channels instead. |
| 6 | One position mechanism on the ruled three values, ±0.5-ATR tolerance seam | **DONE 2026-08-30** | `MINI_POSITION_TOL_ATR` 1.0→0.5 (the ruled area; fixes the chair-verified band-overlap defect — `mid_range` was unreachable under 2.0-ATR parents). Raw signed distances stamped beside the band at the ONE `select_inner_box` point (ride `InnerBox.detection`; no dataclass change). Darkness re-proven at the seam: pin recapture diff = **readings byte-identical on all 88 charts, position grid rows 2/3 only**. Battery expectations re-derived by the ruled arithmetic (refusal legs untouched). doctrine_audit PASS. Full battery (pytest + marks ratchet + shadow) run at the seam. |
| 7 | Retire `holding_shelf` as a NAME (code identifiers only) | **DONE 2026-08-30** | Smaller than planned: the stored string + signed label are FROZEN history (AP-12), so only code identifiers moved — `_holding_shelf_verdict`→`_rest_verdict` (the operator's word), the `_swing_type` param, the local flag; the retired term and its stored spelling meet at exactly ONE documented line (`_swing_type`). One test symbol substitution; no expected value touched. **Proof: `fold_parity --compare` vs the Task-1 pre-fold baseline = 37 tickers byte-identical** (the rename sits in live election code and changed nothing); reader pin PASS with NO recapture; 64 LPS-battery tests; doctrine_audit PASS. |
| 8 | Coverage proof: the vocabulary can NAME the four above-R contexts | **DONE 2026-08-30** | Five committed tests (tests/test_event_vocabulary.py): LPS ✓ · recovering upthrust ✓ (word=upthrust, verdict=held) · departure ✓ (markup, gave) · right edge ✓ (engagement word + verdict=open, never pre-typed) · completed rest-on-R ✓ (the SOS hold). **Honest gaps stated in the test file:** the mini-consolidation-resting-on-R becomes a TAPE record only when Task 9 lands (today it is named by the dark `InnerBox.position`); "forming a double base" is the chain reader's structure-level axis, deliberately outside the rail tape. Treatment untouched — Program 2's. |
| 9 | The positioned-shelf event (additive, measure-first, knowable-bar from first commit) | **DONE 2026-08-30** | NO new detector — the 2026-08-23 ruling already named the event: the tape record IS the elected inner box projected (`_fold_mini_consolidation`, a fourth `unify_events` channel consuming `InnerBox.detection`). Word = `mini_consolidation` (ruled; zero new jargon); position + raw distances ride from the Task-6 stamp; knowability DECLARED by the caller (`at_right_edge` → in_progress, undeclared reads in_progress — fail-closed); election_dependent=True. **Zero engine-file changes beyond the dark projection module**; the critical wrong path (emitting into `_box_events_with_meta`'s stream) was identified and avoided — it would have perturbed the narrative grades → setup_quality → behavior. 18 projection tests green; pin PASS untouched. Fire-path serialization = Task 10. |
| 10 | The position archive family, all landing sites | **DONE 2026-08-30** | `inner_position` (closed set + model CHECK, EC-19) + `inner_position_r_atr`/`_s_atr` (the raw distances) — evaluation result keys → ORM → live writer; the seed writer auto-covers via the model-driven mapper (the column-parity AST guard proves it; no hand list grown, AP-7). **Seam audit: fold_parity diff vs the pre-fold baseline = exactly the three new keys, ZERO value drift on all 220 existing fields.** Near-miss population: N/A by structure (refusal rows carry no inner box) — stated, not skipped. Wire serving DELIBERATELY deferred until the operator signs the labels (asks.md; measure-first). EC-19/EC-22 battery committed. |
| 11 | Display-label contract for new + retired values | **DONE 2026-08-30 (contract; frontend untouched by scope)** | The retired `holding_shelf` keeps its signed label forever (already present — AP-12). The new position words deliberately do NOT reach the wire: the label registry is an operator-SIGNED artifact; serving + labels land as one small change after signing. Two asks.md rows landed (the word table + the position labels), each with blocks + look-at pointers (EC-50). |
| 12 | ONE declared manifest rotation | **DONE 2026-08-30** | Four reader-behavior constants promoted to `config/settings.py` + the frozen manifest, VALUES UNCHANGED: `EPISODE_MAX_GAP_BARS` 2 (what an episode IS) · `EPISODE_DRIFT_MIN_BARS` 3 · `EVENT_HOLD_MIN_BARS` 6 (was import-shared across the two readers) · `MINI_POSITION_TOL_ATR` 0.5 (the ruled knob). All use sites converted to LAZY settings reads (AP-3/AP-10 — an import-time default is a copy no flag override can move). `engine_config_version` rotated `0ac88199…`→`92863be0…` as the declared epoch. RECOVERY_* / `_PRIORITY` / `_TIGHT_BOX_WIDTH` stay module-internal per the narrow rule (dark or single-module). Plus Hunt's ratchet advisory: `marks_corpus --check` now prints an epoch-differs ADVISORY (never a failure) — its FIRST run revealed the sealed baseline was frozen at `424fbfa1…`, an epoch OLDER than this branch's start: the gap had been open for weeks. Gates: pin PASS (values unchanged), fold_parity byte-identical, doctrine PASS, manifest-completeness green. |
| 13 | The "nothing moved" verdict + concordance + doc truth-up + pointer audit | **DONE 2026-08-30** | Concordance rows in `wyckoff_canon.md` §5 (holding shelf → REST; "freshness read" → the stale-support check, retired by operator order). `strategy_alpha.md` Reading Model gains **"The rails are AREAS"** (the ruled doctrine + the one-event-language principle). This program record. Pointer audit run (its one flag = this doc while untracked; resolves at commit). The composite "nothing moved" verdict: **fold_parity 37/37 byte-identical to the pre-fold capture (modulo the three DECLARED position keys) · reader_pin 88 charts zero drift (modulo the DECLARED grid seam) · ratchet 28/33 held · shadow byte-identical · doctrine green** — every "modulo" is a named, audited, deliberate seam. |

## The word table (operator ruling pending — engine-internal until ruled)

Declared in `event_vocabulary.py` (one dict per axis; re-wording = one-line
edit; nothing serializes these): spring / sos / upthrust / markup / lps / range
verbatim; `rejection` → **touch_and_pivot** (his phrase); S-family `test`/
`failed` → **support_test** with verdict held/gave; unresolved waves/episodes →
**support_test / resistance_test** with verdict **open** (typing before
resolution would be lookahead by naming); episode outcomes → verdicts
(completed→held, failed→gave, open→open, unreadable→unreadable).

## Standing guard-rails

Zero behavior change; no geometry unification; no gate loosening; emitted/stored
vocabulary never changes (AP-12 — the fold renames code, never cells); no
baseline recapture outside declared seam commits (EC-29); evidence rides
sidecars only (EC-46); the projection layer may never receive measurement
inputs (the fourth-reader failure mode).
