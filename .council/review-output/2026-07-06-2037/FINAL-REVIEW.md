# Council Review — Yahoo 429 backoff jitter (`core/pipeline/rate_limit.py` + companions)

**Run:** 2026-07-06-2037 · **Mode:** council-review on context-core · **Chair:** Carmack
**Branch:** `engine/yahoo-backoff-jitter` @ `9b92b2c`

## Scope
The 429-jitter change: `rate_limit.py::_respect_cooldown` cooldown-exit stagger, `downloads.py::_apply_backoff_jitter`
per-retry jitter, and the two new `config/settings.py` knobs. Out of scope: detector math, the token bucket
redesign. Read-only.

## Context
- Grounding gates: `py_compile` (both files) PASS; `pytest -k jitter` → 2 passed.
- Memory read first (`conventions.md`): AP-3 (lazy settings) — the lazy `from config import settings` imports
  are intentional; **not to be flagged.** EC-3 (fold twins) — considered and ruled out (see finding cluster).

## Council dispatched
Ramírez (backend/async, 3), McKinney (numerical/determinism, 2), Beck (tests, 2), Fowler (structure, 1).
Logged empty/low lanes (not dispatched): Pipeline Performance (overlaps Ramírez), Hunt (no injection/secret
surface — the change *reduces* self-inflicted DoS), Leach (no DB), Dodds/Saarinen/Friedman (no UI).

## Findings

### P2
**1. Cooldown-exit stagger doesn't re-check a cooldown re-armed while it sleeps** — `rate_limit.py:99-111`
`Council: Ramírez × Carmack — quality-backend.md P1 (operational discipline)` · cross-ref #2 (untested)
- `_respect_cooldown` breaks out of the guarded `while` loop once the window is clear, then sleeps a random
  `0..JITTER` **outside** any re-check of `_cooldown_until`. If another worker's fresh 429 calls
  `note_rate_limit()` during that stagger, this worker wakes and proceeds to `acquire()` without observing the
  newly-armed cooldown — one request slips onto Yahoo mid-cooldown, per worker per re-arm.
- Consequence: on a sustained-429 day (the exact failure this change targets) the thundering-herd guard partially
  defeats itself. **Carmack filter:** bounded — the token bucket still rate-limits the slipped request globally,
  so this is a P2 weakening of an *additional* guard, not a P1. Fix or consciously accept.
