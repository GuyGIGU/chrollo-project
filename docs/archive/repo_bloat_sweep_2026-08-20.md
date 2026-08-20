# Bloat audit — consolidated plan
7-domain read-only inventory, tip `a3397a5`, 2026-08-20. The per-domain worker files
(`bloat-*.md`) stayed machine-local in the run folder; this consolidated plan is archived here
because `decisions.md` cites it, and evidence never lives in gitignored scaffolding (EC-16 /
conventions.md line 252).

> **Closed out the same day** — see "What the operator ruled" at the foot of this file. Every row
> in "NOT executed" below has since been actioned or explicitly deferred; read that section as the
> state at audit time, not as open work.

## The measured picture

| | Size | Note |
|---|---|---|
| Tracked repo | 30.3 MB / 855 files | **17.9 MB (59%) is `tools/fidelity/` PNG evidence** |
| `.git` history | 36.2 MB | untracking never shrinks this; only a history rewrite would |
| Working tree | ~1.1 GB | .venv 492 · webapp 301 · output 287 · rest |

**Two separate problems, and they are not the same problem.** The tracked repo's bloat is
almost entirely chart-image evidence from closed programs. The *disk* bloat is 245 MB of
never-rotated service logs plus 154 MB of misplaced database backups. Source code — Python and
frontend alike — came back essentially clean: 1 dead module in 128, 0 dead exported functions in
513, 0 dead files in 212 frontend sources.

## The rule the auditors applied (so it can be re-applied later)

- **ARCHIVE** if the file records a *decision* or a *measurement* — it answers "why is the engine
  shaped this way?" or "was this lever already tried?". Value survives zero references.
- **DELETE** if the file is *process scaffolding* or an *undistilled capture* — worktree recipes,
  agent handoffs, raw console dumps. `git log` holds them; nobody will ask.
- **UNTRACK** if the file is *regenerable output* — renders, charts, exports. Keep on disk, out of
  the tip.
- **KEEP** only for load-bearing (a scan/gate/boot/ruling depends on it), cited evidence (EC-16),
  or sealed ground truth (EC-7).

## The finding that explains the whole mess

**Commit `44f8293` (2026-07-18) deleted 17 closed-track probe tools on the operator's signed kill
list — and left every one of their output folders standing.** Eight orphaned evidence dirs
survive, 8.76 MB, with no producing instrument, no citation, and their findings already written
into `decisions.md` prose. That commit's own closing line is the disposal policy:
*"Resurrection = one git command from this commit."*

Second-order: the same sweep left three dangling EC-16 pointers in `docs/flag_ledger.md`
(`tools/candle_ab`, `tools/puzzle_ab`, `tools/phase_a_pip_diff` — none exist).

**And the operator already ruled on the biggest render family.** `.git/info/exclude` carries a
hand-written block: *"trend-terminal eyeball renders — operator ruled DO NOT COMMIT (2026-08-04);
reproducible via python -m tools.full_package_render <TICKERS>"*, listing 30 PNGs. But
`.git/info/exclude` is **machine-local** — it does not survive a clone, does not protect CI, and
is exactly why new renders keep appearing untracked-and-unignored (FTNT/MAN/TTC today).

---

## EXECUTED this session (tracked side — all git-recoverable)

### 1. Delete 7 orphaned fidelity dirs — 7.39 MB, 82 files
`substrate_ab/` (2.55) · `box_start_extension/` (1.32) · `pip/` (1.20) · `l2/` (0.86) ·
`charts/` (0.63) · `ab/` (0.53) · `band_rails_ab/` (0.30).
Each cleared four checks: producing tool deleted in `44f8293`; zero references across every
`.md/.py/.txt/.json/.html/.js/.jsx` outside `tools/fidelity/`; not in `_SEALED_FILES`/`_SEALED_DIRS`;
no scan, gate, boot path or test reads them. `charts/` verdicts survive in full as text in
`labels.csv`; `band_rails_ab`'s ruling survives at `decisions.md:88`.

### 2. Untrack regenerable renders + fold the machine-local ruling into `.gitignore`
`full_package/*.png` (9 tracked, 1.79 MB — the operator's own DO-NOT-COMMIT family, escaped only
by predating the ruling by 8 days) and `ar_first_reaction_2026-08-13/*.png` (12 files, 2.47 MB —
purpose fully discharged: RULED 2026-08-14 DO NOT FLIP, verdicts preserved in
`docs/anchor_marks_ruling_2026-08-14.md` and the sealed `trend_end_marks_2026-08.json`).
The 30-line `.git/info/exclude` block folds into one `.gitignore` rule carrying the ruling's own
words. Text sheets (`LOSSES.md`, `index.html`, `README.md`, `scan_2026-08-13.txt`) stay tracked so
every EC-16 pointer keeps resolving.

