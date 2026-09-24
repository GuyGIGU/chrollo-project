# 2026-09 domain refactor: migration map

The refactor on `claude/domain-refactor` grouped the code by what it does. It runs from `3bd4531` to `93ac245` in five commits (`git log 3bd4531..93ac245` explains each). This page says what moved where, what was split or deleted, which compatibility paths remain, and how to port a branch that was cut before it.

The machine-readable map is [2026-09-domain-refactor.json](2026-09-domain-refactor.json). [apply_move_map.py](../../tools/maintenance/apply_move_map.py) reads it to port a branch, and [test_apply_move_map.py](../../tests/tooling/test_apply_move_map.py) checks that the rewrite is idempotent, that every import it writes resolves, and that every file move in the JSON has a row on this page. The tables below are generated from the JSON; if you edit one, edit the other.

The JSON records 586 file moves, 138 Python module moves, 10 whole-folder moves and 5 deletions. They come from `git diff -M --name-status --find-renames=50% 3bd4531 93ac245`; the rows marked `manual` in the JSON are the exceptions git does not pair on its own.

| Area | Files moved |
|---|---|
| Engine | 29 |
| Pipeline | 21 |
| Backend | 47 |
| Frontend | 220 |
| Tests | 157 |
| Tools | 45 |
| Research evidence | 67 |

## How to port a branch

Seven `claude/` branches were cut before the refactor and edit files it moved. On 2026-09-24 (refactor tip `93ac245`) they stood as below. *Changed* counts the files each branch changed since its merge base with `claude/domain-refactor`; *moved* counts how many of those are an old path in the map, a deleted file, or `config/settings.py`. None of the merge bases has a rename between it and the baseline, so this map covers them all. Which branch lands first is the operator's call.

| Branch | Merge base | Changed | Moved |
|---|---|---|---|
| `claude/two-eyes-reader` | `ee23e8d` | 146 | 72 |
| `claude/method-steps-7-12` | `ee23e8d` | 112 | 59 |
| `claude/clever-napier-08f25d` | `ee23e8d` | 57 | 27 |
| `claude/sos-session` | `ee23e8d` | 57 | 27 |
| `claude/eager-chatelet-65e8d4` | `2a5dd13` | 78 | 25 |
| `claude/engine-time-axis-and-nan-contract` | `516b36f` | 12 | 7 |
| `claude/indexless-universe-cold-gate` | `2a5dd13` | 3 | 2 |

For each branch:

1. Bring it onto the refactor: `git merge claude/domain-refactor` (or `git rebase claude/domain-refactor`). Git's rename detection carries most edits to the new paths. Resolve conflicts with the tables below. An edit to `config/settings.py` always conflicts: see [What was split](#what-was-split).
2. Preview the port of every file the branch changed:

   ```powershell
   .\.venv\Scripts\python.exe -m tools.maintenance.apply_move_map --check (git diff --name-only --diff-filter=AMR claude/domain-refactor HEAD)
   ```

   It prints a diff and a note for everything it will not guess. It exits 1 when a file would change.
