# McKinney — Numerical Correctness & Determinism review

**Change under review:** Yahoo 429 backoff jitter (branch `engine/yahoo-backoff-jitter`, HEAD `9b92b2c`).
**Lane:** jitter float formula & bounds, clamp of the jitter fraction, `random` determinism / byte-parity /
seed-recall leakage, float-equality in the assertions. NOT thread-safety, test structure, or refactoring.

Bottom line: **the numerical core is correct and the `random` cannot leak into detector data.** The formula
produces the advertised bounds, the fraction is properly clamped, and every `random` draw feeds only a
`time.sleep` — never a cached, archived, or compared value. I have one P3 (a latent fragility in the exact
float-equality assertions that only holds because of the specific hand-picked constants) and one P3
documentation-gap note. No P1/P2 in my lane.

---

## Verified correct (so the next reviewer doesn't re-derive it)

- **Bounds are exactly as advertised.** `_apply_backoff_jitter` (downloads.py:89-97) computes
  `wait*(1-j) + U(0, wait*j)`. With the draw in `[0, wait*j]` the result lies in `[wait*(1-j), wait]` — the
  backoff floor never collapses below `wait*(1-j)` and never exceeds the original `wait`. Correct.
- **`wait` is always non-negative at every call site.** `_retry_wait_seconds` seeds `wait = 2**attempt` with
  `attempt >= 1` (so `>= 2.0`), optionally raised by `max(wait, YAHOO_RATE_LIMIT_BACKOFF_SECONDS)`. It is never
  negative, so `random.uniform(0.0, wait*j)` never receives an inverted interval and the bounds never flip.
- **The jitter fraction is properly clamped to `[0, 1]`** via `min(max(float(...), 0.0), 1.0)`, and
  `jitter <= 0.0` short-circuits to the raw `wait`. A settings value of `2.0` or `-1` cannot corrupt the
  bounds; a mis-entered fraction degrades to "no jitter" or "full jitter," never to a negative sleep.
- **The cooldown-exit jitter is bounded the same way.** `rate_limit.py::_respect_cooldown` (line 111) sleeps
  `random.uniform(0.0, jitter)` only when `jitter > 0`, so the extra stagger is always in `[0, jitter]` and can
  never be negative. `note_rate_limit` clamps its own input with `max(float(seconds), 0.0)`.

## Determinism / byte-parity (the central lane question): CLEAN

The introduced `random` is **retry-timing only** and cannot reach any compared surface:

- In `downloads.py`, the jittered value is returned by `_retry_wait_seconds` and consumed **exclusively** by
  `time.sleep(wait)` in the two retry branches. It is not stored, not written to the parquet, not passed to any
  metric.
- The shared cooldown deliberately receives the **un-jittered** full wait (`note_rate_limit(wait)` on
  downloads.py:105, and the fixed-`BACKOFF_SECONDS` note on line 208), so the global 429 window is
  deterministic regardless of the per-worker draw. The test on lines 400-411 pins this.
- In `rate_limit.py`, the cooldown-exit `random.uniform` feeds only `time.sleep`; `_cooldown_until` is set from
  `time.monotonic()` + a clamped seconds value, never from `random`.

Therefore the unseeded module-level `random` — which would be a **P1** under quality-llm.md Principle 7 if it
touched detector math — is correct **here** because it governs wall-clock retry pacing, not a measurement. It
changes *when* a request is re-issued, not *what number the engine computes*. Byte-parity of detector output,
the shadow harness, and seed-recall are all unaffected. This matches the brief's framing (affects retry TIMING
only) and does not warrant a finding.

---

## FINDING 1 — Exact float-equality assertions survive only by hand-picked constants

- **File:** `tests/test_fetch_health.py:393-397` (`test_backoff_jitter_stays_within_bounds`)
- **Principle:** quality-llm.md **P3** (Principle 3 — never compare ratios/derived floats with `==`; here it is
  the assertion side of that principle rather than the engine side, so it is hygiene, not a live miscompare).
