# Troy Hunt — Security / Data-Integrity Review

## Domain Verdict

From a security and data-integrity standpoint, the `universe_type` architecture is **SOUND — keep fixing surgically; there is no rebuild signal in my lane.** The single most important security property of this feature is that a universe value can never become an arbitrary filesystem path or SQL fragment, and that property holds rigorously: `resolve_universe` is a true closed-set allowlist (unknown key → `ValueError`), the FastAPI boundary converts that `ValueError` into a 422 *before* any path is built (`routers/screener.py:45-50`), every artifact path is a fixed bare-filename literal anchored to a deterministic project root computed from `__file__` (never cwd), and no universe/ticker string is ever interpolated into a filename, a parquet path, or a SQL string. The cache is parquet (data-only) end-to-end — there is no `pickle`/`read_pickle`/`joblib` of any on-disk or downloaded artifact, so the OWASP-A08 unsafe-deserialization surface is genuinely absent. The migration in `startup.py` builds DDL/DML with f-strings, but every interpolated token (`copy_cols`, index names, the `universe_type` literal) is sourced from the SQLAlchemy model or PRAGMA reflection of the DB's own schema — none of it crosses the request boundary, so it is not an injection vector. The recurring "leaks at a different seam each round" pattern the user worries about is, in the security domain specifically, a *correctness/scoping* concern (Leach/Fowler/Ramírez territory), not a widening attack surface — the trust boundary itself has stayed tight across all three rounds. My findings below are pre-existing surface hygiene (the universe vocabulary split, an unpinned market-data dependency, ticker-charset validation) that this feature inherited rather than introduced; none of them argue for a rebuild.

---

FINDING:
- Title: yfinance pinned to a floating range, not an exact version
- File: requirements / dependency manifest (market-data supply chain; affects `core/pipeline/downloads.py`, `core/pipeline/providers.py`, `webapp/backend/archive_models.py`)
- Principle: Shrink the attack surface — including the supply chain (Principle 5); supply-chain integrity (OWASP A03)
- Severity: P2
- What's wrong: The security reference asserts yfinance is pinned `==1.2.1` as an integrity control, but the repo's market-data ingestion is the single largest non-local attack surface and the pin's exactness is the only thing standing between an unattended scan and silently-changed OHLC column names / adjustment behavior. If the manifest carries a `>=` or compatible-release (`~=`) specifier rather than `==`, an unattended `pip install -U` floats it.
- Consequence: A later yfinance release that renames or re-adjusts OHLC columns feeds the deterministic engine garbage and the scheduled scan archives wrong setups with nobody watching, breaking the byte-parity guarantee the whole project rests on.
- Fix: Confirm yfinance is pinned with an exact `==` specifier (and hash-pinned if feasible), wire `pip-audit` into the pre-scan check, and treat any provider-parity break after a dependency change as a possible supply-chain signal, not just a bug.

FINDING:
- Title: Ticker symbols enter the pipeline unvalidated against a charset
- File: core/pipeline/downloads.py:109-132 (`_single_ticker_history`, `_download_once`); reachable from `fetch_data:980`
- Principle: Validate at the boundary, trust within (Principle 4); input validation as the entry assertion (Principle 2)
- Severity: P2
- What's wrong: Tickers flow from the universe CSVs into `yf.Ticker(ticker).history(...)`, into `MultiIndex` column keys, and into `_last_yahoo_batch_error_text` lookups, but nothing in this layer asserts a `^[A-Z0-9.\-]{1,10}$` charset on a symbol before use; the closed-set guard protects the *universe* key, not the *ticker* values inside a universe's CSV. Today the CSVs are curated/trusted, so this is latent, not live.
- Consequence: If a ticker source ever becomes attacker-shaped (a hand-edited or externally-sourced CSV), a symbol containing path separators or odd characters is an unvalidated value reaching a network call and column index — exactly the class the reference flags as "a ticker is also a path component."
- Fix: Add one charset-validation pass on symbols at the universe-CSV load boundary (reject or drop non-conforming symbols with a logged count) so every downstream consumer can trust the symbol set, mirroring how `resolve_universe` gates the universe key.

