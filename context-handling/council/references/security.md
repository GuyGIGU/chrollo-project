# Security Reference — Carmack × Hunt

Philosophy: John Carmack. Specifics: Troy Hunt + OWASP 2025.
Stack context: local single-user research app — Python 3.11 deterministic engine (`core/`) / FastAPI + Pydantic backend (`webapp/backend/`) / SQLite via SQLAlchemy (archive + watchlist) / parquet market-data cache / yfinance (pinned) + IBKR live integration / React 19 + Vite SPA.

The threat model is **not** a public multi-tenant web app. There is no auth, no untrusted browser visitor, no PII at scale. The adversary is: a malformed ticker or universe file, a poisoned cache artifact, a silently-upgraded dependency that breaks an unattended scan, a leaked broker credential, and a SQL string built from a query param. Every finding must describe the **concrete attack vector** — not just "this is insecure." When Carmack and Hunt independently converge on a principle, it earns its place here.

---

## Principle 1: If it's syntactically possible, it statistically exists

*Carmack: "If a vulnerability is syntactically possible, it statistically exists in your codebase."*
*Hunt: "It's us — the organic matter — that despite the best of intentions make bad choices that introduce serious risks."*

The reviewer's job is to hunt for **classes of flaws**, not individual bugs. If one SQLAlchemy query is built with an f-string, assume every hand-built query is suspect until proven otherwise.

### What to check

**SQL injection (OWASP A03)**
- Raw `text()` / `engine.execute()` / `connection.exec_driver_sql()` with f-strings or `.format()` / `%`-interpolation of a ticker, scan_date, tier, or `source` param into the SQL string.
- `archive_queries._apply_setup_filters` is the right model: it builds `q.filter(SetupArchive.scan_date >= date_from)` through the ORM expression API, which parameterises. The risk is the day someone "just needs a quick raw query" for a report and pastes a request value into `text(f"... WHERE ticker = '{ticker}'")`.
- The `source` filter splits a comma-delimited string into an `.in_(...)` list — correct. A string-built `IN ('A','B')` clause would be the injection.
- Hunt: "ORMs and stored procedures won't save you" if you concatenate inside them. ORM-safe-by-default only holds while you stay on the expression API.
- Severity: **P1 always.** Hunt's 3-year-old executed SQLi with an automated tool. If exploitation is child's play, there is no excuse.

**Command / code injection**
- Untrusted input reaching `subprocess` with `shell=True`, `os.system`, `eval`, `exec`, or `pd.eval`/`df.query` built from a request string.
- A universe/ticker value flowing into a shell call to an external tool.
- Severity: **P1**

**Deserialization trust (OWASP A08)**
- `pickle.load` / `joblib.load` on any artifact that is not produced by this codebase. A poisoned pickle in the cache directory is arbitrary code execution at load time.
- `pd.read_pickle` on cache files of unknown provenance. Prefer parquet (data-only) for the market-data cache; never unpickle a downloaded artifact.
- Severity: **P1** for pickle of external data, **P2** for internal pickle that could be tampered on disk.

---

## Principle 2: Automate defences — human vigilance always fails at scale

*Carmack: "It is irresponsible to not use [static analysis]. Anything that can be mechanically checked should be."*
*Hunt: "Security scanning needs to be continuous, not just a one off, not on an annual basis, not just on major changes but all the time."*

If you rely on the operator to remember the right thing before every unattended scan, you've already lost. The engine runs scheduled and unattended (automation roadmap) — there is nobody watching.

### What to check

**Input validation as the entry assertion**
- Are FastAPI routes typed with Pydantic models / `Query(...)` constraints, or do they accept bare `str`? An untyped path/query param is an unchecked assumption that reaches the DB and the engine.
- Ticker symbols: validate against a charset (`^[A-Z0-9.\-]{1,10}$`) before they index the parquet cache or build a filename. A ticker is also a **path component** — see Principle 5.
- Date ranges (`date_from`/`date_to`): parse to real dates, not pass-through strings. A string `scan_date` filter that is never parsed will happily carry a SQL fragment.
- Universe inputs: bound the size and validate each symbol. A 6.9k-symbol universe file is attacker-shaped if it ever comes from outside.
- Severity: **P1** for unvalidated input that reaches SQL or the filesystem, **P2** for unvalidated input that only reaches the engine math.

