# Data Integrity Reference — Carmack × Brandur (SQLite + SQLAlchemy + Parquet)

Philosophy: John Carmack. Database integrity discipline: Brandur Leach (Crunchy Data, ex-Stripe), translated from Postgres to Chrollo's stack.
Stack context: Python 3.11 / FastAPI / **SQLite via SQLAlchemy** (the `setup_archive` + `watchlist` tables in `webapp/backend/`) / **parquet market-data cache** (`core/pipeline/cache.py`) / pandas.

> **Note:** This document was repurposed from the original Postgres/Prisma/Neon reference for the Chrollo stack. Chrollo has no Postgres, no connection pooler, and no ORM beyond SQLAlchemy's declarative layer. The *universal* database principles — constraints as assertions, transaction boundaries, migration safety, schema design, bounded queries — carry over directly. The examples are re-grounded in SQLite's specific gotchas and in the parquet cache as a second, file-based data store.

Every finding must describe the **concrete failure mode** — not just "this is bad practice."
Security patterns are in security.md (Hunt). Backend error handling is in quality-backend.md (Ramírez). Numerical correctness — the engine's bugs — is in quality-llm.md (McKinney). This doc covers: data integrity, transaction safety, migration correctness on a live archive, schema design, query correctness, and the two-store split between SQLite and parquet.

---

## Principle 1: Constraints are assertions — the database is the last line of defence

*Carmack: assertions catch assumption violations before they cause corruption.*
*Brandur: "Your database can and should act as a foundational substrate that offers your application profound leverage for fast and correct operation."*

Database constraints are the only safety layer that cannot be bypassed by any code path — not by a raw `text()` query, not by `core/archive/seed.py` writing rows directly, not by a future tool that opens `trading_journal.db` with the stdlib `sqlite3` module, not by an interrupted scan. SQLAlchemy validates nothing at the Python level unless you write a validator. Only the database enforces invariants at the point of insert.

Brandur: **"You can get away without constraints and schemas, but only by internalizing a nihilistic understanding that your production data isn't cohesive."** For an archive whose entire purpose is to be the calibration ground-truth, incohesion is fatal — a duplicated or malformed setup row silently poisons every recall and forward-return statistic computed off it.

### What to check

**Missing CHECK constraints**
- Scores, prices, and ratios that have a known valid range. `score` should be ≥ 0; `r_level` should be > `s_level`; `box_width` should be positive; `triggered` should be 0/1. Without CHECKs, SQLite's loose type affinity will accept a `'nan'` string or a negative width and the calibration regression inherits garbage.
- SQLite **does** enforce CHECK constraints, but SQLAlchemy declarative columns don't add them unless you pass `CheckConstraint(...)` in `__table_args__`. They must be created at table-creation time — SQLite cannot add a CHECK to an existing table via `ALTER` (see Principle 3).
- Severity: **P2** for business-critical fields (`score`, `tier`, level ordering). **P3** for advisory ranges.

**Missing compound unique constraints**
- `setup_archive` already declares identity columns (`ticker`, `scan_date`, `setup_type`). If the natural key `(ticker, scan_date, setup_type)` is not a `UniqueConstraint`, a re-run of the same scan day double-archives the setup. No code path *intends* this, but a crashed-and-retried scan job, or the live archiver firing alongside a manual re-seed, produces it. The duplicate then counts twice in recall.
- Add it explicitly: `__table_args__ = (UniqueConstraint("ticker", "scan_date", "setup_type", name="uq_setup_identity"),)`. This is the SQLite analogue of the isolation race — two writers both check "is this archived?", both see no row, both insert.
- Severity: **P1** for the archive identity key. **P2** for the `watchlist` star (a duplicate star is cosmetic but still wrong).

**Indexes for the columns you actually filter on**
- The archive is queried by `ticker` and `scan_date` constantly (browse, recall, forward-return backfill). `archive_models.py` correctly marks both `index=True`. The failure mode is the *new* hot column added later — e.g. filtering by `tier` or `setup_type` — without an index, every dashboard query becomes a full table scan of the archive. SQLite will not warn you; it just gets linearly slower as the archive grows.
- SQLite does **not** auto-index foreign-key columns either. If `watchlist` references `setup_archive` and you filter or join on that column, add the index.
- Severity: **P2** — fine at a few thousand rows, painful once the archive holds a season of daily scans.

