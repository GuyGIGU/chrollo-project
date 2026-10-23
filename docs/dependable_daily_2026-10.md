# Dependable daily Chrollo

The operator's goal (23 October 2026): make Chrollo a tool he can rely on more
with each release. Its daily promise is to find the setups he values early,
explain the reading, and preserve what was actually shown at the time.

## First implementation

Built on `codex/dependable-daily` and integrated into `main` with the operator's
authorization. Deployment is still pending; run the ordinary
`update_dashboard.bat` from the main checkout after integration.

- The new reader's scan chart carries `base_len`, counted from the parent's
  opening through its end or the read day using the supplied trading sessions.
  This fixes the screener's base-length sort on newly generated payloads. The
  grade's pre-SOS `base_days` is a different measure and is not substituted.
- Daily new-reader charts expose read agreement and optional grade feedback
  (too high, about right, too low). The existing API stores both, with the
  ticker/session/universe identity and engine version. A read verdict is needed
  before a grade verdict because that is the existing storage contract.
- Old-version or unstamped feedback is identified and requires a new judgment.
  Changing the grade preserves the read reason. Requests serialize; a failed
  save restores the prior state; a late response cannot update another chart.
- `python -m tools.audits.live_reader_audit --check --repeat` replays the saved
  US stock fires against the cache through the active reader door. It checks
  chronology, grade availability, saved dated facts, score/tier agreement and
  repeated-read consistency. It refuses a different engine hash and fails on
  missing sessions. Floating-point comparisons ignore only round-off below
  quoted cents (absolute tolerance 1e-10, relative 1e-12).

For an isolated worktree, pass `--source` pointing to the main checkout. The
tool reads its payload and parquet cache; it never imports the backend, fetches
data, writes the archive or starts services. `--output` writes an optional JSON
report outside sealed evidence. Tests exercise the gate on a sealed ALB chart,
future anchors, a lost fire, changed scores, engine epochs and date truncation.

This is a saved-fire reproducibility audit. It does not replace a new-reader
negative corpus, preferred-example recall, or an outcome study. The legacy
marks/negative/shadow/doctrine gates remain explicit old-reader checks.

The first live check of the 22 October payload found EVOX's final cached and
displayed bar is 21 October although the scan identity is 22 October. It is a
real per-symbol freshness exception, not a lost fire. AGL's apparent drift was
8.4e-12 in a derived height; prices, dates, grade and setup did not change.
The final audit must retain the EVOX failure until the data/publication policy
is resolved; it must not bless the stale frame or rewrite historical rows.
The completed check under the saved `af59af4b...` engine epoch reproduced 268
of 269 fires, including repeated public scan reads; EVOX was the sole exception.
The branch subsequently incorporated the operator's two STGW commits from
`main` through `1996ed9e`. That rotates the engine epoch, so checking the old
saved scan against that code correctly refuses until a matching scan exists.

## Next release: freshness and replay evidence

### Shortlisting pass — built in the isolated quality branch

On 23 October the operator named **finding and shortlisting setups** as the
most frustrating part. Inspection of the running UI found that hearts had no
matching screener view, sorting sat inside a popover, search-only/tier-only
filters had no reset control, paging required reaching the bottom of the chart
wall, and the global header overlapped in a narrow window.

The source on `codex/engineering-quality` now includes:

- A URL-restored **Liked** view of hearted setups in the selected scan. Its
  count refers to drawable charts in this scan, rather than all historical
  hearts. The inspected 22 October scan showed six hearted setups among 269
  charts; historical hearts outside that scan are not deleted or reclassified.
- Visible sorting, removable active-filter chips, a clear-filters control and
  a compact pager above the chart wall. The filter hook owns page resets;
  duplicate page-reset writes and the toolbar's duplicate view choices are gone.
- Retry actions for failed screener and likes loads. A failed likes read does
  not become a false empty shortlist. A failed refresh keeps the loaded charts
  visible with a warning and a retry action.
- Visible failure feedback for heart/star writes. One pending write per ticker
  prevents opposite toggles racing. Watchlist saves for different tickers
  reconcile independently, and a GET issued during a save cannot replace its pin.
- A wrapping header and viewport-contained filter panels for narrow windows.