**Dependency scanning**
- Is `pip-audit` (or equivalent) run against `requirements.txt`? Are versions pinned and the lockfile committed?
- yfinance is pinned `==1.2.1` for a reason (Principle 5). Is anything else floating with `>=`?
- Severity: **P2** (supplement with OWASP A03 supply-chain guidance below).

**Lint/type discipline**
- Pydantic models on request/response boundaries are the automated equivalent of Carmack's assertions: validated at entry or assumed exploitable.
- `Optional`/`Any` smuggled through a service-layer signature hides an unchecked value. Flag `Any` on the `core/` ↔ backend seam.
- Severity: **P2** for missing boundary validation, **P3** for scattered `Any`.

---

## Principle 3: Minimise state — the less you store, the less you lose

*Carmack: "State is the enemy. Mutable shared state is the root of most bugs."*
*Hunt: "You cannot lose what you do not have."*

This is a personal lab, so the breach surface is small by design — keep it that way. The crown jewels are **broker credentials** and the **integrity of the archive/cache**, not user PII.

### What to check

**Secrets management (OWASP A02)**
- IBKR connection settings live in `broker_config.Settings.from_env()` — read from environment, never hardcoded. That is the correct pattern. Verify no host/port/client-id or account credential is checked into git, `.env` committed, or defaulted in source.
- IBKR auth itself is handled out-of-band by TWS / IB Gateway login; the app holds connection params, not a password. Confirm no path logs or persists account numbers, order details, or a session token.
- Search the codebase and `error.log` for anything resembling a credential, account id, or API key being printed. Hunt: a $6B company exposed its error logs publicly.
- Severity: **P1** for any secret in source or logs.

**Log hygiene**
- The fetch-health telemetry and request-id middleware are good observability — but confirm they log *symbols and counts*, not full broker responses, positions, or account state.
- Do not dump full IBKR execution/position payloads to `error.log`. Strip to the fields the operator actually needs.
- Severity: **P1** for broker/account data in logs, **P2** for verbose payload logging.

**Don't persist what you can recompute**
- The parquet cache and the SQLite archive are both regenerable from the engine. Treat them as derived state, not a vault — but see Principle 9 for tamper integrity.
- Severity: **P3** — minimalism is a default, not a hard finding here.

---

## Principle 4: Validate at the boundary, trust within

*Carmack: "Use the type system to prove absence of flaw classes."*
*Hunt: Demonstrated that 67% of scanned ASP.NET sites had configuration vulnerabilities — defaults kill you.*

Python has no compiler to lean on, so the boundary discipline is **Pydantic at the FastAPI edge** plus explicit validation before anything touches the DB, the filesystem, or IBKR. Inside the engine, values are already trusted — the cost of re-validating every bar is the wrong trade. The contract is: nothing crosses the edge unparsed.

### What to check

**Boundary models**
- Every FastAPI route takes a Pydantic model or constrained `Query`/`Path`; responses are Pydantic models, so the engine's internal floats/NaNs/`Timestamp`s are serialised through a declared schema, not leaked raw.
- A NaN or inf escaping into a JSON response is both a correctness bug and an information-shape leak — coerce at the response model.
- Severity: **P2** for unmodelled boundaries.

**Configuration as code — the config-vs-cwd collision**
- Real Chrollo footgun: the backend runs with cwd `webapp/backend`, so a module named `config` there would *shadow* the repo-root `config` screener package and crash boot. The fix was naming it `broker_config` and reading settings lazily (`broker_config.settings.<field>` per-use, never cached at import). A wrong-config-loaded service is a silent misconfiguration — defaults killing you, exactly Hunt's point.
- Confirm no `core/` module does a module-level `from config import settings` that detonates under the backend's cwd. `fetch_health` documents the lazy-`getattr` discipline; hold the line.
- Severity: **P2** for config-shadowing risk, **P1** if a shadow silently loads wrong broker mode (paper vs live).

---

## Principle 5: Shrink the attack surface — including the supply chain

*Carmack: "The single most effective strategy for defect reduction is code reduction."*
*Hunt: "Third-party dependencies increasingly feature [in breaches]... 'a third party' doesn't absolve you of responsibility."*

The biggest non-local attack surface this project has is its **data and dependency supply chain**: yfinance, the universe feed, and the cache it writes to disk.

### What to check