**NOT NULL discipline**
- Brandur: **"Nullable columns are literally the default in DDL — you'll get one unless you're really thinking about what you're doing and explicitly use NOT NULL."** In SQLAlchemy, a `Column(Float)` is nullable by default; you opt *out* with `nullable=False`.
- `archive_models.py` gets the identity and scoring spine right (`ticker`, `scan_date`, `setup_type`, `tier`, `score` are all `nullable=False`). The forward-return columns (`fwd_return_1d`, `triggered`) are legitimately nullable — they're "not computed yet." That's the correct use of NULL: genuinely-unknown state, not a missing value you forgot to require.
- Review every nullable column for whether NULL has a *meaning*. A nullable `score` would be a bug; a nullable `fwd_return_1d` is a lifecycle stage.
- Severity: **P3** for unnecessary nullable fields. **P2** if a nullable column is used in a WHERE/aggregate without NULL handling (see Principle 4).

---

## Principle 2: Transactions are the unit of correctness — one scan, one commit

*Carmack: if a race condition is syntactically possible, it will happen in production.*
*Brandur: "Transactions are really just a really good idea. Maybe the best idea in robust service design."*

SQLite has exactly **one writer at a time** — there is no row-level concurrency to reason about, which removes a whole class of isolation puzzles. But Chrollo has *two processes* contending for that single writer: the FastAPI backend (uvicorn) and the screener pipeline (`core/archive/writer.py`, `seed.py`). The `database.py` engine is configured for this with `busy_timeout=30000` and WAL mode. The remaining correctness questions are about *boundaries*.

### What to check

**Partial archive writes without a single transaction boundary**
- Archiving a setup writes the identity row plus its decomposed sub-scores. If that's done as several `session.add` + intermediate `commit` calls, a crash mid-write leaves a half-populated row that the recall harness reads as a real (broken) setup. Wrap the whole setup write in one `with session.begin():` so it's all-or-nothing.
- Severity: **P1** for the archive write — a torn row is silently-wrong calibration data.

**Holding the single write lock during slow work**
- The deadlock-equivalent in SQLite: a long-running read or an open transaction on one process makes the *other* process's write block for the full 30s `busy_timeout`, then raise `OperationalError: database is locked`. The real instance of this is documented in `database.py`'s own comments — autoflush-during-query in the writer hit it when uvicorn held a short read lock. The fix already shipped (busy_timeout first), but the rule stands: **never do network I/O, a yfinance fetch, or a pandas detector pass while holding an open SQLite transaction.** Fetch and compute first, open the transaction only to write the result.
- SQLAlchemy's `autoflush=False` in `SessionLocal` is deliberate — it stops a stray read inside a half-built unit of work from emitting a write and grabbing the lock early.
- Severity: **P1** for any I/O or heavy compute inside an open transaction. **P2** for an unnecessarily long-lived session.

**Side effects ordered around the commit — the archive-then-notify problem**
- The pattern: archive a setup, then trigger a downstream effect (write a chip, update fetch-health, kick a forward-return job). If the effect runs *before* the commit lands, it acts on data that may roll back. If it runs *after* and the process dies in between, the effect is lost. Brandur: **"It's a problem that's far more nefarious; you almost certainly won't notice when it happens."**
- For Chrollo the stakes are low (this is a single-user research lab, not a payment flow), so the heavy outbox pattern is overkill. The lightweight discipline: make the downstream effect **idempotent and re-derivable** from the archive itself. The forward-return updater already does this — it scans for rows where `fwd_return_1d IS NULL` and fills them, so a lost-notification just means the next backfill catches it. Prefer "poll the table for unfinished work" over "fire an event and hope."
- Severity: **P2** for effects that aren't re-derivable from the archive. **P3** when the effect is just a recompute-on-next-pass.

