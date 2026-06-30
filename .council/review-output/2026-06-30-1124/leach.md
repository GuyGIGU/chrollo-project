# Brandur Leach — Data-Integrity Review (universe_type seam)

## Domain Verdict

`universe_type` as a persisted identity dimension is **SOUND** — keep fixing surgically, no
schema/data-model refactor warranted. At the schema layer it is modeled correctly and defensively:
`NOT NULL` + `server_default='us_equities'` + a closed-set `CHECK` + the 3-col `UNIQUE(ticker,
scan_date, universe_type)`, all of which I verified survive the migration rebuild verbatim (the
compiled `CreateTable` DDL emits `universe_type VARCHAR DEFAULT 'us_equities' NOT NULL`, the named
UNIQUE, and the CHECK). This is the key point the brief asks about: **there is no NULL/default
identity ambiguity at the database layer** — a row physically cannot carry a NULL or out-of-set
`universe_type`, so the "same ticker as ETF and stock on one date" case is collision-free by
construction, and a pre-migration row deterministically backfills to `us_equities` via COALESCE.
The migration itself is textbook (rename → create-from-model → INSERT…SELECT → row-count guard →
drop, all in one explicit transaction with `foreign_keys=OFF`, preceded by a WAL checkpoint + file
backup). The genuine integrity risk is *not* the column's modeling — it is that the **"equities is
the default scope" decision is re-pinned at every read AND write surface independently**, and one
write surface (the seeder) was missed in this round, leaving it on the pre-widening 2-col upsert key.
That is a leaky-by-repetition pattern, not a leaky-by-design one: the fix is to thread
`universe_type` through the one missed writer and (longer term) centralize the equities-default, not
to rebuild the identity model. The fact that every prior round closed a *different* boundary is
consistent with surgical hardening of a sound design, provided the remaining write surface below is
closed.

---

FINDING:
- Title: Seed writer upserts on the pre-widening 2-col key and never stamps `universe_type`
- File: core/archive/seed.py:296, core/archive/seed.py:331-490
- Principle: Constraints are assertions / Upsert races on the archive identity (Principle 1 & 4)
- Severity: P2
- What's wrong: The live screener writer was updated to upsert on `(ticker, scan_date, universe_type)` and to stamp the universe, but the seed writer still does `filter_by(ticker=ticker, scan_date=eval_date_str).first()` and omits `universe_type` from its `values` dict entirely (it falls through to the `server_default`).
- Consequence: A seed run that ever covers a non-equities universe would mass-update or skip the wrong row (its existence check ignores the universe dimension), silently overwriting an `us_equities` seed row with a sectors/commodities one — corrupting the calibration ground-truth on the exact identity the 3-col key was added to disambiguate.
- Fix: Thread the resolved `universe_type` into the seed writer's `values` and add it to the `filter_by` existence check, mirroring `core/archive/writer.py`; the DB CHECK/NOT-NULL already protect against NULL, but the application upsert must match the widened key.

FINDING:
- Title: Archive upsert is application-side SELECT-then-write, not a DB-atomic `ON CONFLICT`
- File: core/archive/writer.py:424-624
- Principle: Upsert races on the archive identity (Principle 4)
- Severity: P3
- What's wrong: The writer resolves the conflict in Python (`query(...).filter_by(...).first()` then either `setattr` or `session.add`) rather than letting the database resolve it via `sqlite.insert(...).on_conflict_do_update(...)` on the 3-col unique key. The whole loop commits once at the end, so within one process this is fine, but the check-then-insert is not atomic across the two writer processes (backend forward-return job vs. scan pipeline).
- Consequence: If the seeder/forward-return job and a live scan ever interleave on the same `(ticker, scan_date, universe_type)`, both can see "no row" and the second `INSERT` raises an `IntegrityError` that aborts the whole scan's single commit — losing the entire scan's archive write, not just the one collision.
- Fix: Replace the SELECT-then-add/update with SQLite's `INSERT … ON CONFLICT(ticker, scan_date, universe_type) DO UPDATE`, letting the unique constraint resolve the collision in the database; this also removes the per-ticker existence query that the `autoflush=False` workaround exists to protect.