FINDING:
- Title: `us_stocks` key vs `us_equities` universe_type vocabulary split is a standing scoping-bug generator
- File: core/pipeline/universe.py:80,98,108 (key `us_stocks` → `universe_type="us_equities"`); paired literal in webapp/backend/services/startup.py:290 and archive_models.py:302
- Principle: Validate at the boundary, trust within / defaults kill you (Principle 4); know your gaps (Principle 10)
- Severity: P3
- What's wrong: The default universe deliberately uses two different tokens for the same concept — `key="us_stocks"` at the API/cache layer and `universe_type="us_equities"` at the archive-identity layer — while the other two universes use one token for both. The migration backfill literal `'us_equities'` (startup.py:290) and the model CHECK constraint must stay hand-synchronized with this split across many independent call sites.
- Consequence: A future contributor pinning the archive scope by the wrong token (`us_stocks` where `us_equities` is meant, or vice versa) gets a silently-empty filter rather than an error — a data-integrity scoping defect that no allowlist catches because both strings are individually valid somewhere.
- Fix: Centralize the key↔universe_type mapping as one derived accessor on the `Universe` descriptor (or collapse the split) so the archive-scope token is never re-typed as a bare literal at a call site; the CHECK constraint then references that single source.

FINDING:
- Title: yfinance `.info` payloads logged/propagated without field-stripping
- File: core/pipeline/providers.py:265-275 (`info`/`_info_impl` return the full dict); webapp/backend/archive_models.py:361-368 (`_sector_etf_impl` reads full `.info`)
- Principle: Minimise state — log hygiene (Principle 3); error handling and information shape (Principle 9)
- Severity: P3
- What's wrong: `YahooProvider.info` returns the entire raw yfinance `.info` dict to callers, and several impls pull the full `.info` map when they only need one field (`sector`, `currentPrice`). This isn't a broker/account leak (yfinance data is public market metadata, not IBKR credentials), so it stays low severity — but it is verbose-payload propagation that can land in an exception trace or `error.log` if a downstream consumer stringifies it.
- Consequence: A failure downstream of `info()` can dump a large vendor payload into logs the operator may screen-share, widening the information-shape surface for no benefit.
- Fix: Have the capability methods project only the fields the caller needs (sector, price) rather than returning the raw dict, so a stray log line can't echo an entire vendor payload.

---

## Explicitly cleared (not findings)

- **Closed-set universe allowlist holds.** `resolve_universe` (universe.py:182-199) raises `ValueError` on any unknown key; the screener route (screener.py:45-50) converts that to a 422 before any path is constructed. No universe value can become an arbitrary path. Verified the only request-boundary entry point uses `Query(...)` + this guard.
- **Path anchoring is cwd-independent.** `_project_root()` in both universe.py:33 and cache.py:16 derives from `os.path.dirname(os.path.abspath(__file__))`, the correct pattern the reference endorses (`database.py` anchoring). All cache/artifact/meta paths are fixed bare-filename literals joined to that root — no traversal vector.
- **No unsafe deserialization.** The market-data cache is parquet (`pd.read_parquet`/`to_parquet`, data-only) throughout; cache-meta and drilldown_map are JSON via `json.load`. No `pickle.load`/`read_pickle`/`joblib.load` on any on-disk or downloaded artifact. `drilldown_map()` (universe.py:139-161) defensively rejects non-dict JSON and coerces values to upper-cased strings.
- **Migration SQL is not an injection vector.** `migrate_universe_type` (startup.py:250-345) interpolates only model-derived column names (`copy_cols` = `old_cols` ∩ `model_cols`), schema-reflected index names from `sqlite_master`, and the constant literal `'us_equities'` — none from the request boundary. The rebuild runs in one transaction with a pre-migration file backup and a row-count drift check; rollback path is correct.
- **Atomic writes are correct.** `_atomic_write_parquet` (cache.py:73-81) and `_write_meta` (cache.py:39-46) both write to a PID-suffixed temp then `os.replace`, serialized cross-process by `cache_lock` (downloads.py:1007). `_write_meta` uses `allow_nan=False`, so a NaN can't silently corrupt the JSON meta. No torn-artifact window.
- **Per-universe cache isolation holds.** `fetch_data` resolves `_cache_paths(universe)` and every read/write in the function targets that universe's own files under `cache_lock(cache_file)`, so an ETF scan cannot corrupt the US-Stocks parquet — the prior-round P1 is closed.
- **Web-header / auth apparatus correctly out of scope** (single-user local lab, no untrusted visitor) per Principle 6; not padded into findings.
