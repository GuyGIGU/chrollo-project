# McKinney — Numerical / Data Correctness Findings

Lane: numerical / data correctness (boundary, empty-input, division, NaN/inf, float, dtype).
Target: `average` in `fixtures/sample.py`.

---

FINDING:
- Title: `average` divides by zero on empty input
- File: fixtures/sample.py:4-8
- Principle: Off-by-one / empty-slice and boundary edge cases (Principle 4)
- Severity: P1 (bug/correctness)
- What's wrong: When `values` is empty the loop leaves `total` at zero and the return divides by `len(values)`, which is zero, so the call raises ZeroDivisionError instead of returning a defined result.
- Consequence: Any caller that reaches `average` with an empty sequence — an empty slice, a fully-filtered window, a base with no bars — crashes rather than degrading gracefully.
- Fix: Add an explicit empty-input guard at the top of `average` that returns a defined sentinel (e.g. None) before the division, mirroring the "return the explicit empty result" pattern the reference doc calls mandatory for length-zero slices.

---

FINDING:
- Title: `average` can propagate or return NaN/inf without quarantine
- File: fixtures/sample.py:4-8
- Principle: NaN and inf propagate silently — quarantine them at the boundary (Principle 2)
- Severity: P2 (silent mis-measurement)
- What's wrong: The running sum accepts any element unfiltered, so a single NaN in `values` poisons the total and the returned mean is NaN, and an inf element yields an inf mean — neither is rejected or flagged at the boundary.
- Consequence: A downstream gate comparing this mean against a threshold silently fails (NaN compares False; inf compares False the wrong way), so a setup is dropped or mis-ranked with no error surfaced.
- Fix: Before summing, filter non-finite elements (or assert a valid count) so NaN/inf cannot flow into the returned mean, matching the finite-filtering guard the reference doc cites for "needs N valid points" logic.

---

FINDING:
- Title: `average` sums via a Python loop with no dtype discipline
- File: fixtures/sample.py:4-8
- Principle: Dtype correctness — int/float/object surprises (Principle 6)
- Severity: P3 (clarity / hygiene)
- What's wrong: `total` is seeded as an integer and accumulated element-by-element, so the output dtype and any accumulated float drift depend entirely on what the caller passes; an object-dtype or stringified element would raise or concatenate rather than average.
- Consequence: The result type is caller-dependent and an iterative sum accumulates last-bit float error, which can nudge a borderline ranking; over numeric data a single vectorized mean would be clearer and drift-free.
- Fix: If this ever moves beyond the teaching fixture, cast inputs to float at the boundary and prefer a single mean over numeric data rather than a Python `+=` loop, so dtype and reduction order are pinned.

---

Note: `last_or_none` NOT flagged — its explicit `len(items) - 1` indexing is accepted per AP-1.
