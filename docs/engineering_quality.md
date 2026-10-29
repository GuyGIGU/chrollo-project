# Engineering quality gates

The first engineering-quality increment protects the current app while larger
startup and archive-storage refactors remain separate work. It adds a fast
`contracts` CI job and browser checks to the existing `frontend` job. Existing
Python, Windows and engine acceptance jobs retain their own responsibilities.

## Python checks

`ruff.toml` checks production Python, configuration and tools for syntax errors,
undefined names and invalid control-flow constructs (`E9`, `F63`, `F7`, `F82`).
It does not impose a formatting migration. One existing unresolved `pd` string
annotation in the frozen legacy box reader is explicitly excepted; the existing
frozen-engine hash test still guards that file.

`mypy.ini` enables strict typing on the pure screener response schemas. This is
an initial boundary, not a claim that the whole Python codebase is typed.
Ruff and mypy are pinned in `requirements-dev.txt`; they are development tools,
not runtime dependencies. CI installs these alongside the constrained runtime.

## API contracts

The backend's Pydantic models are authoritative. The screener's core metadata
is validated on each data response without reserializing the artifact, dropping
extra engine facts or inventing missing measurements in older scans. Numeric
metadata must be finite numbers; nullable measurements stay nullable. Candle
arrays are checked only as containers here: existing chart-wire tests own the
detailed bar contract, avoiding another deep parse of every price history.

The feedback GET now declares its existing four-field response model. Archive
setup rows and watchlist items use their existing response models. Run:

```powershell
.\.venv\Scripts\python.exe -m tools.audits.api_contracts --write
.\.venv\Scripts\python.exe -m tools.audits.api_contracts --check
```

The exporter writes only `webapp/frontend/src/api/contracts.schema.json` and
`contracts.js` (JSDoc types, consumed by the screener store). It does not import
the app, initialize a database, start the scheduler or contact market data.
`--check` fails on drift and never rewrites the generated files. Update the
Python model first and regenerate in the same change.

Contract tests check both scan producers and serve the actual router through an in-process HTTP scope without
a backend listener or lifespan. They also validate the browser suite's shared
synthetic JSON fixture, check additive/legacy compatibility and reject malformed
core metadata. The exporter has a subprocess test that refuses SQLite connects.

## Browser checks

Playwright loads the production Vite bundle using the frontend preview server.
All API responses are explicitly mocked; unexpected requests and uncaught UI
errors fail the test. The public font stylesheet is stubbed. No backend, scan,
archive write or broker connection runs. Every browser test has isolated mock
state, and the suite covers:

- Search, tier filtering, base-age sorting, chart stepping, keyboard close and URL reload.
- Read/grade feedback, reload persistence, failed-save rollback and old-engine feedback.
- Watchlist persistence and the displayed scan identity sent on save.
- An initial screener request failure with a readable empty state.
- The Liked shortlist, visible query controls, removal/reset and reload persistence.
- Likes-load and cached-refresh failures, explicit retries and saved-chart retention.
- Failed heart/star writes, rapid-click protection, top paging and narrow layouts.

These checks verify the rendered frontend and its request behavior; they do not
replace real database integration tests or engine acceptance corpora. The data
in `webapp/frontend/e2e/fixtures/` is synthetic UI data, not calibration evidence.

In a worktree, after installing the locked frontend dependencies:

```powershell
npm --prefix webapp/frontend exec -- playwright install chromium
npm --prefix webapp/frontend run build
npm --prefix webapp/frontend run test:e2e
```

An installed Edge can be selected locally with
`$env:PLAYWRIGHT_CHANNEL='msedge'`. CI uses Playwright's Chromium. CI retains
the HTML report, screenshots and traces for seven days on a failure. Open a
local report with
`npm --prefix webapp/frontend exec -- playwright show-report webapp/frontend/playwright-report`.
The preview server exits with the suite and never replaces the live service.

The screener pass also checks that a card is one size (460px) at 2560, 1920 and
1024 with no table view, and keyboard/lens focus over the card grid.
The Watchlist cases cover the ticker ledger, immediate quote loading, search/sort,
row inspection and candle retry, saved replay, removal/undo and keyboard actions.
The frontend ownership guard covers indirect feature cycles and prevents shared
production code from importing features. See the [Finviz workflow review](finviz_workflow_review_2026-10.md).

## Verification commands

With development dependencies available to the repo interpreter:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m tools.audits.api_contracts --check
.\.venv\Scripts\python.exe -m pytest tests/contracts/test_api_responses.py tests/contracts/test_dashboard_wire.py tests/contracts/test_two_eyes_wire.py -q
```

A linked worktree uses the main checkout's interpreter as described in
`AGENTS.md`. Frontend builds must stay in that worktree, or use a separate output
directory. Run the existing full verification stack before merge; these fast
checks complement it. Loading source changes remains the operator's job through
`update_dashboard.bat` after integration into a clean release checkout.
