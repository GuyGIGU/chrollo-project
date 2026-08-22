# Hunt — repository hygiene as RISK + security pass
Council review 2026-08-22-2250 · main @ dd4c0ab (clean) · read-only run

Method note: every branch was judged by content, not by `git cherry` alone (all six cherry as `+`
because main re-landed work through different commits). Per-file blob comparison against today's
main is what the verdicts below rest on.

---

FINDING:
- Title: Seven commits of merged work exist on exactly one physical disk
- File/Branch: main (dd4c0ab..6792d78, ahead of origin/main @ 3448fdb by 7)
- Principle: Security P9 (assume breach — design for the failure case)
- Severity: P1
- What's wrong: The last two days of merged work — the pointer-audit pytest gate, the backlog
  sweep, the slope-knob wiring, the trend-terminal test — live only in this machine's `.git`.
  The nightly `tools/ChrolloBackup.ps1` deliberately snapshots only the DB, uploads,
  calibration_frames and state files, NOT the repository, and its own header records that this
  box has a single physical disk. The stash and the local-only proposal branch (below) share the
  same exposure.
- Consequence: One disk failure erases the pointer-audit gate and the backlog-sweep merge with
  no recovery path — the exact loss class the project already lived through once with the
  worktree-lost-work incident.
- Fix: `git push origin main` now (origin is GitHub — real off-machine durability), and push
  `proposal/first-legal-look-fix` in the same breath. This is a two-command fix with no ruling
  attached; pushing is not merging.
- Ruling-recommendation: KEEP + PUSH immediately.

---

## 1. Local branch census (6 branches)

FINDING:
- Title: proposal/first-legal-look-fix — unruled correctness fix, and the only branch with no remote copy
- File/Branch: proposal/first-legal-look-fix @ 80efa9f (2026-08-20, based directly on main dd4c0ab)
- Principle: Security P9; EC-15 (decision records must resolve)
- Severity: P2
- What's wrong: Classification: STRANDED-VALUABLE pending ruling. The payload (an oracle-validated
  fix to first_legal_look in engine_alpha/structure/power_play.py, +148 lines of tests, program
  doc) is content main does not have, it is based on current main so it applies cleanly, and the
  commit message itself says "do not merge unruled". It is the only local branch with no origin
  tracking ref — single copy on this disk.
- Consequence: If the disk dies before the ruling, the validated fix, its 65-exact/0-late oracle
  evidence tests, and the program doc are gone. Separately, an unruled branch with no deadline is
  exactly the "parked indefinitely" state this run outlaws.
- Fix: Push the branch today (backup, not approval). Then close the ruling: McKinney's seat rules
  the correctness this run; the operator's flip ruling should get a date the way the AR flag got
  its kill-by 2026-09-15.
- Ruling-recommendation: KEEP + push now; merge/kill per McKinney's verdict and the operator's
  ruling — do not let it age past a named date.

FINDING:
- Title: engine/ta-score-v2 — both commits re-implemented by the live TA_SCORE_V2; targets retired paths
- File/Branch: engine/ta-score-v2 @ 47d6ade (2026-07-02; 2 unmerged commits, 433 behind)
- Principle: Security P5 (shrink the attack surface); EC-3 (no twin paths)
- Severity: P3
- What's wrong: Classification: SUPERSEDED. The two commits (P1a two-stage 0-100 skeleton, spring
  tag-fold) edit `core/scoring/` — a path that no longer exists on main (Engine-Alpha extraction
  moved it to `engine_alpha/scoring/`). The concepts both shipped live in the 2026-08 TA_SCORE_V2
  build: the spring term exists today as SCORE_SPRING inside `_ta_v2_terms` in
  engine_alpha/scoring/scoring.py. The branch is a fossil of the earlier attempt at the same idea
  — a second VERSION in exactly the operator's sense.
- Consequence: Its presence invites someone to "finish Wave-1" against dead module paths, forking
  the one live scoring system.
