# Expert Catalog — for council-init

`council-init` uses this catalog to **tailor the council to a project**. Each entry says who the
seat is, *when it applies*, its reference doc, and how to adapt/rename it for a project's domain.
Keep the named experts (real practitioners) — the name carries the doctrine.

## How council-init uses this

1. Detect the project's stack/domain (map, don't ingest).
2. For each seat below, decide **include / drop / recast** using its "Applies when" rule.
3. For recast seats, keep the reference doc but rename the seat to fit the domain (record why).
4. Write the resulting roster + seat→ref map + gates into `<project>/.council/council.config.md`.
5. Propose to the user for confirmation (names kept per project decision #3).

## Canonical seats (the Carmack 10)

| Seat | Domain | Reference doc | Applies when | Recast / drop rule |
|---|---|---|---|---|
| **Troy Hunt** | Security | `security.md` | Almost always (any input handling, auth, secrets, external I/O) | Rarely dropped; recast to "integrity/safety" for non-web |
| **Martin Fowler** | Refactoring / structure | `refactoring.md` | Always (every codebase has structure) | Never drop — the load-bearing seat |
| **Kent C. Dodds** | Frontend quality | `quality-frontend.md` | There is a UI component layer | Drop if no frontend |
| **Matteo Collina** | Backend quality | `quality-backend.md` | There is server/API/async logic | Recast to generic **backend** (e.g. "Ramírez") if not Node/tRPC |
| **Brandur Leach** | Postgres quality | `quality-postgres.md` | There is a relational DB / migrations | Recast to **data-integrity** (e.g. keep "Leach") for SQLite/parquet/other stores |
| **Vercel Performance** | Performance | external (Vercel rules) | Perf-sensitive frontend/runtime | Drop or recast to a general **performance/pipeline** seat if not Next.js |
| **Simon Willison** | LLM pipeline quality | `quality-llm.md` | There is an LLM/prompt pipeline | Recast to **numerical** (e.g. "McKinney") for deterministic numeric/data engines — reuse `quality-llm.md`'s boundary/NaN/dtype principles |
| **Karri Saarinen** | UI quality (visual) | `quality-ui.md` | There is a visual surface | Drop if no UI |
| **Vitaly Friedman** | UX quality | `quality-ux.md` | There is user-facing interaction | Drop if no UX surface |
| **Kent Beck** | Test quality | `quality-testing.md` | There are (or should be) tests | Never drop — audits the test suite that guards everything |

## Worked example — Chrollo (this project)

Chrollo is a deterministic Wyckoff/VCP **numerical** screener (Python engine + FastAPI + SQLite/parquet
+ React). `council-init` should reproduce the hand-tuned roster you already run:

- **Hunt** (security) — keep. **Fowler** (refactoring) — keep. **Beck** (tests) — keep.
- **Collina → Ramírez** (backend) — recast: FastAPI/SQLAlchemy, not Node/tRPC.
- **Willison → McKinney** (numerical) — recast: pandas/numpy correctness; reuse `quality-llm.md`
  boundary/NaN-dtype principles (see Chrollo `conventions.md` EC-2).
- **Leach** (data integrity) — recast from Postgres to SQLite/parquet schema/migration integrity
  (see `conventions.md` EC-4, references `quality-postgres.md`).
- **Dodds / Saarinen / Friedman** — keep (React frontend exists).
- **Vercel Performance → "Performance" (pipeline)** — recast to engine/pipeline performance (no Next.js).

Gates for Chrollo: `pytest`, `npm --prefix webapp/frontend run lint`, `npm --prefix webapp/frontend run build`
(no tsc/vitest/cypress). `council-init` detects these from the repo, not from the Carmack defaults.

## Adding a seat

New project type needs a lens not covered? Add a row here with its "Applies when" rule and a
reference doc, then `council-init` can select it. Grow the catalog as new domains appear.
