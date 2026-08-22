# FINAL REVIEW — "One System" consolidation review + research
Council run 2026-08-22-2250 · main @ dd4c0ab (clean) · explicit operator invocation

## Scope
The operator's ruling: no more parallel VERSIONS of code solving the same thing — Chrollo is ONE
system that recognizes setups from price-action patterns he describes. This run: (1) the complete
version census with a MERGE/DELETE/FOLD/KEEP ruling per site ("parked indefinitely" banned),
(2) the architecture answer for how a described pattern enters the one engine, (3) full bug hunt.
Out of scope: implementing fixes; weight/threshold changes; sealed corpora; booting the backend.

## Context (grounding gates)
pytest 1,624 passed / 0 failed (368s) · eslint 0 · frontend node suite 289/289 (Dodds re-ran).
Census corrections measured this run (Leach, live DB mode=ro): setup_archive holds **9,952 rows**
(not 9,438); **12 rows** carry species data (admitted_dark + refused_clock — the preset has been
stamping since 08-19); commodities_etf universe has archived **0 rows ever** (confirm intended);
near_miss_archive 1,123 rows; zero duplicate identities anywhere.

## Council dispatched
All 10 seats ran and reported: Fowler, McKinney, Beck, Ramírez, Dodds, Leach, Hunt, Performance,
Saarinen, Friedman. No seat came back empty. 85 raw findings aggregated → deduped → capped at 15
(P3 register below cap). Chair verification re-confirmed the five load-bearing claims against the
real code (chips guard absent; sort_values('Score'); doctrine_audit absent from tests/; the
pivot hunk on main; the 173.8 MB log regrowth — diagnosed as INFO chatter on stderr, not a crash).

---

# Findings

## P1

**1. Seven commits of merged work + the only validated engine fix exist on one physical disk — push now**
- File: main (7 ahead of origin), branch `proposal/first-legal-look-fix` (no remote copy)
- Council: Hunt × Carmack — Security P9; Beck (CI gates) cross-ref
- Finding: The last two days of merged work live only in this machine's .git; the nightly backup
  deliberately excludes the repository. Compounding it: the two HARD corpus replays (seed-recall,
  marks-corpus) run only in CI, and CI only fires on push — so the must-fire ratchets have not
  executed for the whole unpushed window.
- Consequence: One disk failure erases the work (the worktree-lost-work class, again); a ratchet
  regression could sit invisible on main meanwhile.
- Fix: `git push origin main` and `git push origin proposal/first-legal-look-fix` (backup, not
  approval). Two commands, no ruling attached.

**2. The parked engine fix is CORRECT — verdict MERGE, through a new Correction lane, never as a parked branch**
- File: `proposal/first-legal-look-fix` @ 80efa9f; engine_alpha/structure/power_play.py:208-257
- Council: McKinney (oracle: 175/175 exact vs main's 169/175 with both bias directions
  reproduced) × Friedman (fork-cause confirmed: no lane exists for a correctness fix to a ruled
  mechanism) × Beck (merge conditions) — EC-45/EC-15
- Finding: main's "first day the engine may consider a Power Play" arithmetic reads reserved
  edge sessions it should not see; the branch's corrected walk matched the real seeder exactly on
  every one of 175 randomized episodes. KILL is indefensible; PARK is the disease.
- Consequence: THE engine and a corrected twin coexist; main's committed program doc still claims
  the census evidence is as-of-consistent — a claim already falsified.
- Fix: MERGE in ONE change that also (a) re-runs the clock-8 census so the cohort statistics the
  2026-08-18 ruling cites are re-derived (EC-15), (b) trues the program-doc claim, (c) reconciles
  main's exact as-of test pins (Beck: any pin that moves gets its new value hand-derived),
  (d) records the decisions.md "evidence re-derivation" row. Presumption of continuity: the
  ruling STANDS unless the re-derived headline crosses the ruling's own acceptance condition —
  then and only then the merge waits on the operator.

**3. The screener's rank order comes from the retired score while every badge on it comes from the live grade**
- File: core/pipeline/screener.py:327 (`sort_values(by='Score')`); output/dashboard.py:471-474;
  useScreenerFilters.js:137
