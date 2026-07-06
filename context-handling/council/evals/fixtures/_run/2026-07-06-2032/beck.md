# Beck — Test-Quality Seat Findings

Lane: test coverage and testability of `fixtures/sample.py` (`average`, `last_or_none`).
I complement the correctness seat (McKinney): I flag the *missing tests* that would have
caught the empty-input defect and pin the happy path — I do not re-file the division bug itself.

AP-1 respected: `last_or_none`'s explicit `len(items) - 1` indexing is intentional and NOT flagged.

---

FINDING:
- Title: No test for the empty-input boundary of `average`
- File: sample.py:4-8 (the untested `average([])` case)
- Principle: Principle 5 — Specify tests as behavioral variants (the test list is analysis); reinforced by Principle 4 — Test what might break
- Severity: P1
- What's wrong: The single most likely-to-break path — calling `average` with an empty
  sequence, which hits `len(values)` as a divisor — has no test enumerating it. Beck's
  minimum test list (basic case + failures + missing data + boundary) leaves the "missing
  data / empty" variant completely uncovered here.
- Consequence: The defect on the return line ships undetected; the first empty batch of
  `values` in real use raises at runtime instead of being caught by a red test up front.
- Fix: Add a boundary test in the module's test file that calls `average` with an empty
  input and pins the agreed-on contract for that case (a defined return value or a
  specific, asserted exception). Writing this test first is what turns the latent defect
  into a visible red step.

FINDING:
- Title: No happy-path test pins `average` on a known, hand-reasoned value
- File: sample.py:4-8 (the un-exercised canonical case)
- Principle: Principle 5 — the missing happy-path/fire test; and Principle 6 — Assertions are the test
- Severity: P2
- What's wrong: The canonical "fires correctly" case — averaging a small list whose mean
  is knowable by hand — is not asserted anywhere. Nothing proves the function returns the
  right number for ordinary input, only that it compiles.
- Consequence: A future edit to the accumulation loop or the divisor could silently change
  the returned mean and no test would go red; the function's core behavior has zero
  regression protection.
- Fix: Add a happy-path test that averages a short fixed list and asserts the exact
  independently-reasoned mean (not a value copied from running the function). Because the
  result is a float, assert within a small tolerance rather than on naked `==`.

FINDING:
- Title: No happy-path or empty-input tests pin `last_or_none`'s two branches
- File: sample.py:11-12 (both branches untested)
- Principle: Principle 5 — enumerate behavioral variants (non-empty vs empty); Principle 6 — meaningful assertions
- Severity: P2
- What's wrong: Neither branch of `last_or_none` is covered — the non-empty case (returns
  the final element) and the empty case (returns `None`) are both un-asserted. This is a
  coverage note on the branching behavior only; the AP-1 indexing style itself is accepted
  and not in scope.
- Consequence: A regression that returns the wrong element or breaks the empty-guard would
  pass CI unnoticed, since no test discriminates working from broken behavior here.
- Fix: Add two small behavioral tests — one asserting the last element is returned for a
  known non-empty list, one asserting `None` is returned for an empty input. Assert the
  concrete expected values, not merely that the result is-or-isn't `None` in a vague way.

---

Summary: 3 findings — P1: 1, P2: 2. The P1 (missing empty-input boundary test for
`average`) is the test that would have caught the division defect the correctness seat
owns; the P2s pin the two happy paths and `last_or_none`'s branches that currently have no
regression protection.