- Fix: Tag `retired/ta-score-v2-wave1-2026-07` at 47d6ade, then delete the local branch and the
  origin copy.
- Ruling-recommendation: tag-then-DELETE (local + server).

FINDING:
- Title: wip/audit-tool-tweaks — tool enhancements written against pre-extraction imports; main's tool evolved past it
- File/Branch: wip/audit-tool-tweaks @ 6b87bee (2026-07-13; 362 behind)
- Principle: Security P5; EC-3
- Severity: P3
- What's wrong: Classification: SUPERSEDED. Half the payload enhances tools/phase_a_pip_diff.py —
  a file main deliberately deleted whole-file in the Purity task-9 prune of 17 closed-track
  probes. The other half enhances tools/structure_case_audit.py but imports
  `core.pipeline.evaluation` and `core.structure`, both retired paths; it would crash on import
  today. Main's structure_case_audit meanwhile grew its own richer feature set (engine trace,
  pair cascade, roots table, find_last_valid) through the engine-alpha era.
- Consequence: Unappliable code kept as a branch reads as pending work; it is not.
- Fix: Tag `retired/audit-tool-tweaks-2026-07` if a pointer is wanted, then delete local + origin.
- Ruling-recommendation: tag-then-DELETE.

FINDING:
- Title: wip/pivot-canon-2026-07 — the parked payload has fully re-landed on main; the memory claim "PARKED UNMERGED" is stale
- File/Branch: wip/pivot-canon-2026-07 @ 281db4f (2026-07-27; 109 behind)
- Principle: Security P5; EC-15 (a stale decision record misleads)
- Severity: P3
- What's wrong: Classification: SUPERSEDED, verified blob-by-blob. The branch's real payload is
  byte-identical on main today: docs/wyckoff_canon.md, engine_alpha/structure/phase_features.py,
  tests/test_phase_bins.py, the calibration_stat_card change. The engine hunks re-landed too: the
  `_last_supper_pivot_*` bins sit in engine_alpha/evaluation.py lines 943-946 and
  core/archive/writer.py, and the retired-jargon scrub (creek/BUEC → plain words) is complete on
  main (zero hits in engine_alpha/). The only content main lacks is
  tools/fidelity/full_package/BBVA.png — a 196 KB evidence chart from a closed program, i.e. the
  documented repo-bloat pattern, plus pre-sweep snapshots of docs main has since archived.
- Consequence: The auto-memory line "pivot-program work PARKED UNMERGED on wip/pivot-canon-2026-07"
  is now false and will keep sending future sessions to re-examine a branch that holds nothing.
