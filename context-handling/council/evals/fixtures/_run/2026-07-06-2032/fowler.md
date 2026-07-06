# Fowler — Refactoring / Structure Review of `fixtures/sample.py`

Lane: structural clarity, guard placement, simplicity, naming.
Not my lane: the empty-input division semantics of `average` (McKinney), the missing tests (Beck).

## Summary

This is a 12-line, two-function pure module. Applying the Carmack economic filter
("will this slow us down?" / "is this hiding surprising state?"), the structure is
essentially clean. Both functions are referentially transparent, sequential, and
readable. There is no hidden mutation, no twin-path divergence, no feature envy, no
data clump, and no premature abstraction to flag.

One genuinely structural observation is on the record below (guard placement), kept at
P3 and deliberately not overstated, because the underlying empty-input behavior is
McKinney's call, not mine — my point is only about *where a guard would structurally
live*, not what the numerical answer should be.

---

FINDING:
- Title: `average` has no early guard clause for the empty case, so its structure has no place for the caller-contract decision to live
- File: sample.py:4-8
- Principle: Principle 3 — State / control-flow containment (guard placement); severity-lowered per Principle 1 (economic filter) and the Overriding Filter
- Severity: P3
- What's wrong: `average` runs straight into the accumulate-then-divide sequence with no leading guard, so the empty-input path is decided implicitly by `len(values)` reaching zero at the final line rather than by an explicit, visible clause at the top of the function.
- Consequence: The function has no structural "slot" where the empty-input contract (raise, return None, or return 0) can be expressed, so whatever decision McKinney's lane lands on will have nowhere clean to sit and each caller re-derives the contract.
- Fix: Add a single early guard clause at the top of `average` that handles the empty input explicitly before the loop; leave the exact returned/raised value to the numerical-correctness lane. Do not restructure the loop itself — the accumulate-and-divide sequence is fine as-is.

---

## Explicitly NOT flagged (coverage proof)

- `last_or_none` line 12 — `items[len(items) - 1]` is intentional per AP-1; not flagged.
- The `for`-loop accumulator in `average` — a plain sequential sum; inlining/extraction
  would add indirection with no clarity gain (Principle 2, excessive extraction). Leaving it.
- The `# BUG (D3)` divide-by-zero on line 8 — that is McKinney's numerical lane; I note it
  only to hand off, not to flag structurally.
- No naming issues: `average`, `last_or_none`, `values`, `items`, `total` are all accurate
  and non-misleading (Principle 4).
