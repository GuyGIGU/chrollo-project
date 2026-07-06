# Beck — Test Quality Review (Yahoo 429 backoff jitter)

Lane: test coverage & quality of THIS change. The change adds jitter in TWO places
(`downloads.py::_apply_backoff_jitter` and `rate_limit.py::_respect_cooldown` cooldown-exit
stagger). Only the first is tested. Below: the coverage hole, plus a quality read on the two
new bound tests.

---

## FINDING 1 — The cooldown-exit jitter (`_respect_cooldown`) has ZERO tests
- **File:** `core/pipeline/rate_limit.py:95-111` (the `waited`-gated `time.sleep(random.uniform(0.0, jitter))`);
  no covering test in `tests/test_rate_limit.py` or `tests/test_fetch_health.py`.
- **Principle:** P4 "Test what might break" (a new behavioral branch untested) + P5 "The test list is
  analysis" (missing behavioral variant) + Desiderata #11 Predictive.
- **Severity:** P2
- **What's wrong:** Half of the change — the second jitter, the whole point of which is the
  "thundering herd on cooldown exit" guard — has no direct test. The new `waited` flag introduces a
  real conditional: jitter fires ONLY when a thread actually slept through an active cooldown, and is
  skipped when the window was already clear. Neither leg of that branch is exercised. There is a
  natural home for it — `tests/test_rate_limit.py` already tests the bucket, the global ceiling, the
  disabled no-op, and ships a `reset_for_test` teardown — yet `_respect_cooldown` is not touched there
  at all (the entire cooldown wait-loop, pre-existing, is also untested, but the NEW jitter is the
  in-scope gap).
- **Consequence:** The behavioral contract the brief states this jitter must honor — "each worker
  sleeps an extra random 0..JITTER after the window clears, and does NOT when it never waited" — is
  unproven. A future refactor could invert the `waited` gate (jitter every caller, including the
  fast-path no-wait case, adding latency to every throttled request) or drop the `jitter > 0` guard,
  and the suite stays green. Note the two jitters read from DIFFERENT `random` module objects
  (`downloads.random` vs `rate_limit.random`); the `downloads` tests monkeypatch `downloads_module.random`,
  so they provably cannot cover this path even incidentally.
- **Fix:** Add a behavioral test in `tests/test_rate_limit.py`. Inject the clock/RNG rather than
  sleeping for real (Desiderata: Fast + Deterministic): monkeypatch `rate_limit.random.uniform` to a
  recording lambda and `rate_limit.time.sleep` to a recorder. Assert two variants: (a) when a cooldown
  is active (set via `note_rate_limit`) the exit jitter is drawn and slept within `[0, JITTER]`; (b)
  when no cooldown is active (`waited` stays False) `random.uniform` is NEVER called — the fast path
  pays no jitter. A third cheap variant: `YAHOO_COOLDOWN_JITTER_SECONDS = 0` draws no jitter. Reset
  `_cooldown_until` via the existing `reset_for_test` in teardown.

---

## FINDING 2 — `test_backoff_jitter_stays_within_bounds` pins the endpoints but not the jitter's spread
- **File:** `tests/test_fetch_health.py:386-397`
- **Principle:** P2 "Behavioral & structure-insensitive" + P6 "Assertions are the test" (mutation
  resistance) — read against the Carmack filter, not as an over-ask.
- **Severity:** P3
- **What's wrong:** The test monkeypatches `random.uniform` to return its bound `b` (max draw) and `a`
  (min draw), then asserts the result equals `wait` and `wait*(1-j)` respectively. That is a genuinely
  good discriminating pair — it pins the low and high edges of `[wait*(1-j), wait]` and the `jitter=0`
  exact case, and it WOULD fail if the formula's fixed fraction or the multiplier were wrong. The one
  soft spot: because `uniform` is stubbed to return a bound rather than a value strictly inside
  `(a, b)`, the test never demonstrates that a mid-range draw lands strictly inside the interval — a
  buggy implementation that ignored the random component and always returned one endpoint would still
  pass. This is minor given the two-endpoint pinning already present.
- **Consequence:** Low. A formula that collapsed the random term to a constant offset could slip
  through, but the endpoint assertions catch the likely real regressions (wrong fixed fraction, sign
  flip, jitter applied to the whole wait). Not worth heavy investment — this is the low-risk,
  duration-only jitter, and the endpoints are the behavior that matters.
- **Fix:** Optional. If tightening is wanted, add one assertion with `uniform` stubbed to a strictly
  interior value (e.g. the midpoint of its passed `a, b`) and assert the result is `> wait*(1-j)` and
  `< wait` — proving the random component actually moves the result, not just the endpoints. Keep it
  as a single extra assert in the same test; do not split.

---

## Not flagged (in-lane, deliberately)
- **Monkeypatching `random.uniform` for determinism is CORRECT, not a smell.** This is exactly
  Principle 8 / Desiderata #3: "code that uses random numbers should be passed those values by their
  unit tests." Both new tests inject the RNG at the boundary rather than asserting on a real random
  draw — that is the right call and pins behavior (the bounds), not implementation. No finding.
- **`test_backoff_jitter_preserves_shared_cooldown_value` (`:400-411`) is a strong, in-scope test.**
  It asserts the shared cooldown receives the UN-jittered `45.0` while THIS worker's own retry sleep is
  jittered shorter (`wait < 45.0`) — precisely the cross-cutting invariant that the two jitters must
  NOT contaminate the global window. `note_rate_limit` is faked as a pure recorder (boundary, not an
  internal collaborator), mock count is 1, assertions are specific and mutation-resistant. Exemplary;
  no finding.
- **`assert wait < 45.0` is an inequality, not a naked float `==`.** Under the min-draw stub the exact
  value is knowable, but the inequality is the behaviorally-meaningful claim ("jittered shorter than the
  shared window") and is robust to the fixed-fraction constant. Not a float-equality defect.
- **The tests co-committed with the change / no red step** (P1 signal, P3 severity): the jitter
  helpers and their tests landed together, so the red step was structurally skipped. But the expected
  values here are human-reasoned interval endpoints (`wait`, `wait*(1-j)`, `0`), NOT
  implementation-artifact floats copied from output — so the P1 "expected values derived from
  implementation" concern does NOT apply. Logged as a signal only; not a finding.

---

**Summary:** 1×P2 (untested cooldown-exit jitter — the real gap), 1×P3 (bound test could show interior
spread; low value). The `downloads.py` jitter is well-tested and the shared-cooldown invariant test is
exemplary; the hole is entirely on the `rate_limit.py` side the new tests structurally cannot reach.
