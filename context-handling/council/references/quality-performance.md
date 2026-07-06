# Performance — seat reference (starter)

> This is a **starter** doc. Upstream (Carmack Council) the Performance seat is the Vercel React
> Best Practices skill (external, Next.js-specific). For a general council, `council-init` recasts
> this seat to the project's real performance surface (frontend, backend/pipeline, or numerical).
> Flesh out the principles below for your stack, or point the seat at your own rules doc.

## When this seat applies
Any performance-sensitive surface: render hot paths, data-fetch waterfalls, N+1 queries, large
allocations, O(n²) loops on real data sizes, bundle/startup cost, batch/streaming throughput.

## Review lens (economic, not aesthetic)
Only flag performance issues that cost real time/money **at this project's actual scale** — measure
or reason concretely, don't speculate. Prefer the simplest fix that removes the cost.

## Principle starters (replace with your stack's specifics)
- **P1 — Measure before claiming.** Don't guess a query plan or a hot path; verify (profile,
  `EXPLAIN ANALYZE`, a timing) before asserting a cost.
- **P2 — Kill waterfalls.** Parallelize independent I/O; batch N+1 access.
- **P3 — Right-size work.** Avoid O(n²) over real n; stream/paginate large data instead of loading whole.
- **P4 — Budget the critical path.** Know the wall-clock budget (request timeout, frame budget,
  scan window) and keep the hot path inside it.
- **P5 — Cache with intent.** Cache what's stable and hot; never cache what must be fresh.

## Recast examples
- **Frontend (Next.js/React):** point this seat at the Vercel React Best Practices rules.
- **Backend/pipeline:** timeout budgets, batching, subprocess/threadpool offload, connection reuse.
- **Numerical engine (Chrollo):** vectorization vs Python loops, cache/parquet IO, avoiding
  recompute across the scan; byte-parity constraints on refactors.