### 3. docs/ — 6 deletes, 9 archives, 1 untrack (1.24 MB; root 40 → 25 files)
Deletes are all scaffolding/undistilled: a 30 KB raw console paste, a demotion note already folded
into `decisions.md` Tested-DEAD row 32, a June worktree launch recipe, and three Codex↔Claude
sprint handoffs. Archives are decisions/measurements (June roadmap, July quality audit, frontend
audit, α release note, superseded edge read, cockpit teardown, flip checklist). Untrack:
`engine_pass/e1_renders_2026-06-30/` (1.18 MB, 54% of docs/).

### 4. python-src — 2 deletes, specs/ archived, 2 PLAN files untracked
`wipe_manual_trades.py` (a destructive-by-design one-shot with **zero references anywhere** —
a hazard, not an asset) and `routers/position_calculator.py` (a live HTTP endpoint duplicating
two lines of arithmetic the frontend already does inline, with no caller). `specs/` (13 files)
moves under `docs/archive/specs/` with all five citing sites repointed — the top-level directory
disappears.

### 5. tools/ — 1 delete, 4 archives
Delete `backtest_watchlist.py`: superseded by the hermetic CI-gated `seed_recall`, and its own
docstring warns its Score/Tier come from a legacy signature — a divergent shadow implementation of
the reading. Archive 4 spent-event instruments (`heal_scan_dates_2026_08` — heal complete and this
tool is cohort-grain so it is the *wrong* instrument for the deferred June work; `anchor_bar_study`,
`cluster_rail_validation`, `bar_dwell_ab` — all falsified/tested-DEAD), each with its citation
repointed rather than left to rot into a fourth dangling pointer.

### 6. frontend — 367 dead CSS lines (10.3% of the stylesheet)
**The council's original line ranges were not safe** — two of seven would have deleted live rules.
The inventory pass re-verified every block against dynamically-built class names and produced
corrected ranges, plus two dead blocks the council missed entirely (`.instrument-lockon` 46 lines,
`.inst-cov/.inst-bar/.inst-dot` 30 lines).

### 7. Pure cache — ~24 MB
22 `__pycache__` dirs (14.0), `node_modules/.vite` (9.7), `.pytest_cache` (0.3). All regenerate.

---

## NOT executed — operator's call

| Item | Size | Why it is yours |
|---|---|---|
| **`output/chrollo-service-error.log` + `chrollo-service.log`** | **245 MB** | Never rotated since deployment, still growing. `docs/deploy.md` §2 already documents the four `nssm set … AppRotate*` commands — they were never run. Needs elevated `nssm`; truncating a file the running service holds open is not an agent's move. **Largest single win in the repo.** |
| **14 `trading_journal` DB snapshots in `webapp/backend/`** | **~154 MB** | Personal trading data — never deleted on size grounds. But the repo working folder is the wrong home; move to the ChrolloBackup target. Two are load-bearing history: the 2026-08-08 pre-journal-wipe (66 wiped trades) and the 2026-08-11 pre-scan-date-heal (the un-healed archive, still relevant while the June forming-bar ruling is open). |
| **`trend_terminal_2026-08-13/*.png`** | 4.33 MB | Held deliberately. `flag_ledger.md` names this folder's sheet as the **current** eyeball for `TREND_TERMINAL_BOX_GATE_ENABLED`, kill-by **2026-08-31** — and that eyeball has not happened. Untracking now leaves broken `<img>` tags in the cited sheet. Read the sheet and rule, then untrack; or untrack and re-render on demand (the tool's own docstring says the sheet decays by design, so a fresh render is better evidence). |
| **`docs/marks/` + the 4 docs-root corpora** | — | Sealed. Inventoried, never touched. |

## ⚠ The most fragile thing this audit found — and it is not bloat

**`calibration_frames/` (3.3 MB, 110 frames) is irreplaceable and is not backed up.**
Marks bind to frame digests; a refetch after a vendor restatement yields different bytes and
permanently destroys the calibration corpus's replay basis. `.gitignore` says to "back it up with
the same habit that covers trading_journal.db" — but `tools/ChrolloBackup.ps1` does not mention it
anywhere. The nightly snapshot covers the journal DB, `uploads/` and the small state JSONs, not the
frames. Right now the only copy is one unbacked-up folder on one machine. **This costs disk to fix,
not save.**

## Defects surfaced by the inventory (not size items)

