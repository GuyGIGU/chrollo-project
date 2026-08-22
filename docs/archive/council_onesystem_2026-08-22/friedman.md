# Friedman — UX / THE RESEARCH SEAT: the operator→engine loop, end to end

Council review 2026-08-22-2250 · repo @ main `dd4c0ab` (clean) · read-only run
Lane: the describe → engine reads → engine outputs loop. Part A audits the loop as built and
names where practice forked versions instead. Part B designs the definitive intake shape.

---

## Part A — the loop as built, stage by stage

Walked artifacts: the calibration workbench (`CalibrationTab.jsx` + `useCalibrationMarks.js` +
`webapp/backend/routers/calibration.py`, marks DB read `mode=ro`: **34 marks**, newest UNF
2026-07-27) → the graduation gate (`tools/guided_list_export.py`, pin `b671e056…`) → the sealed
corpus (`docs/marks/` + the four EC-44 docs-root corpus files in `tools/_bootstrap.py:36-55`) →
census/harness instruments (`tools/power_play_census.py`, `marks_corpus.py`, `shadow_diff.py`,
`event_map_census.py`) → the flag ledger (`docs/flag_ledger.md`) → `docs/decisions.md` → the
flips. Fork sites examined via git: `proposal/first-legal-look-fix` (`80efa9f`), the refused
story-form flip (`a3397a5`), `wip/pivot-canon-2026-07` (`281db4f`), `stash@{0}`, the retired
Trigger re-pin branch (decisions.md 2026-08-20 row).

**Verdict in one paragraph.** The loop's spine is real and recently proved itself at its
hardest point: the story-form flip was attempted, the shadow guard caught a 2.2×-wider WCC
election the marks ratchet could not see, and the flip was refused with the evidence recorded
(`a3397a5`; decisions.md 2026-08-19). Describe→live also works when a program carries it: the
Power Play species went from the operator's words (2026-08-14) to a live preset (2026-08-19)
in five days, through marks, census, sealed verdict sheets, dark flags, and rulings. What the
loop lacks is everything AROUND that spine: there is no lane for a correctness fix to a ruled
mechanism (so fixes park as branches while main keeps the falsified record), no landing
guarantee for rulings given in chat, no intake register for described-but-unmeasured patterns,
no queue for the questions the operator is owed, and the one legal graduation channel has been
sealed shut for nearly four weeks with no surface saying so. Each fork in the census is one of
these absences made concrete — not a person routing around the law, but the law having no lane
for the case in hand.

### Why each fork happened (the hypothesis test the brief asked for)

- **`proposal/first-legal-look-fix`** — hypothesis "no lane for a correctness fix to a ruled
  mechanism": **CONFIRMED**. The commit message states the cause verbatim: "the corrected
  arithmetic re-derives the evidence the clock-8 ruling was made on. Landing it silently would
  move the ground under a ruling." Neither existing lane fits — the EC-8 dark-flag lane would
  flag-gate a bug (preserving wrong arithmetic as the default), and the direct-land lane would
  silently re-derive ruled evidence. With no third lane, it parked. (Finding 1.)
- **Story-form refusal (`a3397a5`)** — hypothesis "the flip protocol is heavyweight": **REFUTED
  for the flip itself** — the weight is exactly what caught WCC and must not be reduced. The
  fork is in the AFTERMATH: the ledger converts the blocker from "a decision" into "a program",
  and there is no intake for programs, so refused-but-sound code idles dark with only a kill-by
  bounding it. (Finding 6.)
- **`wip/pivot-canon-2026-07`** — hypothesis "ruling latency": partially. The proximate cause
  was mechanical (the shared checkout had to move to main for the near-miss deploy, so 25
  modified files were parked verbatim), but the reason it is STILL parked 26 days later is that
  "the owning program picks it up from here" named an owner that does not exist. (Finding 12.)
- **Uncommitted patches / lost worktrees** (the first-legal-look fix lived as an uncommitted
  patch before the branch; four finished fixes died in an abandoned worktree per the standing
  memory) — same absence as above: session-end work has no required landing artifact.