Verification: 605 JavaScript tests, production build and lint; the expanded
browser suite covers the shortlist, retry paths, persistence, concurrent clicks,
top paging and narrow layouts. All browser API writes use controlled mocks.
Real-data visual inspection used only navigation/filtering against the existing
backend. Merged into main on 23 October; the live bundle changes only with the operator's update.

### Product priorities after integration

The daily loop is **find → inspect → shortlist → revisit → learn**. Each release
should remove a named obstacle in that loop and carry a regression check for it.

| Order | Change | Evidence of completion |
|---|---|---|
| 1 | Make freshness and partial failures explicit. Distinguish service health, scan completeness and the individual chart's last bar. The current UI can say "Healthy" while the run detail names unread charts. | A stale symbol or an incomplete scan is named in the relevant view, with its actual session and recovery action. Server verdicts drive the presentation. |
| 2 | Preserve exact replay inputs and publication identity; then show what changed since the last review. | Reopening a saved setup explains whether its bars, reading or engine changed, and reproduces the evidence originally shown. |
| 3 | Make favorite examples and explicit negatives a maintained evaluation set for the active reader. | A proposed ranking change is checked on examples excluded from tuning; reading agreement, preferred first-page results and later outcomes remain separate questions. No automatic weight changes from hearts. |
| 4 | Simplify the next high-risk ownership boundaries: import-time database initialization, archive record preparation/transaction ownership, and chart/mark/fix logic still held in the calibration router. | Imports are side-effect free, storage retains the same atomic behavior, and domain routers delegate logic with producing tests. Refactor one boundary per change. |
| 5 | Refine workspace hierarchy: put secondary account tools in a disclosure, preserve meaningful connection/mode visibility, and add saved views if repeated daily filters justify them. | Common shortlist/review actions remain visible; secondary tools stay reachable by keyboard; existing bookmarks and manual broker gates continue to work. |

The archive writer is about 900 lines and the calibration router about 890 in
this snapshot. Those are responsibility reviews, not split-at-N-lines targets.
The existing frozen reader and sealed evidence need their compatibility guards;
removing them for a smaller tree is a separate migration decision. Prefer a
clear owner and fewer competing state paths over a generic store/repository
framework or a broad cosmetic rewrite.

### Freshness and replay work remaining

1. Investigate per-symbol freshness on the normal archive path, including a
   mostly current panel containing a stale firing symbol. Show the individual
   chart's data session and keep it distinct from the scan run's session.
2. Preserve the evaluated OHLCV frame (or a content-addressed immutable copy)
   with engine/code identity and publication identity. A rolling cache and an
   engine-settings hash alone do not establish exact historical input identity.
3. Add live-reader preferred-example and explicit-negative regression checks
   with reviewed baselines. Existing passes are not automatically bad charts;
   existing legacy misses must not become new-reader acceptance baselines.
4. Show changes since the last review: new setup, changed reading, changed
   grade and readiness. Distinguish new bars, provider corrections and engine
   changes using the preserved evidence rather than guessing from the score.

## Later: ranking evidence and scan latency

Use the current calibration examples and hearts as training evidence; reserve
fresh, unselected examples for evaluation. Assess reading agreement and
preferred setups in the first 20 positions separately from subsequent returns.
Group repeated daily fires by setup episode and keep versions separate. Grade
feedback informs measured changes; it does not automatically retune weights.

Profile price-fetch and fundamentals cache misses. Advisory enrichment may
complete after a technical publication only with explicit freshness and a
consistent archive/update contract. Do not shorten price history or revive
provider batching as assumed performance wins; see the Tested-DEAD registry.

## Acceptance for the observation period

Proposed observation window: 20 completed trading sessions after the freshness
and replay-evidence release. This is a target, not an elapsed or proven result.

- Every scheduled scan is current, or visibly names the missing session or
  symbols and retains the last usable result with its original date.
- Replaying frozen inputs with the same code and settings reproduces the read.
- Every recorded judgment can be tied to the evidence the operator saw.
- The first-page preference comparison is measured on examples excluded from
  tuning; any predictive claim waits for the relevant outcomes to mature.
- Releases are reviewed, locally committed and integrated into clean `main`
  only with operator authorization. The operator loads them with
  `update_dashboard.bat`; agents never boot or restart the service.
