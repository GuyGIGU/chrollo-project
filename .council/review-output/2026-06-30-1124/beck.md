# Beck — Test Quality Review (universe_type seam)

## Domain Verdict

The `universe_type` seam has **partial, asymmetric** behavioral coverage — strong where the last
adversarial pass actually got burned, thin or absent everywhere else. The genuinely good news: the
NaN-coercion regression that escaped is now pinned by a *behavioral* test (`_clean_cell` /
`collapse_to_episodes` with mixed-NULL rows, `test_loader_universe_filter.py:66`), the episode
universe-split is pinned at two layers (`test_episodes.py:26`, `test_loader_universe_filter.py:51`),
the migration **rebuild body** is now exercised on a real legacy DB (`test_universe_migration.py:37`),
and the equities-default archive scope is locked at one call site
(`test_canonical_setups_excludes_etf_rows_by_default`). That is real, surgical progress.

But the **recurring-leak pattern is itself a coverage signal, not just an architecture one.** Each
round, a *different* boundary leaked because each boundary re-pins the same cross-cutting fact
(`universe_type == "us_equities"` / "this is the equities scope") independently, and the test suite
mirrors that fragmentation: it tests whichever site just broke, not the invariant across all of them.
The literal `"us_equities"` is now hard-coded in **six** places (migration backfill, `_apply_setup_filters`
default, the cache-key `setdefault`, `_latest_episode_first_seen`, `engine_edge`, `backtest_engine`) and
only TWO of those have a behavioral test; the descriptor's deliberate `us_stocks` key vs `us_equities`
universe_type split — flagged in every prior round as the trap — has **zero** assertion pinning it
(see Finding 1). There is no single test that says "the value the migration writes is the value the
read side filters on." So I would not call for a rebuild — the descriptor design is sound — but the
seam needs **one deliberate test-suite hardening pass** (a centralized invariant test that ties the
backfill literal to every read-side scope, plus coverage of the three untested re-pin sites) **before**
more feature work, or the fourth round will leak at the fourth boundary. The architecture is fixable
surgically; the *test strategy* of "patch the site that broke" is what's accumulating risk.

---

