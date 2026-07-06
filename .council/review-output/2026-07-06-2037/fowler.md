# Fowler — Structure & Simplicity (refactoring lane)

Council Review 2026-07-06-2037 — Yahoo 429 backoff jitter
Scope: `core/pipeline/rate_limit.py::_respect_cooldown` + its `waited` flag, naming, and the
twin-path question on the two jitter helpers. NOT thread-safety, numerics, or tests.

---

## LEAD VERDICT ON THE ASSIGNED QUESTION: the two jitters are NOT a twin (EC-3 does not apply)

`downloads.py::_apply_backoff_jitter(wait)` and the cooldown-exit stagger in
`rate_limit.py::_respect_cooldown` are **legitimately distinct**, not a twin code path to fold.
No finding. Justification (this is the seat's headline call, so I state it in full):

- **They compute different shapes from different inputs.** `_apply_backoff_jitter` takes a duration
  and returns a value in `[wait*(1-j), wait]` — it *shrinks a fixed backoff downward* by a random
  fraction, keeping a `(1-j)` floor so the backoff still grows across retries. The cooldown-exit
  stagger takes no duration and *adds* an absolute random delay drawn from `[0, seconds]` on top of a
  zero baseline. One is a proportional band around a moving anchor; the other is an absolute band from
  zero.
- **Their settings are different types with different meaning.** `YAHOO_BACKOFF_JITTER` is a
  dimensionless fraction (0.5); `YAHOO_COOLDOWN_JITTER_SECONDS` is an absolute duration (2.0 s).
  Folding them would force one unit onto both and reintroduce the primitive-obsession/unit-confusion
  hazard the reference warns about.
- **EC-3's trigger is absent.** EC-3 folds logic that *must agree* across sites (eval-twins,
  depth/coverage predicates) — a silent divergence would be a correctness bug. Here there is no
  invariant that these two must produce the same number; they intentionally serve two different
  points in the flow (spreading a *retry backoff duration* vs staggering *resume timing after a shared
  pause*). Making them share an impl would be coupling for its own sake, not preventing drift. The
  context-brief's own read (EC-3 note) matches this conclusion.

Carmack filter: folding these would ADD an abstraction (a shared jitter helper with a mode/units
parameter) to serve two callers that legitimately differ — that is speculative generality, the
opposite of what the filter rewards. Leave them separate.

---

## FINDINGS

### FINDING 1 — `_respect_cooldown` conflates "wait loop" and "post-wait stagger" in one function
- **File:** `core/pipeline/rate_limit.py:95-111`
- **Principle:** Refactoring P2 — Extract pure logic / small functions you can read as prose
  (Extract Function); also P4 — Names reveal design.
- **Severity:** P3
- **What's wrong:** The function does two conceptually separate things: (a) block while the shared
  cooldown window is open (the `while True` loop over `_cooldown_until`), and (b) *iff* it actually
  blocked, sleep an extra random stagger on exit. The `waited` boolean exists solely to carry state
  from phase (a) into phase (b). The docstring already has to describe two behaviors joined by "then".
  This is the classic shape where a name for the second half ("stagger the cooldown-exit resume")
  would make the code read as two clear steps instead of one loop with a trailing conditional.
- **Consequence:** Minor. The reader must hold the `waited` flag in their head across the loop to see
  why the stagger sometimes fires and sometimes doesn't. It is 17 lines and self-contained, so the
  cost is small — but if the cooldown logic is tuned again (this is an actively-tuned Yahoo-hardening
  area per the memory log), the coupling of "did I wait" to "should I stagger" is the part someone
  will have to re-read.
- **Fix (what & where, not how):** Optional, low-value. If touched again, lift the cooldown-exit
  stagger into a small named helper in the same module (e.g. a `_stagger_cooldown_exit()` that reads
  the seconds setting and sleeps) and call it from `_respect_cooldown` only on the `waited` branch.
  That names the second behavior and lets the main function read as "wait out the window, then stagger
  the resume." Do NOT fold it with `_apply_backoff_jitter` (see LEAD VERDICT). Given the file is 142
  lines and the function is already readable, I would not block on this — it is a P3 "consider," not a
  "fix."

---

## APPLIED THE CARMACK ECONOMIC FILTER — what I deliberately did NOT flag

- **The `waited` flag itself.** It is a plain, correctly-named boolean whose true/false meaning is
  obvious ("did we actually block?"). Per P4 that is a *good* boolean name, not a bare `flag`. The
  control flow (break out of the loop, then a single guarded post-step) is linear and visible in the
  Carmack sense — no hidden mutation, no cross-function state. Not a finding.
- **The lazy `from config import settings` reads** inside `_respect_cooldown` / `throttle` /
  `download_workers` — AP-3, intentional (cwd-shadow boot guard). Not flagged.
- **`_respect_cooldown` reading the setting after the loop rather than before.** Reading it only on
  the `waited` branch is a deliberate micro-optimization (skip the import on the common no-wait path)
  and is behavior-neutral. Not a smell worth a finding.
- **`random` in the pipeline / determinism.** In-lane only structurally: this randomness affects retry
  *timing*, never a value that reaches an archived/compared detector output, so it does not threaten
  the byte-parity refactor guard (P8). The determinism question proper is McKinney's lane; I note only
  that no structural boundary is crossed here.
- **Naming of the new settings.** `YAHOO_BACKOFF_JITTER` (fraction) vs `YAHOO_COOLDOWN_JITTER_SECONDS`
  (the `_SECONDS` suffix disambiguates the unit) — the vocabulary is consistent and the units are
  self-documenting. Not a finding.

Net: one P3 consideration, no P1/P2. The change is small, well-named, and does not degrade the file's
structure; the headline call is that the two jitters are correctly kept distinct.
