# Fowler — Refactoring / Structural Review (LEAD SEAT)

## Domain Verdict (LEAD)

The `universe_type` architecture is **fundamentally sound**, and the verdict is **surgical, not rebuild**. The load-bearing decision — one immutable `Universe` descriptor (`core/pipeline/universe.py`) that owns ticker source, cache paths, regime set, and archive tag, resolved at call time to dodge the config-vs-cwd shadow — is exactly the right shape. It folds six co-travelling literals into one registry entry, anchors paths to the project root so a stray cwd can't cross-write a universe's parquet, and makes the closed-set allowlist a `ValueError` wall. Adding a fourth universe is genuinely one registry entry. The three rounds of "fixes at the seam" the user is worried about are NOT the same bug recurring — they are *distinct boundaries* (cache write, archive scoping, episode identity, health scope, metadata lock) each being closed once as the descriptor's reach extended outward from the engine core to the archive read surfaces. That is normal hardening of a young abstraction reaching its edges, not a leaky design thrashing. The engine is byte-parity-locked, 604 tests pass, and the descriptor is the single write-side source of truth. Nothing here signals "tear it down."

BUT there is one genuine cross-cutting inconsistency worth a **targeted, cheap refactor**: the **read-side `"us_equities"` scope is a hardcoded string literal re-pinned in ~9 independent call sites** (archive_queries default + `_grouped_episodes` setdefault + `_latest_episode_first_seen`, archive_browse `_resolve_universe_type`, archive_calibration `archive_health`, engine_edge, backtest_engine, loader `_clean_cell` fallback, episodes `SetupRow` default). The *write* side already does this correctly — it routes through `resolve_universe(universe).universe_type`. The read side does not; it stamps the bare string. This is the one place where the `us_stocks`-key / `us_equities`-type vocabulary split actually bites, because every read author must *remember* which of the two tokens the archive uses and type it by hand. The fix is small (a named `DEFAULT_EQUITIES_UNIVERSE_TYPE` constant or a `default_universe().universe_type` helper, threaded through the read surfaces) and pays off within weeks given the active multi-universe + calibration work. Estimate: a 2-4 hour surgical pass touching ~9 sites, no engine math, fully test-covered already. Do that, and the seam is closed for good. Everything else below is P3 hygiene.

---

FINDING:
- Title: Read-side "equities scope" is a duplicated magic literal, not a single policy
- File: webapp/backend/services/archive_queries.py:26,117,161; webapp/backend/routers/archive_browse.py:30; webapp/backend/routers/archive_calibration.py:89; webapp/backend/services/engine_edge.py:73; tools/backtest_engine.py:458; core/backtest/loader.py:122; core/archive/episodes.py:43
- Principle: Inconsistent Vocabulary / Shotgun Surgery (Principle 4 + Principle 5)
- Severity: P2
- What's wrong: The "default population is equities" policy is expressed as the bare string `"us_equities"` typed independently at ~9 read sites, while the write side correctly derives it from `resolve_universe(universe).universe_type`. The descriptor is the single source of truth for the `key`↔`universe_type` duality everywhere EXCEPT the read surfaces, which bypass it.
- Consequence: If the default universe's archive tag ever changes (or a second equities-class universe is added), the change is a hunt-and-replace across 9 files in three packages, and a missed site silently mis-scopes a stats/edge surface rather than failing loudly.
- Fix: Introduce one named constant (e.g. `DEFAULT_EQUITIES_UNIVERSE_TYPE = default_universe().universe_type`) exported from the universe module, and reference it at every read site instead of the literal. engine_edge already does this — make the rest match.

FINDING:
- Title: `_weekly_refresh_due` is a true twin — two implementations, subtly divergent
- File: core/pipeline/downloads.py:726-735 and core/pipeline/scan_job.py:351-360
- Principle: Shotgun Surgery / twin code paths (Principle 5)
- Severity: P2
- What's wrong: Two separately-maintained `_weekly_refresh_due(meta)` functions decide the same thing (is a full refresh due) from the same `last_full_refresh` meta key, but differ in detail — downloads reads `last_full_refresh` and compares against `settings.FULL_REFRESH_INTERVAL_DAYS` with naive UTC; scan_job reads the same key but branches on `ts.tzinfo` and defaults the interval via `getattr`. This is the exact "the live and seed evals must agree but were separate" shape the eval-twins fold was created to kill.
- Consequence: A change to the weekly-refresh cadence (or a timezone-handling fix) edited in one copy and not the other makes the downloader and the health/refresh path disagree about whether the cache is due — one forces a cold refetch the other reports healthy, an invisible ping-pong.
- Fix: Hoist one `_weekly_refresh_due` into a shared module (it belongs next to `data_freshness` or `cache`, beside the other meta predicates) and have both downloads and scan_job import it; delete the second copy.

