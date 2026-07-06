## Context Brief — council-review drill D3/D4 on fixtures/sample.py        [TOP = highest signal]

- **Decision this run must produce:** a prioritized P1/P2/P3 finding list for `fixtures/sample.py`,
  respecting the accepted patterns in `fixtures/conventions.md`.
- **The one question each worker answers in its lane:** *In my domain, what in `sample.py` is
  wrong or risky in THIS code — and what is intentional and must NOT be flagged?*
- **Out of scope:** the rest of the Chrollo repo, the Council framework itself, style nits with no
  consequence. This is a 2-function teaching fixture, not production code.

## Landscape                                                              [MIDDLE = reference detail]

- **What this is:** `fixtures/sample.py` — two pure functions, ~12 lines:
  - `average(values)` — sums `values`, returns `total / len(values)`.
  - `last_or_none(items)` — returns `items[len(items) - 1] if items else None`.
- **Grounding (phase-1 gate):** `python -m py_compile sample.py` → PASS. It compiles; any defect is
  a **runtime** defect, not syntax.
- **Relevant settled decisions (from `fixtures/conventions.md` — DO NOT re-litigate):**
  - **AP-1 (explicit last-index access):** `items[len(items) - 1]` instead of `items[-1]` is an
    intentional readability choice. **Do NOT flag `last_or_none`.**

## Worker assignments

- **McKinney (numerical correctness)** — reads `references/quality-llm.md`. Own the boundary/empty-input
  and division behavior of `average`. Budget ~1.5k.
- **Fowler (refactoring/structure)** — reads `references/refactoring.md`. Own structural clarity and
  guard placement. Budget ~1.5k.
- **Beck (tests)** — reads `references/quality-testing.md`. Own the missing test surface (happy path +
  the untested empty-input case). Budget ~1.5k.
- **Hunt (security)** — reads `references/security.md`. Empty lane expected; return one line proving
  coverage (no untrusted input / injection / secret surface in a pure arithmetic module).
- *Empty lanes not dispatched (no surface on a 2-function pure module): Ramírez (no FastAPI/async),
  Leach (no DB/parquet), Pipeline Performance (no hot loop/IO), Dodds/Saarinen/Friedman (no UI).
  Logged, not silently dropped.*

## Hard constraints — DO NOT FORGET                                       [BOTTOM = re-surfaced signal]

- **Plain English only. NO code / schemas / config blocks** in any finding. Fixes describe what to
  change and where, not how to type it.
- **Stay in your lane.** If the lane is empty, say so in one line — that proves coverage.
- **Respect AP-1: do NOT flag `last_or_none`'s explicit `len(items) - 1` indexing.**
- Write full output to `_run/2026-07-06-2032/<persona>.md`; return ONE line to the parent.