- **Severity:** **P3**
- **What's wrong:** The test asserts the jittered wait `== 4.0` and `== 2.0` using exact float equality against
  the output of `wait*(1-j) + draw`. This passes *today* only because every operand was chosen to be exactly
  representable in binary floating point: `wait = 2**2 = 4.0`, `j = 0.5`, so `4.0*0.5 = 2.0` and `2.0 + 2.0 =
  4.0` are all bit-exact. The equality is not testing a tolerance; it is relying on the arithmetic landing on a
  representable value. If anyone later re-parametrizes this test with a "realistic" backoff/fraction (e.g. the
  live defaults produce `wait = 30`, or a `jitter` like `0.3`), `30.0*(1-0.3) = 20.999999999999996` and the
  `==` assertion would flake or fail even though the code is correct — turning a green determinism guard into a
  spurious red.
- **Consequence:** Latent brittleness, not a current defect. A future edit to the constants (very plausible when
  the live `YAHOO_RATE_LIMIT_BACKOFF_SECONDS = 30` path is exercised) breaks the test for a floating-point
  representation reason unrelated to the behavior under test, and the next author may "fix" it by loosening the
  wrong thing.
- **Fix (what & where):** In these three assertions, compare against the bound with an explicit tolerance
  (`math.isclose` / `pytest.approx`) instead of `==`, OR add a one-line comment at
  `test_fetch_health.py:391-397` stating that the exact-equality assertions are valid **only because `4.0` and
  `0.5` are exactly representable** and that any re-parametrization must switch to an approximate compare. The
  companion test's `assert wait < 45.0` (line 411) already uses an inequality and is fine — leave it.

---

## FINDING 2 — Formula's "still-grows" claim is unstated at the cross-attempt level (doc gap)

- **File:** `core/pipeline/downloads.py:89-106` (`_apply_backoff_jitter` docstring / `_retry_wait_seconds`)
- **Principle:** quality-llm.md **P3** (conscious-tradeoff documentation gap).
- **Severity:** **P3**
- **What's wrong:** The docstring says "the backoff still grows, it just spreads," which is true of the
  *un-jittered* base (`2**attempt`) but is **not guaranteed of the jittered values across consecutive
  attempts**: with `jitter = 0.5` a lucky low draw on attempt N+1 (`2**(N+1) * 0.5`) can equal the base of
  attempt N (`2**N`), so a jittered attempt-2 wait can be numerically *below* an un-lucky jittered attempt-1
  wait. This is intentional and harmless (the whole point is to de-synchronize workers, and the shared cooldown
  still enforces the real floor), but the claim as written could mislead a future reader into assuming
  monotonic per-worker growth and "simplifying" the jitter away or tightening it.
- **Consequence:** No runtime effect. Purely a comprehension hazard that could seed a wrong future edit.
- **Fix (what & where):** Soften the docstring wording at `downloads.py:92-93` to say the *base* backoff grows
  and the jitter only spreads each attempt's wait within its own `[wait*(1-j), wait]` band — i.e. drop the
  implication of strict cross-attempt monotonicity. Documentation-only; no code behavior change.

---

## Out-of-lane items I deliberately did NOT flag

- The lazy `from config import settings` reads inside `rate_limit.py` functions — **AP-3, intentional.**
- The `downloads.py` module-level `from config import settings` vs `rate_limit.py` lazy read asymmetry —
  operational/import concern, **Ramírez's lane** (backend), not numerical.
- The `waited`-flag control flow and whether the two jitters are twins — **Fowler's lane**; and the brief
  already settles they are NOT EC-3 twins (one jitters a duration, the other staggers resume timing — different
  units, different math, correctly separate).
- The absence of a direct test for the `rate_limit.py` cooldown-exit jitter path — **Beck's lane** (coverage).
- Thread-safety of `_cooldown_until` / the token bucket — **Ramírez's lane.**

## Carmack filter applied

Both my findings are P3 hygiene. There is **no** wrong-number, no silent leak, no non-determinism reaching a
compared surface, and no unbounded/negative sleep in this change. At this pipeline's scale the jitter is a
correct, well-bounded operational-timing tweak; I am not manufacturing a P1/P2 where the numerics are sound.
