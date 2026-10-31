# Current state

**2026-10-31 The old engine retired (branch `claude/retire-old-engine`, not merged; deployment
pending):** his word, late Fri 30/10/2026: *"retire the old engine, from now on we focus on the new
one obviously!"*. One reader: the alpha reader (`engine_alpha/two_eyes/`) behind the one door
(`engine_alpha/reader.py`), no switch. `engine_alpha/structure/`, `engine_alpha/scoring/`,
`evaluation.py`, `config/engine.py`, `config/scoring.py`, the near-miss writer and the old ratchets
and audits are deleted (170 files; the engine 24,163 lines to 5,565; the suite 3,676 tests to 2,367).
Nothing the reader says moved: his board 43 of 51, the junk 47 fire days, the reader pin zero-diff.
Engine stamp `3f3aefb5…`, ruleset `two-eyes-0.12.0-one-reader`, a declared epoch. The weekly and
monthly panes carry the parent box's own rails; the health board reads the reader's parent box through
the door; the archive writers NULL the retired column families on every write; the frontend lost only
the calibration engine overlay, the agreement chip and the sub-score panels. The saved payload of 30/10
carries the old stamp, so `tools.audits.live_reader_audit --check` refuses until the first scan after
the deploy re-pins it (then `--check --repeat`). Record and decisions A to H: [`engine_reference.md`](engine_reference.md), "The old engine retired";
the ruling row in [`decisions.md`](decisions.md).

**2026-10-28 ETFs in the base list (branch `claude/etfs-in-base-list`, not merged; deployment
pending):** the US-stocks universe keeps the NASDAQ directory's fund rows (it used to drop
every `ETF == 'Y'` row), minus the leveraged / inverse daily products by name
(`leveraged_fund` in the admission ledger). On the directory of 28/10/2026 that is 4,911
funds beside the 5,892 stocks. The door and the reader judge them as stocks; nothing else
moved. The change lands at the next daily refresh of `config/tickers.csv`, and that first
refresh fetches two years of history for every new name. FBT, the chart that raised it,
is on the curated ETF list as well.