- Council: Saarinen × Performance × Fowler — three seats independently — EC-28 spirit
- Finding: Tier letters and the /100 grade derive from the new TA grade; the ORDER of the grid is
  still the legacy ~122-point raw sum (which includes the breadth term the grade exiled and
  ignores the grade's warnings). They agree today only because every divergence knob is neutral —
  nothing pins that.
- Consequence: On the primary triage surface, top-left-is-best is computed by the system the
  operator retired; the first A/B that moves a warning cost forks rank from badge permanently and
  silently (the WCC rank-3-vs-19 class of surprise).
- Fix: Repoint ranking to the grade at the retirement seam, operator-gated (it changes what he
  sees first). This is the retirement program's first task, not a side effect.

**4. The rollback the legacy path is kept for is already broken — demoted RS/Uptrend chips fire on EVERY legacy-epoch row**
- File: setupTagsData.js:47-49 (`firesAt` has no cap>0 guard) + setupScoreMath.js:15-16 (caps 0)
- Council: Fowler × Dodds (independent, executable repro) — EC-8/EC-18/EC-34
- Finding: The engine guards zero-cap chips dead; the frozen JS twin does not, so since the caps
  were corrected to 0 its threshold is "anything ≥ 0" — always true. Every pre-flip archive row
  the operator reviews wears false Strong-RS and Uptrend chips today, and a TA-grade rollback
  would light them on every live card. No test sits on the refusing side.
- Consequence: The legacy path's entire justification — a faithful rollback — has lapsed while
  its tax (dual-epoch switches, frozen mirror, extra test surface) is still being paid.
- Fix: Interim two-line guard + one wrong-side test if retirement waits on the operator;
  otherwise the retirement (finding 7) deletes the whole path.

**5. The doctrine gate is the only guard with zero automated execution — and it already went silently dark once**
- File: tools/doctrine_audit.py (spy at :234-284); no pytest import, no CI step
- Council: Beck × Carmack — quality-testing P1/P10; the 9fbbca3 precedent
- Finding: Of the seven offline guards, six now have real pytest or CI execution; the ONE that
  proves the reading is RIGHT (not merely unchanged) has neither, and it monkey-patches engine
  seams by direct assignment — the exact arity trap that already blinded it once.
- Consequence: The next engine signature change re-blinds the doctrine battery and nothing goes
  red anywhere.
- Fix: A cheap pytest plumbing module on the pointer-audit pattern: assert the spied signatures
  still match, drive one committed synthetic frame through the battery with a bite-proof.

**6. The marks graduation channel has been sealed shut for ~4 weeks and no surface says so**
- File: tools/guided_list_export.py:50-56 (fingerprint pin); live marks DB (34 marks, drifted
  since ~2026-07-27); the workbench (no drift surface)
- Council: Friedman × Carmack — EC-9/EC-12; quality-ux P6
- Finding: The live marks fingerprint moved past the operator-approved pin, so the export
  correctly refuses — but the refusal is discoverable only by running the CLI. The operator's
  newest ground truth cannot enter the engine's test standard, and the open Trigger-coverage
  seal gap can only close "inside the next graduation event" — which nothing schedules or signals.
- Consequence: The loop's intake of HIS OWN eye is silently stalled — the exact opposite of the
  omnipotent-reader goal.
- Fix: Advisory line in `marks_corpus --check` ("live DB holds N marks beyond the sealed 33,
  drifted since DATE — a graduation event is owed") + a one-line workbench banner; convene the
  first graduation event now (it also closes the Trigger seal gap).

## P2

**7. The staged retirement of the legacy score path — the master version-site — has three undeclared blockers and a data-side ruling; execute it as ONE program**
- Council: Fowler (census, 20+ sites) × Beck (test moves) × Dodds (consumer map) × Leach (archive
  ruling) × Ramírez (server sites) × Saarinen (verdict surfaces) — EC-3/EC-28/EC-29/EC-42
- The program, in order: (1) rank repoint (finding 3, operator-gated); (2) serialize the LPS
  earned-fraction engine-side — the lens's LPS row currently divides by the legacy cap mirror,
  so the delete-unit no longer closes as written (checklist falsified by the 08-12 lens build);
  (3) extract the presentational tag catalog/tones/tooltips out of setupTagsData.js so the file
  that remains IS the legacy path and deletes clean; (4) rewrite the tier band/width-cap tests
  against the LIVE ladder first — calculate_structure_tier currently has ZERO direct tests, its
  coverage rides entirely on the retiring twin; (5) the deletion wave per Fowler's census
  (engine ladder + flag + frontend remnant + dead sorts + tests), manifest rotation = the
  declared EC-29 seam; (6) Leach's archive ruling: ALL columns stay as history, writers KEEP
  stamping score/tier (NOT NULL model contract; computationally free) — retire only the ladder
  path, wire legacy fields, and frontend re-derivation; the seed scan-back election and the
  ranking re-key to the live basis at this seam, never separately; (7) server-side: the
  /archive/calibration legacy-analytics block retires with the path; the chart envelope drops
  its legacy-only verdict cells; (8) the four surfaces printing the raw score unlabeled beside
  grade-derived tiers (cockpit chips, watchlist column, weekly review, hover glance) switch to
  the grade with its /100 marker (missing wire fields = backend additions per EC-28).
- Precondition: the operator's one-line flip-good declaration (the ledger's own gate).

**8. `triggered` means two different things in the two maturation lanes, and the report card deflates trigger rates over 973 still-maturing rows**
- File: core/archive/forward_returns.py:214-231 vs near_miss_outcomes.py:150-166; analyze.py:557
- Council: Leach × Carmack — EC-23/EC-18
- Finding: Fires stamp 0 = "not yet"; near-misses (per the 2026-07-26 ruling) stamp 0 only after
  full maturation, NULL while maturing. The report card averages the blend, so the newest —
  most decision-relevant — cohorts systematically understate trigger rates.
- Fix: Land the reporter's maturity gate now (one predicate, no schema change); fold the fires
  onto the ruled three-state form at a named seam later.

**9. The scoring clamps award FULL points on NaN**
- File: engine_alpha/scoring/scoring.py:25-45 (`_clamp`/`_ramp`); unguarded inputs evaluation.py:521-545
- Council: McKinney × Carmack — quality-llm P2; the Reading Model's absence-is-neutral law
- Finding: `min(cap, nan)` returns cap, so a NaN input scores a term's MAXIMUM (verified live).
  Latent — 0 of 9,951 archived rows affected — but the failure mode is maximal and invisible:
  one NaN silently promotes the least-measurable chart.
- Fix: Non-finite reads as None (neutral 0.0) at the two shared seams; one NaN/±inf test per
  shape. Byte-identical on every finite input; no flag needed.

**10. The live-updates lane is structurally unreliable: the fills stream kills itself every idle 15s, and connecting the broker orphans every open stream**
- File: routers/portfolio_streams.py:77-97 (wait_for cancels the generator — verified
  empirically), :32-40 (silent 1 Hz swallow); ibkr/broadcaster.py:27-72 (binds to the broker
  thread's loop, wipes live subscribers)
- Council: Ramírez × Carmack — quality-backend P5/P1
- Fix: Use the sibling's task-based wait (the correct implementation is 40 lines above the broken
  one); bind the broadcaster to the server loop captured at startup and stop clearing
  subscribers; add the loud log line to both catch sites. The journal is safe throughout
  (fills persist independently) — this is the live UI channel only.

**11. Two unguarded routes let a drive-by web page starve the nightly scan**
- File: routers/archive_actions.py:252-337 (GET /analysis spawns a 120s subprocess; POST
  /update-returns holds SCAN_LOCK up to 300s; the 18:00 scan does a non-blocking acquire and
  SKIPS when held)
- Council: Ramírez × Hunt — quality-backend P4
- Fix: Add the same-app header dependency both newer surfaces already carry; optionally let the
  scheduled scan retry once after a bounded wait.

**12. The one live "rules re-declared client-side" breach: the zone-coverage unreadable floor**
- File: narrativeRead.js:99-106 (hand-mirrors STORY_UNREADABLE_ZONE_COVERAGE, no pin test)
- Council: Dodds × Fowler (independent) — EC-28
- Fix: Serialize the resolved judgment (or the floor) from the engine; pin test as fallback.
  Recalibrating the engine floor today silently splits the caveat from the judgment it explains.

**13. The "near trigger" judgment is declared three times — and the copies already disagree on the denominator**
- File: home/ActionCenter.jsx, home/WatchlistZone.jsx, ScreenerStockLens.jsx, useScreenerFilters.js
- Council: Dodds × Carmack — EC-3
- Finding: Two hand-typed 2% constants, the fired rule twice, three classification vocabularies;
  the home zones divide by trigger, the lens divides by price — the same concept prints
  different numbers on different surfaces today. Legitimately client-side (live prices), so it
  must live ONCE.
- Fix: One shared triggerProximity module with one denominator convention, four consumers.

**14. The branch graveyard — per-branch disposition (Hunt's content-verified census)**
- Council: Hunt × Carmack — Security P5/P9; the worktree-lost-work precedent
- Verdicts: `engine/ta-score-v2` (both commits re-implemented by the live V2; targets retired
  paths) → tag `retired/…` then DELETE local+origin. `wip/audit-tool-tweaks` (enhances a deleted
  tool + imports retired paths; would not even import) → tag-then-DELETE.
  `wip/pivot-canon-2026-07` (payload verbatim on main, blob-verified; only a 196 KB evidence PNG
  differs — the documented bloat pattern) → DELETE; the memory claim "PARKED UNMERGED" is false
  and must be corrected. `wip/signal-edge-backtest` (STRANDED-VALUABLE: 2,246 lines of
  edge-honesty rigor main lacks — deflated Sharpe, event study, regime segmentation — but its
  diff would strip an EC-14 sealed-output guard) → operator go/no-go: re-land on current main
  with the guard restored, or tag-then-DELETE if the program is dead.
  `worktree-council-p2-followups` → recover THREE stranded pieces as fresh commits (the
  close-coverage vectorization + its 69-line test file, the universe-scoped archive-cache key,
  the scan-metrics routing test), then tag-then-DELETE. `stash@{0}` → drop (verbatim on main,
  verified). 11 remote-only refs → delete server-side (7 merged, 4 superseded/dead).
  Also: 7 empty worktree husk directories → delete; the `claude/focused-ellis-499011` build
  referenced in memory resolves NOWHERE — locate the cloud session or declare it dead.

**15. The decision surfaces themselves are minting forks — five truth debts, one intake design**
- Council: Friedman × Carmack — EC-15/EC-16/EC-42; quality-ux P1/P9
- The debts: (a) docs/BACKLOG_2026-07.md still instructs "rebuild TA Score v2 from a fresh
  branch" for a feature LIVE since 08-09 — committed guidance to mint a forbidden parallel
  version; true the file or stamp it SUPERSEDED. (b) Chat rulings have no landing guarantee (the
  2026-07-28 trend-terminal ruling took three weeks of forensics; the two record surfaces still
  disagree whether the debt is paid). (c) The three questions blocking the parked fix live only
  in an unmerged branch's commit message — deleting the branch deletes the ask. (d) The flag
  ledger's rows bury the blocking decision in 8,000-character narratives — give every row a
  one-line "DECIDE NOW:" head. (e) A refused flip's aftermath ("the blocker is now a program")
  names a program nothing creates or owns. The remedy is the intake design below.

## P3 register (below cap — full detail in the seat files)
Dead RS sort control (3 seats) · TIER_RANK hand-copied ladder · three inline null-guard
re-declarations · species lane re-runs frame prep (~40-80 worker-s/scan) · breadth-50 computed
twice (~1.6s) · two unbounded backend caches · calibration candle-cache can never cover a recent
as-of (rate-limit pressure mid-sitting) · would_be_score/tier unfillable columns → DROP ·
trend_base_count never >1 in 3,150 rows — probe the predecessor-walk predicate · seed --force
wipes operator curation · hermetic fixture rebuild is an unguarded one-command reseal ·
docs/decisions.md + anchor ruling record outside the sealed-output guard · Python deps unpinned
beyond yfinance (no lock; disaster-recovery risk pairs with finding 1) · service log regrew to
173.8 MB in 2 days (INFO chatter on stderr; rotation ask now urgent) · traversal_density twin
fold · scan_status dead schema branch · _parse_n_setups phantom entry point · archive lens
starved of per-term points · analyze.py opens the books read-write · mythril has no channel
token · ticker typeface swaps mid-click · six deprecated utcnow call sites · archive Score
column lacks an epoch tell · geometry-invariant module can go green-by-skip · live/seed
twin-parity test tolerates the divergence it exists to catch.

---

# The consolidation verdict table

| Version site | Verdict | Owner / gate |
|---|---|---|
| Legacy score path (engine ladder, flag, wire, frontend remnant) | **DELETE — execute the retirement program (finding 7)** | Operator's flip-good line, then one program |
| `proposal/first-legal-look-fix` | **MERGE via the Correction lane (finding 2)** | Census re-run in the same change |
| Story-form species read | **KEEP-WITH-REASON** — verified ONE admission seam, EC-18-clean, dark flag + banked evidence = the protocol working; its graduation A/B gets a register row | McKinney F4 |
| atr_squeeze "rebase twin" | **KEEP + record the null** — measured: already self-relative (corr −0.254 vs the −0.73 that condemned tightness); not a twin | decisions.md row |
| rs/uptrend weight-0 knobs | **KEEP engine-side** (uniform arithmetic, measure-first archive); DELETE the frontend remnants with the retirement | — |
| detect_boxes vs narrative read | **KEEP-WITH-REASON** — shared primitives, parity test-pinned, different question | — |
| Dual-vocabulary archive serializers | **KEEP** — books of record speak both epochs forever; ruled deliberate | Ramírez census |
| `engine/ta-score-v2`, `wip/audit-tool-tweaks`, `wip/pivot-canon-2026-07` | **tag-then-DELETE / DELETE** (superseded, content-verified) | Finding 14 |
| `wip/signal-edge-backtest` | **MERGE via re-land (guard restored) or close the program** | Operator go/no-go |
| `worktree-council-p2-followups` | **Recover 3 stranded pieces, then tag-then-DELETE** | Finding 14 |
| stash@{0}, 11 remote refs, 7 worktree husks | **DELETE** | Finding 14 |

Zero sites ruled "parked."

# The architecture answer (Friedman's research, chair-endorsed)

The loop's spine WORKS — the species program went from the operator's words to a live preset in
five days, and the flip gate caught WCC when it mattered. What forks versions is everything
around the spine: no lane for correctness fixes to ruled mechanisms, no durable home for
described-but-unmeasured patterns, no queue for the questions the operator is owed, and a
graduation channel that seals shut silently. The design (full text in friedman.md §Part B):

1. **Pattern Register** (`docs/pattern_register.md`, append-only): one row per described
   pattern — verbatim words, catalog event, specimens, state
   (DESCRIBED→SPECIMENED→MEASURED→BUILT-DARK→RULED), kill-by. Seeds: the five scattered
   "recorded as theory" fragments + the story-form graduation program + parked-branch owners.
2. **Specimens into the ONE marks DB** under population labels — never a seventh hand-rolled
   JSON store; buys the validated loader, fingerprints, digests, and graduation for free.
3. **The program spine templated** from the species program (graveyard check → refusal autopsy →
   census → ruling sheets → dark build → gated flip). Unchanged, just no longer bespoke.
4. **The Correction lane** — the missing lane finding 2 exercises: fix + evidence re-derivation +
   ruling true-up in ONE change; continuity presumed unless the ruling's own acceptance condition
   is crossed; seven-day SLA; "proposal branch" abolished as a resting state.
5. **The trial flip** — a live-only cost bound is measured by one named scan with pre-agreed
   one-word revert (codifies the species preset's ad-hoc exception; unblocks the trace-export
   flag = the operator's future in-app "why did you refuse this chart" surface).
6. **The Asks queue** (`docs/asks.md`): every question owed to the operator, one line, landed in
   the same change that creates it; a chat ruling lands its decisions.md row and closes its ask
   in the same session.
7. **The graduation cadence**: fingerprint drift is REPORTED, and drift + operator = a convened
   graduation event (the first one is owed now; it also closes the Trigger seal gap).

# Verdict

**Not yet one system — but one program away from it, and the engine core itself is sound.**
pytest 1,624 green, no lookahead primitives anywhere in the engine, closed sets enforced three
ways, writer families disciplined, the flip gate battle-proven. The single most important thing:
execute the legacy-path retirement (finding 7) and adopt the Correction lane (finding 2) — those
two moves eliminate every live parallel version and the mechanism that mints new ones. The most
critical expert domain this run: the version discipline itself (Fowler/Friedman axis), with
Hunt's push-now as the zero-cost immediate action.

# Findings breakdown by expert

| Seat | Raw items | Into final review |
|---|---|---|
| Fowler | 8 (1 P1) | #3, #4, #7, #12 + census |
| McKinney | 4 (1 P1) | #2, #9 + story-form/atr_squeeze verdicts |
| Beck | 8 (1 P1) | #1(CI), #2(pins), #5, #7(tests) |
| Ramírez | 14 (0 P1) | #10, #11, #7(server) + P3s |
| Dodds | 9 (0 P1) | #4, #7(consumers), #12, #13 + P3s |
| Leach | 7 (0 P1) | #7(archive ruling), #8 + census corrections |
| Hunt | 12 (1 P1) | #1, #14 + security-clean record |
| Performance | 3 (0 P1) | #3(cost shape), scan economics + P3s |
| Saarinen | 8 (1 P1) | #3, #7(surfaces) + P3s |
| Friedman | 12 (2 P1) | #2(lane), #6, #15 + the intake design |