FINDING:
- Title: Idempotency guard for the `score_oscillation` DROP swallows real failures by string-match
- File: webapp/backend/services/startup.py:215-230
- Principle: Migrations are production operations / narrow the catch so genuine failure is loud (Principle 3)
- Severity: P3
- What's wrong: `_apply_migrations` treats any exception whose text contains `"no such column"` as "already applied" for the in-place `DROP COLUMN score_oscillation`. That substring can also appear in a genuinely different failure (e.g. a typo'd ADD referencing a missing column, or a future statement), and the loop also commits per-statement on a single shared connection, so a real DROP failure mid-list is logged as a benign skip.
- Consequence: A legitimately failed migration on the live archive is silently downgraded to a warning/skip, so the schema can drift from the model without the boot failing loudly — the opposite of the "migration is a production operation" discipline.
- Fix: Scope the `"no such column"` swallow to the known retired-DROP statements only (the additive `duplicate column`/`already exists` cases are correctly broad), so an unexpected `no such column` from any other statement surfaces.

---

## Notes (verified sound — not findings)

- **Migration safety (startup.migrate_universe_type):** correct 12-step rebuild — WAL checkpoint +
  `shutil.copy2` backup before any DDL, single explicit `BEGIN`/`COMMIT` with `foreign_keys=OFF`,
  pre/post `COUNT(*)` drift guard with rollback, stale `ix_*` index drop to avoid the
  rename-collision, and `COALESCE(universe_type, 'us_equities')` to preserve any out-of-band column
  values. The `_has_universe_identity` PRAGMA-based guard (column AND 3-col unique must both exist)
  is sound and correctly distinguishes a real migration from an out-of-band ADD COLUMN. Per the
  brief I did not re-flag the 0041 idempotency-guard fix; it holds.
- **Parquet atomicity (cache._atomic_write_parquet / _write_meta):** PID-suffixed `.tmp` +
  `os.replace` beside the target — atomic on a single filesystem, torn-write safe, and the
  per-PID temp prevents two processes sharing one `.tmp`. Dtype is pinned at the boundary
  (`float32` OHLC, `Int64` volume) so the cache schema is writer-enforced.
- **Schema-drift on read:** the freshness predicates (`data_freshness`, `_history_too_shallow`,
  `_has_all_symbols`) all guard `isinstance(columns, MultiIndex)` and treat an unexpected shape as
  empty/shallow → a cold refetch rather than a crash. This is the Principle-5 "treat unexpected
  cache shape as a miss" pattern, done right; the cache is correctly treated as disposable.
- **Duplicate-column torn-merge shape:** every merge path
  (`_patch_market_data`, `_incremental_fetch`, `_write_incremental_result`, `_cold_fetch`,
  `_full_refetch`) dedupes columns with `~columns.duplicated(keep='last')` before the
  `combine_first`/persist, defusing the `Series.combine_first(DataFrame)` crash the comment
  documents.
- **NaN-coercion fix (loader._clean_cell):** correct — `None`/`NaN`/blank → the typed default,
  so a SQL `NULL` `universe_type` can never leak the literal `"nan"` into an episode grouping key.
  The projection threads `universe_type` through so ETF/stock episodes don't merge.
- **Identity-key NULL handling (the brief's KEY question):** sound. `NOT NULL` + `server_default`
  + `CHECK` make NULL/out-of-set physically impossible; the loader/episodes/queries all default a
  reflected NULL to `us_equities`, matching the DB backfill. No latent ambiguity at the DB layer.
- **Unbounded `SELECT * FROM setup_archive` (loader.load_archive:73):** technically an unbounded
  read (Principle 4), but it is the offline backtest harness and reading every row is *required* to
  form episodes correctly (you cannot LIMIT a gap-and-islands grouping). Acceptable as-is; would
  only warrant attention if this loader is ever put behind a hot UI endpoint.