**2026-10-24 The weekly Watchlist (branch `claude/weekly-watchlist`, not merged; deployment
pending):** the Watchlist tab shows one week's list, in the operator's weekly sheet's
column order: Type (L/S), Ticker, Ready, Tier (the 0-100 chart score on hover), Change %,
% Diff since add, % Best 30d, Cap $B, 52W distance, Sector, Industry, Added. A save
belongs to the week of its add day, the first weekday after the scan on screen, so
saves made after Friday's scan (Friday evening, the weekend) open next week's list.
The week comes from the scan date, never a clock (EC-37). Nothing is deleted at the
roll: a past week's list stays as it ended, one click back (‹ ›), with all six
best-gain windows and a Carry over button (a fresh save into this week). Any ticker
can be typed in as L or S; one that is not in the scan still measures from the scan on
screen (`basis_scan_date`). His V/VV marks are the Ready column: ✓ = a valid LPS to
take on the trigger, ✓✓ = a top candidate this week. Click to cycle; the default sort
puts ✓✓ first, then ✓, longs before shorts. Marks belong to the week's save; a carried-over
name starts blank, and `ready_at` stamps each change so we can later check whether ✓✓
pays more than ✓. The ♥ Liked column left the Watchlist (it stays on the screener).
Change % divides the live quote by the close before the quote's trading day, and %
Diff since add by the high of the day before the add (the best gains' basis). The
52-week distance is the engine's own, taken at the last close. Schema: `side`, `ready`,
`ready_at`, `basis_scan_date`, `week_start` on `watchlist`, plus one active save per
ticker per week (`migrate_watchlist_weeks`, which backfills every row's week). GET
`/watchlist/` is this week's list (`?week=` for a past one), plus `GET /watchlist/weeks` and
`PATCH /watchlist/{ticker}`. Home's watchlist surfaces follow this week's list too. Not
built: the sheet's R column, Source and Opt.

**2026-10-26 additions on the same branch:** To trigger (the move the quote still needs,
Triggered once over it; tonight's trigger, else the one the save quoted), Earnings (the
next report, amber when it falls in the shown week, `?` when estimated), a Finviz link
button (the shown tickers' Finviz charts, copied to share), and leadership: the Sector
and Group columns carry their rank by the median RS rating of their stocks (the top
quarter reads as leading) and RS · in group gives the stock's RS and its place in its
group (#1 = the group's leader). The scan writes the read as `market_context.leadership`
(US stocks; `core/regime/leadership.py`), so the leadership columns stay empty until the
first scan after deploy. A save's week is always the US-stocks scan's, whatever universe
it came from.

**2026-10-28 The Watchlist table, his list (supersedes the column lists above):** Side
(an L/S dropdown), Ticker, % Change, % Diff since add, % Diff best 30 days, Mkt cap $B,
52W distance, Next earnings, Sector (the SPDR fund on a tile, the sector's name on hover),
Industry, Date (his clock, to the second), with taller rows. A past week shows the same
columns, so no list scrolls sideways; the other best-gain windows ride the 30-day cell's hover. Ready, Tier, To trigger and
the leadership ranks left the table; the default sort is the newest add first. The data
stays: `ready` is still stored and patchable, and the scan still writes
`market_context.leadership`, which no screen shows now.

**2026-10-24 Watchlist best-gain columns (merged into main; deployment pending):** the
Watchlist tab gains the operator's sheet's six "% Best Diff" columns: the best gain since
the add, and within the first 60, 30, 14, 7 and 2 days after it. The basis is the high of
the saved scan's day (his sheet's "day before the add", his buy-stop trigger); each window
runs from the first trading day after it through N calendar days, end day included, so a
young save's long windows show its best so far. Checked against his 23 October sheet on
the 35 of its names the price cache holds: 193 of 210 values equal to the hundredth and
every one within 0.06 points (the rest trace to his feed's highs differing by cents).
Measured server-side on the same cached daily bars as the chart dialog
(`GET /watchlist/best-gains`, `domains/watchlist/best_gains.py`); display only, nothing
judges a setup. The sheet's hand-set RDY/TOP/Side/R columns are not built.

**2026-10-23 engineering-quality increment (merged into main; deployment pending):**
`codex/engineering-quality` adds Python correctness checks, strict types at the
screener response boundary, generated API schema/JSDoc drift checks and twenty
browser checks against the production frontend build. Its review's three UI
fixes landed with it: Undo during a removal still saving, Alt+arrow left to the
browser in the Watchlist dialog and the lens, and the Watchlist chart dialog
fitting the screen at 130% UI scale. The shortlisting pass
adds a Liked view, visible sort/query controls, top paging,
refresh/save recovery and responsive header fixes. A Finviz workflow review adds
a Table/Charts switch over the same query and a focused module-ownership cleanup:
[review and next adaptations](finviz_workflow_review_2026-10.md). The new fast CI job runs
beside the existing regression jobs. Scope and commands:
[engineering_quality.md](engineering_quality.md). Startup and archive storage
refactors remain later work; no service was restarted.

**2026-10-23 Watchlist redesign (same branch, merged into main; deployment pending):**
the screener's dedicated Watchlist filter/manager is removed; saving stars remain.
The Watchlist tab is now a compact, sortable ticker ledger with search, dated
saves, saved-price comparisons, company facts, likes, removal/undo and history.
Daily/weekly/monthly charts open from a row. Active-save responses expose five
nullable facts from their existing stored snapshots; no database migration or
new scan is needed. The top navigation is slightly larger. Details and measured
scope: [workflow review](finviz_workflow_review_2026-10.md#operator-watchlist-redesign).

**2026-10-23 dependable-daily source integrated into main (deployment pending):** the first implementation
adds new-reader base-length sorting data, chart read/grade feedback and an
offline saved-fire replay audit through the active reader. The audit exposed a
per-symbol session lag on EVOX in the 22 October scan. Scope, remaining work
and acceptance criteria: [dependable_daily_2026-10.md](dependable_daily_2026-10.md).

**2026-10-22 experimental clarity update:** source and published screener grades are active under `two-eyes-0.10.0-clarity` (`af59af4b...`). The cache-only rescan of the 21 October session re-published all three universes: 233 stocks, 2 sector setups and 3 commodity/ETF setups, with no archive writes or evaluation errors. Stock scores changed on 70 names; tiers are 119 S / 50 A / 38 B / 26 C (previously 132 / 40 / 35 / 26). The technical grade reads main-swing travel and event-aware rail definition, capped by the former integrity grade. Clarity changes no fire rule or fundamental grading rule; the separately authorized strict 80% mini-height rule is included. Raw clarity and prior integrity archive in `two_eyes_clarity_json` on future archived scans. The work is committed on `main` (unpushed); the new BOX explanations and backend reads load when the operator runs the ordinary `update_dashboard.bat`; the service was not restarted. Older lifecycle descriptions below remain historical.

Snapshot of 2026-09-26, branch `main` (deployed 2026-09-25: the domain refactor, its follow-ups and
the merge train below). Update it when a flag flips, a
priority lands or a branch merges. Layout: [`architecture.md`](architecture.md). Every
`python` here means the repo venv, `.\.venv\Scripts\python.exe` (bare `python` is a trap, `AGENTS.md`).

## Engine, scoring, research

- **Engine (Sat 31/10/2026): the alpha reader is the one reader.** Config hash `3f3aefb5…`
  (`python -m engine_alpha.freeze.manifest --hash`), ruleset `two-eyes-0.12.0-one-reader`; the manifest
  holds 29 settings (the door's floors in `config/universe.py`, the reader's own in `config/reader.py`,
  the fundamentals, RS-line and sector-ranking knobs) plus every number in `two_eyes_numbers.py`. The old
  engine and its knobs are gone ([`engine_reference.md`](engine_reference.md), "The old engine retired"); the live stamp before was `80f2ec31…`
  (the scan of 30/10). Reader pin passes (`python -m tools.regression.reader_pin --check`, rebuilt on the
  reader's own record over 105 charts); the marks ratchet reads 51 of his 52; the junk gate pins 47 days.
  The retired lanes: the near-miss lane (its table read-only history), the watch and rescue lanes, the
  final method's 27 switches, the HTF context, the sub-scores and chapters (the tier is the reader's
  letter, the score its place within it).
- **The hash's history, before the retirement:** config hash `0bbadfac…`,
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
- **The leadership read** (branch `claude/leadership-read`, 2026-10-02, display only, no flag): the
  card and the detail panel show the RS rating (twelve-month strength ranked against every stock
  the scan reads, archived as `rs_rating`), the trend-template count and the 50-day dollar volume,
  and the screener sorts by RS. None of it gates, scores or tiers; no dollar-volume floor (his word).
  2026-10-03 the detail panel adds the distance above the 52-week low and the 200-day average's
  one-month change. The base count is NOT shown: it reads 1 on every archived fire.
- **The market-cap floor and the fundamentals** (2026-10-03, his yes): a fire under $300M market
  cap leaves the scan (`MIN_MARKET_CAP`, checked on the fires after the read; a cap that cannot be
  read keeps the fire), and `FUNDAMENTALS_ENABLED` is live, display and archive only: the detail
  panel's Fundamentals section shows market cap, EPS and sales growth, EPS acceleration and the
  earnings surprise, naming the quarter. Next on his word (2026-10-03, "yes also for #3"): after a
  few weeks of archived fires, measure which leadership / fundamentals combination finds the
  winners, then define the stock grade from that. More grade work on both reads is planned.
- **The fundamentals sheet and the fundamental grade** (2026-10-12, his go-ahead; display and
  archive only): the detail panel's Fundamentals section shows the last four reports and quarters,
  margins, beats, estimate revisions, the report-day reactions and earnings quality, and a grade
  A-D from nine checks (`FUND_*` in `config/enrichment.py`; archived `fund_grade`,
  `fund_grade_score`, `fund_sheet_json`). Two grades by his ruling: technical (the chart + ADR,
  trend template) and fundamental. Not on the card, not in the board order yet. The SEC fill of
  year-ago quarters is ON (his email as the SEC contact, 2026-10-12). The card's chart well flips to a
  fundamentals page (F), with a descriptive label, a strict Code 33 badge and quality flags. Engine stamp `ece8546e`.
- **The group read** (2026-10-23, his yes, display only): every fired name shows the industry its
  sheet names and "N of M in the group fired tonight, K in the last 10 days" on the card and the
  lens, resolved engine-side (`group` on the wire); no sort, no gate. Measured first on 5,949
  archived episodes: the counts pay nothing in the tail, and "the group already at its highs" is
  mostly the stock's daily range ([`decisions.md`](decisions.md), Nulls, 2026-10-23). The group's
  size counts the scanned universe through `output/industry_cache.json`; the operator runs
  `python -m tools.maintenance.industry_backfill` once to fill it (the nightly scan keeps it fresh
  from the sheets; until then a group reads as the names seen firing).
- **The stage read** (2026-10-16, built for his book stops; display and archive only, no flag): every
  fire of the live reader carries the stock's stage on its weekly chart (1 neglect, 2 advance, 3 top,
  4 decline) and the week its stage-2 advance began (`engine_alpha/stage_read.py`; archived as
  `cycle_stage`, `advance_start`, `advance_weeks`), shown in the detail panel's Leadership section.
  It gates nothing, and by his ruling (16/10/2026) stage-1 and stage-3 fires stay on the board, the
  stage shown only. The base count and the inter-base width still wait on where the first leg ends. Live after `update_dashboard.bat` and
  the next scan.
- **Volume at key points** (2026-10-04, his go-ahead after the step-2 measurement): the detail
  panel shows the LPS pullback's volume and the Phase C spring's against the 50-day average,
  display only. Of the Momentum Masters volume lines, only the quiet LPS pullback separated
  outcomes in the archive (decisions.md Nulls, 2026-10-04): the old reader's own LPS stretch.
  On the new reader's LPS days nothing separates, his criterion (under the 50-day average)
  included; the quietest 2-to-5-day stretch of the last week is a lead, not graded
  (decisions.md Nulls, 2026-10-12).
- **His calibration setups are archived setups too** (2026-10-03, his ruling; built 2026-10-04):
  each is measured like a fire from the day before his trigger (`calibration_outcomes`, filled by the nightly outcome job as a contained passenger) and
  shown as its own group, never pooled: report card section 7, a line on the Home edge tile, and
  the Archive screen's "Calibration setups" filter. Live after `update_dashboard.bat` and the next
  outcome run (or the Archive's Update Forward Returns button).
- **Scoring:** retired with the old engine on Sat 31/10/2026. The tier is the reader's grade letter
  (S/A/B/C, from the dead space and the hold) and the score its place within the letter from his traits
  (`two_eyes/grade.py`, `two_eyes/traits.py`; the weights in `two_eyes_numbers.py`). The 62 / 52 / 42 / 32
  ladder, `S_MAX_BOX_WIDTH`, the sub-scores and the RS / uptrend weights are gone with `config/scoring.py`;
  the RS/uptrend answer owed in [`asks.md`](asks.md) is moot.
- **Engine rewrite (history; the reader went live 10/10 and became the one reader 31/10):** the final method (`claude/method-steps-7-12` with `claude/sos-session`) is merged
  here, every switch dark; the approval sitting flips them together ([`final_method_2026-09.md`](final_method_2026-09.md)).
  `claude/two-eyes-reader` still carries unmerged engine work; it was ported onto this layout on
  2026-09-26 (base `61c88cc`). Its build is CLOSED (Fri 09/10/2026: every stage, the screen block and
  the approval pack built, dark) and the branch review's fixes followed; next are his approval sitting and
  a go-live plan. His FRPH ruling of Fri 09/10/2026 was DROPPED on Sat 10/10/2026, in his words "just leave these two
  behind": no reader rule, nothing on the go-live list. None of it is live here.
- **The two-eyes flip (history: flipped on his word, Sat 10/10/2026; the switch itself deleted Sat 31/10/2026).** The go-live plan
  (`.council/plans/two-eyes-go-live.md`) joins the reader branch with the live branch on
  `claude/sweet-napier-461716`, `TWO_EYES_READER_ENABLED` still False there. The flip commit (the
  switch on, every pin of "off" moved with it) is prepared on `claude/two-eyes-flip`; on the night it
  lands, the scan reads with the new reader and stamps `cdb7ee2d`. The flip is his, after his
  approval sitting, by the checklist in [`deploy.md`](deploy.md), "The Flip"; both undos were rehearsed
  on a copy of the archive. The engine stamps it moves through are written in
  [`flag_ledger.md`](flag_ledger.md): the live scan stamps `a2252c6c` (not the `0bbadfac` above, which
  predates the market-cap floor), the joined tree `8cae6fd9` with the switch off and `cdb7ee2d` on.
  The deploy now refuses a checkout that is not `main` or has uncommitted tracked files.
- **The archive is the new reader's measuring stick** (his word Mon 12/10/2026, option A,
  [`decisions.md`](decisions.md)): the Home edge tile reads one reader at a time (the one that
  wrote the latest scan, the other as a baseline line, never pooled) and leads with the chance of
  +25% and +40% in 20 days; the new reader's fires archive the LPS pullback's volume
  (`two_eyes_lps_volume_ratio`). Live after `update_dashboard.bat`; the column fills from the
  next scan on.
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
| LIVE, engine | none left as flags: the reader has no `*_ENABLED` setting. Its rules built to be measured are bools in `two_eyes_numbers.py` (`MINI_ENABLED` off, `RESPECT_ELECTS` off, `WRAP_TAKES_OVER` on), recorded in `decisions.md`. The old engine's live flags (`CAUSE_BEFORE_EFFECT_VETO`, `BAND_RAILS`, `STORY_POOL`, `NEAR_MISS_LANE`, `ELECTION_DETHRONE`, `LPS_OVERSHOOT_WINDOW_ATR`, `LPS_AFTER_SPRING`, `LPS_HOLDING_SHELF`, `HTF_CONTEXT`, `EVENT_MAP`, `SENTENCE_ARCHIVE`) went with it on 2026-10-31 |
| LIVE, advisory (display + archive, never scored) | `FUNDAMENTALS` (2026-10-03) |
| LIVE, infrastructure | `HEALTH_BOARD`, `TICKER_ADMISSION`, `YAHOO_RATE_LIMIT`, `QUARANTINE` |
| DARK, kill-by 2026-11-30 | `RS_LINE`, `SECTOR_RANKING` (Lane C enrichment, outside the reader; [`flag_ledger.md`](flag_ledger.md)) |
| RETIRED (key deleted) | **2026-10-31, with the old engine:** the final method's 27 switches (`RESPECT_WHOLE_BAR` ... `GRADE_LEDGER`), `ELECTION_TRACE_EXPORT`, `STRATEGY_READ`, `ELECTION_STABILITY`, `CONTRACTION_RESCUE`, `BAR_POSTURE_RESCUE`, `SMA50_DIP_EXCEPTION`, `BOTTOMING_BASE_LANE`, `LPS_CEILING_REST`, `POWER_PLAY_STORY_FORM`, `TWO_EYES_READER` (the switch) and every live flag of the old engine; before that `POWER_PLAY_PRESET` (2026-09-19, with the species lane), `TREND_TERMINAL_BOX_GATE`, `AR_FIRST_REACTION` (both 2026-09-08), `PIP_PIVOTS`, `LPS_REQUIRE_PEAK_DOWN`, `TA_SCORE_V2`, `EQ_DWELL_BAR_BASIS`, and the seven keys folded 2026-07-18 |

## Known limitations

- The marks ratchet reads 51 of his 52 drawings (`python -m tools.regression.marks_corpus --check`;
  MDT of 24/07 the door refuses, 3.77 ranges under the 200-day) and reports **STALE** whenever he
  redraws, until `--build-fixture` is run from the calibration frames (never `guided_list_export`).
- On his day, 43 of his 51 drawings fire at his trigger (the board); the eight misses are the
  reader's open work ([`decisions.md`](decisions.md), the rows of October). The old engine's open
  items (the 60-day climax window, `segment_trends` box-blindness) retired with it on 2026-10-31.
- The parquet cache is survivor-only: delisted names are absent ([`edge_read_2026-07-22.md`](edge_read_2026-07-22.md)).
- `core/archive` and the payload writer import the backend's ORM by bare name (the one seam left in
  [`architecture.md`](architecture.md) §2).

## Infrastructure

- One NSSM service, `ChrolloDashboard`: uvicorn on 127.0.0.1:8000 (API + built UI), SQLite WAL
  archive at `webapp/backend/trading_journal.db`. Boot is broker-free (`IBKR_AUTO_CONNECT` false).
- Scan and forward returns at 17:00 `America/New_York`, Mon–Fri (`config/runtime.py`). Backups and
  a backend-independent forward-return tick are Windows scheduled tasks ([`deploy.md`](deploy.md) §4, §4b).
  The tick's task runs `tools/run_maturation.bat`, a permanent forwarder to `tools/ops/`: the task
  stays registered there, so nothing is owed to re-point it.
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
that LIVN may drop out ([`decisions.md`](decisions.md)). One branch remains unmerged:
`claude/two-eyes-reader` (ported onto this layout on 2026-09-26 at `61c88cc`, one merge commit plus the
port; its build closed on Fri 09/10/2026, the branch review's fixes on top). On 2026-09-26 the
two superseded branches were retired as tags, `retired/indexless-universe-cold-gate-2026-09` (superseded
by `937ecd4`) and `retired/signal-edge-backtest-2026-07` (an older copy of `revive/signal-edge`); every
merged branch and leftover worktree was removed, and their uncommitted leftovers were saved to
`%USERPROFILE%\ChrolloBackups\worktree-sweep-2026-09-26\`. After any merge run pytest;
`tests/integration/test_moved_module_paths.py` catches old names.