3. Apply it: the same command without `--check`. Running it again changes nothing.
4. Fix each note by hand. The notes name imports of a split module (with the new home of each name), relative imports that no longer resolve, and JS specifiers or markdown links it could not place.
5. Files the branch **added** in an old folder (for example `tools/`, `engine_alpha/structure/` or `src/components/`) are not in the map. `git mv` each one to where it belongs and pass the move with `--move OLD=NEW` (repeatable) when you run the tool, so every reference to it, and the moved file's own relative imports, are ported the same way. New tests go in a category folder under `tests/` and use `from _paths import REPO_ROOT`. New tools go in a category folder under `tools/` and use the `tools._bootstrap` fallback. New frontend tests are listed in `package.json`.
6. Verify (with the repo venv's `python`): `python -m pytest` (it includes [test_moved_module_paths.py](../../tests/integration/test_moved_module_paths.py), which rejects every old module name in live Python), `python -m tools.audits.pointer_audit --check`, `npm --prefix webapp/frontend run lint`, and a frontend build in a worktree.

## What the porter does, and what it leaves to you

| File type | What it rewrites |
|---|---|
| Python | Import statements, from the AST, and a `from x import y` written inside a string or comment (a `-c` script), by the same rules. Dotted module names anywhere else (`mock.patch` and `monkeypatch` targets, `-m pkg.mod` text, attribute chains, comments). Repo-relative paths such as `engine_alpha/structure/pivots.py`. |
| JS / JSX | Relative import specifiers, resolved against the file (or its old location), remapped and made relative again. Only a file counts as resolving: `src/api.js` became the folder `src/api/`, and a folder without an index is not an import target. Repo-relative and `src/...` paths in text. |
| Markdown | Link targets, resolved against the doc. Prose and backticked paths are left alone: they are often a historical record. |
| Anything else | Dotted module names and forward-slash repo paths (for example the test list in `package.json`, `-m` lines in `.bat` files). In `.ps1`, `.bat` and `.cmd` files, backslash paths too (`tools\shadow_diff.py`). |
| A tool in a category folder | The old direct-run fallback `from _bootstrap import ...` becomes the repo-root `sys.path` insert plus `from tools._bootstrap import ...`, the form every migrated tool uses. |

It never rewrites a name that is already new. Four old modules became packages of the same name (`engine_alpha.structure.lps`, `.narrative`, `.metrics` and `core.pipeline.universe`), so each old name is also a prefix of new ones. A rewrite stops when the next segment is a submodule of the new package. The rewriter this replaces had no such stop: a second pass turned the new `core.pipeline.universe.ticker_admission` into an import of `ticker_admission` from `core.pipeline.universe.descriptor`, which does not resolve.

Limits:

- It does not move files. Git moves the files the refactor moved; you move the ones a branch added and name them with `--move` (step 5).
- Relative Python imports are reported when they no longer resolve (`from . import x` included), never rewritten.
- Imports of the split or deleted modules below are reported with each name's new home, never rewritten. So are imports of the deleted packages (`routers`, `ibkr`, `output`).
- For the four packages, `from <package> import <name>` keeps the package when every name in the statement is a submodule or a name the package re-exports. Otherwise the statement moves to the implementation module. In text (a `mock.patch` target, a comment) a name that is not a submodule always gets the implementation module, because patching the package does not reach code that imported the implementation.
- A JS specifier or markdown link that already resolves from the file's current folder is kept, even when the author meant a different file at that relative path from the old folder.
- Paths built from `__file__`, `import.meta.url` or `__dirname` are not rewritten. When the file itself moved, each such line is reported: tests and tools now sit one folder deeper. Paths spelled as separate string segments (`ROOT / "webapp" / "backend" / "routers"`) that name a moved or deleted path are reported too.
- Dotted chains in code are rewritten by the text pass. When the rewritten chain's head is a name the file never imports (`services.trade_risk.x` after `from webapp.backend import services`), it is reported, because the new name is unbound. When a file binds one of the four packages (`from core.pipeline import universe`) and also uses it as the package (`universe.tickers`), the port binds the implementation module and says so.
- An import written as text (in a string or comment) is ported only in its one-line form. A parenthesised or multi-line one is left as it is, and prose that happens to read `from x import y` is rewritten like an import.
- Only file moves and the splits below are in the map. A function that moved between two modules that both still exist is not.
- A file with merge-conflict markers cannot be parsed. Resolve the conflicts first.
- It leaves these alone: `docs/archive/`, `docs/migrations/`, `docs/marks/`, `research/`, `tests/baselines/`, `.council/`, `docs/*.json`, every sealed file `tools/_bootstrap.py` guards (`docs/decisions.md` among them), and the porter and its test, which hold pre-refactor examples on purpose.

## What was split

These changes are recorded in the JSON as notes, not as rewrite rules.

### `config/settings.py`

The defaults moved into seven domain files. `config/settings.py` imports every name from them and stays the one namespace every consumer reads. Scoped overrides patch it too: `engine_alpha/structure/context/htf.py` setattr's `config.settings`. So keep `from config import settings` and never import a domain file.

| File | Owns |
|---|---|
| `config/engine.py` | Chart measurement, baseline admission and reading presets (the detection knobs) |
| `config/scoring.py` | Score weights, grading scales and tier thresholds (`SCORE_*`, `TIER_*`) |
| `config/enrichment.py` | Optional fundamentals and relative-strength enrichment |
| `config/archive.py` | Archive persistence policy |
| `config/market_data.py` | Provider, cache, universe admission and price-series policy |
| `config/market_context.py` | Passive market regime and sector health measurements |
| `config/runtime.py` | Dashboard output, scan scheduling and alert policy |

A branch that adds or changes a knob puts the value in the file that owns it and adds the name to that file's import list in `config/settings.py`. The backend's scheduler still reads a fresh copy through `load_core_settings` in `webapp/backend/app/core_settings.py`.

### `webapp/backend/services/startup.py`

Split into `app/startup.py` (`initialize_database`), `app/migrations/{additive,archive,calibration,watchlist}.py` and `app/reconciliation.py`, then deleted. The porter reports an import of `services.startup` with each name's new home:

| Name | Import it from |
|---|---|
| `_MIGRATIONS` | `app.migrations.additive` |
| `initialize_database` | `app.startup` |
| `_apply_migrations` | `app.migrations.additive` |
| `_reconcile_orphaned_runs` | `app.reconciliation` |
| `_has_universe_identity` | `app.migrations.archive` |
| `migrate_universe_type` | `app.migrations.archive` |
| `migrate_watchlist_ledger` | `app.migrations.watchlist` |
| `_NEAR_MISS_IDENTITY` | `app.migrations.archive` |
| `_has_near_miss_framing_identity` | `app.migrations.archive` |
| `migrate_near_miss_framing_identity` | `app.migrations.archive` |
| `_live_event_type_vocabulary` | `app.migrations.calibration` |
| `migrate_calibration_event_types` | `app.migrations.calibration` |
| `_MIGRATED_ARCHIVE_MODELS` | `app.migrations.additive` |
| `model_add_column_migrations` | `app.migrations.additive` |
| `_apply_model_add_columns` | `app.migrations.additive` |

### `webapp/backend/routers/calibration.py`

Moved to `domains/calibration/router.py`, so the porter rewrites the module name. Two groups of names left the router on the way: the same-app guard went to `app/dependencies.py` and the request and response schemas to `domains/calibration/schemas.py`. The router still imports `require_same_app` and the four schemas, so those rewritten imports resolve; `_CLIENT_HEADER_VALUE` does not, so import it from `app.dependencies`. The porter names the home of each:

| Name | Import it from |
|---|---|
| `_CLIENT_HEADER_VALUE` | `app.dependencies` |
| `require_same_app` | `app.dependencies` |
| `EventIn` | `domains.calibration.schemas` |
| `MarkIn` | `domains.calibration.schemas` |
| `EventOut` | `domains.calibration.schemas` |
| `MarkOut` | `domains.calibration.schemas` |

### `webapp/backend/main.py`

The FastAPI lifespan handler moved out of `main.py`:

| Name | Import it from |
|---|---|
| `lifespan` | `app.lifecycle` |
| `_stop_services` | `app.lifecycle` |

## What was deleted, and why

| Path | Why |
|---|---|
| `output/__init__.py` | output/ holds runtime files only; its two Python modules (dashboard, terminal) moved to core/pipeline/screening/, so it is no longer a package. |
| `webapp/backend/ibkr/__init__.py` | Dead re-export package once its modules moved to domains/ibkr/ (domains/ibkr/__init__.py carries the same two names). |
| `webapp/backend/routers/__init__.py` | Every router moved into its domain folder; the empty package was left with no modules. |
| `webapp/backend/services/startup.py` | Split into app/startup.py, app/migrations/*, app/reconciliation.py (the lifespan went to app/lifecycle.py); after the split it was only an alias. |
| `webapp/backend/services/core_settings.py` | Moved to app/core_settings.py (recorded as a manual move; git scores it as delete + add). |

Commit `3fa71b5` also deleted `webapp/backend/schemas.py` and the rest of `webapp/backend/ibkr/`, which the first commit had left behind as aliases. Across the whole refactor git pairs each of them with its new home, so they appear as moves in the tables below, not here.

## Compatibility paths that remain

| Path | Keeps working | Real home |
|---|---|---|
| `config/settings.py` | `from config import settings`, and every override of it | `config/<domain>.py` |
| `engine_alpha/structure/{lps,narrative,metrics}/__init__.py` | `from <package> import <name>` for the names in each `__all__` | `lps/detection.py`, `narrative/reader.py`, `metrics/base.py` |
| `core/pipeline/{universe,market_data,screening}/__init__.py` | `from <package> import <name>` for the names in each `__all__` | `universe/descriptor.py`, `market_data/providers.py`, `screening/screener.py` |
| `webapp/backend/frame_store.py` | `import frame_store` and `webapp.backend.frame_store` (the spelling tools use) | `webapp/backend/domains/calibration/frame_store.py` |
| `webapp/backend/marks_validity.py` | `import marks_validity` and `webapp.backend.marks_validity` (the spelling tools use) | `webapp/backend/domains/calibration/validation.py` |
| `webapp/backend/models.py` | The model registry `create_all` needs | `webapp/backend/domains/<name>/models.py` |
| `webapp/backend/archive_models.py` | The archive ORM and market-context names | `domains/archive/models.py`, `domains/archive/market_context.py` |
| `webapp/backend/broker_config.py` | Unchanged: it carries its own manual-connection safety contract | (same file) |
| `tools/run_maturation.bat` | The Task Scheduler entry registered with this absolute path | `tools/ops/run_maturation.bat` |
| `tools/fidelity/README.md` | Sealed records that cite `tools/fidelity/<name>/` | `research/fidelity/` |

## Python modules that moved

Import names, as the porter rewrites them. Repo-root modules import from the repository root. Backend modules import from `webapp/backend` (the service puts it on `sys.path`); tools and tests also spell them `webapp.backend.<name>`, and the porter keeps that spelling. The four rows marked *package* are old modules that became a package of the same name; the old name still imports, as the package, and the implementation is the child named on the right.

### Repo root

| Old import | New import |
|---|---|
| `core.pipeline.cache` | `core.pipeline.market_data.cache` |
| `core.pipeline.cache_status` | `core.pipeline.market_data.cache_status` |
| `core.pipeline.candles` | `core.pipeline.market_data.candles` |
| `core.pipeline.data_freshness` | `core.pipeline.market_data.data_freshness` |
| `core.pipeline.downloads` | `core.pipeline.market_data.downloads` |
| `core.pipeline.fetch_health` | `core.pipeline.market_data.fetch_health` |
| `core.pipeline.file_lock` | `core.pipeline.market_data.file_lock` |
| `core.pipeline.health_board` | `core.pipeline.context.health_board` |
| `core.pipeline.market_calendar` | `core.pipeline.market_data.market_calendar` |
| `core.pipeline.market_context` | `core.pipeline.context.market_context` |
| `core.pipeline.market_data_health` | `core.pipeline.market_data.market_data_health` |
| `core.pipeline.providers` | `core.pipeline.market_data.providers` |
| `core.pipeline.rate_limit` | `core.pipeline.market_data.rate_limit` |
| `core.pipeline.scan_job` | `core.pipeline.screening.scan_job` |
| `core.pipeline.scan_metrics` | `core.pipeline.telemetry.scan_metrics` |
| `core.pipeline.screener` | `core.pipeline.screening.screener` |
| `core.pipeline.ticker_admission` | `core.pipeline.universe.ticker_admission` |
| `core.pipeline.tickers` | `core.pipeline.universe.tickers` |
| `core.pipeline.universe` | `core.pipeline.universe.descriptor` *package* |
| `engine_alpha.structure.box_events` | `engine_alpha.structure.events.box_events` |
| `engine_alpha.structure.box_gates` | `engine_alpha.structure.box.box_gates` |
| `engine_alpha.structure.box_primitives` | `engine_alpha.structure.box.box_primitives` |
| `engine_alpha.structure.box_trace` | `engine_alpha.structure.box.box_trace` |
| `engine_alpha.structure.bricks` | `engine_alpha.structure.narrative.bricks` |
| `engine_alpha.structure.chain` | `engine_alpha.structure.narrative.chain` |
| `engine_alpha.structure.consolidation` | `engine_alpha.structure.box.consolidation` |
| `engine_alpha.structure.displacement` | `engine_alpha.structure.events.displacement` |
| `engine_alpha.structure.event_map` | `engine_alpha.structure.events.event_map` |
| `engine_alpha.structure.event_vocabulary` | `engine_alpha.structure.events.event_vocabulary` |
| `engine_alpha.structure.gate_margins` | `engine_alpha.structure.box.gate_margins` |
| `engine_alpha.structure.htf` | `engine_alpha.structure.context.htf` |
| `engine_alpha.structure.indicators` | `engine_alpha.structure.metrics.indicators` |
| `engine_alpha.structure.inner_box` | `engine_alpha.structure.box.inner_box` |
| `engine_alpha.structure.lps` | `engine_alpha.structure.lps.detection` *package* |
| `engine_alpha.structure.market_structure` | `engine_alpha.structure.events.market_structure` |
| `engine_alpha.structure.metrics` | `engine_alpha.structure.metrics.base` *package* |
| `engine_alpha.structure.narrative` | `engine_alpha.structure.narrative.reader` *package* |
| `engine_alpha.structure.near_miss` | `engine_alpha.structure.box.near_miss` |
| `engine_alpha.structure.phase_a` | `engine_alpha.structure.phases.phase_a` |
| `engine_alpha.structure.phase_d` | `engine_alpha.structure.phases.phase_d` |
| `engine_alpha.structure.phase_features` | `engine_alpha.structure.phases.phase_features` |
| `engine_alpha.structure.pivots` | `engine_alpha.structure.metrics.pivots` |
| `engine_alpha.structure.power_play` | `engine_alpha.structure.context.power_play` |
| `engine_alpha.structure.rail_qualification` | `engine_alpha.structure.box.rail_qualification` |
| `engine_alpha.structure.scope` | `engine_alpha.structure.context.scope` |
| `engine_alpha.structure.segmentation` | `engine_alpha.structure.phases.segmentation` |
| `engine_alpha.structure.strategy_read` | `engine_alpha.structure.context.strategy_read` |
| `engine_alpha.structure.trace_export` | `engine_alpha.structure.box.trace_export` |
| `output.dashboard` | `core.pipeline.screening.dashboard` |
| `output.terminal` | `core.pipeline.screening.terminal` |
| `tools.agreement` | `tools.calibration.agreement` |
| `tools.backtest_engine` | `tools.research.backtest_engine` |
| `tools.bar_state_census` | `tools.research.bar_state_census` |
| `tools.build_universe_returns` | `tools.research.build_universe_returns` |
| `tools.calibration_harness` | `tools.calibration.calibration_harness` |
| `tools.calibration_stat_card` | `tools.calibration.calibration_stat_card` |
| `tools.cause_veto_corpus` | `tools.regression.cause_veto_corpus` |
| `tools.correspondence_census` | `tools.research.correspondence_census` |
| `tools.doctrine_audit` | `tools.audits.doctrine_audit` |
| `tools.event_map_census` | `tools.research.event_map_census` |
| `tools.event_map_chronology` | `tools.audits.event_map_chronology` |
| `tools.fold_parity` | `tools.regression.fold_parity` |
| `tools.full_package_render` | `tools.research.full_package_render` |
| `tools.guided_list_export` | `tools.calibration.guided_list_export` |
| `tools.htf_audit` | `tools.audits.htf_audit` |
| `tools.marks_corpus` | `tools.regression.marks_corpus` |
| `tools.marks_json` | `tools.calibration.marks_json` |
| `tools.miss_lane_census` | `tools.research.miss_lane_census` |
| `tools.near_miss_census` | `tools.research.near_miss_census` |
| `tools.near_miss_report` | `tools.research.near_miss_report` |
| `tools.negative_corpus` | `tools.regression.negative_corpus` |
| `tools.operator_marks_diff` | `tools.research.operator_marks_diff` |
| `tools.pointer_audit` | `tools.audits.pointer_audit` |
| `tools.power_play_census` | `tools.research.power_play_census` |
| `tools.power_play_fixture` | `tools.regression.power_play_fixture` |
| `tools.power_play_sheets` | `tools.research.power_play_sheets` |
| `tools.provider_parity` | `tools.audits.provider_parity` |
| `tools.rail_area_census` | `tools.research.rail_area_census` |
| `tools.rail_margin_ab` | `tools.research.rail_margin_ab` |
| `tools.rail_margin_evidence` | `tools.research.rail_margin_evidence` |
| `tools.reader_pin` | `tools.regression.reader_pin` |
| `tools.replay` | `tools.calibration.replay` |
| `tools.restore_drill` | `tools.ops.restore_drill` |
| `tools.settings_reference` | `tools.maintenance.settings_reference` |
| `tools.shadow_diff` | `tools.regression.shadow_diff` |
| `tools.shape_profile` | `tools.research.shape_profile` |
| `tools.shelf_harness` | `tools.calibration.shelf_harness` |
| `tools.story_chain_candidates` | `tools.research.story_chain_candidates` |
| `tools.structure_case_audit` | `tools.audits.structure_case_audit` |
| `tools.ta_grade_archive_replay` | `tools.research.ta_grade_archive_replay` |
| `tools.ta_grade_timing` | `tools.audits.ta_grade_timing` |

### Backend root

| Old import | New import |
|---|---|
| `ibkr.broadcaster` | `domains.ibkr.broadcaster` |
| `ibkr.mapping` | `domains.ibkr.mapping` |
| `ibkr.service` | `domains.ibkr.service` |
| `routers.analytics` | `domains.trading.analytics` |
| `routers.archive` | `domains.archive.router` |
| `routers.archive_actions` | `domains.archive.actions` |
| `routers.archive_browse` | `domains.archive.browse` |
| `routers.archive_calibration` | `domains.archive.calibration` |
| `routers.archive_reviews` | `domains.archive.reviews` |
| `routers.archive_schemas` | `domains.archive.schemas` |
| `routers.calibration` | `domains.calibration.router` |
| `routers.candles` | `domains.market_data.candles` |
| `routers.engine_edge` | `domains.archive.edge_router` |
| `routers.ibkr` | `domains.ibkr.router` |
| `routers.journal` | `domains.trading.journal` |
| `routers.market_data` | `domains.market_data.router` |
| `routers.portfolio` | `domains.portfolio.router` |
| `routers.portfolio_streams` | `domains.portfolio.streams` |
| `routers.prices` | `domains.market_data.prices` |
| `routers.screener` | `domains.screener.router` |
| `routers.tags` | `domains.trading.tags` |
| `routers.trade_risk` | `domains.trading.risk_router` |
| `routers.trades` | `domains.trading.router` |
| `routers.watchlist` | `domains.watchlist.router` |
| `schemas` | `domains.trading.schemas` |
| `services.alpaca_prices` | `domains.market_data.alpaca_prices` |
| `services.archive_queries` | `domains.archive.queries` |
| `services.auto_import` | `domains.trading.auto_import` |
| `services.calibration_agreement` | `domains.calibration.agreement` |
| `services.calibration_fired` | `domains.calibration.fired` |
| `services.candle_cache` | `domains.market_data.candle_cache` |
| `services.concordance` | `domains.archive.concordance` |
| `services.core_settings` | `app.core_settings` |
| `services.csv_import` | `domains.trading.csv_import` |
| `services.earnings` | `domains.market_data.earnings` |
| `services.engine_edge` | `domains.archive.edge` |
| `services.episode_cache` | `domains.archive.episode_cache` |
| `services.frontend` | `app.frontend` |
| `services.journal_stats` | `domains.trading.statistics` |
| `services.log_encoding` | `app.log_encoding` |
| `services.market_data` | `domains.market_data.service` |
| `services.portfolio_snapshot` | `domains.portfolio.snapshot` |
| `services.screener_data` | `domains.screener.data` |
| `services.trade_risk` | `domains.trading.risk` |
| `services.trigger_grade` | `domains.calibration.trigger_grade` |
| `services.watchlist_candles` | `domains.market_data.watchlist_candles` |
| `services.watchlist_ledger` | `domains.watchlist.ledger` |

## Files that moved

Whole folders that moved unchanged:

| Old folder | New folder |
|---|---|
| `tools/fidelity/ar_first_reaction_2026-08-13/` | `research/fidelity/ar_first_reaction_2026-08-13/` |
| `tools/fidelity/ar_first_reaction_2026-08-31/` | `research/fidelity/ar_first_reaction_2026-08-31/` |
| `tools/fidelity/box_backext/` | `research/fidelity/box_backext/` |
| `tools/fidelity/full_package/` | `research/fidelity/full_package/` |
| `tools/fidelity/pip_phase_a/` | `research/fidelity/pip_phase_a/` |
| `tools/fidelity/trend_terminal_2026-08-13/` | `research/fidelity/trend_terminal_2026-08-13/` |
| `webapp/frontend/src/components/archive/` | `webapp/frontend/src/features/archive/components/` |
| `webapp/frontend/src/components/tradeDetail/` | `webapp/frontend/src/features/journal/components/tradeDetail/` |
| `webapp/frontend/src/components/tradeTable/` | `webapp/frontend/src/features/journal/components/tradeTable/` |
| `webapp/frontend/src/components/watchlist/` | `webapp/frontend/src/features/watchlist/components/` |

### Engine (`engine_alpha/structure/`)

| Old path | New path |
|---|---|
| `engine_alpha/structure/box_events.py` | `engine_alpha/structure/events/box_events.py` |
| `engine_alpha/structure/box_gates.py` | `engine_alpha/structure/box/box_gates.py` |
| `engine_alpha/structure/box_primitives.py` | `engine_alpha/structure/box/box_primitives.py` |
| `engine_alpha/structure/box_trace.py` | `engine_alpha/structure/box/box_trace.py` |
| `engine_alpha/structure/bricks.py` | `engine_alpha/structure/narrative/bricks.py` |
| `engine_alpha/structure/chain.py` | `engine_alpha/structure/narrative/chain.py` |
| `engine_alpha/structure/consolidation.py` | `engine_alpha/structure/box/consolidation.py` |
| `engine_alpha/structure/displacement.py` | `engine_alpha/structure/events/displacement.py` |
| `engine_alpha/structure/event_map.py` | `engine_alpha/structure/events/event_map.py` |
| `engine_alpha/structure/event_vocabulary.py` | `engine_alpha/structure/events/event_vocabulary.py` |
| `engine_alpha/structure/gate_margins.py` | `engine_alpha/structure/box/gate_margins.py` |
| `engine_alpha/structure/htf.py` | `engine_alpha/structure/context/htf.py` |
| `engine_alpha/structure/indicators.py` | `engine_alpha/structure/metrics/indicators.py` |
| `engine_alpha/structure/inner_box.py` | `engine_alpha/structure/box/inner_box.py` |
| `engine_alpha/structure/lps.py` | `engine_alpha/structure/lps/detection.py` |
| `engine_alpha/structure/market_structure.py` | `engine_alpha/structure/events/market_structure.py` |
| `engine_alpha/structure/metrics.py` | `engine_alpha/structure/metrics/base.py` |
| `engine_alpha/structure/narrative.py` | `engine_alpha/structure/narrative/reader.py` |
| `engine_alpha/structure/near_miss.py` | `engine_alpha/structure/box/near_miss.py` |
| `engine_alpha/structure/phase_a.py` | `engine_alpha/structure/phases/phase_a.py` |
| `engine_alpha/structure/phase_d.py` | `engine_alpha/structure/phases/phase_d.py` |
| `engine_alpha/structure/phase_features.py` | `engine_alpha/structure/phases/phase_features.py` |
| `engine_alpha/structure/pivots.py` | `engine_alpha/structure/metrics/pivots.py` |
| `engine_alpha/structure/power_play.py` | `engine_alpha/structure/context/power_play.py` |
| `engine_alpha/structure/rail_qualification.py` | `engine_alpha/structure/box/rail_qualification.py` |
| `engine_alpha/structure/scope.py` | `engine_alpha/structure/context/scope.py` |
| `engine_alpha/structure/segmentation.py` | `engine_alpha/structure/phases/segmentation.py` |
| `engine_alpha/structure/strategy_read.py` | `engine_alpha/structure/context/strategy_read.py` |
| `engine_alpha/structure/trace_export.py` | `engine_alpha/structure/box/trace_export.py` |

### Pipeline (`core/pipeline/`, and the writers that left `output/`)

| Old path | New path |
|---|---|
| `core/pipeline/cache.py` | `core/pipeline/market_data/cache.py` |
| `core/pipeline/cache_status.py` | `core/pipeline/market_data/cache_status.py` |
| `core/pipeline/candles.py` | `core/pipeline/market_data/candles.py` |
| `core/pipeline/data_freshness.py` | `core/pipeline/market_data/data_freshness.py` |
| `core/pipeline/downloads.py` | `core/pipeline/market_data/downloads.py` |
| `core/pipeline/fetch_health.py` | `core/pipeline/market_data/fetch_health.py` |
| `core/pipeline/file_lock.py` | `core/pipeline/market_data/file_lock.py` |
| `core/pipeline/health_board.py` | `core/pipeline/context/health_board.py` |
| `core/pipeline/market_calendar.py` | `core/pipeline/market_data/market_calendar.py` |
| `core/pipeline/market_context.py` | `core/pipeline/context/market_context.py` |
| `core/pipeline/market_data_health.py` | `core/pipeline/market_data/market_data_health.py` |
| `core/pipeline/providers.py` | `core/pipeline/market_data/providers.py` |
| `core/pipeline/rate_limit.py` | `core/pipeline/market_data/rate_limit.py` |
| `core/pipeline/scan_job.py` | `core/pipeline/screening/scan_job.py` |
| `core/pipeline/scan_metrics.py` | `core/pipeline/telemetry/scan_metrics.py` |
| `core/pipeline/screener.py` | `core/pipeline/screening/screener.py` |
| `core/pipeline/ticker_admission.py` | `core/pipeline/universe/ticker_admission.py` |
| `core/pipeline/tickers.py` | `core/pipeline/universe/tickers.py` |
| `core/pipeline/universe.py` | `core/pipeline/universe/descriptor.py` |
| `output/dashboard.py` | `core/pipeline/screening/dashboard.py` |
| `output/terminal.py` | `core/pipeline/screening/terminal.py` |

### Backend (`webapp/backend/`)

| Old path | New path |
|---|---|
| `webapp/backend/ibkr/broadcaster.py` | `webapp/backend/domains/ibkr/broadcaster.py` |
| `webapp/backend/ibkr/mapping.py` | `webapp/backend/domains/ibkr/mapping.py` |
| `webapp/backend/ibkr/service.py` | `webapp/backend/domains/ibkr/service.py` |
| `webapp/backend/routers/analytics.py` | `webapp/backend/domains/trading/analytics.py` |
| `webapp/backend/routers/archive.py` | `webapp/backend/domains/archive/router.py` |
| `webapp/backend/routers/archive_actions.py` | `webapp/backend/domains/archive/actions.py` |
| `webapp/backend/routers/archive_browse.py` | `webapp/backend/domains/archive/browse.py` |
| `webapp/backend/routers/archive_calibration.py` | `webapp/backend/domains/archive/calibration.py` |
| `webapp/backend/routers/archive_reviews.py` | `webapp/backend/domains/archive/reviews.py` |
| `webapp/backend/routers/archive_schemas.py` | `webapp/backend/domains/archive/schemas.py` |
| `webapp/backend/routers/calibration.py` | `webapp/backend/domains/calibration/router.py` |
| `webapp/backend/routers/candles.py` | `webapp/backend/domains/market_data/candles.py` |
| `webapp/backend/routers/engine_edge.py` | `webapp/backend/domains/archive/edge_router.py` |
| `webapp/backend/routers/ibkr.py` | `webapp/backend/domains/ibkr/router.py` |
| `webapp/backend/routers/journal.py` | `webapp/backend/domains/trading/journal.py` |
| `webapp/backend/routers/market_data.py` | `webapp/backend/domains/market_data/router.py` |
| `webapp/backend/routers/portfolio.py` | `webapp/backend/domains/portfolio/router.py` |
| `webapp/backend/routers/portfolio_streams.py` | `webapp/backend/domains/portfolio/streams.py` |
| `webapp/backend/routers/prices.py` | `webapp/backend/domains/market_data/prices.py` |
| `webapp/backend/routers/screener.py` | `webapp/backend/domains/screener/router.py` |
| `webapp/backend/routers/tags.py` | `webapp/backend/domains/trading/tags.py` |
| `webapp/backend/routers/trade_risk.py` | `webapp/backend/domains/trading/risk_router.py` |
| `webapp/backend/routers/trades.py` | `webapp/backend/domains/trading/router.py` |
| `webapp/backend/routers/watchlist.py` | `webapp/backend/domains/watchlist/router.py` |
| `webapp/backend/schemas.py` | `webapp/backend/domains/trading/schemas.py` |
| `webapp/backend/services/alpaca_prices.py` | `webapp/backend/domains/market_data/alpaca_prices.py` |
| `webapp/backend/services/archive_queries.py` | `webapp/backend/domains/archive/queries.py` |
| `webapp/backend/services/auto_import.py` | `webapp/backend/domains/trading/auto_import.py` |
| `webapp/backend/services/calibration_agreement.py` | `webapp/backend/domains/calibration/agreement.py` |
| `webapp/backend/services/calibration_fired.py` | `webapp/backend/domains/calibration/fired.py` |
| `webapp/backend/services/candle_cache.py` | `webapp/backend/domains/market_data/candle_cache.py` |
| `webapp/backend/services/concordance.py` | `webapp/backend/domains/archive/concordance.py` |
| `webapp/backend/services/core_settings.py` | `webapp/backend/app/core_settings.py` |
| `webapp/backend/services/csv_import.py` | `webapp/backend/domains/trading/csv_import.py` |
| `webapp/backend/services/earnings.py` | `webapp/backend/domains/market_data/earnings.py` |
| `webapp/backend/services/engine_edge.py` | `webapp/backend/domains/archive/edge.py` |
| `webapp/backend/services/episode_cache.py` | `webapp/backend/domains/archive/episode_cache.py` |
| `webapp/backend/services/frontend.py` | `webapp/backend/app/frontend.py` |
| `webapp/backend/services/journal_stats.py` | `webapp/backend/domains/trading/statistics.py` |
| `webapp/backend/services/log_encoding.py` | `webapp/backend/app/log_encoding.py` |
| `webapp/backend/services/market_data.py` | `webapp/backend/domains/market_data/service.py` |
| `webapp/backend/services/portfolio_snapshot.py` | `webapp/backend/domains/portfolio/snapshot.py` |
| `webapp/backend/services/screener_data.py` | `webapp/backend/domains/screener/data.py` |
| `webapp/backend/services/trade_risk.py` | `webapp/backend/domains/trading/risk.py` |
| `webapp/backend/services/trigger_grade.py` | `webapp/backend/domains/calibration/trigger_grade.py` |
| `webapp/backend/services/watchlist_candles.py` | `webapp/backend/domains/market_data/watchlist_candles.py` |
| `webapp/backend/services/watchlist_ledger.py` | `webapp/backend/domains/watchlist/ledger.py` |

### Frontend (`webapp/frontend/src/`)

| Old path | New path |
|---|---|
| `webapp/frontend/src/App.jsx` | `webapp/frontend/src/app/App.jsx` |
| `webapp/frontend/src/api.js` | `webapp/frontend/src/api/base.js` |
| `webapp/frontend/src/components/AnalyticsPanel.jsx` | `webapp/frontend/src/features/journal/components/AnalyticsPanel.jsx` |
| `webapp/frontend/src/components/AppShell.jsx` | `webapp/frontend/src/app/components/AppShell.jsx` |
| `webapp/frontend/src/components/AppTopbar.jsx` | `webapp/frontend/src/app/components/AppTopbar.jsx` |
| `webapp/frontend/src/components/AppearanceControl.jsx` | `webapp/frontend/src/app/components/AppearanceControl.jsx` |
| `webapp/frontend/src/components/ArchiveMaintenanceModals.jsx` | `webapp/frontend/src/features/archive/components/ArchiveMaintenanceModals.jsx` |
| `webapp/frontend/src/components/ArchiveTab.jsx` | `webapp/frontend/src/features/archive/components/ArchiveTab.jsx` |
| `webapp/frontend/src/components/AttachmentUploader.jsx` | `webapp/frontend/src/features/journal/components/AttachmentUploader.jsx` |
| `webapp/frontend/src/components/CalculatorModal.jsx` | `webapp/frontend/src/features/journal/components/CalculatorModal.jsx` |
| `webapp/frontend/src/components/CalibrationMarkingBar.jsx` | `webapp/frontend/src/features/calibration/components/CalibrationMarkingBar.jsx` |
| `webapp/frontend/src/components/CalibrationMarksList.jsx` | `webapp/frontend/src/features/calibration/components/CalibrationMarksList.jsx` |
| `webapp/frontend/src/components/CalibrationRail.jsx` | `webapp/frontend/src/features/calibration/components/CalibrationRail.jsx` |
| `webapp/frontend/src/components/CalibrationSaveBar.jsx` | `webapp/frontend/src/features/calibration/components/CalibrationSaveBar.jsx` |
| `webapp/frontend/src/components/CalibrationTab.jsx` | `webapp/frontend/src/features/calibration/components/CalibrationTab.jsx` |
| `webapp/frontend/src/components/CandleChart.jsx` | `webapp/frontend/src/shared/charts/CandleChart.jsx` |
| `webapp/frontend/src/components/DashboardStats.jsx` | `webapp/frontend/src/features/journal/components/DashboardStats.jsx` |
| `webapp/frontend/src/components/EquityCurve.jsx` | `webapp/frontend/src/features/journal/components/EquityCurve.jsx` |
| `webapp/frontend/src/components/ErrorBoundary.jsx` | `webapp/frontend/src/shared/components/ErrorBoundary.jsx` |
| `webapp/frontend/src/components/FrameThumb.jsx` | `webapp/frontend/src/features/calibration/components/FrameThumb.jsx` |
| `webapp/frontend/src/components/HealthBoard.jsx` | `webapp/frontend/src/features/screener/components/HealthBoard.jsx` |
| `webapp/frontend/src/components/IbkrModeControls.jsx` | `webapp/frontend/src/features/ibkr/components/IbkrModeControls.jsx` |
| `webapp/frontend/src/components/MarketPulse.jsx` | `webapp/frontend/src/features/home/components/MarketPulse.jsx` |
| `webapp/frontend/src/components/MarketRegimeDetailModal.jsx` | `webapp/frontend/src/features/home/components/MarketRegimeDetailModal.jsx` |
| `webapp/frontend/src/components/NavIcons.jsx` | `webapp/frontend/src/shared/components/NavIcons.jsx` |
| `webapp/frontend/src/components/PortfolioDailyPnl.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioDailyPnl.jsx` |
| `webapp/frontend/src/components/PortfolioPositionChart.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioPositionChart.jsx` |
| `webapp/frontend/src/components/PortfolioPositionInsights.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioPositionInsights.jsx` |
| `webapp/frontend/src/components/PortfolioStatusBar.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioStatusBar.jsx` |
| `webapp/frontend/src/components/PortfolioSummary.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioSummary.jsx` |
| `webapp/frontend/src/components/PortfolioTab.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioTab.jsx` |
| `webapp/frontend/src/components/PortfolioTables.jsx` | `webapp/frontend/src/features/portfolio/components/PortfolioTables.jsx` |
| `webapp/frontend/src/components/PositionCalculator.jsx` | `webapp/frontend/src/features/journal/components/PositionCalculator.jsx` |
| `webapp/frontend/src/components/RMultipleHistogram.jsx` | `webapp/frontend/src/features/journal/components/RMultipleHistogram.jsx` |
| `webapp/frontend/src/components/RegimePanel.jsx` | `webapp/frontend/src/features/home/components/RegimePanel.jsx` |
| `webapp/frontend/src/components/ScanHistoryModal.jsx` | `webapp/frontend/src/features/screener/components/ScanHistoryModal.jsx` |
| `webapp/frontend/src/components/ScreenerCard.jsx` | `webapp/frontend/src/shared/setup/ScreenerCard.jsx` |
| `webapp/frontend/src/components/ScreenerGrid.jsx` | `webapp/frontend/src/features/screener/components/ScreenerGrid.jsx` |
| `webapp/frontend/src/components/ScreenerMiniChart.jsx` | `webapp/frontend/src/shared/charts/ScreenerMiniChart.jsx` |
| `webapp/frontend/src/components/ScreenerModal.jsx` | `webapp/frontend/src/shared/setup/ScreenerModal.jsx` |
| `webapp/frontend/src/components/ScreenerPager.jsx` | `webapp/frontend/src/features/screener/components/ScreenerPager.jsx` |
| `webapp/frontend/src/components/ScreenerScanProgress.jsx` | `webapp/frontend/src/features/screener/components/ScreenerScanProgress.jsx` |
| `webapp/frontend/src/components/ScreenerStockLens.jsx` | `webapp/frontend/src/shared/setup/ScreenerStockLens.jsx` |
| `webapp/frontend/src/components/ScreenerToolbar.jsx` | `webapp/frontend/src/features/screener/components/ScreenerToolbar.jsx` |
| `webapp/frontend/src/components/ScreenerWatchlistPanel.jsx` | `webapp/frontend/src/features/watchlist/components/ScreenerWatchlistPanel.jsx` |
| `webapp/frontend/src/components/SetupStoryPanel.jsx` | `webapp/frontend/src/shared/setup/SetupStoryPanel.jsx` |
| `webapp/frontend/src/components/SetupTags.jsx` | `webapp/frontend/src/shared/setup/SetupTags.jsx` |
| `webapp/frontend/src/components/TimeframeMainChart.jsx` | `webapp/frontend/src/shared/charts/TimeframeMainChart.jsx` |
| `webapp/frontend/src/components/TimeframeMiniRow.jsx` | `webapp/frontend/src/shared/setup/TimeframeMiniRow.jsx` |
| `webapp/frontend/src/components/TradeDetailDrawer.jsx` | `webapp/frontend/src/features/journal/components/TradeDetailDrawer.jsx` |
| `webapp/frontend/src/components/TradeTable.jsx` | `webapp/frontend/src/features/journal/components/TradeTable.jsx` |
| `webapp/frontend/src/components/UniverseSwitcher.jsx` | `webapp/frontend/src/features/screener/components/UniverseSwitcher.jsx` |
| `webapp/frontend/src/components/WeeklyReview.jsx` | `webapp/frontend/src/features/watchlist/components/WeeklyReview.jsx` |
| `webapp/frontend/src/components/archive/AddSetupModal.jsx` | `webapp/frontend/src/features/archive/components/AddSetupModal.jsx` |
| `webapp/frontend/src/components/archive/ArchiveCalibrationPanels.jsx` | `webapp/frontend/src/features/archive/components/ArchiveCalibrationPanels.jsx` |
| `webapp/frontend/src/components/archive/ArchiveEquityCurve.jsx` | `webapp/frontend/src/features/archive/components/ArchiveEquityCurve.jsx` |
| `webapp/frontend/src/components/archive/ArchiveFilters.jsx` | `webapp/frontend/src/features/archive/components/ArchiveFilters.jsx` |
| `webapp/frontend/src/components/archive/ArchiveHeader.jsx` | `webapp/frontend/src/features/archive/components/ArchiveHeader.jsx` |
| `webapp/frontend/src/components/archive/ArchiveReweightingStrip.jsx` | `webapp/frontend/src/features/archive/components/ArchiveReweightingStrip.jsx` |
| `webapp/frontend/src/components/archive/ArchiveSummary.jsx` | `webapp/frontend/src/features/archive/components/ArchiveSummary.jsx` |
| `webapp/frontend/src/components/archive/ArchiveTable.jsx` | `webapp/frontend/src/features/archive/components/ArchiveTable.jsx` |
| `webapp/frontend/src/components/archive/ArchiveTierCards.jsx` | `webapp/frontend/src/features/archive/components/ArchiveTierCards.jsx` |
| `webapp/frontend/src/components/calibrationAsOfLine.js` | `webapp/frontend/src/features/calibration/chart/calibrationAsOfLine.js` |
| `webapp/frontend/src/components/calibrationDraw.js` | `webapp/frontend/src/features/calibration/chart/calibrationDraw.js` |
| `webapp/frontend/src/components/calibrationHover.js` | `webapp/frontend/src/features/calibration/chart/calibrationHover.js` |
| `webapp/frontend/src/components/chapterStrip.js` | `webapp/frontend/src/shared/setup/chapterStrip.js` |
| `webapp/frontend/src/components/chapterStrip.test.js` | `webapp/frontend/src/shared/setup/chapterStrip.test.js` |
| `webapp/frontend/src/components/chartGeometry.js` | `webapp/frontend/src/shared/charts/chartGeometry.js` |
| `webapp/frontend/src/components/chartGeometry.test.js` | `webapp/frontend/src/shared/charts/chartGeometry.test.js` |
| `webapp/frontend/src/components/chartIndicators.js` | `webapp/frontend/src/shared/charts/chartIndicators.js` |
| `webapp/frontend/src/components/chartPhaseOverlay.js` | `webapp/frontend/src/shared/charts/chartPhaseOverlay.js` |
| `webapp/frontend/src/components/chartRails.js` | `webapp/frontend/src/shared/charts/chartRails.js` |
| `webapp/frontend/src/components/chartTheme.js` | `webapp/frontend/src/shared/charts/chartTheme.js` |
| `webapp/frontend/src/components/glanceCache.js` | `webapp/frontend/src/shared/charts/glance/glanceCache.js` |
| `webapp/frontend/src/components/glanceCache.test.js` | `webapp/frontend/src/shared/charts/glance/glanceCache.test.js` |
| `webapp/frontend/src/components/glanceMath.js` | `webapp/frontend/src/shared/charts/glance/glanceMath.js` |
| `webapp/frontend/src/components/glanceMath.test.js` | `webapp/frontend/src/shared/charts/glance/glanceMath.test.js` |
| `webapp/frontend/src/components/glanceResolvers.js` | `webapp/frontend/src/shared/charts/glance/glanceResolvers.js` |
| `webapp/frontend/src/components/healthBoardSort.js` | `webapp/frontend/src/features/screener/presentation/healthBoardSort.js` |
| `webapp/frontend/src/components/healthBoardSort.test.js` | `webapp/frontend/src/features/screener/presentation/healthBoardSort.test.js` |
| `webapp/frontend/src/components/healthStateData.js` | `webapp/frontend/src/shared/setup/healthStateData.js` |
| `webapp/frontend/src/components/home/ActionCenter.jsx` | `webapp/frontend/src/features/home/components/ActionCenter.jsx` |
| `webapp/frontend/src/components/home/BridgeOut.jsx` | `webapp/frontend/src/features/home/components/BridgeOut.jsx` |
| `webapp/frontend/src/components/home/EdgePulse.jsx` | `webapp/frontend/src/features/home/components/EdgePulse.jsx` |
| `webapp/frontend/src/components/home/HomeView.jsx` | `webapp/frontend/src/features/home/components/HomeView.jsx` |
| `webapp/frontend/src/components/home/HomeZone.jsx` | `webapp/frontend/src/features/home/components/HomeZone.jsx` |
| `webapp/frontend/src/components/home/JournalPulseZone.jsx` | `webapp/frontend/src/features/home/components/JournalPulseZone.jsx` |
| `webapp/frontend/src/components/home/OpenBookZone.jsx` | `webapp/frontend/src/features/home/components/OpenBookZone.jsx` |
| `webapp/frontend/src/components/home/WatchlistZone.jsx` | `webapp/frontend/src/features/home/components/WatchlistZone.jsx` |
| `webapp/frontend/src/components/home/homeFormat.js` | `webapp/frontend/src/features/home/presentation/homeFormat.js` |
| `webapp/frontend/src/components/marketRegimeFormat.js` | `webapp/frontend/src/features/home/presentation/marketRegimeFormat.js` |
| `webapp/frontend/src/components/narrativeRead.js` | `webapp/frontend/src/shared/setup/narrativeRead.js` |
| `webapp/frontend/src/components/narrativeRead.test.js` | `webapp/frontend/src/shared/setup/narrativeRead.test.js` |
| `webapp/frontend/src/components/portfolioFormat.js` | `webapp/frontend/src/features/portfolio/presentation/portfolioFormat.js` |
| `webapp/frontend/src/components/replayAdapter.js` | `webapp/frontend/src/shared/charts/glance/replayAdapter.js` |
| `webapp/frontend/src/components/replayAdapter.test.js` | `webapp/frontend/src/shared/charts/glance/replayAdapter.test.js` |
| `webapp/frontend/src/components/setupStoryRows.js` | `webapp/frontend/src/shared/setup/setupStoryRows.js` |
| `webapp/frontend/src/components/setupStoryRows.test.js` | `webapp/frontend/src/shared/setup/setupStoryRows.test.js` |
| `webapp/frontend/src/components/tagCatalog.js` | `webapp/frontend/src/shared/setup/tagCatalog.js` |
| `webapp/frontend/src/components/tagResolver.js` | `webapp/frontend/src/shared/setup/tagResolver.js` |
| `webapp/frontend/src/components/tagResolver.test.js` | `webapp/frontend/src/shared/setup/tagResolver.test.js` |
| `webapp/frontend/src/components/tagTooltips.js` | `webapp/frontend/src/shared/setup/tagTooltips.js` |
| `webapp/frontend/src/components/tooltipText.js` | `webapp/frontend/src/shared/formatting/tooltipText.js` |
| `webapp/frontend/src/components/tradeDetail/ExecutionsTab.jsx` | `webapp/frontend/src/features/journal/components/tradeDetail/ExecutionsTab.jsx` |
| `webapp/frontend/src/components/tradeDetail/NotesTab.jsx` | `webapp/frontend/src/features/journal/components/tradeDetail/NotesTab.jsx` |
| `webapp/frontend/src/components/tradeDetail/TradeSetupChart.jsx` | `webapp/frontend/src/features/journal/components/tradeDetail/TradeSetupChart.jsx` |
| `webapp/frontend/src/components/tradeDetail/styles.js` | `webapp/frontend/src/features/journal/components/tradeDetail/styles.js` |
| `webapp/frontend/src/components/tradeDetail/tradePlanDrawerStyles.js` | `webapp/frontend/src/features/journal/components/tradeDetail/tradePlanDrawerStyles.js` |
| `webapp/frontend/src/components/tradeTable/DraftTradeRow.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/DraftTradeRow.jsx` |
| `webapp/frontend/src/components/tradeTable/FillsRow.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/FillsRow.jsx` |
| `webapp/frontend/src/components/tradeTable/TradeCells.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/TradeCells.jsx` |
| `webapp/frontend/src/components/tradeTable/TradeRiskAlerts.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/TradeRiskAlerts.jsx` |
| `webapp/frontend/src/components/tradeTable/TradeRow.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/TradeRow.jsx` |
| `webapp/frontend/src/components/tradeTable/TradeTablePager.jsx` | `webapp/frontend/src/features/journal/components/tradeTable/TradeTablePager.jsx` |
| `webapp/frontend/src/components/ui/FeedbackHost.jsx` | `webapp/frontend/src/app/components/FeedbackHost.jsx` |
| `webapp/frontend/src/components/ui/HoverGlass.jsx` | `webapp/frontend/src/shared/charts/glance/HoverGlass.jsx` |
| `webapp/frontend/src/components/ui/InstrumentTable.jsx` | `webapp/frontend/src/shared/components/InstrumentTable.jsx` |
| `webapp/frontend/src/components/ui/MetricTile.jsx` | `webapp/frontend/src/features/portfolio/components/MetricTile.jsx` |
| `webapp/frontend/src/components/ui/Modal.jsx` | `webapp/frontend/src/shared/components/Modal.jsx` |
| `webapp/frontend/src/components/ui/Panel.jsx` | `webapp/frontend/src/shared/components/Panel.jsx` |
| `webapp/frontend/src/components/ui/Popover.jsx` | `webapp/frontend/src/features/screener/components/Popover.jsx` |
| `webapp/frontend/src/components/ui/feedback.js` | `webapp/frontend/src/shared/components/feedback.js` |
| `webapp/frontend/src/components/universeSwitcherData.js` | `webapp/frontend/src/shared/presentation/universeSwitcherData.js` |
| `webapp/frontend/src/components/watchlist/WatchlistCardGrid.jsx` | `webapp/frontend/src/features/watchlist/components/WatchlistCardGrid.jsx` |
| `webapp/frontend/src/components/watchlist/WatchlistChartCluster.jsx` | `webapp/frontend/src/features/watchlist/components/WatchlistChartCluster.jsx` |
| `webapp/frontend/src/components/watchlist/WatchlistPage.jsx` | `webapp/frontend/src/features/watchlist/components/WatchlistPage.jsx` |
| `webapp/frontend/src/components/wireVocabulary.js` | `webapp/frontend/src/shared/presentation/wireVocabulary.js` |
| `webapp/frontend/src/components/wireVocabulary.test.js` | `webapp/frontend/src/shared/presentation/wireVocabulary.test.js` |
| `webapp/frontend/src/hooks/screenerStore.js` | `webapp/frontend/src/features/screener/hooks/screenerStore.js` |
| `webapp/frontend/src/hooks/screenerStore.test.js` | `webapp/frontend/src/features/screener/hooks/screenerStore.test.js` |
| `webapp/frontend/src/hooks/useArchiveAddSetup.js` | `webapp/frontend/src/features/archive/hooks/useArchiveAddSetup.js` |
| `webapp/frontend/src/hooks/useArchiveChart.js` | `webapp/frontend/src/features/archive/hooks/useArchiveChart.js` |
| `webapp/frontend/src/hooks/useArchiveData.js` | `webapp/frontend/src/features/archive/hooks/useArchiveData.js` |
| `webapp/frontend/src/hooks/useArchiveGrid.js` | `webapp/frontend/src/features/archive/hooks/useArchiveGrid.js` |
| `webapp/frontend/src/hooks/useArchiveMaintenance.js` | `webapp/frontend/src/features/archive/hooks/useArchiveMaintenance.js` |
| `webapp/frontend/src/hooks/useCalibrationChart.js` | `webapp/frontend/src/features/calibration/hooks/useCalibrationChart.js` |
| `webapp/frontend/src/hooks/useCalibrationMarks.js` | `webapp/frontend/src/features/calibration/hooks/useCalibrationMarks.js` |
| `webapp/frontend/src/hooks/useDailyStructureChart.js` | `webapp/frontend/src/shared/charts/useDailyStructureChart.js` |
| `webapp/frontend/src/hooks/useDashboardData.js` | `webapp/frontend/src/features/journal/hooks/useDashboardData.js` |
| `webapp/frontend/src/hooks/useDrilldown.js` | `webapp/frontend/src/features/screener/hooks/useDrilldown.js` |
| `webapp/frontend/src/hooks/useEdgePulse.js` | `webapp/frontend/src/features/home/hooks/useEdgePulse.js` |
| `webapp/frontend/src/hooks/useEngineRead.js` | `webapp/frontend/src/features/calibration/hooks/useEngineRead.js` |
| `webapp/frontend/src/hooks/useFrameThumb.js` | `webapp/frontend/src/features/calibration/hooks/useFrameThumb.js` |
| `webapp/frontend/src/hooks/useHoverGlance.js` | `webapp/frontend/src/shared/charts/glance/useHoverGlance.js` |
| `webapp/frontend/src/hooks/useIBKRStatus.js` | `webapp/frontend/src/features/ibkr/hooks/useIBKRStatus.js` |
| `webapp/frontend/src/hooks/useIbkrActions.js` | `webapp/frontend/src/features/ibkr/hooks/useIbkrActions.js` |
| `webapp/frontend/src/hooks/useLightweightChart.js` | `webapp/frontend/src/shared/charts/useLightweightChart.js` |
| `webapp/frontend/src/hooks/useLivePrices.js` | `webapp/frontend/src/features/watchlist/hooks/useLivePrices.js` |
| `webapp/frontend/src/hooks/useLiveRisk.js` | `webapp/frontend/src/features/journal/hooks/useLiveRisk.js` |
| `webapp/frontend/src/hooks/useMarkAgreement.js` | `webapp/frontend/src/features/calibration/hooks/useMarkAgreement.js` |
| `webapp/frontend/src/hooks/useMarkFired.js` | `webapp/frontend/src/features/calibration/hooks/useMarkFired.js` |
| `webapp/frontend/src/hooks/usePollingInterval.js` | `webapp/frontend/src/shared/hooks/usePollingInterval.js` |
| `webapp/frontend/src/hooks/usePortfolioSnapshot.js` | `webapp/frontend/src/features/portfolio/hooks/usePortfolioSnapshot.js` |
| `webapp/frontend/src/hooks/usePositionChartData.js` | `webapp/frontend/src/shared/charts/usePositionChartData.js` |
| `webapp/frontend/src/hooks/useReviews.js` | `webapp/frontend/src/features/watchlist/hooks/useReviews.js` |
| `webapp/frontend/src/hooks/useSSE.js` | `webapp/frontend/src/features/portfolio/hooks/useSSE.js` |
| `webapp/frontend/src/hooks/useScanHistory.js` | `webapp/frontend/src/features/screener/hooks/useScanHistory.js` |
| `webapp/frontend/src/hooks/useScanRunner.js` | `webapp/frontend/src/features/screener/hooks/useScanRunner.js` |
| `webapp/frontend/src/hooks/useScreenerData.js` | `webapp/frontend/src/features/screener/hooks/useScreenerData.js` |
| `webapp/frontend/src/hooks/useScreenerFilters.js` | `webapp/frontend/src/features/screener/hooks/useScreenerFilters.js` |
| `webapp/frontend/src/hooks/useTradeCellEditing.js` | `webapp/frontend/src/features/journal/hooks/useTradeCellEditing.js` |
| `webapp/frontend/src/hooks/useTradeFills.js` | `webapp/frontend/src/features/journal/hooks/useTradeFills.js` |
| `webapp/frontend/src/hooks/useTradePlanEditor.js` | `webapp/frontend/src/features/journal/hooks/useTradePlanEditor.js` |
| `webapp/frontend/src/hooks/useTriggerGrade.js` | `webapp/frontend/src/features/calibration/hooks/useTriggerGrade.js` |
| `webapp/frontend/src/hooks/useWatchlist.js` | `webapp/frontend/src/features/watchlist/hooks/useWatchlist.js` |
| `webapp/frontend/src/hooks/useWatchlistCandles.js` | `webapp/frontend/src/features/watchlist/hooks/useWatchlistCandles.js` |
| `webapp/frontend/src/hooks/useWatchlistHistory.js` | `webapp/frontend/src/features/watchlist/hooks/useWatchlistHistory.js` |
| `webapp/frontend/src/hooks/useWatchlistRecords.js` | `webapp/frontend/src/features/watchlist/hooks/useWatchlistRecords.js` |
| `webapp/frontend/src/hooks/watchlistCandlesStore.js` | `webapp/frontend/src/features/watchlist/hooks/watchlistCandlesStore.js` |
| `webapp/frontend/src/hooks/watchlistCandlesStore.test.js` | `webapp/frontend/src/features/watchlist/hooks/watchlistCandlesStore.test.js` |
| `webapp/frontend/src/hooks/watchlistStore.js` | `webapp/frontend/src/features/watchlist/hooks/watchlistStore.js` |
| `webapp/frontend/src/routes/ArchiveRoute.jsx` | `webapp/frontend/src/features/archive/ArchiveRoute.jsx` |
| `webapp/frontend/src/routes/CalibrationRoute.jsx` | `webapp/frontend/src/features/calibration/CalibrationRoute.jsx` |
| `webapp/frontend/src/routes/DashboardRoute.jsx` | `webapp/frontend/src/features/journal/DashboardRoute.jsx` |
| `webapp/frontend/src/routes/HomeRoute.jsx` | `webapp/frontend/src/features/home/HomeRoute.jsx` |
| `webapp/frontend/src/routes/LoadingPanel.jsx` | `webapp/frontend/src/shared/components/LoadingPanel.jsx` |
| `webapp/frontend/src/routes/OptionsRoute.jsx` | `webapp/frontend/src/features/options/OptionsRoute.jsx` |
| `webapp/frontend/src/routes/PortfolioRoute.jsx` | `webapp/frontend/src/features/portfolio/PortfolioRoute.jsx` |
| `webapp/frontend/src/routes/ScreenerRoute.jsx` | `webapp/frontend/src/features/screener/ScreenerRoute.jsx` |
| `webapp/frontend/src/routes/WatchlistRoute.jsx` | `webapp/frontend/src/features/watchlist/WatchlistRoute.jsx` |
| `webapp/frontend/src/theme.js` | `webapp/frontend/src/shared/presentation/theme.js` |
| `webapp/frontend/src/utils/actionCenterState.js` | `webapp/frontend/src/features/home/presentation/actionCenterState.js` |
| `webapp/frontend/src/utils/actionCenterState.test.js` | `webapp/frontend/src/features/home/presentation/actionCenterState.test.js` |
| `webapp/frontend/src/utils/alertMuting.js` | `webapp/frontend/src/features/journal/model/alertMuting.js` |
| `webapp/frontend/src/utils/alertMuting.test.js` | `webapp/frontend/src/features/journal/model/alertMuting.test.js` |
| `webapp/frontend/src/utils/appFormat.js` | `webapp/frontend/src/shared/formatting/appFormat.js` |
| `webapp/frontend/src/utils/appFormat.test.js` | `webapp/frontend/src/shared/formatting/appFormat.test.js` |
| `webapp/frontend/src/utils/archiveTabUtils.js` | `webapp/frontend/src/features/archive/presentation/archiveTabUtils.js` |
| `webapp/frontend/src/utils/calibrationChartUtils.js` | `webapp/frontend/src/features/calibration/model/calibrationChartUtils.js` |
| `webapp/frontend/src/utils/calibrationChartUtils.test.js` | `webapp/frontend/src/features/calibration/model/calibrationChartUtils.test.js` |
| `webapp/frontend/src/utils/calibrationMarking.js` | `webapp/frontend/src/features/calibration/model/calibrationMarking.js` |
| `webapp/frontend/src/utils/calibrationMarking.remark.test.js` | `webapp/frontend/src/features/calibration/model/calibrationMarking.remark.test.js` |
| `webapp/frontend/src/utils/calibrationMarking.test.js` | `webapp/frontend/src/features/calibration/model/calibrationMarking.test.js` |
| `webapp/frontend/src/utils/calibrationTables.js` | `webapp/frontend/src/features/calibration/model/calibrationTables.js` |
| `webapp/frontend/src/utils/calibrationTables.test.js` | `webapp/frontend/src/features/calibration/model/calibrationTables.test.js` |
| `webapp/frontend/src/utils/format.js` | `webapp/frontend/src/shared/formatting/format.js` |
| `webapp/frontend/src/utils/format.test.js` | `webapp/frontend/src/shared/formatting/format.test.js` |
| `webapp/frontend/src/utils/frameThumb.js` | `webapp/frontend/src/features/calibration/model/frameThumb.js` |
| `webapp/frontend/src/utils/frameThumb.test.js` | `webapp/frontend/src/features/calibration/model/frameThumb.test.js` |
| `webapp/frontend/src/utils/inkContrast.test.js` | `webapp/frontend/src/app/appearance/inkContrast.test.js` |
| `webapp/frontend/src/utils/leaveGuard.js` | `webapp/frontend/src/shared/navigation/leaveGuard.js` |
| `webapp/frontend/src/utils/leaveGuard.test.js` | `webapp/frontend/src/shared/navigation/leaveGuard.test.js` |
| `webapp/frontend/src/utils/portfolioPlanUtils.js` | `webapp/frontend/src/features/portfolio/model/portfolioPlanUtils.js` |
| `webapp/frontend/src/utils/portfolioPlanUtils.test.js` | `webapp/frontend/src/features/portfolio/model/portfolioPlanUtils.test.js` |
| `webapp/frontend/src/utils/scanStream.js` | `webapp/frontend/src/features/screener/api/scanStream.js` |
| `webapp/frontend/src/utils/scanStream.test.js` | `webapp/frontend/src/features/screener/api/scanStream.test.js` |
| `webapp/frontend/src/utils/scoreFormat.js` | `webapp/frontend/src/shared/formatting/scoreFormat.js` |
| `webapp/frontend/src/utils/scoreFormat.test.js` | `webapp/frontend/src/shared/formatting/scoreFormat.test.js` |
| `webapp/frontend/src/utils/screenerCardData.js` | `webapp/frontend/src/shared/setup/screenerCardData.js` |
| `webapp/frontend/src/utils/tradeDetailFormat.js` | `webapp/frontend/src/features/journal/presentation/tradeDetailFormat.js` |
| `webapp/frontend/src/utils/tradeTableUtils.js` | `webapp/frontend/src/features/journal/model/tradeTableUtils.js` |
| `webapp/frontend/src/utils/tradeTableUtils.test.js` | `webapp/frontend/src/features/journal/model/tradeTableUtils.test.js` |
| `webapp/frontend/src/utils/tradeUtils.js` | `webapp/frontend/src/features/journal/model/tradeUtils.js` |
| `webapp/frontend/src/utils/triggerProximity.js` | `webapp/frontend/src/shared/setup/triggerProximity.js` |
| `webapp/frontend/src/utils/uiScale.js` | `webapp/frontend/src/app/appearance/uiScale.js` |
| `webapp/frontend/src/utils/uiScale.test.js` | `webapp/frontend/src/app/appearance/uiScale.test.js` |
| `webapp/frontend/src/utils/watchlistChartData.js` | `webapp/frontend/src/features/watchlist/presentation/watchlistChartData.js` |
| `webapp/frontend/src/utils/watchlistChartData.test.js` | `webapp/frontend/src/features/watchlist/presentation/watchlistChartData.test.js` |
| `webapp/frontend/src/utils/watchlistTable.js` | `webapp/frontend/src/features/watchlist/presentation/watchlistTable.js` |
| `webapp/frontend/src/utils/watchlistTable.test.js` | `webapp/frontend/src/features/watchlist/presentation/watchlistTable.test.js` |

### Tests

| Old path | New path |
|---|---|
| `tests/test_advisory_wiring.py` | `tests/pipeline/test_advisory_wiring.py` |
| `tests/test_agreement.py` | `tests/tooling/test_agreement.py` |
| `tests/test_analyze_anchor_seam.py` | `tests/archive/test_analyze_anchor_seam.py` |
| `tests/test_analyze_dedup.py` | `tests/archive/test_analyze_dedup.py` |
| `tests/test_analyze_reporter_gates.py` | `tests/archive/test_analyze_reporter_gates.py` |
| `tests/test_archive_actions_guard.py` | `tests/backend/test_archive_actions_guard.py` |
| `tests/test_archive_column_parity.py` | `tests/archive/test_archive_column_parity.py` |
| `tests/test_archive_feed_completeness.py` | `tests/archive/test_archive_feed_completeness.py` |
| `tests/test_archive_glance_window.py` | `tests/backend/test_archive_glance_window.py` |
| `tests/test_archive_purge.py` | `tests/archive/test_archive_purge.py` |
| `tests/test_archive_reliability.py` | `tests/backend/test_archive_reliability.py` |
| `tests/test_archive_row_assembly.py` | `tests/archive/test_archive_row_assembly.py` |
| `tests/test_archive_version_scope.py` | `tests/backend/test_archive_version_scope.py` |
| `tests/test_backend_services.py` | `tests/backend/test_backend_services.py` |
| `tests/test_backtest_engine.py` | `tests/tooling/test_backtest_engine.py` |
| `tests/test_bricks.py` | `tests/engine/test_bricks.py` |
| `tests/test_build_universe_returns.py` | `tests/tooling/test_build_universe_returns.py` |
| `tests/test_calibration_harness.py` | `tests/tooling/test_calibration_harness.py` |
| `tests/test_calibration_marks_schema.py` | `tests/backend/test_calibration_marks_schema.py` |
| `tests/test_calibration_router.py` | `tests/backend/test_calibration_router.py` |
| `tests/test_candle_cache.py` | `tests/backend/test_candle_cache.py` |
| `tests/test_candle_parity.py` | `tests/market_data/test_candle_parity.py` |
| `tests/test_candles_router.py` | `tests/backend/test_candles_router.py` |
| `tests/test_cause_veto_bite.py` | `tests/regression/test_cause_veto_bite.py` |
| `tests/test_chain.py` | `tests/engine/test_chain.py` |
| `tests/test_charter_measurements.py` | `tests/engine/test_charter_measurements.py` |
| `tests/test_concordance.py` | `tests/backend/test_concordance.py` |
| `tests/test_core_logic.py` | `tests/engine/test_core_logic.py` |
| `tests/test_csv_import.py` | `tests/backend/test_csv_import.py` |
| `tests/test_dashboard_wire.py` | `tests/contracts/test_dashboard_wire.py` |
| `tests/test_data_freshness.py` | `tests/market_data/test_data_freshness.py` |
| `tests/test_db_isolation.py` | `tests/integration/test_db_isolation.py` |
| `tests/test_displacement.py` | `tests/engine/test_displacement.py` |
| `tests/test_docs_sync.py` | `tests/tooling/test_docs_sync.py` |
| `tests/test_doctrine_audit.py` | `tests/tooling/test_doctrine_audit.py` |
| `tests/test_download_integrity.py` | `tests/market_data/test_download_integrity.py` |
| `tests/test_election_stability.py` | `tests/engine/test_election_stability.py` |
| `tests/test_election_surgery.py` | `tests/engine/test_election_surgery.py` |
| `tests/test_engine_alpha_runtime.py` | `tests/integration/test_engine_alpha_runtime.py` |
| `tests/test_episode_cache.py` | `tests/backend/test_episode_cache.py` |
| `tests/test_episodes.py` | `tests/archive/test_episodes.py` |
| `tests/test_eval_error_counter.py` | `tests/pipeline/test_eval_error_counter.py` |
| `tests/test_event_map.py` | `tests/engine/test_event_map.py` |
| `tests/test_event_vocabulary.py` | `tests/engine/test_event_vocabulary.py` |
| `tests/test_fetch_health.py` | `tests/market_data/test_fetch_health.py` |
| `tests/test_fetch_repair.py` | `tests/market_data/test_fetch_repair.py` |
| `tests/test_file_lock.py` | `tests/market_data/test_file_lock.py` |
| `tests/test_fired_tags.py` | `tests/scoring/test_fired_tags.py` |
| `tests/test_first_legal_look.py` | `tests/engine/test_first_legal_look.py` |
| `tests/test_fold_parity.py` | `tests/tooling/test_fold_parity.py` |
| `tests/test_frame_store.py` | `tests/backend/test_frame_store.py` |
| `tests/test_framing_identity.py` | `tests/engine/test_framing_identity.py` |
| `tests/test_fundamentals_metrics.py` | `tests/pipeline/test_fundamentals_metrics.py` |
| `tests/test_fundamentals_post_pass.py` | `tests/pipeline/test_fundamentals_post_pass.py` |
| `tests/test_fundamentals_provider.py` | `tests/market_data/test_fundamentals_provider.py` |
| `tests/test_gate_leg_registry.py` | `tests/engine/test_gate_leg_registry.py` |
| `tests/test_gate_margins.py` | `tests/engine/test_gate_margins.py` |
| `tests/test_grading_frame.py` | `tests/backend/test_grading_frame.py` |
| `tests/test_guards.py` | `tests/integration/test_guards.py` |
| `tests/test_handler_concurrency_shape.py` | `tests/backend/test_handler_concurrency_shape.py` |
| `tests/test_health_board.py` | `tests/pipeline/test_health_board.py` |
| `tests/test_htf.py` | `tests/engine/test_htf.py` |
| `tests/test_ibkr_hardening.py` | `tests/backend/test_ibkr_hardening.py` |
| `tests/test_inner_position_archive.py` | `tests/archive/test_inner_position_archive.py` |
| `tests/test_invariants.py` | `tests/engine/test_invariants.py` |
| `tests/test_loader_universe_filter.py` | `tests/archive/test_loader_universe_filter.py` |
| `tests/test_log_encoding.py` | `tests/backend/test_log_encoding.py` |
| `tests/test_lps.py` | `tests/engine/test_lps.py` |
| `tests/test_lps_two_form_guards.py` | `tests/engine/test_lps_two_form_guards.py` |
| `tests/test_manual_add_universe_stamp.py` | `tests/archive/test_manual_add_universe_stamp.py` |
| `tests/test_market_context_universe.py` | `tests/pipeline/test_market_context_universe.py` |
| `tests/test_market_data_cache.py` | `tests/backend/test_market_data_cache.py` |
| `tests/test_market_data_health.py` | `tests/market_data/test_market_data_health.py` |
| `tests/test_market_data_service.py` | `tests/backend/test_market_data_service.py` |
| `tests/test_market_structure.py` | `tests/engine/test_market_structure.py` |
| `tests/test_marks_corpus.py` | `tests/regression/test_marks_corpus.py` |
| `tests/test_marks_json.py` | `tests/tooling/test_marks_json.py` |
| `tests/test_marks_validity.py` | `tests/contracts/test_marks_validity.py` |
| `tests/test_mini_consolidation_position.py` | `tests/engine/test_mini_consolidation_position.py` |
| `tests/test_miss_program_lanes.py` | `tests/engine/test_miss_program_lanes.py` |
| `tests/test_missed_winners.py` | `tests/archive/test_missed_winners.py` |
| `tests/test_narrative.py` | `tests/engine/test_narrative.py` |
| `tests/test_narrative_surface_guards.py` | `tests/engine/test_narrative_surface_guards.py` |
| `tests/test_near_miss_archive.py` | `tests/archive/test_near_miss_archive.py` |
| `tests/test_near_miss_deferred.py` | `tests/pipeline/test_near_miss_deferred.py` |
| `tests/test_near_miss_guards.py` | `tests/engine/test_near_miss_guards.py` |
| `tests/test_near_miss_identity_migration.py` | `tests/backend/test_near_miss_identity_migration.py` |
| `tests/test_near_miss_outcomes.py` | `tests/archive/test_near_miss_outcomes.py` |
| `tests/test_near_miss_report.py` | `tests/tooling/test_near_miss_report.py` |
| `tests/test_near_miss_ruling.py` | `tests/engine/test_near_miss_ruling.py` |
| `tests/test_near_miss_wiring.py` | `tests/pipeline/test_near_miss_wiring.py` |
| `tests/test_negative_corpus.py` | `tests/regression/test_negative_corpus.py` |
| `tests/test_outcomes.py` | `tests/archive/test_outcomes.py` |
| `tests/test_phase_a.py` | `tests/engine/test_phase_a.py` |
| `tests/test_phase_bins.py` | `tests/engine/test_phase_bins.py` |
| `tests/test_pointer_audit.py` | `tests/tooling/test_pointer_audit.py` |
| `tests/test_portfolio_stream_lifecycle.py` | `tests/backend/test_portfolio_stream_lifecycle.py` |
| `tests/test_power_play_acceptance.py` | `tests/regression/test_power_play_acceptance.py` |
| `tests/test_power_play_archive.py` | `tests/archive/test_power_play_archive.py` |
| `tests/test_power_play_census.py` | `tests/tooling/test_power_play_census.py` |
| `tests/test_power_play_lane.py` | `tests/engine/test_power_play_lane.py` |
| `tests/test_power_play_preset.py` | `tests/engine/test_power_play_preset.py` |
| `tests/test_power_play_sheets.py` | `tests/tooling/test_power_play_sheets.py` |
| `tests/test_price_regime.py` | `tests/pipeline/test_price_regime.py` |
| `tests/test_price_scale_unknown.py` | `tests/archive/test_price_scale_unknown.py` |
| `tests/test_provider_capabilities.py` | `tests/market_data/test_provider_capabilities.py` |
| `tests/test_provider_parity.py` | `tests/tooling/test_provider_parity.py` |
| `tests/test_providers.py` | `tests/market_data/test_providers.py` |
| `tests/test_rail_margin_evidence.py` | `tests/tooling/test_rail_margin_evidence.py` |
| `tests/test_rail_qualification.py` | `tests/engine/test_rail_qualification.py` |
| `tests/test_rate_limit.py` | `tests/market_data/test_rate_limit.py` |
| `tests/test_reader_pin.py` | `tests/regression/test_reader_pin.py` |
| `tests/test_recovery_view.py` | `tests/engine/test_recovery_view.py` |
| `tests/test_refusal_telemetry.py` | `tests/engine/test_refusal_telemetry.py` |
| `tests/test_regime_primitives.py` | `tests/pipeline/test_regime_primitives.py` |
| `tests/test_regression_guards.py` | `tests/regression/test_regression_guards.py` |
| `tests/test_replay_layer.py` | `tests/tooling/test_replay_layer.py` |
| `tests/test_request_logging.py` | `tests/backend/test_request_logging.py` |
| `tests/test_resistance_contraction.py` | `tests/engine/test_resistance_contraction.py` |
| `tests/test_result_adapter.py` | `tests/archive/test_result_adapter.py` |
| `tests/test_same_app_guard.py` | `tests/backend/test_same_app_guard.py` |
| `tests/test_scan_diagnosis.py` | `tests/backend/test_scan_diagnosis.py` |
| `tests/test_scan_metrics.py` | `tests/pipeline/test_scan_metrics.py` |
| `tests/test_scan_status.py` | `tests/backend/test_scan_status.py` |
| `tests/test_scheduler_misfire.py` | `tests/backend/test_scheduler_misfire.py` |
| `tests/test_scope_phase_d.py` | `tests/engine/test_scope_phase_d.py` |
| `tests/test_score_taxonomy.py` | `tests/scoring/test_score_taxonomy.py` |
| `tests/test_scoring.py` | `tests/scoring/test_scoring.py` |
| `tests/test_seed_force_curation.py` | `tests/archive/test_seed_force_curation.py` |
| `tests/test_seed_recall.py` | `tests/regression/test_seed_recall.py` |
| `tests/test_seed_recall_hermetic.py` | `tests/regression/test_seed_recall_hermetic.py` |
| `tests/test_seeding_refusals.py` | `tests/engine/test_seeding_refusals.py` |
| `tests/test_service_boot.py` | `tests/backend/test_service_boot.py` |
| `tests/test_setup_like_verdict.py` | `tests/backend/test_setup_like_verdict.py` |
| `tests/test_shelf_harness.py` | `tests/tooling/test_shelf_harness.py` |
| `tests/test_startup_migrations.py` | `tests/backend/test_startup_migrations.py` |
| `tests/test_story_chain_candidates.py` | `tests/tooling/test_story_chain_candidates.py` |
| `tests/test_story_pool.py` | `tests/engine/test_story_pool.py` |
| `tests/test_story_pool_guards.py` | `tests/engine/test_story_pool_guards.py` |
| `tests/test_strategy_read.py` | `tests/engine/test_strategy_read.py` |
| `tests/test_suggested_weights.py` | `tests/archive/test_suggested_weights.py` |
| `tests/test_ta_grade_archive_replay.py` | `tests/tooling/test_ta_grade_archive_replay.py` |
| `tests/test_ta_grade_cascade.py` | `tests/scoring/test_ta_grade_cascade.py` |
| `tests/test_ticker_admission.py` | `tests/pipeline/test_ticker_admission.py` |
| `tests/test_tickers.py` | `tests/pipeline/test_tickers.py` |
| `tests/test_tool_sealed_guards.py` | `tests/tooling/test_tool_sealed_guards.py` |
| `tests/test_trace_export.py` | `tests/engine/test_trace_export.py` |
| `tests/test_trade_risk.py` | `tests/contracts/test_trade_risk.py` |
| `tests/test_trend_state.py` | `tests/engine/test_trend_state.py` |
| `tests/test_trend_terminal_floor.py` | `tests/engine/test_trend_terminal_floor.py` |
| `tests/test_trigger_grade_spec.py` | `tests/backend/test_trigger_grade_spec.py` |
| `tests/test_universe_descriptor.py` | `tests/pipeline/test_universe_descriptor.py` |
| `tests/test_universe_migration.py` | `tests/backend/test_universe_migration.py` |
| `tests/test_universe_scope_invariant.py` | `tests/archive/test_universe_scope_invariant.py` |
| `tests/test_upload_handlers.py` | `tests/backend/test_upload_handlers.py` |
| `tests/test_watchlist_migration.py` | `tests/backend/test_watchlist_migration.py` |
| `tests/test_watchlist_router.py` | `tests/backend/test_watchlist_router.py` |

### Tools

| Old path | New path |
|---|---|
| `tools/ChrolloBackup.ps1` | `tools/ops/ChrolloBackup.ps1` |
| `tools/agreement.py` | `tools/calibration/agreement.py` |
| `tools/backtest_engine.py` | `tools/research/backtest_engine.py` |
| `tools/bar_state_census.py` | `tools/research/bar_state_census.py` |
| `tools/build_universe_returns.py` | `tools/research/build_universe_returns.py` |
| `tools/calibration_harness.py` | `tools/calibration/calibration_harness.py` |
| `tools/calibration_stat_card.py` | `tools/calibration/calibration_stat_card.py` |
| `tools/cause_veto_corpus.py` | `tools/regression/cause_veto_corpus.py` |
| `tools/chart_framing_census.mjs` | `tools/research/chart_framing_census.mjs` |
| `tools/correspondence_census.py` | `tools/research/correspondence_census.py` |
| `tools/doctrine_audit.py` | `tools/audits/doctrine_audit.py` |
| `tools/event_map_census.py` | `tools/research/event_map_census.py` |
| `tools/event_map_chronology.py` | `tools/audits/event_map_chronology.py` |
| `tools/fold_parity.py` | `tools/regression/fold_parity.py` |
| `tools/full_package_render.py` | `tools/research/full_package_render.py` |
| `tools/guided_list_export.py` | `tools/calibration/guided_list_export.py` |
| `tools/htf_audit.py` | `tools/audits/htf_audit.py` |
| `tools/marks_corpus.py` | `tools/regression/marks_corpus.py` |
| `tools/marks_json.py` | `tools/calibration/marks_json.py` |
| `tools/miss_lane_census.py` | `tools/research/miss_lane_census.py` |
| `tools/near_miss_census.py` | `tools/research/near_miss_census.py` |
| `tools/near_miss_report.py` | `tools/research/near_miss_report.py` |
| `tools/negative_corpus.py` | `tools/regression/negative_corpus.py` |
| `tools/operator_marks_diff.py` | `tools/research/operator_marks_diff.py` |
| `tools/pointer_audit.py` | `tools/audits/pointer_audit.py` |
| `tools/power_play_census.py` | `tools/research/power_play_census.py` |
| `tools/power_play_fixture.py` | `tools/regression/power_play_fixture.py` |
| `tools/power_play_sheets.py` | `tools/research/power_play_sheets.py` |
| `tools/provider_parity.py` | `tools/audits/provider_parity.py` |
| `tools/rail_area_census.py` | `tools/research/rail_area_census.py` |
| `tools/rail_margin_ab.py` | `tools/research/rail_margin_ab.py` |
| `tools/rail_margin_evidence.py` | `tools/research/rail_margin_evidence.py` |
| `tools/reader_pin.py` | `tools/regression/reader_pin.py` |
| `tools/recover_service_python.bat` | `tools/ops/recover_service_python.bat` |
| `tools/recover_service_python.ps1` | `tools/ops/recover_service_python.ps1` |
| `tools/replay.py` | `tools/calibration/replay.py` |
| `tools/restore_drill.py` | `tools/ops/restore_drill.py` |
| `tools/settings_reference.py` | `tools/maintenance/settings_reference.py` |
| `tools/shadow_diff.py` | `tools/regression/shadow_diff.py` |
| `tools/shape_profile.py` | `tools/research/shape_profile.py` |
| `tools/shelf_harness.py` | `tools/calibration/shelf_harness.py` |
| `tools/story_chain_candidates.py` | `tools/research/story_chain_candidates.py` |
| `tools/structure_case_audit.py` | `tools/audits/structure_case_audit.py` |
| `tools/ta_grade_archive_replay.py` | `tools/research/ta_grade_archive_replay.py` |
| `tools/ta_grade_timing.py` | `tools/audits/ta_grade_timing.py` |

### Research evidence (to `research/`)

| Old path | New path |
|---|---|
| `output/bar_state_census_2026-08-30.json` | `research/evidence/bar_state_census_2026-08-30.json` |
| `output/miss_lane_census_2026-08-28.json` | `research/evidence/miss_lane_census_2026-08-28.json` |
| `output/miss_lane_census_2026-08-29.json` | `research/evidence/miss_lane_census_2026-08-29.json` |
| `output/rail_area_census_2026-08-30.json` | `research/evidence/rail_area_census_2026-08-30.json` |
| `output/shape_profile_2026-08-29.json` | `research/evidence/shape_profile_2026-08-29.json` |
| `output/trend_terminal_ab_2026-08-31.json` | `research/evidence/trend_terminal_ab_2026-08-31.json` |
| `tools/fidelity/ar_first_reaction_2026-08-13/README.md` | `research/fidelity/ar_first_reaction_2026-08-13/README.md` |
| `tools/fidelity/ar_first_reaction_2026-08-13/scan_2026-08-13.txt` | `research/fidelity/ar_first_reaction_2026-08-13/scan_2026-08-13.txt` |
| `tools/fidelity/ar_first_reaction_2026-08-31/rekey_isolation.json` | `research/fidelity/ar_first_reaction_2026-08-31/rekey_isolation.json` |
| `tools/fidelity/ar_first_reaction_2026-08-31/rekey_isolation.py` | `research/fidelity/ar_first_reaction_2026-08-31/rekey_isolation.py` |
| `tools/fidelity/ar_first_reaction_2026-08-31/scan_2026-08-31.txt` | `research/fidelity/ar_first_reaction_2026-08-31/scan_2026-08-31.txt` |
| `tools/fidelity/box_backext/BKH.png` | `research/fidelity/box_backext/BKH.png` |
| `tools/fidelity/box_backext/BYD.png` | `research/fidelity/box_backext/BYD.png` |
| `tools/fidelity/box_backext/CNP.png` | `research/fidelity/box_backext/CNP.png` |
| `tools/fidelity/box_backext/EMA.png` | `research/fidelity/box_backext/EMA.png` |
| `tools/fidelity/box_backext/FELE.png` | `research/fidelity/box_backext/FELE.png` |
| `tools/fidelity/box_backext/GCV.png` | `research/fidelity/box_backext/GCV.png` |
| `tools/fidelity/box_backext/HR.png` | `research/fidelity/box_backext/HR.png` |
| `tools/fidelity/box_backext/INMD.png` | `research/fidelity/box_backext/INMD.png` |
| `tools/fidelity/box_backext/LOVE.png` | `research/fidelity/box_backext/LOVE.png` |
| `tools/fidelity/box_backext/MLAB.png` | `research/fidelity/box_backext/MLAB.png` |
| `tools/fidelity/box_backext/MTG.png` | `research/fidelity/box_backext/MTG.png` |
| `tools/fidelity/box_backext/MXF.png` | `research/fidelity/box_backext/MXF.png` |
| `tools/fidelity/box_backext/ab_log.txt` | `research/fidelity/box_backext/ab_log.txt` |
| `tools/fidelity/full_package/LOSSES.md` | `research/fidelity/full_package/LOSSES.md` |
| `tools/fidelity/full_package/index.html` | `research/fidelity/full_package/index.html` |
| `tools/fidelity/pip_phase_a/AGCO.png` | `research/fidelity/pip_phase_a/AGCO.png` |
| `tools/fidelity/pip_phase_a/ATI.png` | `research/fidelity/pip_phase_a/ATI.png` |
| `tools/fidelity/pip_phase_a/AXTA.png` | `research/fidelity/pip_phase_a/AXTA.png` |
| `tools/fidelity/pip_phase_a/BCH.png` | `research/fidelity/pip_phase_a/BCH.png` |
| `tools/fidelity/pip_phase_a/BSAC.png` | `research/fidelity/pip_phase_a/BSAC.png` |
| `tools/fidelity/pip_phase_a/BYD.png` | `research/fidelity/pip_phase_a/BYD.png` |
| `tools/fidelity/pip_phase_a/GOOD.png` | `research/fidelity/pip_phase_a/GOOD.png` |
| `tools/fidelity/pip_phase_a/MO.png` | `research/fidelity/pip_phase_a/MO.png` |
| `tools/fidelity/pip_phase_a/MPLX.png` | `research/fidelity/pip_phase_a/MPLX.png` |
| `tools/fidelity/pip_phase_a/MTRX.png` | `research/fidelity/pip_phase_a/MTRX.png` |
| `tools/fidelity/pip_phase_a/PH.png` | `research/fidelity/pip_phase_a/PH.png` |
| `tools/fidelity/pip_phase_a/POCI.png` | `research/fidelity/pip_phase_a/POCI.png` |
| `tools/fidelity/pip_phase_a/SABS.png` | `research/fidelity/pip_phase_a/SABS.png` |
| `tools/fidelity/pip_phase_a/SAFE.png` | `research/fidelity/pip_phase_a/SAFE.png` |
| `tools/fidelity/pip_phase_a/TFX.png` | `research/fidelity/pip_phase_a/TFX.png` |
| `tools/fidelity/pip_phase_a/TNC.png` | `research/fidelity/pip_phase_a/TNC.png` |
| `tools/fidelity/pip_phase_a/WFG.png` | `research/fidelity/pip_phase_a/WFG.png` |
| `tools/fidelity/trend_terminal_2026-08-13/APH.png` | `research/fidelity/trend_terminal_2026-08-13/APH.png` |
| `tools/fidelity/trend_terminal_2026-08-13/AWR.png` | `research/fidelity/trend_terminal_2026-08-13/AWR.png` |
| `tools/fidelity/trend_terminal_2026-08-13/BALL.png` | `research/fidelity/trend_terminal_2026-08-13/BALL.png` |
| `tools/fidelity/trend_terminal_2026-08-13/BCS.png` | `research/fidelity/trend_terminal_2026-08-13/BCS.png` |
| `tools/fidelity/trend_terminal_2026-08-13/BMRC.png` | `research/fidelity/trend_terminal_2026-08-13/BMRC.png` |
| `tools/fidelity/trend_terminal_2026-08-13/CDP.png` | `research/fidelity/trend_terminal_2026-08-13/CDP.png` |
| `tools/fidelity/trend_terminal_2026-08-13/CNI.png` | `research/fidelity/trend_terminal_2026-08-13/CNI.png` |
| `tools/fidelity/trend_terminal_2026-08-13/CWT.png` | `research/fidelity/trend_terminal_2026-08-13/CWT.png` |
| `tools/fidelity/trend_terminal_2026-08-13/DIN.png` | `research/fidelity/trend_terminal_2026-08-13/DIN.png` |
| `tools/fidelity/trend_terminal_2026-08-13/EVER.png` | `research/fidelity/trend_terminal_2026-08-13/EVER.png` |
| `tools/fidelity/trend_terminal_2026-08-13/IMO.png` | `research/fidelity/trend_terminal_2026-08-13/IMO.png` |
| `tools/fidelity/trend_terminal_2026-08-13/KMX.png` | `research/fidelity/trend_terminal_2026-08-13/KMX.png` |
| `tools/fidelity/trend_terminal_2026-08-13/KN.png` | `research/fidelity/trend_terminal_2026-08-13/KN.png` |
| `tools/fidelity/trend_terminal_2026-08-13/LOSSES.md` | `research/fidelity/trend_terminal_2026-08-13/LOSSES.md` |
| `tools/fidelity/trend_terminal_2026-08-13/NAT.png` | `research/fidelity/trend_terminal_2026-08-13/NAT.png` |
| `tools/fidelity/trend_terminal_2026-08-13/NPO.png` | `research/fidelity/trend_terminal_2026-08-13/NPO.png` |
| `tools/fidelity/trend_terminal_2026-08-13/OSK.png` | `research/fidelity/trend_terminal_2026-08-13/OSK.png` |
| `tools/fidelity/trend_terminal_2026-08-13/SNA.png` | `research/fidelity/trend_terminal_2026-08-13/SNA.png` |
| `tools/fidelity/trend_terminal_2026-08-13/SXC.png` | `research/fidelity/trend_terminal_2026-08-13/SXC.png` |
| `tools/fidelity/trend_terminal_2026-08-13/TFIN.png` | `research/fidelity/trend_terminal_2026-08-13/TFIN.png` |
| `tools/fidelity/trend_terminal_2026-08-13/UTL.png` | `research/fidelity/trend_terminal_2026-08-13/UTL.png` |
| `tools/fidelity/trend_terminal_2026-08-13/WFC.png` | `research/fidelity/trend_terminal_2026-08-13/WFC.png` |
| `tools/fidelity/trend_terminal_2026-08-13/XOM.png` | `research/fidelity/trend_terminal_2026-08-13/XOM.png` |
| `tools/fidelity/trend_terminal_2026-08-13/index.html` | `research/fidelity/trend_terminal_2026-08-13/index.html` |
