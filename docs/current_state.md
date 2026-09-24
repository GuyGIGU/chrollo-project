# Current state

Snapshot of 2026-09-24, branch `claude/domain-refactor`. Update it when a flag flips, a
priority lands or a branch merges. Layout: [`architecture.md`](architecture.md). Every
`python` here means the repo venv, `.\.venv\Scripts\python.exe` (bare `python` is a trap, `AGENTS.md`).

## Engine, scoring, research

- **Engine:** config hash `0bbadfac…` (`python -m engine_alpha.freeze.manifest --hash`),
  unchanged by the domain refactor. Reader pin passes (`python -m tools.regression.reader_pin --check`).
- **Scoring:** tier comes from the TA grade against 62 / 52 / 42 / 32, with the
  `S_MAX_BOX_WIDTH` cap (0.15) on top (`config/scoring.py`). RS and uptrend weights are 0;
  the re-opened A/B recommends keeping them there, and the operator's answer is owed ([`asks.md`](asks.md)).
- **Engine rewrite:** `claude/two-eyes-reader`, `claude/method-steps-7-12` and
  `claude/sos-session` carry unmerged engine work. None of it is live here.
- **Research:** the 2026-09-03 "no standalone edge" verdict has not been re-run on the
  corrected statistics ([`edge_denominator_2026-09-08.md`](edge_denominator_2026-09-08.md), [`asks.md`](asks.md)).
  Archive counts come from `python -m core.archive.analyze`; do not quote them from memory.

## Validated vs experimental

For the engine flags with a *Retired* row in [`flag_ledger.md`](flag_ledger.md), "live" means
the operator flipped it after an A/B eyeball and the regression gates. The infrastructure flags
are operational switches, flipped on request, with no ledger row. Forward-return proof is the
archive's job and is not settled (see Research). "Dark" means built, off, and waiting on a ruling.

| State | `*_ENABLED` flags (value in `config/*.py`) |
|---|---|
| LIVE, engine | `CAUSE_BEFORE_EFFECT_VETO`, `BAND_RAILS`, `STORY_POOL`, `NEAR_MISS_LANE`, `ELECTION_DETHRONE`, `LPS_OVERSHOOT_WINDOW_ATR`, `LPS_AFTER_SPRING`, `LPS_HOLDING_SHELF`, `HTF_CONTEXT`, `POWER_PLAY_PRESET`, `EVENT_MAP` |
| LIVE, infrastructure | `HEALTH_BOARD`, `TICKER_ADMISSION`, `YAHOO_RATE_LIMIT`, `QUARANTINE` |
| DARK, kill-by 2026-09-30 | `FUNDAMENTALS`, `RS_LINE`, `SECTOR_RANKING`, `ELECTION_TRACE_EXPORT`, `STRATEGY_READ` |
| DARK, kill-by 2026-10-31 | `CONTRACTION_RESCUE`, `SMA50_DIP_EXCEPTION`, `BOTTOMING_BASE_LANE`, `LPS_CEILING_REST`, `POWER_PLAY_STORY_FORM` |
| DARK, overdue | `ELECTION_STABILITY`: this branch's ledger says 2026-09-15; the three rewrite branches re-date it to 2026-11-30 |
| RETIRED (key deleted) | `TREND_TERMINAL_BOX_GATE`, `AR_FIRST_REACTION` (both 2026-09-08), `PIP_PIVOTS`, `LPS_REQUIRE_PEAK_DOWN`, `TA_SCORE_V2`, `EQ_DWELL_BAR_BASIS`, and the seven keys folded 2026-07-18 |

## Known limitations

- The marks ratchet reports **STALE** (`python -m tools.regression.marks_corpus --check`): the
  operator redrew, so the live DB's box marks no longer match the corpus (the check prints the
  count and the refresh).
- The climax anchor is still a fixed 60-day window off the box open; box placement and
  `segment_trends` box-blindness are open ([`flag_ledger.md`](flag_ledger.md), AR row).
- The parquet cache is survivor-only: delisted names are absent ([`edge_read_2026-07-22.md`](edge_read_2026-07-22.md)).
- `core/archive` and the payload writer import the backend's ORM by bare name (the one seam left in
  [`architecture.md`](architecture.md) §2).

## Infrastructure

- One NSSM service, `ChrolloDashboard`: uvicorn on 127.0.0.1:8000 (API + built UI), SQLite WAL
  archive at `webapp/backend/trading_journal.db`. Boot is broker-free (`IBKR_AUTO_CONNECT` false).
- Scan and forward returns at 17:00 `America/New_York`, Mon–Fri (`config/runtime.py`). Backups and
  a backend-independent forward-return tick are Windows scheduled tasks ([`deploy.md`](deploy.md) §4, §4b).
- Code goes live only when the operator runs `update_dashboard.bat`.

## Structural work

Done 2026-09-24 on `claude/structural-followups` (local, unmerged; behaviour pinned by tests first,
engine hash and every regression gate unchanged):

- The backend no longer imports `tools/`: the replay layer and agreement taxonomy live in
  `core/calibration/`, the chips' grading in `domains/calibration/grading.py`.
- The two frontend feature cycles are gone, and a test keeps them out.
- Quality pass: `downloads.py` 1,390 lines became four modules (764 + 471 + 220 + 36);
  `analyze.py` 1,156 became four (227 + 164 + 450 + 491); `scan_diagnosis.py` 805 became 547 plus
  `interruption_cause.py` 300; `CalibrationTab.jsx` 803 became 518 plus two components and three
  tested model modules.

Next candidates, none of which changes the method:

1. Retire the ORM bare-name seam (`core/archive` and the payload writer reaching into the backend).
2. Retire the `tools/calibration/{replay,agreement}.py` aliases once the older branches are ported
   (two engine comments cite them; repointing those is an engine edit).
3. Tidy the names that stutter (`box/box_*.py`; `domains/archive/calibration.py` beside
   `domains/calibration/`), and move `shared/navigation/leaveGuard.test.js`'s calibration case
   into the calibration feature.

Engine files wait until `claude/two-eyes-reader` lands, and change only through operator rulings.

**Merge-order risk.** Nine local branches are unmerged (`git branch --no-merged`) and all nine
edit paths that `3bd4531..93ac245` renamed or deleted: most of all `claude/two-eyes-reader`
(72 paths, counting `config/settings.py`), `claude/method-steps-7-12` (59), `claude/sos-session` (27).
The per-branch table and the porting steps are in
[`migrations/2026-09-domain-refactor.md`](migrations/2026-09-domain-refactor.md). Merge order is the operator's call.
After any merge run pytest; `tests/integration/test_moved_module_paths.py` catches old names.