- Fix: Delete local + origin (a retired/* tag is optional — every valuable blob is reachable from
  main). Correct the memory/tracking claim wherever the consolidation run records outcomes.
- Ruling-recommendation: DELETE.

FINDING:
- Title: wip/signal-edge-backtest — 2,246 lines of never-landed edge-honesty tooling, and merging it as-is would strip an EC-14 guard
- File/Branch: wip/signal-edge-backtest @ ca8863a (2026-07-13; 391 behind)
- Principle: EC-14 (sealed-output guard); Security P5/P9
- Severity: P2
- What's wrong: Classification: STRANDED-VALUABLE. Main has the base backtest framework
  (core/backtest/: edge_report, null_model, is_oos, stats, loader); the branch adds the entire
  rigor layer on top — deflated Sharpe (selection-corrected verdict), event-study CAR with
  calendar-time t, regime-segmented edge, trigger-gated edge from the breakout day, exit
  simulation, backfill tool, methodology doc, results doc, three test files. None of it exists on
  main in any form. This is the machinery the engine-validation pivot ("measure standalone edge
  honestly") asks for, and memory still carries "verdict pending". BUT: the branch predates the
  EC-14 hardening — its diff of tools/backtest_engine.py removes the `refuse_sealed_output`
  pre-flight main later added to the --json path. A straight merge would silently revert a
  sealed-output guard.
- Consequence: Left as a branch it is the largest single body of stranded work in the repo and a
  drifting twin of main's tools/backtest_engine.py; merged carelessly it re-opens a guarded write
  path.
- Fix: Operator decides whether the signal-edge program lives ("parked indefinitely" is not an
  allowed verdict). If it lives: re-land the rigor layer on current main as a deliberate change,
  restoring the EC-14 guard and re-basing the backtest_engine edits on main's current file. If it
  dies: tag `retired/signal-edge-backtest-2026-07` and delete both copies.
- Ruling-recommendation: MERGE (via re-land, guard restored) — fallback tag-then-DELETE if the
  program is closed.

FINDING:
- Title: worktree-council-p2-followups — the worktree-lost-work pattern repeated: two finished council fixes never re-landed
- File/Branch: worktree-council-p2-followups @ 20fe178 (2026-06-30; 462 behind)
- Principle: EC-3; Security P9; the worktree-lost-work precedent
- Severity: P2
- What's wrong: Classification: PARTIALLY SUPERSEDED with stranded remainder — checked fix by fix.
  Re-landed on main (better or equivalent): the `_weekly_refresh_due` twin fold (lives in
  core/pipeline/cache.py, the EC-3 poster child), per-universe persist_scan_metrics routing,
  the drilldown stale-resolve guard (main's request-token rewrite is strictly better), the
  ScreenerGrid tier/search reset (folded into resetFilters), and the split-probe inf concern
  (main's vectorized rewrite makes an inf FLAG conservatively instead of escape). STRANDED —
  content main still lacks: (1) the close-coverage vectorization (`_close_presence_on`) — main's
  core/pipeline/data_freshness.py still runs the per-symbol scalar loop the branch measured at
  tens of thousands of MultiIndex lookups per run — together with tests/test_data_freshness.py,
  69 lines pinning the torn-merge duplicate-column/duplicate-row semantics, which exists nowhere
  on main; (2) the universe-scoped `_archive_version` cache signature — on main any ETF/commodity
  archive insert still busts the cached us_equities episode grouping (whole-table signature at
  webapp/backend/services/archive_queries.py:67); (3) the scan-metrics routing regression test.
- Consequence: Two reviewed, finished, tested council fixes have sat unreachable for eight weeks —
  the precise failure mode the worktree-lost-work memory exists to prevent, recurring on the
  branch that memory points at.
- Fix: Recover items 1-3 as fresh commits against current main (small, independent, low-risk;
  Performance's seat will want item 1). Then tag `retired/council-p2-followups-2026-06` and
  delete local + origin.
- Ruling-recommendation: recover the three stranded pieces, then tag-then-DELETE.

---

## 2. The stash

FINDING:
- Title: stash@{0} is verbatim on main — safe to drop
- File/Branch: stash@{0} ("On engine/near-miss-lane: foreign: last_supper_pivot hunk (other session) - evaluation.py")
- Principle: Security P5 (dead state is risk surface)
- Severity: P3
- What's wrong: The stash is exactly four insertions: the `_last_supper_pivot_*` keys in
  engine_alpha/evaluation.py's result-row build. Those four lines exist verbatim on main today
  (lines 943-946). It was a hunk rescued from the pivot-canon session that subsequently landed
  through the front door.
- Consequence: A stash that outlived its purpose invites a future `stash pop` onto code that
  already contains it, producing a confusing conflict or a silent duplicate.
- Fix: Operator runs `git stash drop stash@{0}` (this run is read-only and drops nothing).
- Ruling-recommendation: DELETE (drop) — content confirmed on main.

---

## 3. Remote-only branches

FINDING:
- Title: Eleven remote-only branches — seven merged, four superseded/dead; all deletable server-side
- File/Branch: origin/* (verified against both origin/main and local main)
- Principle: Security P5
- Severity: P3
- What's wrong: MERGED (ancestors of origin/main — history keeps them forever, refs are pure
  clutter): batch/session-plus-health-board, engine/near-miss-lane, engine/solve-the-engine,
  engine/wyckoff-canon, evidence/flag-rulings, feat/calibration-workbench,
  feat/climax-polarity-and-species-flip. UNMERGED but resolved by content:
  engine/ar-first-reaction — `git cherry` shows its commit patch-equivalent IN main (the dark
  flag lives there; the kill-by 2026-09-15 decision concerns main's flag, not this ref);
  engine/band-rails-flip — one line in docs/flag_ledger.md recording "PAUSED", superseded by the
  executed flip's EC-15 ledger update; docs/last-supper-definition — edits docs/strategy_v2.md,
  which no longer exists (renamed; the Last Supper definition lives in strategy_alpha.md on
  main); codex/backend-hardening — a 3,637-line June build from a foreign tool targeting
  pre-restructure paths and alert/notify features the project never adopted: DEAD.
- Consequence: Eleven stale refs make every future census slower and give a foreign dead build
  (codex/backend-hardening) the standing of pending work.
- Fix: Server-side `git push origin --delete` for all eleven once the operator nods; nothing needs
  tagging (the seven merged are in main's history; the four others carry no content main lacks —
  if sentiment wants a pointer, tag codex/backend-hardening as retired/* first).
- Ruling-recommendation: DELETE server-side (all 11).

---

## 4. Security pass

FINDING:
- Title: Python dependency surface is unpinned beyond yfinance — no lock for the numerical core
- File/Branch: requirements.txt
- Principle: Security P2 (automate defences) / OWASP A03 supply chain
- Severity: P2
- What's wrong: Only yfinance carries a pin (==1.2.1, AP-4, intentional and correct). pandas,
  numpy, scipy, sqlalchemy, fastapi, uvicorn, apscheduler, ib_async, pyarrow and the rest all
  float. The venv currently runs pandas 3.0.3 / numpy 2.5.1 / scipy 1.18.0, but nothing records
  that. The frontend, by contrast, has package-lock.json committed — the Python half has no
  equivalent.
- Consequence: Two failure modes, one of them tied to this review's P1: (a) supply chain — a
  compromised or breaking release of any floating package lands silently on the next
  `setup.bat`; (b) disaster recovery — rebuilding the machine after the single-disk loss would
  install today's-latest everything, and a byte-parity engine whose regression story is frozen
  baselines (shadow fixture, seed recall, marks corpus) could fail every gate — or worse, read
  charts subtly differently — with no way to reconstruct the known-good environment.
- Fix: Commit a `pip freeze`-derived constraints/lock file alongside requirements.txt (a record,
  not a policy change — upgrades stay deliberate exactly as AP-4 already demands for yfinance).
- Ruling-recommendation: KEEP requirements.txt as-is + ADD the lock in a follow-up commit.

FINDING:
- Title: docs/decisions.md and the anchor-marks ruling record sit outside the sealed-output guard
- File/Branch: tools/_bootstrap.py (_SEALED_FILES) vs docs/decisions.md, docs/anchor_marks_ruling_2026-08-14.md
- Principle: EC-44 (a ruling record joins the sealed set); EC-14/EC-35; Security P7
- Severity: P2
- What's wrong: Guard coverage is otherwise healthy — verified this run: both sealed dirs
  (docs/marks/, tests/baselines/) plus all four docs-root marks/verdict JSON corpora are in the
  set, the EC-35 case-normalization is in place, and all 18 tools that take an --out/--json
  route through refuse_sealed_output. But EC-44's own words cover "marks corpus, RULING RECORD",
  and two ruling records are unguarded: docs/decisions.md — the append-only operator rulings +
  Tested-DEAD registry, the single most load-bearing hand-curated file in the repo — and
  docs/anchor_marks_ruling_2026-08-14.md, the interpretation record for the sealed
  trend_end_marks corpus (its JSON sibling made the sealed set on 2026-08-17; the md that
  carries the operator's quoted rulings did not).
- Consequence: A mistyped `--out docs/decisions.md` on any of the 18 guarded tools truncates the
  project's decision law in place — the precise accident class the guard was built for after the
  power-play-corpus finding.
- Fix: Add both files (and sweep docs-root once for other verdict/ruling artifacts, e.g.
  htf_edge_verdict_2026-07-04.md) to _SEALED_FILES with the standard case-variant refusal test.
- Ruling-recommendation: MERGE (small guarded-set addition in the consolidation follow-up).

FINDING:
- Title: Secrets and broker-gate audit — CLEAN (recorded so absence of evidence is evidence here)
- File/Branch: repo-wide tracked files
- Principle: Security P3 (minimise state); the project's hard IBKR rules
- Severity: P3
- What's wrong: Nothing — this is the verified-clean record. No secret-token patterns anywhere in
  tracked content (AWS/GitHub/OpenAI/Slack/Google key shapes, private-key blocks: zero hits);
  every "token/key" hit is rate-limiter vocabulary. `.env` is gitignored and none is tracked.
  `IBKR_LIVE_CONFIRMED` appears only in docs/scripts that forbid setting it — no code path sets,
  exports, or defaults it; broker_config defaults IBKR_AUTO_CONNECT to False. The live DB and
  its heal-backup are untracked as intended and covered by the hash-verified nightly snapshot
  with a OneDrive mirror.
- Consequence: None.
- Fix: None.
- Ruling-recommendation: KEEP — no action.

FINDING:
- Title: Worktree husks and one unaccounted-for in-flight branch
- File/Branch: .claude/worktrees/ (7 empty directories); branch claude/focused-ellis-499011 (memory reference)
- Principle: Security P5; the worktree-lost-work precedent
- Severity: P3
- What's wrong: Seven directories under .claude/worktrees/ (bold-wilson, elegant-nash,
  gifted-liskov, great-ptolemy, nervous-goldstine, trusting-mccarthy, zealous-ishizaka) are
  empty husks — inspected this run: no .git, no files, no stranded work, and `git worktree list`
  registers none of them. Separately, the lens-tweaks memory says a build is "IN FLIGHT on
  claude/focused-ellis-499011" — that branch resolves NOWHERE in this repo: not local, not on
  origin, not in dangling commits (the dangling set was walked; it is all landed-work
  WIP/amend debris).
- Consequence: The husks are only clutter. The focused-ellis reference is the real one: if that
  build exists only in a remote cloud session, it is one session-expiry away from being the next
  worktree-lost-work entry.
- Fix: Delete the seven empty directories (trivial, any session). Operator checks the cloud
  session for focused-ellis and either lands it as a branch on origin or declares it dead.
- Ruling-recommendation: DELETE the husks; locate-or-declare-dead focused-ellis.

---

## Census summary table

| Ref | Classification | Recommendation |
|---|---|---|
| main (7 unpushed) | single-copy risk | PUSH now (P1) |
| proposal/first-legal-look-fix | STRANDED-VALUABLE, unruled, local-only | KEEP + push; rule by a named date |
| engine/ta-score-v2 | SUPERSEDED (live V2 re-implemented it; paths retired) | tag-then-DELETE |
| wip/audit-tool-tweaks | SUPERSEDED (target pruned / imports retired paths) | tag-then-DELETE |
| wip/pivot-canon-2026-07 | SUPERSEDED (payload verbatim on main; PNG bloat remains) | DELETE |
| wip/signal-edge-backtest | STRANDED-VALUABLE (rigor layer; EC-14 caveat) | MERGE via re-land, else tag-then-DELETE |
| worktree-council-p2-followups | PARTIALLY SUPERSEDED; 2 fixes + 2 tests stranded | recover 3 pieces, then tag-then-DELETE |
| stash@{0} | SUPERSEDED (verbatim on main) | drop |
| 7 merged remote refs | merged | DELETE server-side |
| 4 unmerged remote refs | re-landed / superseded / dead | DELETE server-side |