- **Ruling latency generally**: real, but the deeper defect is that open asks have no home —
  they live in branch commit messages, ledger row tails, and agent memories, so the operator
  cannot see what he is being asked, and sessions cannot see what was already asked. (Findings
  4, 7.)

### Findings

FINDING 1:
- Title: A correctness fix to a ruled mechanism has no lane — the fix parks as a second version while main keeps the falsified record
- File: branch `proposal/first-legal-look-fix` @ `80efa9f` (2026-08-20); `engine_alpha/structure/power_play.py:208-266` (main); `docs/power_play_program_2026-08.md:804`
- Principle: EC-45 (as-of arithmetic), EC-15 (falsified record trued in the same change); quality-ux P9 (trust destroyed by single failures)
- Severity: P1
- What's wrong: A confirmed as-of correctness defect (council 2026-08-20 finding 3; oracle-validated 65 exact/0 late vs 1/66) sits unmerged because landing it would re-derive evidence the clock-8 ruling consumed, and no protocol lane exists for that case. Meanwhile main's committed evidence record still claims "the census evidence is as-of-consistent" — a claim the same council falsified — because the correcting doc text lives only on the branch.
- Consequence: The exact disease the operator ruled against: THE engine and a corrected twin of it coexist, main asserts something known false, and every day of latency grows the re-derivation debt (the clock-8 census statistics are already stated as "unmeasured, must not be quoted").
- Fix: Adopt the Correction lane (Part B §5): land the fix, re-run the affected census in the same change, true the ruling row per EC-15, presume the ruling stands unless its own recorded acceptance condition is crossed — and give parked corrections a hard SLA so "proposal branch" stops being a resting state.

FINDING 2:
- Title: The one legal graduation channel is sealed shut and no surface says so — the operator's newest ground truth cannot enter the standard
- File: tools/guided_list_export.py:50-56 (pin `b671e056…`); live marks DB (34 marks, drifted since UNF 2026-07-27); webapp/frontend/src/components/CalibrationTab.jsx + routers/calibration.py (zero graduation/fingerprint surface)
- Principle: EC-9 (one-way human-gated graduation), EC-12; quality-ux P6 (data freshness indicators, metrics that drive action)
- Severity: P1
- What's wrong: The live marks-DB fingerprint moved past the operator-approved pin ~2026-07-27, so `guided_list_export` refuses (by design — the seal working). But the refusal is discoverable ONLY by running the CLI: `OPERATOR_APPROVED_FINGERPRINT` is referenced nowhere else in the tree, no check reports the drift as an advisory, and the calibration workbench — the surface where the operator creates the drift — says nothing.
- Consequence: The operator's 34th mark has sat outside the engine's test standard for almost a month invisibly; the known Trigger-coverage seal gap (decisions.md 2026-08-20: closable "only inside the next graduation event") stays open indefinitely because no next graduation event is scheduled or even signaled as owed.
- Fix: Report the drift where eyes are — an advisory line in `marks_corpus --check` output ("live DB holds N marks beyond the sealed 33, drifted since DATE; a graduation event is owed") and a one-line banner in the workbench; define the graduation EVENT cadence in Part B §7.

FINDING 3:
- Title: The backlog file is a falsified decision surface that instructs building a second version of a live feature
- File: docs/BACKLOG_2026-07.md:22-24 (and :19, :25); merge `dd4c0ab` ("the backlog closes")
- Principle: EC-15/EC-42 (a snapshot a sibling change falsified is a falsified record); quality-ux P9
- Severity: P2
- What's wrong: The "living checklist" still carries, unticked, "TA Score v2 … Next: rebuild from a fresh branch off main" — for a feature that shipped by another route and FLIPPED LIVE 2026-08-09 — and the 2026-08-20 merge commit announces "the backlog closes" without touching the file (its slope-knob item was in fact done in that very merge, also unticked).
- Consequence: A fresh session following the repo's own committed guidance would mint exactly the parallel version the operator has forbidden; the announcement/artifact mismatch also erodes trust in every other checkbox in the file.
- Fix: True the file once against reality (tick/annotate the shipped and superseded items, point the TA-v2 entry at the flip evidence), or stamp it SUPERSEDED with a pointer to the successor surface; fold its still-live items into the intake register (Part B §2).