FINDING:
- Title: `fetch_data` state machine is cohesive — do NOT split further
- File: core/pipeline/downloads.py:980-1056 (`fetch_data`) and its `_try_*` helpers
- Principle: Extract pure logic, keep mutations visible / Premature modularisation (Principle 2 + Principle 6)
- Severity: P3
- What's wrong: This is a positive finding answering central question (4). `fetch_data` is NOT a god-function: it is a ~70-line readable sequence (lock → scope → fresh? → current? → incremental? → cold) where each state is a named `_try_*`/`_*_result` helper, and crucially the IO/mutation (parquet writes, meta writes, quarantine saves) stays VISIBLE at the helper boundaries rather than hidden behind getters. That matches the Carmack/Fowler synthesis exactly. The one mild smell is the long positional parameter lists threaded through `_try_current_cache`/`_write_*_cold_result` (`cached, cache_file, meta_file, meta, scope, ...`) — a Data Clump.
- Consequence: None blocking. The parameter clumps cost a little reading friction when modifying a write path, but the sequencing is clear and the state is contained.
- Fix: Leave the state machine as-is. Optionally, later, bundle the `(cache_file, meta_file, meta)` trio into a small `CacheTarget` dataclass to shorten the write-helper signatures — only if a calibration change actually forces edits there.

FINDING:
- Title: Duplicate-column dedupe is a scattered idiom that should be one named helper
- File: core/pipeline/downloads.py:317,440,475,476,534,803,944; core/pipeline/data_freshness.py:110
- Principle: Duplicated knowledge / Mysterious idiom (Principle 4 — names reveal design)
- Severity: P3
- What's wrong: The corruption-repair idiom `df.loc[:, ~df.columns.duplicated(keep='last')]` appears 8 times across two modules, each guarding the same documented torn-merge corruption shape (a duplicate `(ticker, field)` column that makes `frame[col]` return a DataFrame and crashes `combine_first`). The knowledge of WHY this is needed lives in three long comments; the operation itself is an unnamed one-liner repeated verbatim.
- Consequence: The dedupe is load-bearing (it prevents a crash in the very fetch meant to repair the cache), but a reader can't tell a defensive dedupe from an incidental one, and a future column-handling change must find all 8 sites. Low cost today because the panel shape is stable, but it compounds.
- Fix: Extract `_dedupe_columns(df)` (or `drop_duplicate_columns`) with the WHY comment attached once, and call it at the 8 sites. Pure function, byte-identical, safe to fold.

FINDING:
- Title: `us_stocks` key vs `us_equities` type split is sound at the descriptor but unguarded at the boundary
- File: core/pipeline/universe.py:80,98-100 (the deliberate split)
- Principle: Inconsistent Vocabulary (Principle 4)
- Severity: P3
- What's wrong: Answering central question (1): the key/type split itself is a legitimate, documented decision (the API/cache token `us_stocks` vs the archive tag `us_equities`), and isolated INSIDE the descriptor it's harmless — the descriptor owns both and `resolve_universe` maps between them. It only becomes a bug source when callers reach past the descriptor and hardcode whichever token they happen to need (see the P2 above). The split is not itself worth a migration to unify the vocabulary — renaming the archive tag would be a live-DB migration for cosmetic gain, which the economic test rejects.
- Consequence: As long as reads route through the descriptor, zero cost. The cost is entirely the hand-typed literals, which the P2 fix removes.
- Fix: Do not unify the vocabulary or migrate the archive tag — not worth a live-SQLite migration. Just close the boundary leak (P2) so no caller ever has to know which token applies. The split then lives, correctly, only inside `universe.py`.

FINDING:
- Title: Archive-read modules duplicate the SetupRow→episode adapter three times
- File: webapp/backend/services/archive_queries.py:80-84,165-169; core/backtest/loader.py:99-125
- Principle: Duplicated knowledge (Principle 5 — Data Clumps / repeated projection)
- Severity: P3
- What's wrong: The projection "SELECT the five identity columns → build `ep_mod.SetupRow(id=…, ticker=…, scan_date=…, setup_type=…, universe_type=…)` → `build_episodes`" is written out three times (twice inline in archive_queries `_build_grouping` and `_latest_episode_first_seen`, once in loader `_setup_rows`). The loader copy correctly NaN-cleans cells via `_clean_cell`; the two archive_queries copies do not (they rely on ORM columns being clean). The knowledge of "which columns make a SetupRow" is duplicated, and the NaN-safety is inconsistent between copies.
- Consequence: Adding a sixth grouping-relevant column (or changing the universe_type fallback) means editing three projections; the inconsistent `_clean_cell` usage means the SQL-NULL-as-`nan` bug class is guarded in one copy but not the others (it happens not to bite the ORM path today, but it's the same latent shape).
- Fix: Lift one `setup_row_from(obj)` adapter (accepting an ORM row or a namedtuple) into `core.archive.episodes` or a shared helper, NaN-clean inside it, and call it from all three sites.

---

Summary: 6 findings — 2 × P2, 4 × P3. Headline verdict: the `universe_type` architecture is sound; keep fixing surgically. The single targeted refactor worth doing now is centralizing the read-side equities-scope literal (P2 #1) and folding the `_weekly_refresh_due` twin (P2 #2). `fetch_data` is a well-factored state machine — leave it alone.