- Fix: after the stagger, re-enter the guarded `_cooldown_until` check under `_cooldown_lock`; return only when
  still clear (keep the stagger one-shot per drain so it can't livelock). `rate_limit.py`-only. **NO code emitted.**

**2. The cooldown-exit jitter (`_respect_cooldown`) has zero tests** — `rate_limit.py:95-111`
`Council: Beck × Carmack — quality-testing.md P4/P5` · cross-ref #1 (the runtime gap it would guard)
- **Validated:** no test references `_respect_cooldown` / `YAHOO_COOLDOWN_JITTER_SECONDS`; the downloads tests
  monkeypatch `downloads.random`, so they structurally cannot reach `rate_limit.random`. Half the change — and
  the `waited`-gated branch — is unproven.
- Consequence: a future refactor could invert the `waited` gate (jitter every caller) or drop the `jitter>0`
  guard and the suite stays green. It's also where finding #1 would be caught.
- Fix: behavioral test in `tests/test_rate_limit.py` injecting `rate_limit.random.uniform` + `time.sleep`
  recorders — assert (a) waited→draw within `[0,J]`, (b) no-wait→`uniform` never called, (c) `J=0`→no draw.

### P3
**3. Jitter test uses exact float `==`, valid only for the hand-picked constants** — `tests/test_fetch_health.py:393-397`
`Council: McKinney × Carmack — quality-llm.md P3 (never `==` on derived floats)`
- `== 4.0` / `== 2.0` pass only because `4.0`, `0.5`, `2.0` are exactly representable; a realistic re-parametrization
  (e.g. `wait=30`, `j=0.3` → `20.999999999999996`) would flake for a representation reason unrelated to behavior.
- Fix: assert with `math.isclose` / `pytest.approx`, or comment that exact-eq is valid *only* for these
  representable constants. (`assert wait < 45.0` is already an inequality — leave it.)

**4. Intentional un-jittered-cooldown / jittered-local-sleep redundancy is uncommented** — `downloads.py` retry site
`Council: Ramírez × Carmack — quality-backend.md P1`
- `note_rate_limit()` gets the full un-jittered wait (correct — conservative shared window) while the returned
  jittered value drives the local `time.sleep`, which may under-run the shared cooldown. `_respect_cooldown()` is
  the authoritative backstop, but that ordering invariant is unstated; a future "optimize away the redundant
  cooldown check" edit would reintroduce lockstep bursts. Fix: one-line invariant comment.

**5. `_apply_backoff_jitter` docstring implies cross-attempt monotonic growth it doesn't guarantee** — `downloads.py:92-93`
`Council: McKinney × Carmack — quality-llm.md P3 (tradeoff doc gap)`
- "the backoff still grows" is true of the base `2**attempt`, not of jittered values across attempts (a low draw
  on N+1 can dip below N). Harmless, but could mislead a future edit. Fix: soften wording to "base grows; jitter
  spreads each attempt within its own band."

**6. `_respect_cooldown` conflates wait-loop and post-wait stagger** — `rate_limit.py:95-111`
`Council: Fowler × Carmack — refactoring.md P2 (Extract Function) / P4 (names)`
- The `waited` flag carries state from the loop into a trailing conditional. Optional: extract
  `_stagger_cooldown_exit()` **if** this area is tuned again. Low value; do not block. (Fowler's LEAD call: the two
  jitters are **not** an EC-3 twin — a fraction-of-duration vs an absolute resume delay; folding them would be
  speculative generality. No finding.)

**7. Settings-source asymmetry (downloads module-level vs rate_limit lazy) is a latent config-split seam** — `downloads.py:14` vs `rate_limit.py:108`
`Council: Ramírez × Carmack — quality-backend.md P5 (config lifecycle)`
- No live defect (both resolve to one singleton today); it's the AP-3 tradeoff. A future config-reload/patch on one
  path could split the two halves of the backoff invisibly. Fix: record as an accepted seam (candidate AP), or read
  the backoff constant through the same lazy accessor — do **not** module-hoist `rate_limit.py` (reintroduces the
  boot crash AP-3 guards).

*Folded (Carmack filter / cap): Beck's "bound test doesn't show interior spread" (P3, optional — endpoints already
pin the real regressions); Ramírez's out-of-lane note that the retry loop still uses `print()` not `chrollo.*`
logging (pre-existing, untouched by this diff — mention, don't fix here).*

## Summary
| # | Finding | Severity | Expert | Fix effort |
|---|---------|----------|--------|-----------|
| 1 | Cooldown re-arm race in stagger | P2 | Ramírez | small (re-check after stagger) |
| 2 | `_respect_cooldown` jitter untested | P2 | Beck | small (one injected test) |
| 3 | Exact float `==` in jitter test | P3 | McKinney | trivial |
| 4 | Uncommented cooldown-authority invariant | P3 | Ramírez | trivial (comment) |
| 5 | Docstring overstates cross-attempt growth | P3 | McKinney | trivial (comment) |
| 6 | Wait-loop + stagger conflated | P3 | Fowler | optional |
| 7 | Settings-source asymmetry seam | P3 | Ramírez | doc-level |

Totals: 0 P1, 2 P2, 5 P3.

## Verdict
**Shipping-quality with one worth-fixing P2.** The change is small, well-bounded, and — per McKinney — the new
`random` is retry-timing only and **cannot leak into detector data** (byte-parity / seed-recall unaffected). The
single most important thing: **close (or consciously accept) the cooldown re-arm race in `_respect_cooldown`, and
add the one test that covers it** — findings #1 and #2 are the same under-covered function from two lenses. Most
critical domain: **concurrency (Ramírez)**.

**AP-3 honored:** the lazy `from config import settings` imports were flagged by **no** worker (all four called
them out as intentional). Read-before-review + the compound-memory effect both held on live code.

## Findings-Breakdown-by-Expert
| Expert | Lane | Raw | Kept |
|--------|------|-----|------|
| Ramírez | backend/async | 3 (1 P2, 2 P3) | 3 (#1, #4, #7) |
| Beck | tests | 2 (1 P2, 1 P3) | 1 (#2) + 1 folded |
| McKinney | numerical/determinism | 2 (2 P3) | 2 (#3, #5) + "determinism CLEAN" verified |
| Fowler | structure | 1 (P3) | 1 (#6) + LEAD: not-a-twin resolved |

## Validation (Core phase 10 — checked against real code)
- #1 re-arm race — CONFIRMED: `_respect_cooldown` sleeps the stagger after the loop break with no re-check.
- #2 untested — CONFIRMED via grep: zero test references to `_respect_cooldown` / `YAHOO_COOLDOWN_JITTER_SECONDS`.
- #3 float-eq — CONFIRMED: test asserts `== 4.0` / `== 2.0`.
- #4/#5/#7 — CONFIRMED against the diff (un-jittered `note_rate_limit`; "still grows" docstring; import asymmetry).
- AP-3 — CONFIRMED against all 4 files: lazy imports appear in zero findings. No lone dissenter to dismiss.