FINDING:
- Title: The `us_stocks`-key / `us_equities`-type split — the seam's most-flagged trap — is unverified
- File: tests/test_universe_descriptor.py:31-79 (and the missing assert across the whole file)
- Principle: Test what might break (#4); the test list is analysis (#5)
- Severity: P1
- What's wrong: `test_default_universe_matches_current_literals` pins `key`, cache/meta/context filenames and index symbols, but never asserts `default_universe().universe_type == "us_equities"`. The single field that the migration backfill, `engine_edge`, and every archive scope depend on — and the one the brief names as the deliberate vocabulary split — has no test. `test_three_universes_registered` checks the keys but not the `universe_type` of any universe.
- Consequence: A typo or "tidy-up" renaming the default's `universe_type` to match its key (`us_stocks`) would pass the whole descriptor suite green while silently orphaning every archived equities row from every read surface (edge tile, missed-winners, calibration) — exactly the class of cross-universe scoping bug this seam keeps producing.
- Fix: Add a test pinning each universe's `universe_type` explicitly (`us_stocks`→`us_equities`, the other two→their key), asserting the key≠type split for the default, as an immutable expected value.

FINDING:
- Title: No test ties the migration backfill literal to the read-side scope literal
- File: tests/test_universe_migration.py:80-82 (comment only); webapp/backend/services/startup.py:290; webapp/backend/services/archive_queries.py:26,117,161; tools/backtest_engine.py:458
- Principle: Test what might break (#4); determinism / pin the oracle (#8)
- Severity: P1
- What's wrong: The migration writes the literal `'us_equities'` and six read sites independently filter on `'us_equities'` (two via the literal, one via `default_universe().universe_type`). A code comment at line 80 *claims* "engine_edge/load_archive filter on exactly this," but no test enforces the agreement — it is asserted in prose, not in code. The migration test checks the backfilled value equals `{"us_equities"}` in isolation; the read tests check their own literal in isolation.
- Consequence: If the descriptor's `universe_type` or any single read-site literal drifts from the backfilled value, every per-site test still passes (each is internally consistent) while the read surface silently returns zero equities rows — a false-green suite over a fully-broken seam. This is the precise failure mode the recurring leaks share.
- Fix: One invariant test asserting the migration's backfill value, `default_universe().universe_type`, the `_apply_setup_filters` default, and the `_latest_episode_first_seen` literal are all the same string — so drift at any one site fails loudly and centrally.

FINDING:
- Title: `persist_scan_metrics` per-universe routing — the actual fix — is never exercised
- File: tests/test_scan_metrics.py:14-27
- Principle: Test what might break (#4); mocks configured to hide the seam (#3)
- Severity: P2
- What's wrong: The fix in this round was making `persist_scan_metrics(metrics, universe=...)` write the *correct universe's* `cache_meta` (and re-take the per-universe lock). The only test calls `persist_scan_metrics(metrics)` with no universe and monkeypatches `_cache_paths` to a single fixed path that ignores its argument (`lambda *a, **k: (...)`) — so the universe→path routing and the per-universe lock target are both untested. The test would pass identically if `universe` were dropped from the signature.
- Consequence: A regression that routes an ETF scan's metrics into the US-Stocks `cache_meta` (the exact "writes only its own artifact" invariant this fix protects) sails through green; the lock-correctness claim in the docstring has no test behind it.
- Fix: Add a case passing a real ETF universe and assert the metrics land in that universe's `cache_meta` path (and not the default's) — let `_cache_paths` actually branch on the universe argument rather than swallowing it.

FINDING:
- Title: Migration row-count-drift guard and the COALESCE (out-of-band column) branch are untested
- File: tests/test_universe_migration.py:37-90; webapp/backend/services/startup.py:285-333
- Principle: The test list is analysis (#5); test what might break (#4)
- Severity: P2
- What's wrong: The rebuild test exercises the clean legacy path (no `universe_type` column → `'us_equities'` literal). Two branches the source explicitly carries are not covered: (a) `has_ut_col=True` → `ut_select = COALESCE(universe_type, 'us_equities')`, which must PRESERVE pre-existing out-of-band values while backfilling NULLs (the "column added without the constraint" case the docstring calls out); (b) the `pre != post` row-count-drift `RuntimeError` + ROLLBACK. Both are real, conditional, consequential code with no test.
- Consequence: The COALESCE preserve-vs-overwrite logic could regress (clobbering already-tagged ETF/sector rows back to `us_equities` on a re-run) and the guard could be inverted or the rollback could leave a half-built table, with the suite still green — these are data-loss-adjacent paths going unverified.
- Fix: Add a case seeding a legacy table that already has a nullable `universe_type` with mixed real values + NULLs, assert COALESCE preserves the real ones and fills NULLs with `us_equities`; the drift-guard is harder to trigger honestly, but at minimum assert the backup file is written so a failed rebuild is recoverable.

FINDING:
- Title: `_latest_episode_first_seen` and `engine_edge` equities-scoping have no behavioral test
- File: webapp/backend/services/archive_queries.py:146-162; webapp/backend/services/engine_edge.py:67-84 (no covering test in tests/)
- Principle: Test what might break (#4)
- Severity: P2
- What's wrong: Only `_canonical_setups` among the equities-default scope sites has a behavioral test (`test_canonical_setups_excludes_etf_rows_by_default`). `_latest_episode_first_seen` (whose whole reason for the `universe_type == "us_equities"` filter is preventing a two-universe ticker from resolving its first-seen to the ETF episode) and `engine_edge._compute`'s `default_universe().universe_type` scope are both untested. These are exactly the "same ticker in two universes" cross-resolution bugs the seam keeps producing.
- Consequence: A two-universe ticker (e.g. GLD as both a commodities_etf and a us_equities row) could have its equities saw-&-passed marker silently bind to the ETF episode, or the edge tile could pool ETF rows into the equities edge, with no failing test — the missed-winners/first-seen mismatch the docstring at line 150 says it is "exactly the" bug to prevent.
- Fix: Seed a tmp archive with the same ticker under two universe_types and assert `_latest_episode_first_seen` returns the equities episode's date; for `engine_edge`, assert an ETF row never enters the headline population.

FINDING:
- Title: The episode-cache-key collision (`us_equities` default vs explicit `None`) is asserted only structurally
- File: tests/test_episode_cache.py:39-44; webapp/backend/services/archive_queries.py:112-117
- Principle: Tests must be behavioral, not structural (#2); the test list is analysis (#5)
- Severity: P2
- What's wrong: The source comment (lines 112-115) describes a real bug: without the explicit `setdefault("universe_type", "us_equities")` landing in the cache key, the default scope (us_equities) and an explicit `universe_type=None` (all universes) would key on the same empty signature and serve each other's cached episodes. The cache test (`test_distinct_keys_are_independent`) only checks that two *different string keys* cache separately — it tests `VersionedCache` in the abstract, not the `_apply_setup_filters` key-derivation that the bug actually lives in.
- Consequence: If the `setdefault` were removed or moved, the default-equities and all-universe episode reads would silently collide in the cache and cross-contaminate, and no test would catch it — the unit test passes because it never goes through the real key-building path.
- Fix: A behavioral test that runs the episode query twice through the real code (once default, once `universe_type=None`) over a mixed archive and asserts the two results differ (ETF rows absent from the first, present in the second) even when both are cache-served.

FINDING:
- Title: ETF market-context borrow uses hand-pasted expected values lifted from the broad-context fixture
- File: tests/test_market_context_universe.py:29-44
- Principle: The red step is the proof (#1); assertions duplicate inputs (#6)
- Severity: P3
- What's wrong: The borrow test asserts `ctx["spy_6m_return"] == 0.123` and `regime["state"] == "UPTREND"` — but those values are the literal contents of the `broad` dict the same test feeds in via the monkeypatched `_read_meta`. The assertions confirm the values were copied through, which is the intended behavior, but they are tautological against the fixture: any pass-through would satisfy them. The discriminating assertions (`breadth_pct is None`, `context_basis == "broad_market"`, and the session-mismatch fallback) are the ones doing the real work; the borrowed-value asserts add little.
- Consequence: Minor — the borrow path is genuinely covered by the basis + session-gate assertions, so this is economics/readability, not false confidence. The risk is a reader mistaking the echoed-value asserts for independent verification.
- Fix: Keep the basis/neutralization/session-gate asserts (those are the behavior); treat the echoed SPY/regime values as incidental rather than load-bearing, or make the lookahead-guard the focus by varying only the session date.

FINDING:
- Title: `test_yahoo_provider_satisfies_protocol` is a structural smoke test with near-zero discriminating power
- File: tests/test_providers.py:71-74
- Principle: Delete tests that don't earn their keep (#9); assertions are the test (#6)
- Severity: P3
- What's wrong: The test asserts `hasattr(provider, "name") and callable(provider.fetch)` — it passes for any object with a `name` attribute and a callable `fetch`, including a stub that returns nothing. It restates the class definition rather than verifying behavior, and the real delegation contract is already covered by `test_yahoo_provider_delegates_to_fetch_data`.
- Consequence: Pure liability with no delta coverage — it would never fail for any bug that matters (a `fetch` returning a wrong-shaped panel still passes). Maintenance cost without confidence.
- Fix: Delete it, or if a Protocol-conformance guard is wanted, make it assert the full surface (`daily_candles`, `latest_price`, `sector`, … callable) so a missing capability method actually fails — otherwise it's coverage theatre.

---

## Notes (no finding — credit where due)

- `test_collapse_null_universe_type_falls_back_not_nan` (loader, line 66) is exactly the right shape:
  it independently reasons the expected episode count (1, not 2) from the NaN-truthiness bug, with a
  self-documenting comment explaining *why* `bool(np.nan) is True` would split the ticker. This is the
  template the rest of the seam's tests should follow.
- `test_market_data_health.py` is strong: `test_short_panel_is_not_flagged_shallow` (line 183) tests
  the depth predicate at three boundaries (too-short, hollow, healthy) in one readable case, and the
  index-less-universe trio (healthy / still-stale-when-behind / default-still-requires-SPY) correctly
  enumerates the behavioral variants of Fix ② rather than just the happy path.
- `test_backtest_engine.py` headline-contamination tests (lines 228-284) independently reason the
  expected median from the screener-only subset (`np.median([0.20, 0.02, 0.05, 0.04])`) rather than
  pasting the engine's output — a genuine red-step-capable oracle, with float tolerance (`abs=1e-9`)
  applied correctly.
