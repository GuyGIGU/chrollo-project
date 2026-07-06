## Context Brief — council-review: Yahoo 429 backoff jitter                [TOP = highest signal]

- **Decision this run must produce:** prioritized P1/P2/P3 findings for the 429-jitter change,
  centered on `core/pipeline/rate_limit.py` (+ its companion edits in `core/pipeline/downloads.py`
  and `config/settings.py`).
- **The one question each worker answers:** *In my lane, is this concurrency/jitter change correct,
  safe, and well-tested in THIS pipeline — and what here is intentional and must NOT be re-flagged?*
- **Out of scope:** the detector math (`core/structure`, `core/scoring`), the rest of `downloads.py`
  beyond the jitter, redesigning the token bucket. **Read-only review — do NOT run the scan, boot the
  backend, or touch the broker.**

## Landscape                                                              [MIDDLE = reference detail]

- **What this is:** a process-global token-bucket throttle + shared Yahoo-429 cooldown for outbound
  yfinance requests, used by the screener's download `ThreadPoolExecutor` (one scan subprocess under
  `SCAN_LOCK`). File: `core/pipeline/rate_limit.py` (~142 lines).
- **The change (branch `engine/yahoo-backoff-jitter`, HEAD `9b92b2c`):** adds TWO independent jitters
  so many workers rate-limited at once don't retry in lockstep:
  1. `downloads.py::_apply_backoff_jitter(wait)` — randomizes the lower `YAHOO_BACKOFF_JITTER` fraction
     of each retry backoff; result in `[wait*(1-j), wait]`. The shared cooldown `note_rate_limit()`
     still receives the **un-jittered** full wait.
  2. `rate_limit.py::_respect_cooldown()` — after the shared cooldown window clears, each worker sleeps
     an extra random `0..YAHOO_COOLDOWN_JITTER_SECONDS` (a "thundering herd on cooldown exit" guard),
     gated by a new `waited` flag.
  New settings: `YAHOO_BACKOFF_JITTER = 0.5`, `YAHOO_COOLDOWN_JITTER_SECONDS = 2.0`.
- **Grounding (phase-1 gates):** `py_compile` both files → PASS; `pytest -k jitter` → **2 passed**.
  Tests monkeypatch `random.uniform` for determinism and assert the bounds + that the shared cooldown
  keeps the un-jittered value.
- **Coverage note (for the tests lane):** the added tests exercise `downloads.py::_apply_backoff_jitter`
  only; the `rate_limit.py` cooldown-exit jitter path has **no direct test**.
- **Relevant settled decisions (conventions.md — DO NOT re-litigate):**
  - **AP-3:** per-call registry + **LAZY settings reads** (read settings at call time, not module-level)
    are INTENTIONAL — they avoid the backend-cwd-shadows-repo-`config` boot crash. The repeated
    `from config import settings` inside functions in `rate_limit.py` IS this pattern. **DO NOT flag it.**
  - **EC-3:** fold twin code paths — logic that must AGREE across sites lives in one shared impl.
    (Consider whether the two jitters are twins — they are NOT: one jitters a *duration*, the other
    staggers *resume timing*.)
  - The engine's determinism / byte-parity / seed-recall guards protect DETECTOR output; consider
    whether introducing `random` here can leak into archived/compared data (it affects retry TIMING only).

## Worker assignments

- **Ramírez (backend/async)** → `references/quality-backend.md`: thread-safety of `_cooldown_until`
  under `_cooldown_lock`, the token-bucket correctness, the module-level-vs-lazy settings asymmetry
  between `downloads.py` and `rate_limit.py`, operational-vs-programmer error discipline. Budget ~2k.
- **McKinney (numerical/determinism)** → `references/quality-llm.md`: the jitter float formula & bounds,
  `random` in the pipeline, determinism/byte-parity implications (can `random` leak into compared data?),
  float-equality in the assertions. Budget ~2k.
- **Beck (tests)** → `references/quality-testing.md`: coverage of the change — especially the UNTESTED
  `rate_limit.py` cooldown-exit jitter — and the quality of the monkeypatched bound tests. Budget ~2k.
- **Fowler (structure)** → `references/refactoring.md`: the `waited`-flag control flow clarity, whether
  the two jitter helpers are a twin-path (EC-3) or legitimately distinct, naming. Budget ~2k.
- *Empty/low lanes logged, not dispatched (surface overlaps or absent): Pipeline Performance (throughput
  angle, overlaps Ramírez here), Hunt (no injection/secret surface — the change REDUCES self-inflicted
  DoS), Leach (no DB), Dodds/Saarinen/Friedman (no UI).*

## Hard constraints — DO NOT FORGET                                       [BOTTOM = re-surfaced signal]

- **Plain English only. NO code / diffs / config blocks** in findings. Fixes say what & where, not how to type it.
- **Stay in your lane.** Empty lane → one honest line (proves coverage).
- **RESPECT conventions.md:** do NOT flag the lazy `from config import settings` imports (AP-3). Do not
  re-flag any accepted pattern.
- **Read-only.** Do NOT run the scan, boot the backend (`uvicorn`/`start_dashboard`), or touch the broker.
- Apply the **Carmack filter**: a real problem in THIS pipeline at THIS scale, or pattern-matching?
- Read `core/pipeline/rate_limit.py` (full) and `conventions.md` first. Write full output to
  `.council/review-output/2026-07-06-2037/<persona>.md`; return ONE line to the parent.