1. **Three settings knobs that do nothing.** `TOUCH_POINT_RATE`, `LPS_TIGHTNESS_SLOPE`,
   `VOL_CONTRACTION_SLOPE` claim in their own comment to be "consumed by the v2 term expressions";
   `scoring.py` still uses the raw literals at exactly the three sites they were meant to replace.
   Turning them changes nothing — in a file whose whole purpose is that turning a knob changes
   something. Do NOT delete (manifest-registered; removal rotates `engine_config_version`); wire
   them or correct the comment.
2. **Case-twin filenames**: `components/PowerPlayRegister.jsx` and `components/powerPlayRegister.js`
   differ only by case — one name on this Windows checkout. It has already broken a build once.
3. **`tools/backtest_watchlist.py` graded replayed setups on the retired tier ladder** while live
   scans use the new one (it calls `calculate_tier` unconditionally, outside the flag). Resolved by
   its deletion above.
4. **Three dangling EC-16 pointers** in `flag_ledger.md` from the `44f8293` sweep.
5. **`webapp/backend/SETUP.md` drift**: names `_MIGRATIONS` in `main.py` (moved to
   `services/startup.py`) and points at `migrate.py` (recommended for folding).

## Honest accounting

- Tracked tip: **~16 MB reclaimable of 30.3 MB.**
- `.git` stays 36.2 MB regardless — the blobs live in history. Only a rewrite would shrink it, and
  that is hostile to a repo built on append-only decision records. Not recommended.
- Disk: **~459 MB**, but 399 MB of it is the operator's two items above.
- File count: docs root 40 → 25; `specs/` gone; `tools/fidelity` 194 files → ~30.

---

## What the operator ruled (2026-08-20, same session)

Each of the four operator-gated items above was put to him and answered:

- **Service logs — DELETED.** *"delete for me the 245 mb of service logs please."* Both files
  truncated in place (`Clear-Content`, not removed — NSSM holds the handles open and the service
  was running), **244.7 MB freed**. Worth recording what they actually were: the file named
  `chrollo-service-error.log` is not errors, it is the HTTP request log — `logging` writes to
  stderr, so 165 MB of `GET /assets/… -> 200` accumulated under an alarming name since
  2026-06-01. The `AppRotate*` block from `deploy.md` §2a still needs an elevated run; until it
  does, this recurs.
- **Journal snapshots — MOVED.** *"yeah this can be untracked"* — noting they were never tracked
  (`.gitignore` covered `*.db` all along); the cost was disk, not git. **12 files, 126.8 MB moved
  to `%USERPROFILE%\ChrolloBackups\journal-snapshots\`.** `trading_journal.pre_scan_date_heal_2026-08-11.db`
  **deliberately stayed** in `webapp/backend/`: `decisions.md` (2026-08-11 row) names it as that
  ruling's backup, and `decisions.md` is append-only, so moving it would strand an EC-16 pointer
  inside a sealed ruling. 26.8 MB is the price of that pointer resolving.
- **`calibration_frames/` — FIXED.** A third leg was added to `tools/ChrolloBackup.ps1` between
  the uploads copy and the state files, carrying its reason in a comment so it is not later
  "optimized" away. Real cost was smaller than feared: 110 frames / 3.3 MB, so ~92 MB across 14
  retained snapshots plus the OneDrive mirror. **Takes effect only after the script is redeployed**
  to `%USERPROFILE%\ChrolloBackup.ps1` (deploy.md §4) — the repo copy is not what Task Scheduler runs.
- **`trend_terminal_2026-08-13/*.png` — still held.** *"I will look at these later."* Unchanged,
  still tracked; kill-by **2026-08-31** stands.

Also closed out of the review's git-hygiene note: branch `claude/optimistic-grothendieck-19e20e`
was **retired, not merged**, on measurement rather than opinion. Both fingerprint recipes were
recomputed against the live marks DB: it now holds **34 marks (not the 33 at sign-off), all 34
carrying a Trigger**, and the old recipe yields `3cee17e0…` (≠ the `b671e056…` pin) while the
branch's widened recipe yields `a3398865…` (≠ its own `c0c5c88e…` pin). The branch's re-pin was
computed against July's DB and matches nothing today, so merging it would have installed a pin that
refuses immediately. The *idea* survives and is still right — a Trigger edited after sign-off
currently slides through the EC-9 seal — but widening the recipe rotates every fingerprint, so it
can only land inside the next graduation event, against a pin the operator approves that day.
The export is already sealed shut (old recipe ≠ old pin) because the marks drifted past their
sign-off, which is the design working. Standing lesson: **never let a re-pin ride in on a fix
commit** — that branch's message claimed a re-approval whose value is now stale.