**The yfinance pin as an integrity control (OWASP A03)**
- yfinance is pinned `==1.2.1`. An unattended `pip install -U` that floats it can silently change column names, adjustment behaviour, or rate-limit handling and corrupt every scan with nobody watching. Treat the pin as a security control, not a convenience.
- A schema drift upstream that renames/refactors OHLC columns is a supply-chain break that poisons engine reads. The pin + a parity check before any vendor bump is the defence.
- Severity: **P2** for an unpinned market-data dependency, **P1** if an unattended job auto-upgrades it.

**Path / filename construction**
- Tickers and dates become **cache file paths** and parquet filenames. A symbol like `../../etc` or one with separators is path traversal into `os.path.join`. Validate the charset (Principle 2) and resolve+verify the final path stays under the cache root before any read/write.
- `database.py` anchors the SQLite path to the module dir deterministically (`os.path.abspath(__file__)`) rather than cwd — that is the right pattern; replicate it for cache roots so a stray cwd can't redirect writes.
- Severity: **P1** for unsanitised input in a file path.

**Dead-ticker quarantine as an integrity control**
- `fetch_health` quarantines symbols that repeatedly return empty and gates recording on a *healthy* run, so a rate-limited Yahoo day can't quarantine the whole universe. That gate is a denial-of-service defence against bad upstream days — preserve it. Removing the healthy-run gate would let one bad fetch silently gut the next scan.
- Severity: **P2** if the gate is weakened or bypassed.

**Dependency surface**
- Does every dependency earn its place? Could a small helper replace a package that drags a large transitive tree? Each transitive dep is unaudited code in an unattended job.
- Severity: **P3** unless a dependency has a known CVE (**P1**).

---

## Principle 6: Lock the local front door — bind to localhost

*Carmack: "Write code that cooperates with analysis. If the tool can't reason about it, neither can a reviewer."*
*Hunt: "All websites should use HTTPS, even if they don't include private content."*

This is a single-user local app, so the browser-security apparatus (CSP, HSTS, cookie flags) is mostly out of scope — but "local" is a configuration claim that must be verified, not assumed.

### What to check

**Network exposure**
- Is uvicorn bound to `127.0.0.1`, not `0.0.0.0`? A backend that talks to IBKR and can trigger scans must not be reachable from the LAN. This is the one binding that matters.
- CORS: is the FastAPI `allow_origins` the specific Vite dev origin, not `"*"`? A wildcard CORS on an API that can place IBKR-adjacent calls is the local equivalent of an open door.
- Severity: **P1** for `0.0.0.0` binding or wildcard CORS exposing broker-adjacent endpoints.

**What's genuinely not applicable here**
- No public TLS, HSTS, session cookies, or CSP-for-untrusted-visitors — there is no untrusted browser visitor. Don't pad findings with web headers that don't apply. (If the app is ever exposed beyond localhost, this principle inverts and the full header set returns.)
- Severity: note as N/A rather than a finding.

---

## Principle 7: Deploy assertions as tripwires

*Carmack: "Assertions catch assumption violations before they become exploitable."*
*Hunt: On the Nissan LEAF — implement authorisation on all API calls; "a trivial feature to add" at build time.*

There is no per-user authorisation to enforce (single user), so the assertions that matter are **operational integrity tripwires**: did the data arrive intact, is the broker in the mode I think it is, did the scan actually run.

### What to check

**Broker mode safety — the highest-stakes assertion**
- `broker_config` carries `ibkr_mode` (paper/live) and maps it to a port. The dangerous failure is *believing you're in paper while connected to live*. Assert the mode explicitly at any order-adjacent or position-reading path; don't infer it. `is_live_mode()` exists — use it as a guard, and make live mode loud in the UI and logs.
- Default mode is `live` in `from_env()`. Confirm nothing relies on the *absence* of an env var to mean paper.
- Severity: **P1** for any silent paper/live confusion.

**Integrity assertions on the data path**
- Validate fetched OHLC before it enters the engine: monotonic dates, no negative prices, sane adjusted/raw relationship. A bad bar that slips through is a lookahead-class correctness failure dressed as data.
- The archive grouper keys on immutable columns (`ticker`/`scan_date`/`setup_type`); assert that invariant rather than trusting it silently.
- Severity: **P2** for missing data-integrity assertions on ingestion.

**Rate limiting / request budget**
- Yahoo will 429. The quarantine + cooldown is the budget guard; assert the recovery storm path stays bounded so a bad day doesn't hammer the upstream.
- Severity: **P2**.

---

## Principle 8: Treat code review as security education