**The parquet cache is a *second* transaction domain with no rollback**
- The market-data cache (`core/pipeline/cache.py`) is files, not SQL — there is no transaction spanning the SQLite archive and the parquet write. If you archive a setup and *then* the parquet rewrite fails, the two stores disagree. The mitigation is already in place and is the right one: `_atomic_write_parquet` writes to `path + '.tmp'` then `os.replace(tmp, path)`, an atomic rename, so a reader never sees a half-written parquet. The meta JSON uses the same tmp-then-replace dance. Keep every cache writer on this pattern; a direct `to_parquet(path)` is a torn-file waiting for a crash.
- Severity: **P1** for any non-atomic write to the parquet cache or its meta file.

---

## Principle 3: Migrations are production operations — SQLite has no real `ALTER`

*Carmack: if a schema change can corrupt or drop data, it will eventually run against the live archive.*
*Brandur (translated): every DDL is an operation on a file someone is actively reading.*

SQLite's `ALTER TABLE` is severely limited compared to Postgres. It supports only: `RENAME TABLE`, `RENAME COLUMN`, `ADD COLUMN`, and (recent versions) `DROP COLUMN`. There is **no** `ALTER COLUMN TYPE`, **no** adding a CHECK or a UNIQUE to an existing table, and historically **no column drop at all**. The standard workaround for anything unsupported is the **12-step table rebuild**: create a new table with the desired schema, `INSERT ... SELECT` the data across, drop the old, rename the new — all inside one transaction.

This is exactly the operation behind Chrollo's real **oscillation-column drop** (memory: engine cleanup `92c3a43`). Removing the retired `oscillation` score column wasn't a one-line `DROP COLUMN` on older SQLite — it was a rebuild, and getting it wrong means losing every archived setup's history.

### The operation reference (SQLite)

| Operation | Native support | Risk |
|---|---|---|
| `ADD COLUMN` (with constant default) | Yes — fast, metadata-only | Low; default must be a constant, not `CURRENT_TIME`-style volatile |
| `RENAME COLUMN` / `RENAME TABLE` | Yes | Low, but breaks code still reading the old name |
| `DROP COLUMN` | Only newer SQLite; rewrites the table | Medium — silently a no-op or error on old engines |
| `ALTER COLUMN TYPE` | **Not supported** | Must do a full table rebuild |
| Add CHECK / UNIQUE to existing table | **Not supported** | Must rebuild the table to introduce it |
| Drop NOT NULL / change default | **Not supported** | Full table rebuild |

### What to check

