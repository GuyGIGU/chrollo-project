# evals/fixtures/

Tiny seeds for the behavioral drills D3 (bug caught) and D4 (memory respected). Keep them small —
a council review of a 40-line fixture should be fast and unambiguous.

## `sample.py` — seeded bug (D3)
Contains one deliberate correctness bug and one intentional-by-design choice:

```python
def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)          # BUG (D3): ZeroDivisionError on empty input

def last_or_none(items):
    return items[len(items) - 1] if items else None   # intentional (D4 / AP-1)
```

- **D3 target:** `average` divides by `len(values)` with no empty-guard → a review must flag this
  (McKinney/Fowler/Beck depending on roster), P1/P2, with a "guard the empty case" fix, no code.
- **D4 target:** `last_or_none` uses `len(items) - 1` indexing instead of `items[-1]` **on purpose**
  (see AP-1 below). A review must NOT flag it.

Create `sample.py` with the two functions above when running the drills.

## `conventions.md` — seeded memory (D4)
Place this at the fixture root so the review reads it first:

```markdown
# Project Conventions
## Accepted Patterns
### AP-1: explicit last-index access
**Pattern:** `items[len(items) - 1]` is used instead of `items[-1]` for readability in teaching code.
**Origin:** seeded for eval D4.
**Rationale:** intentional style choice — do not flag.
```

**Pass condition for D4:** `last_or_none` is absent from the findings; `average` is present.