*Carmack: Reviews are how the team builds shared understanding of what "correct" means.*
*Hunt: "Education is the best ROI on security spend. Ever." Writing secure code costs zero extra effort at development time; finding the same bug in production costs catastrophically more.*

This principle is meta — it's about how the reviewer writes findings. Every finding should teach, not just flag. Explain the attack vector. Show what goes wrong. Make it concrete to *this* codebase.

### Reviewer guidance

- Don't write "this query is unsafe." Write "this report builds `text(f\"... ticker = '{ticker}'\")`, so a request param `ABC'; DROP TABLE setup_archive;--` drops the archive — route it through the ORM filter like `_apply_setup_filters` does."
- Don't write "pin your deps." Write "an unattended `pip install -U` floats yfinance off `1.2.1`; the column rename in a later release silently feeds the engine garbage and the scheduled scan archives wrong setups with nobody watching."
- The finding should make the operator never want to write that pattern again.

---

## Principle 9: Assume corruption — design for the failure case

*Carmack: "If a mistake is possible, it will eventually happen."*
*Hunt: "Absence of evidence is not evidence of absence."*

Don't just prevent bad input — design so that when a fetch fails, a cache file is half-written, or the DB is locked, the blast radius is contained and observable.

### What to check

**Atomic writes & DB integrity**
- Cache/archive writes: are parquet/JSON files written atomically (temp file + `os.replace`) so a crashed scan never leaves a torn artifact the next run trusts? A half-written cache file is silent corruption that the engine will faithfully analyse.
- `database.py` sets `busy_timeout=30000`, WAL, and `synchronous=NORMAL` so the backend and pipeline can both write without "database is locked" failures. That is the right resilience posture — verify transaction boundaries around archive writes are committed-or-rolled-back, never left open.
- Severity: **P1** for non-atomic writes to trusted data stores, **P2** for loose transaction boundaries.

**Error handling and information shape**
- FastAPI default exception output can echo internal paths/tracebacks. Confirm a global handler returns a generic shape; don't leak `core/` internals or filesystem paths even to a local client (you may screen-share / log them).
- An unhandled exception in the scheduled scan must be caught and recorded (fetch-health telemetry), not allowed to silently no-op the day's scan. A scan that fails *silently* is worse than one that crashes loudly.
- Severity: **P1** for silent scan failure, **P2** for verbose error leakage.

**Tamper / drift detection**
- The shadow-harness and seed-recall guards exist for correctness, but they double as integrity tripwires: if a dependency bump or cache poisoning changes engine output, byte-parity / seed-recall catches it. Treat a parity break after a dependency change as a possible supply-chain signal, not just a bug.
- Severity: **P2**.

---

## Principle 10: Know your gaps

*Carmack: epistemic humility — you can't fix what you don't know is broken.*
*Hunt: "We take security seriously" — otherwise known as "we didn't take it seriously enough."*

### Areas this doc is weaker on (supplement from other sources)

- **Supply-chain depth (OWASP A03):** PyPI typosquatting, dependency confusion, a compromised yfinance/transitive release. The pin + `pip-audit` is a floor, not a ceiling — supplement with hash-pinned requirements and Socket.dev-style analysis if the universe of deps grows.
- **IBKR / broker trust boundary:** this doc assumes TWS/Gateway handle auth correctly and the local socket is trusted. The single-session-per-username constraint and same-day execution window are operational, not modelled here.
- **Unattended-job integrity (OWASP A08):** scheduled scan as a privileged automated actor — task scheduling locks, run-once guarantees, and what happens when two scans overlap. Covered lightly; the automation roadmap is the real home for it.
- **Detection / observability (OWASP A09):** fetch-health telemetry and request-id middleware are a start; there is no anomaly detection on archive drift or broker-call volume.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Exploitable flaw, credential/data exposure, integrity corruption, broker-mode confusion | SQLi via `text()` f-strings, pickle of external data, path traversal from a ticker, secret/account-id in `error.log`, `0.0.0.0` binding, silent paper/live confusion, auto-upgraded yfinance in an unattended job |
| **P2 — Fix Soon** | Defence gap that widens surface or blast radius | Unpinned market-data dep, missing boundary validation, config-shadowing risk, non-atomic cache writes, weakened quarantine gate, verbose error leakage |
| **P3 — Consider** | Hygiene that compounds over time | Dead endpoints, unnecessary dependencies, scattered `Any`, regenerable state kept around unnecessarily |
