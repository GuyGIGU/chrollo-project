# Current state

Snapshot of 2026-09-25, branch `claude/integration-2026-09` (the domain refactor, its follow-ups and
the merge train below). Update it when a flag flips, a
priority lands or a branch merges. Layout: [`architecture.md`](architecture.md). Every
`python` here means the repo venv, `.\.venv\Scripts\python.exe` (bare `python` is a trap, `AGENTS.md`).

## Engine, scoring, research

- **Engine:** config hash `0bbadfac…` (`python -m engine_alpha.freeze.manifest --hash`),
  unchanged by the domain refactor. Reader pin passes (`python -m tools.regression.reader_pin --check`).
  Merging the consolidation-method branch (`claude/eager-chatelet-65e8d4`, PR #11) onto this layout
  rotated it to `193b61c4…`, identity only: two flag keys (`BAR_POSTURE_RESCUE_ENABLED`,
  `SENTENCE_ARCHIVE_ENABLED`) and the signed sentence vocabulary joined the manifest; no value moved.
  Merging the final-method branch (`claude/method-steps-7-12`, which carries `claude/sos-session` and
  `claude/clever-napier-08f25d`) rotated it to `ef5de2f0…`: the operator's final method, steps 1 to 12,
  is built DARK behind 27 default-off switches (52 keys join the manifest, every one off), and on his
  ruling (point 25) the Power Play species lane is DELETED, so its live preset `POWER_PLAY_PRESET_ENABLED`
  and four more keys leave the manifest and the lane's `pp_*` archive columns stay NULL from here on.
  The names the lane fired still fire: it never touched the paying read.
  Merging `claude/engine-time-axis-and-nan-contract` (2026-09-25, on the operator's LIVN ruling in
  [`decisions.md`](decisions.md)) left the hash at `ef5de2f0…`: it adds no setting. Two live reading
  fixes land with it: the band pool cuts its touch-thirds on the window's real trading days, and one
  unreadable price cell no longer blanks the ATR for the rest of the chart. Measured over the cached
  universe, no fire moved.
- **New measure-only columns** (never scored, never gated; the additive migrator adds them at the
  next boot, and older rows stay NULL): `sentence_*` (PR #11) and ten `eq_*` outside-bar descriptors
  (engine-eyes Task 1, no flag). The reader-pin readings also gained one additive key,
  `role_labels.events` (a copy of `box_events`, consolidation-method Task 9); nothing else in them moved.
- **Scoring:** tier comes from the TA grade against 62 / 52 / 42 / 32, with the
  `S_MAX_BOX_WIDTH` cap (0.15) on top (`config/scoring.py`). RS and uptrend weights are 0;
  the re-opened A/B recommends keeping them there, and the operator's answer is owed ([`asks.md`](asks.md)).
- **Engine rewrite:** the final method (`claude/method-steps-7-12` with `claude/sos-session`) is merged
  here, every switch dark; the approval sitting flips them together ([`final_method_2026-09.md`](final_method_2026-09.md)).
  `claude/two-eyes-reader` still carries unmerged engine work. None of it is live here.
- **Research:** the 2026-09-03 "no standalone edge" verdict has not been re-run on the
  corrected statistics ([`edge_denominator_2026-09-08.md`](edge_denominator_2026-09-08.md), [`asks.md`](asks.md)).
  Archive counts come from `python -m core.archive.analyze`; do not quote them from memory.
  The signal-edge rigor layer (`core/backtest/{deflated_sharpe,event_study,exit_sim}.py`,
  `tools/research/backtest_{backfill,exits}.py`) landed 2026-09-24 as research tooling; production
  imports none of it.

## Validated vs experimental

For the engine flags with a *Retired* row in [`flag_ledger.md`](flag_ledger.md), "live" means
the operator flipped it after an A/B eyeball and the regression gates. The infrastructure flags
are operational switches, flipped on request, with no ledger row. Forward-return proof is the
archive's job and is not settled (see Research). "Dark" means built, off, and waiting on a ruling.

| State | `*_ENABLED` flags (value in `config/*.py`) |
|---|---|
| LIVE, engine | `CAUSE_BEFORE_EFFECT_VETO`, `BAND_RAILS`, `STORY_POOL`, `NEAR_MISS_LANE`, `ELECTION_DETHRONE`, `LPS_OVERSHOOT_WINDOW_ATR`, `LPS_AFTER_SPRING`, `LPS_HOLDING_SHELF`, `HTF_CONTEXT`, `EVENT_MAP`, `SENTENCE_ARCHIVE` (measure-only `sentence_*` archive columns) |
| LIVE, infrastructure | `HEALTH_BOARD`, `TICKER_ADMISSION`, `YAHOO_RATE_LIMIT`, `QUARANTINE` |
| DARK, final method, kill-by 2026-11-30 | `RESPECT_WHOLE_BAR`, `DWELL_GRADED`, `BOX_HANDOVER_RANGES`, `SPRING_BOUNDS_LIFTED`, `LPS_RANGES_YARDSTICK`, `LPS_GRADED_TRAITS`, `LPS_WINDOW_RECEDING`, `LPS_BUY_DAY_READS_HIGH`, `LPS_REFUSALS_TO_GRADES`, `LPS_SELLERS_RISING_FATAL`, `TURN_LINE`, `TURN_LINE_TREND`, the six `LINE_WORD_*`, `BASE_AGE_FROM_ANCHOR`, `BOX_WIDTH_CAPS_GRADED`, `DEPTH_CAPS_GRADED`, `RESPECT_GRADED`, `LPS_LEAVES_ELECTION`, `BOX_OPENS_ON_ANCHORS`, `CLIMAX_FIRST_WALK`, `BOX_END`, `GRADE_LEDGER` |
| DARK, kill-by 2026-11-30 | `FUNDAMENTALS`, `RS_LINE`, `SECTOR_RANKING`, `ELECTION_TRACE_EXPORT`, `STRATEGY_READ`, `ELECTION_STABILITY` (all re-dated from 2026-09-30 / 2026-09-15 with written reasons, [`flag_ledger.md`](flag_ledger.md)) |
| DARK, kill-by 2026-10-31 | `CONTRACTION_RESCUE`, `BAR_POSTURE_RESCUE`, `SMA50_DIP_EXCEPTION`, `BOTTOMING_BASE_LANE`, `LPS_CEILING_REST`, `POWER_PLAY_STORY_FORM` |
| RETIRED (key deleted) | `POWER_PLAY_PRESET` (2026-09-19, with the species lane), `TREND_TERMINAL_BOX_GATE`, `AR_FIRST_REACTION` (both 2026-09-08), `PIP_PIVOTS`, `LPS_REQUIRE_PEAK_DOWN`, `TA_SCORE_V2`, `EQ_DWELL_BAR_BASIS`, and the seven keys folded 2026-07-18 |

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
  The tick's task still runs `tools/run_maturation.bat`, a forwarder to `tools/ops/`, so it keeps
  working; pointing it at `tools/ops/` directly is one Administrator command, the operator's
  ([`deploy.md`](deploy.md) §4b).
- Code goes live only when the operator runs `update_dashboard.bat`.

## Structural work

Done 2026-09-24 on `claude/structural-followups`, now inside `claude/integration-2026-09` (behaviour
pinned by tests first, engine hash and every regression gate unchanged):

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

**Merge train (2026-09-24).** Onto the refactor and its follow-ups, in order: `revive/signal-edge`,
`claude/eager-chatelet-65e8d4` (PR #11), `claude/method-steps-7-12` (with `claude/sos-session` and
`claude/clever-napier-08f25d`). Each was ported, gated and checked by two independent reviews; the
checkpoints are in [`migrations/2026-09-domain-refactor.md`](migrations/2026-09-domain-refactor.md).
On 2026-09-25 `claude/engine-time-axis-and-nan-contract` followed, no longer held: the operator ruled
that LIVN may drop out ([`decisions.md`](decisions.md)). Three branches remain unmerged:
`claude/two-eyes-reader` (its council build is in flight; port it when it finishes),
`claude/indexless-universe-cold-gate` (superseded by `937ecd4`) and `wip/signal-edge-backtest`
(an older copy of `revive/signal-edge`). After any merge run pytest;
`tests/integration/test_moved_module_paths.py` catches old names.