**Ad-hoc migrations with bare `sqlite3` and a fragile try/except**
- `webapp/backend/migrate.py` is the live pattern: it opens `trading_journal.db` directly and does `ALTER TABLE ... ADD COLUMN ... DEFAULT`, swallowing "already exists" in a broad `except`. For an *additive* column this is acceptable — `ADD COLUMN` is the one cheap, safe SQLite DDL. But the broad `except Exception` also swallows a *real* failure (locked DB, disk full, typo'd type), printing "Already Exists" when nothing happened. Narrow the catch to the duplicate-column case so a genuine failure is loud.
- It also hardcodes the relative path `'trading_journal.db'` — which only resolves correctly from one working directory. `database.py` deliberately anchors the path to the module's own directory for exactly this reason. A migration run from the wrong cwd silently creates or mutates the *wrong* file. (See the config-vs-cwd collision in quality-backend.md — same class of bug.)
- Severity: **P2** for the over-broad except and the cwd-relative path.

**Anything beyond ADD COLUMN done in place**
- Changing a column's type, adding a UNIQUE to enforce the identity key retroactively, or dropping a column on old SQLite **cannot** be an in-place `ALTER`. It must be the 12-step rebuild, wrapped in a single transaction, with `PRAGMA foreign_keys=OFF` for the duration (the rebuild temporarily breaks FK references). Run it against a *copy* of `trading_journal.db` first and diff the row counts.
- Brandur's table-rename safe pattern translates cleanly: rename the old table, create the new-schema table, backfill, then drop — never destroy data you can't reconstruct from a live scan.
- Severity: **P1** — these are the operations that can drop the archive.

**Foreign keys are OFF by default**
- SQLite ships with `PRAGMA foreign_keys=OFF`. Every connection must opt in. Chrollo's `database.py` sets WAL, `busy_timeout`, and `synchronous=NORMAL` in its connect-listener but does **not** enable `foreign_keys`. If any relation (e.g. `watchlist` → `setup_archive`) is meant to be enforced, add `cur.execute("PRAGMA foreign_keys=ON")` to that same listener — otherwise the FK is decorative and orphan rows accumulate.
- Severity: **P2** if any cross-table reference is intended to be enforced; **P3** if the tables are independent.

**Backfills that rewrite the whole archive in one statement**
- A single `UPDATE setup_archive SET col = ...` over the entire archive holds the sole writer for the full duration, blocking the backend the whole time. SQLite has no batching primitive — do it in `WHERE id BETWEEN ? AND ?` chunks with the transaction committed per chunk, so the backend can interleave. The forward-return updater is the model: it targets only `WHERE fwd_return_1d IS NULL`, which is both bounded and idempotent.
- Severity: **P2** for a full-archive single-statement backfill.

---

## Principle 4: Queries must be bounded, correct under NULL, and explicit about what they fetch

*Carmack: if an unbounded query is possible, someone will call it on the whole archive.*
*Brandur: every fetch-everything and every missing LIMIT is a ticking time bomb.*

### What to check

**Unbounded archive reads**
- `session.query(SetupArchive).all()` returns every row ever archived. Fine in week one; an OOM or a multi-second dashboard stall once the archive holds months of daily scans. Every archive query that backs a UI list must carry a `.limit()` and order deterministically (e.g. `scan_date DESC, score DESC`) so pagination is stable.
- Severity: **P2** for any unbounded `.all()` on the archive; **P1** once the archive has real volume.

**Fetching wide rows when you need three columns**
- `setup_archive` is a wide row (identity + structural DNA + nine sub-scores + forward returns). A browse list that needs `ticker, tier, score` should `query(SetupArchive.ticker, SetupArchive.tier, SetupArchive.score)`, not hydrate the whole ORM object per row. There's no PII here, but pulling every sub-score column for a list view is wasted I/O and serialization.
- Severity: **P2** for hot list endpoints hydrating full rows unnecessarily.

**NULL handling — three-valued logic traps**
- The forward-return columns are NULL until computed, which makes them the prime NULL-logic hazard. `WHERE triggered != 1` does **not** return the not-yet-triggered rows: in SQL `NULL != 1` is `NULL`, not `TRUE`, so every un-backfilled row silently drops out. To count "setups that did not trigger" you must write `WHERE triggered = 0`, and to find un-backfilled rows `WHERE triggered IS NULL`.
- Aggregates over an empty or all-NULL set: `AVG(fwd_return_1d)` over rows that are all NULL returns NULL, and `SUM` returns NULL not 0. Wrap with `COALESCE(...)` when a numeric zero is the intended empty-case.
- In SQLAlchemy, `.filter(col != value)` emits the same `!=` and inherits the same trap — use `.filter(or_(col != value, col.is_(None)))` when NULL rows should be included.
- Severity: **P2** for NULL-logic bugs in recall/forward-return queries — these directly corrupt the statistics the engine is calibrated against.

**N+1 over the archive**
- Querying the archive list, then looping to fetch each setup's `watchlist` star or reviews one-by-one, is the classic N+1. Batch with a single `WHERE ticker IN (...)` or a join. Detection: turn on SQLAlchemy `echo=True` in a dev run and watch for the same SELECT repeating per row.
- Severity: **P2** — degrades linearly with the number of cards on the wall.

**Upsert races on the archive identity**
- "Archive this setup if not already present" implemented as SELECT-then-INSERT is not atomic across the two writer processes. With the `UniqueConstraint` from Principle 1 in place, use SQLite's `INSERT ... ON CONFLICT(ticker, scan_date, setup_type) DO UPDATE` (SQLAlchemy `sqlite.insert(...).on_conflict_do_update(...)`) so the database, not the application, resolves the collision atomically.
- Severity: **P2** for SELECT-then-INSERT on the archive identity key.

---

## Principle 5: Schema design choices compound — get them right from day one

*Carmack: minimise unstructured state. Every optional field, JSON blob, and stringly-typed date is a liability.*
*Brandur: "For services that run in production, the better defined the schema and the more self-consistent the data, the easier life is going to be."*

### What to check

**Dates stored as strings**
- `setup_archive` stores `scan_date` as a `String` in `YYYY-MM-DD` form. This is a *deliberate and defensible* choice in Chrollo — they're trading-calendar dates, compared and sorted lexically, and `YYYY-MM-DD` sorts correctly as text. The trap to guard is consistency: a single row written as `2026-6-7` (no zero-pad) or `06/07/2026` sorts wrong and breaks every range query silently. A CHECK constraint on the format, or a single canonical formatter used by *both* the live writer and the seeder, prevents drift. SQLite has no native date type, so the discipline lives in code and constraints, not the schema.
- Severity: **P2** if multiple writers format dates independently; **P3** if one formatter is enforced.

**Type affinity is advisory, not enforced**
- SQLite columns have *affinity*, not strict types — a `Float` column will happily store the string `'nan'` or `'N/A'` if a writer hands it one, and that value then breaks `AVG`, comparisons, and the calibration regression in non-obvious ways. This is the database-layer twin of the NaN-propagation hazard in quality-llm.md. Defend at the boundary: validate/coerce numeric fields before insert (the cache layer already coerces OHLC with `pd.to_numeric(..., errors='coerce')` and casts to `float32`), and consider a CHECK like `typeof(score) = 'real'` on score-bearing columns.
- Severity: **P2** for numeric columns fed by parsed/external data without coercion.

**JSON/Text columns standing in for structure**
- Stashing a setup's sub-scores or tags as a JSON blob in a `Text` column means no constraints, no per-field query, no per-field index. `archive_models.py` correctly does the opposite — it *decomposes* the nine sub-scores into real `Float` columns precisely so the calibration regression can read each one. That decomposition is the right instinct; resist the temptation to collapse "just a few more fields" into a JSON bag when they have a known shape and you'll want to regress on them.
- JSON is fine for genuinely-unstructured payloads (a raw fetch-health record, a debug trace). It's a design failure for core domain fields you'll query or constrain.
- Severity: **P2** for structured domain data hidden in a Text/JSON column; **P3** for appropriate unstructured use.

**Hard delete plus an archive-of-record, not soft delete**
- Brandur: **"Soft deletion logic bleeds out into all parts of your code. Forgetting that extra predicate on deleted_at can have dangerous consequences."** And: **"never once, in ten plus years, did anyone actually use soft deletion to undelete something."**
- Chrollo's `core/archive/purge.py` exists to *hard*-remove rows, and the whole `setup_archive` table already **is** the archive-of-record — every scan is preserved as historical truth. That's the right architecture: there's no `deleted_at` predicate to forget on every recall query, and a re-seed rebuilds cleanly. Don't introduce a soft-delete flag that every calibration query would then have to remember to filter.
- Severity: **P3** — architectural guidance; escalate to **P2** if a soft-delete predicate ever gets forgotten and skews recall.

**The parquet cache schema can drift silently**
- The parquet cache is a schema too, just an implicit one. If yfinance changes its column layout (recall the `==1.2.1` pin exists precisely because upstream changes silently break unattended scans), a fresh parquet can carry a different column set or dtype than the cached one, and a later read mixes them. `_optimize_market_data_for_cache` pins OHLC to `float32` and volume to `Int64` on write, which is the right defence — it normalizes dtype at the boundary so the cache schema is *enforced by the writer*, not assumed. Validate the column set on read too, and treat an unexpected shape as a cache-miss-and-refetch, not a crash.
- Severity: **P2** for cache reads that trust the on-disk schema without validation.

---

## Principle 6: Two stores, one source of truth — keep SQLite and parquet honest

*Carmack: understand the lifecycle of every resource you allocate — including files.*
*Brandur: the foundational substrate is only foundational if it's self-consistent.*

Chrollo deliberately splits its data: **SQLite** holds derived, queryable state (the archive, watchlist, journal — small, transactional, indexed) and **parquet** holds the bulk raw market-data cache (large, append-mostly, read by pandas). This split is correct — you would not want months of OHLC bars as rows in SQLite, nor the calibration archive as loose files. But two stores means two failure domains.

### What to check

**Single-writer contention between the backend and the pipeline**
- SQLite's one-writer rule is the real "connection limit." The backend and the screener pipeline both open `trading_journal.db`. WAL mode (set in `database.py`) lets readers proceed while one writer holds the lock, which is what makes the two-process setup workable — but it does **not** grant two concurrent writers. If both try to write at once, one waits out the `busy_timeout` then fails. Keep writes short (Principle 2) and serialize the heavy archive write so it never overlaps a backend write storm.
- Severity: **P1** for long writes that can collide across the two processes.

**WAL checkpoint and the `-wal`/`-shm` sidecar files**
- WAL mode creates `trading_journal.db-wal` and `-shm` alongside the DB. They are part of the database — copying or backing up only the main `.db` file while a WAL is unflushed loses recent writes. To snapshot the archive safely, either checkpoint first (`PRAGMA wal_checkpoint(TRUNCATE)`) or copy all three files together. Deleting the `-wal` while the DB is open corrupts recent data.
- Severity: **P1** for a backup/copy that grabs only the `.db` file.

**Atomic, durable parquet writes**
- Covered in Principle 2 and worth its own line: every cache write goes tmp-then-`os.replace`. `os.replace` is atomic on the same filesystem, so a crash mid-write leaves either the old file or the new — never a torn one. The one caveat is *cross-filesystem*: if `path` and `path + '.tmp'` ever land on different mounts, `os.replace` degrades to a non-atomic copy. Keep the tmp file beside its target.
- Severity: **P1** for any cache writer not using the tmp-then-replace pattern.

**Adjusted-OHLC integrity in the cache**
- The cache stores OHLC that may be split/dividend-adjusted. If an adjustment lands between two fetches, the cached bars and a fresh pull disagree on the same calendar date — a constant-ratio shift across the whole series. This is the integrity hazard the provider-parity harness (`tools/provider_parity.py`) exists to catch. A cache that blindly appends new bars onto adjustment-stale old bars produces a discontinuity the detector will read as a real price move. Re-pull and re-validate the full window when an adjustment is suspected, rather than appending.
- Severity: **P1** for appending fresh bars onto possibly-readjusted cached bars without a parity check.

**The cache is reconstructable; the archive is not**
- Final lifecycle point: the parquet cache is *derived* — if it's corrupt, delete it and refetch. The SQLite archive is *primary* — it holds forward-return ground truth that cannot be recomputed once the original scan-day context is gone. Treat them with different paranoia: the cache can be cheap and disposable; the archive needs the transaction discipline and migration care of Principles 2–3.
- Severity: **P1** for any operation that risks the archive treating it as disposable like the cache.

---

## Principle 7: SQLite's defaults are tuned for a single embedded process — know the overrides

*Carmack: if the default is dangerous and changing it requires manual intervention, every new process will hit the default.*

SQLite's out-of-the-box defaults assume one process, one writer, no contention. Chrollo runs two processes against one file, so several defaults must be overridden — and `database.py` already does most of the work. This is the checklist of what must be set and why.

| Default | What Chrollo needs | How | Severity |
|---|---|---|---|
| Rollback-journal mode (writers block readers) | WAL mode | `PRAGMA journal_mode=WAL` (set in `database.py`, sticky on the file) | P1 |
| Immediate "database is locked" on contention | 30s wait | `PRAGMA busy_timeout=30000` + connect `timeout=30` | P1 |
| `synchronous=FULL` (slow) | `NORMAL` (durable with WAL) | `PRAGMA synchronous=NORMAL` | P2 |
| `foreign_keys=OFF` | ON, if any relation is enforced | `PRAGMA foreign_keys=ON` in the connect listener | P2 |
| `check_same_thread=True` (blocks FastAPI threadpool) | per-connection sharing | `connect_args={"check_same_thread": False}` | P1 |
| No CHECK/UNIQUE unless declared | identity + range constraints | `__table_args__` at table creation (can't be added later) | P1 |
| `ALTER` can't change type/constraints | 12-step table rebuild | manual, transactional, tested on a copy | P1 |
| cwd-relative DB path | path anchored to module dir | `os.path.dirname(__file__)` (done in `database.py`) | P2 |
| `to_parquet(path)` torn on crash | atomic tmp-then-replace | `os.replace(tmp, path)` (done in `cache.py`) | P1 |

### The overriding migration review rule

Before any change to `trading_journal.db`, ask: **does this operation fit inside `ADD COLUMN`?** If yes, it's the one cheap, safe SQLite DDL — guard only the cwd path and the over-broad except. If no — a type change, a new constraint, a column drop on old SQLite — it is a **12-step table rebuild**, and you run it inside one transaction, with `foreign_keys=OFF`, against a *copy* of the archive first, diffing row counts before and after. The oscillation-column drop was exactly this, and it's the template: the archive is primary data, so every non-additive migration is a production operation.

---

## Gaps: What This Doc Doesn't Cover

- **Security patterns**: SQL injection via `text()` / string-built queries, untrusted file/path handling, parquet/pickle deserialization trust, the yfinance pin as a supply-chain control. Covered by **security.md (Hunt)**.
- **Backend error handling**: SQLAlchemy error surfacing through FastAPI, the config-vs-cwd collision, fetch-health degradation, async-route discipline. Covered by **quality-backend.md (Ramírez)**.
- **Numerical correctness inside the engine**: NaN/inf propagation, float equality, lookahead bias, dtype and index-alignment bugs, resampling. The engine's real bugs live here — covered by **quality-llm.md (McKinney)**.
- **Pipeline performance**: pandas vectorization, fetch/IO batching, chart-render cost. Covered by the performance seat. This is a correctness doc, not a profiling guide.
- **Postgres-specific machinery**: connection poolers, MVCC/VACUUM, serializable-isolation retry loops, logical replication. Not applicable — Chrollo is embedded SQLite, single-host.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Data loss, archive corruption, guaranteed contention failures | Non-additive in-place `ALTER` instead of a table rebuild, torn parquet/meta writes, backing up only the `.db` and losing the WAL, missing identity `UniqueConstraint`, partial/non-transactional archive writes, I/O held inside an open transaction, appending onto readjusted cached OHLC without a parity check, treating the primary archive as disposable |
| **P2 — Fix Soon** | Correctness bugs that compound or manifest at scale | Unbounded `.all()` on the archive, NULL-logic bugs in recall/forward-return queries, over-broad `except` + cwd-relative migration path, missing index on a new hot filter column, dates formatted inconsistently across writers, numeric columns fed unvalidated parsed data (affinity), cache reads trusting on-disk schema, `foreign_keys` left OFF when a relation is intended |
| **P3 — Consider** | Schema hygiene and architectural guidance | Unnecessary nullable fields, JSON used appropriately, soft-delete avoided in favour of hard-delete + archive-of-record, advisory CHECK ranges, string-date storage with one enforced formatter |

### The Overriding Filter

Before writing any finding, apply the Carmack–Brandur synthesis, re-grounded for SQLite + parquet:

1. **Is there a constraint that could enforce this invariant?** If yes and it's missing, flag it — and remember SQLite can only add it at table-creation time. The constraint is the assertion. (Brandur: the database is the foundational substrate.)
2. **Can this migration touch the live archive non-additively?** Anything beyond `ADD COLUMN` is a 12-step rebuild against primary data — test it on a copy. (Carmack: if it can drop data, it eventually will.)
3. **Is this query bounded and NULL-correct?** No `.limit()` on an archive read, a `!=` that silently eats not-yet-backfilled NULL rows, a full-row hydrate for a three-column list — flag it. (Both: unbounded and three-valued operations are time bombs.)
4. **Does this write hold the single SQLite writer longer than it must?** Two processes, one writer — keep transactions short and do I/O outside them. (Both: understand the lifecycle of every resource.)
5. **Are the two stores kept honest?** Parquet writes atomic, cache schema validated on read, adjusted-OHLC parity-checked, the archive treated as primary and the cache as disposable. (Carmack: the cache lies cheaply; the archive must not lie at all.)