FINDING 4:
- Title: Rulings given in chat have no landing guarantee — one took three weeks of forensics to reconstruct, and the two record surfaces still disagree about whether the debt is paid
- File: docs/decisions.md 2026-08-14 row ("this row exists so that cannot happen again") vs docs/flag_ledger.md:27 tail ("the 2026-07-28 IRMD/IART/CYRX ruling still owes its operator-confirmed decisions.md row")
- Principle: EC-16 (evidence lives in committed paths); quality-ux P9
- Severity: P2
- What's wrong: The 2026-07-28 trend-terminal ruling survived only in an agent session memory; it was corroborated 2026-08-14 only because the operator independently re-marked IRMD to the same date. Even now, decisions.md reads the corroboration row as discharge while the ledger reads the operator-confirmed original row as still owed — the loop's two authority surfaces disagree about an open debt.
- Consequence: A later session already told the operator his gate was "blocked purely on your eye" because the ruling was invisible — a mis-relayed decision on the loop's most expensive channel (his attention).
- Fix: Make the same-session landing rule mechanical via the Asks queue (Part B §6): a ruling received in chat lands its decisions.md row and closes its ask row in the same change; and reconcile the two surfaces' current disagreement in one line each.

FINDING 5:
- Title: The flag ledger's rows have outgrown the reading task they exist for — the blocking decision drowns in the program history
- File: docs/flag_ledger.md:26-34 (longest single line 8,688 characters; one table cell per program history)
- Principle: quality-ux P1 (structure necessary complexity, don't bury the actionable core) + P6 (a decision surface must drive the decision)
- Severity: P2
- What's wrong: EC-15's append-and-true discipline is being satisfied by accretion: each row is now a full multi-month narrative inside one markdown table cell, with the current blocking decision embedded mid-stream. The measured consequence is recorded inside row 27 itself: the 2026-08-13 what's-next board mis-reported the flag's blocker because even the summarizing agent could not extract it.
- Consequence: The one human who must rule reads walls; cheap unblocks go unnoticed (the AR row's current open item — re-run the diff tool against the re-keyed climax — is a one-command evidence refresh that has waited since 2026-08-19).
- Fix: Keep the history, but give every row a mandatory one-line "DECIDE NOW:" head (the current blocking decision + the single artifact to look at + the date it became decidable), and let the what's-next relays quote only that line. No information is removed; it is fronted.

FINDING 6:
- Title: A refused flip's aftermath has no named next state — "the blocker is now a PROGRAM" with no program, no owner, no intake
- File: docs/flag_ledger.md:34 (`POWER_PLAY_STORY_FORM_ENABLED`); docs/decisions.md 2026-08-19 refusal row
- Principle: EC-15 (what actually remains open must be restated) — restated as "a program" that does not exist; quality-ux P6
- Severity: P2
- What's wrong: The refusal correctly converted the blocker from a same-day toggle into "its own program with a real A/B over the firing cohort" — and stopped there. Nothing creates, schedules, or owns that program; the banked EGBN/PKE acceptance evidence idles; only the 2026-10-31 kill-by bounds the wait.
- Consequence: Sound, operator-validated reading code (the resistance contraction reads EGBN and PKE the way he does) idles dark for want of a slot, which is precisely how "described and even built" fails to become "the one engine reads it".
- Fix: A refusal ruling that names a program as the blocker must, in the same change, open that program's intake-register row (Part B §2) with a scope line and a kill-by — the program becomes a tracked thing, not a phrase.

FINDING 7:
- Title: The questions blocking a parked fix live only in an unmerged branch's commit message — invisible from main, dead with the branch
- File: `80efa9f` commit body ("THE THREE QUESTIONS: …"); no reference to the branch or its questions anywhere in main's docs
- Principle: EC-16 (a pointer that dies on a fresh clone is not an evidence trail — here it is the ASK that dies)
- Severity: P2
- What's wrong: The operator is owed three specific rulings (land vs census-first; do MGNX/QLYS/STRZ read correctly; does losing five names change the clock-8 ruling), and the only copy of those questions sits in the head commit of a branch main does not reference. `git branch -d` would delete the ask itself.
- Consequence: The ruling can never arrive, because the question is never put anywhere the operator (or a later session briefing him) looks; the fork self-perpetuates.
- Fix: Open asks land in the committed Asks queue (Part B §6) in the same change that parks the work; a parked branch is additionally listed with a kill-by, same discipline the ledger already applies to flags.

FINDING 8:
- Title: Operator-described patterns land as scattered "recorded as theory, unmeasured" fragments — no state, no index, no owner
- File: docs/strategy_alpha.md:395 (after-shakeout LPS vs Last Supper); docs/decisions.md 2026-08-12 row tail (same), 2026-08-14 rows ("transition zone", "O'Neil/Minervini as principle sources"); docs/BACKLOG_2026-07.md §3 (EGBN two-form LPS)
- Principle: quality-ux P1/P6 — the intake's front door does not exist; strategy_alpha's own law ("a new signal declares its event") has no register to declare INTO
- Severity: P2
- What's wrong: At least five operator-described, engine-relevant patterns exist only as prose asides in three different documents. Nothing tracks their state, nothing schedules their measurement, and nothing prevents a description from being re-described (or worse, independently re-built) later. The Power Play program proves the describe→live path works — but it worked because one session hand-built a bespoke program; the next description starts from zero.
- Consequence: This is the operator's actual ask failing at its first step: his words have nowhere durable to land unless a session happens to open a program that day.
- Fix: The pattern intake register — Part B §2 — with the existing fragments migrated as its seed rows.

FINDING 9:
- Title: Every program mints a new mark store — the mark populations are multiplying past what EC-9/EC-13 govern
- File: docs/marks/ (2 files) + docs/phase_c_marks_2026-07.json + docs/trend_end_marks_2026-08.json + docs/power_play_marks_2026-08.json + docs/power_play_verdicts_2026-08-18.json (tools/_bootstrap.py:47-55) + the calibration DB
- Principle: EC-9 (two populations, one crossing), EC-13 (one validated loader) — both written for two populations; there are now six stores in four formats
- Severity: P3
- What's wrong: EC-44 correctly sealed the docs-root JSON corpora after the fact, but each was hand-rolled in its own shape with its own loader, outside the calibration DB → graduation machinery entirely. The marks DB already carries a `label` column that could have namespaced these populations under the ONE loader and fingerprint recipe.
- Consequence: Each new pattern's specimens will, by precedent, mint store number seven; per-population fingerprints, validity judgments, and staleness reads have to be reinvented each time.
- Fix: Rule (Part B §3) that new-pattern specimens enter the calibration DB under a population label, graduating per EC-9 with per-population pins; docs-root JSON corpora are grandfathered, not a precedent.

FINDING 10:
- Title: EC-8's pre-flip cost bound is unsatisfiable for lanes whose cost only manifests live — the chicken-and-egg is documented twice and codified nowhere
- File: docs/flag_ledger.md:63 (preset row: "could not be measured while the lane was dark"); :31 (`ELECTION_TRACE_EXPORT_ENABLED` blocked on a re-measure "on a real nightly scan")
- Principle: EC-8 (agreed cost bound measured BEFORE the flip)
- Severity: P3
- What's wrong: Two flags have now hit the same wall: the cost instrument only reports with the flag on, but the protocol demands the bound before the flip. The species preset resolved it ad hoc ("if it is too dear the flag is a one-word revert") with operator consent — a sound pattern that exists only as one row's prose.
- Consequence: Each future lane re-negotiates the same exception, or stalls dark on an unmeetable gate (the trace flag has waited since 2026-08-04).
- Fix: Codify the trial flip as a convention (Part B §5): one named nightly scan with the flag on, cost recorded to a sidecar, revert semantics pre-agreed — the bound then exists and the real flip ruling proceeds under EC-8 as written.

FINDING 11:
- Title: The operator has no in-app "why did you refuse this chart" — the loop's describe step starts blind
- File: webapp/backend/routers/ (no trace/refusal route); tools/structure_case_audit.py + tools/near_miss_report.py (CLI only); decisions.md 2026-08-14 MAN row ("seeding refusals are invisible to BOTH the election trace and the near-miss lane")
- Principle: quality-ux P9 (reasoning visibility); the explainability rule in strategy_alpha ("the engine is never allowed to be blind to WHY")
- Severity: P3
- What's wrong: The engine's self-narration exists (the trace, the near-miss lane, the case audit) but every drop of it is agent-run CLI; the operator's first move on a new pattern — "the engine misses this chart, why?" — requires a session. And the MAN autopsy showed one whole refusal class (seeding refusals) is invisible even to the instruments.
- Consequence: Descriptions arrive slower and vaguer than they need to; the ELECTION_TRACE_EXPORT flag that would fix the surface half is itself stalled on Finding 10's chicken-and-egg.
- Fix: Treat the trace-export flip (via the trial-flip lane) as intake infrastructure, not a nicety; separately, the seeding-refusal visibility gap deserves a census-instrument entry when the species program resumes — noted for McKinney's lane, not re-designed here.

FINDING 12:
- Title: Session-interruption parking names owners that do not exist — parked work has no follow-up mechanism
- File: branch `wip/pivot-canon-2026-07` @ `281db4f` ("the owning program picks it up from here" — 26 days, no program); `stash@{0}` (foreign last_supper hunk, unresolved since July)
- Principle: EC-16 in spirit; quality-ux P9
- Severity: P3
- What's wrong: The park commit is honest and verbatim — and terminal. Part of its payload later landed by other routes (wyckoff_canon.md), so nobody can now say which hunks are stranded versus superseded without a diff archaeology session.
- Consequence: Real measured work (the last-supper pivot features + 69 lines of tests) rots; the operator's "no more versions" is violated by entropy rather than intent.
- Fix: A park is legal only WITH an intake-register row (owner-or-kill-by) in the same change — the flag ledger's "flipped, deleted, or re-dated with a written reason, never silently carried" applied to branches; Hunt's census rules the current six.

---

## The intake design

**The shape in one paragraph.** One front door (the Pattern Register), one specimen store
(the calibration DB, labeled populations), one program spine (the species program's skeleton,
made a template), the existing dark-flag/flip machinery unchanged, plus the two lanes the
audit shows missing: a **Correction lane** for fixes to ruled mechanisms, and a standing
**Asks queue** so the operator's attention is scheduled instead of ambushed. Everything below
is process on existing rails; the three genuinely new conventions are named as candidates at
the end. Nothing here weakens the flip gate — the WCC catch (shadow + ratchet, both, always)
is the loop's crown jewel and stays exactly as it is.

### 1 · What a "pattern" is, at intake

The intake admits exactly what `strategy_alpha.md`'s own third law already demands: **a new
signal declares its event.** An operator description enters the system when it can be written
as (a) his verbatim words (the naming doctrine — the record says the behavior he named, never
an invented umbrella word), (b) the catalog event it reads or the explicit new catalog entry
it proposes, and (c) at least one named specimen — ticker + date — the way MAN/FTNT anchored
the species. A description without a specimen is a note, not an intake; the operator is asked
for the chart, which he always has (his descriptions have never once arrived without names).

### 2 · Where the description lands — the Pattern Register

A single committed, append-only file (working name `docs/pattern_register.md`; EC-16 committed
path). One row per described pattern, carrying: the date and verbatim words; the catalog
event; the specimens; the current **state** — DESCRIBED → SPECIMENED → MEASURED → BUILT-DARK
→ RULED (LIVE / DEAD / superseded) — and a **kill-by**, borrowing the flag ledger's exact
discipline: by its date a row is advanced, killed, or re-dated with a written reason, never
silently carried. The register is the successor to today's scattered "recorded as theory,
unmeasured" fragments, which migrate in as the seed rows (after-shakeout LPS, the transition
zone, O'Neil/Minervini principle entry, EGBN's two-form LPS, the story-form graduation program
from Finding 6). The register is also where a parked branch or refused-flip aftermath gets its
owner row (Findings 6, 7, 12) — so "parked" always resolves to a register row with a date,
and the branch census can be read against it. decisions.md remains the ruling record;
the register holds STATE, decisions.md holds JUDGMENT; a register row advancing to RULED
cites its decisions.md row, never restates it.

### 3 · Specimens — into the ONE marks DB, labeled

New-pattern specimens enter the existing calibration marks DB under a population label (the
schema's `label` column), drawn in the existing workbench — not a fresh docs-root JSON (the
grandfathered EC-44 files are history, not precedent; Finding 9). This buys, for free, every
guarantee the loop already built: the one validated loader and fingerprint recipe (EC-13),
editability with revision bumps (EC-9), frame digests binding each mark to the exact bars the
operator saw (EC-10/EC-12), and per-population graduation into `docs/marks/` when a pattern's
marks harden into an acceptance standard. Harness reports already stamp which population they
scored — labeled populations make that stamp meaningful for pattern work. The workbench needs
one small honest addition either way (Finding 2): a line stating how many marks sit outside
the sealed standard and since when.

### 4 · Measurement and build — the program spine, unchanged but templated

The species program is the proven walkthrough; the design makes its skeleton the standing
template so the next description does not start from zero: **(0)** graveyard check —
Tested-DEAD and AP-* before anything (decisions.md's own "how a change should go", step 1);
**(1)** refusal autopsy of every specimen (why does the engine not read it today — the MAN
autopsy is the model); **(2)** a census instrument entering shared reads through the one
override with derived key sets (EC-43), as-of-honest (EC-45), writing sidecars only (EC-46);
**(3)** operator ruling sheets where his eye is the calibrator (the 40-verdict pattern, sealed
per EC-44); **(4)** the build dark behind EC-8 with EC-17 acceptance and the ledger row in the
same change; **(5)** the flip, operator-gated, shadow + ratchet both. Nothing in stages 4–5
moves; they are cited so the register's states map one-to-one onto gates that already exist.

For lanes whose cost only manifests live, codify the **trial flip** (Finding 10): one named
nightly scan with the flag on, the cost recorded to a committed sidecar, one-word revert
semantics agreed in the ledger row beforehand. That converts the species preset's ad-hoc
exception into the standard way EC-8's bound gets measured when darkness itself blocks the
measurement — and it is the path that finally prices `ELECTION_TRACE_EXPORT_ENABLED`, the
flag that would give the operator the in-app "why" surface (Finding 11).

### 5 · The missing lane — the Correction lane

**Definition.** A correction is a change whose purpose is to make an existing ruled mechanism
compute what its ruling already says it should — a bug fix, an as-of repair, an EC-45
violation — as opposed to a new lever, which changes what the engine believes. The
first-legal-look fix is the type specimen; the 2026-08-19 climax re-key is the proof the lane
can work when run properly (a Tested-DEAD-prescribed repair, landed same-day WITH its
re-measurement and its decisions.md row, ratchet held).

**The lane, in order, all in ONE change:** (1) the fix, with a regression battery that pins
the corrected behavior; (2) **re-derivation of every evidence artifact the affected rulings
cite** — the census re-run the proposal branch left as a question becomes a requirement, so
the change ships with old-headline vs new-headline stated side by side; (3) EC-15 true-up of
every ruling row and program-doc claim the re-derivation touches (main must never keep a
claim the fix falsifies — the exact failure standing today at
`power_play_program_2026-08.md:804`); (4) a decisions.md row of a standing kind, "evidence
re-derivation", recording what moved.

**The presumption of continuity — the lane's one genuinely new rule.** The ruling STANDS by
default. The operator is asked to re-rule BEFORE merge only when the re-derived evidence
crosses the ruling's own recorded acceptance condition (for the clock-8 ruling: "clock 8's
elected cohort is the only forward-positive one" — if that headline survives re-derivation,
the fix lands and the row is trued; if it flips, the merge waits on him). This inverts
today's default — park until asked — into land-with-notification, which is the only default
compatible with "one system": a known-wrong engine is a worse state than a ruling whose
evidence got honestly re-derived under it. The refusal to land silently was CORRECT under
current law; the lane changes the law so honesty and landing stop being alternatives.

**SLA.** A correction lands or dies within seven days of its confirming review. While it
waits on a crossed-threshold ruling, its questions live in the Asks queue (below), never in a
commit message. "Proposal branch" is thereby abolished as a resting state: a branch older
than its SLA is a red pointer-audit-class condition, not a parking space.

### 6 · The Asks queue — scheduling the operator's attention

One committed surface (working name `docs/asks.md`, or a fixed section atop the flag ledger):
every open question owed to the operator, one line each — date asked, the question, what it
blocks, the artifact to look at. Sessions append in the same change that creates the ask
(EC-42's build-end true-up extended to questions); a ruling received in chat lands its
decisions.md row AND closes its ask row in the same session — so an unlanded ruling stays
visible as an open ask instead of surviving only in an agent memory (Finding 4). The current
seed content is already known: the three first-legal-look questions, the AR-diff re-measure,
the trend-terminal §(a) program decision, the story-form graduation program's go/no-go, the
June forming-bar era, the graduation event below. Pair this with Finding 5's "DECIDE NOW:"
row heads and the operator's whole decision surface becomes: one short queue, each line one
look, each look one artifact.

### 7 · The graduation cadence — reopening the sealed channel deliberately

Drift between the live marks fingerprint and the export pin becomes a REPORTED state, never a
silent one (Finding 2). When drift exists, a **graduation event** is owed: the operator
reviews the delta (new marks, edits), re-approves, and the re-pin lands as its own declared
change — which is also, by the 2026-08-20 ruling's own words, the only place the Trigger
coverage gap can close, so the recipe widening rides the first such event. EC-29 already says
baselines reseal only at declared events; this names the event and gives it a trigger
condition (drift exists + operator convened) instead of leaving it to whenever someone
notices. The first graduation event is owed NOW — the channel has been shut since 2026-07-27.

### 8 · What this deliberately does not change

The flip gate and its dual guard (shadow + ratchet — the WCC lesson), the sealed corpus and
EC-7/EC-9/EC-14 seals, measure-first (no thresholds at add time), geometry as the only veto,
the append-only decisions record, and the operator as the sole flip authority. The design
adds lanes AROUND the spine; the spine held under fire twice in one week (WCC caught, the
Trigger re-pin refused) and is the reason the one system is still one system at its core.

**New conventions this design needs** (candidates, for the chair to number): (i) the
Correction lane — a fix to a ruled mechanism lands with its evidence re-derived and its
rulings trued in the same change; continuity presumed unless the ruling's own acceptance
condition is crossed; seven-day SLA. (ii) The trial flip — a live-only cost bound is measured
by one named scan with pre-agreed revert, recorded to a committed sidecar. (iii) The landing
rule — parked work and open questions exist only with a register/queue row in the same
change; a chat ruling lands its row in the same session. Everything else above runs on
EC-8/9/13/15/16/17/29/42/43/44/45/46 as already written.

---

*Method note: all git reads were `log`/`show`/`diff` (no checkout); the marks DB was read
`mode=ro`; no repo file outside this output was written.*
