# Refactoring Reference — Carmack × Fowler

Philosophy: John Carmack. Specifics: Martin Fowler.
Stack context: Python 3.11+ deterministic detector engine (`core/`, pandas/numpy) + FastAPI/Pydantic backend (`webapp/backend/`) + React 19 / Vite frontend. SQLite archive + parquet market-data cache.

Every refactoring finding must answer: **"Will this slow us down?"** — not "is this clean?"
Fowler: "The point of refactoring is not to create 'clean code', it is purely economic — we refactor to make it faster."

In Chrollo the prime directive is *accurate visual tight-structure detection*, and the place bugs live is the numerical detector math in `core/`. Refactoring here has a second, non-negotiable obligation: **prove it changed no behavior.** The house method is **capture → fold → byte-parity compare** — and that method IS the enabling condition for everything below.

---

## The Central Question: Less Structure or Better Structure?

Carmack and Fowler both want code that minimises the gap between what the programmer thinks is happening and what actually happens. They disagree on how:

- **Fowler** closes the gap through naming, extraction, and small functions you can read like prose.
- **Carmack** closes the gap through sequential visibility, inlining, and keeping state mutations in plain sight.

**The synthesis:** extract **pure functions** freely — both philosophies approve. A detector measurement like `measure_bar_compression(base_df, box_height, atr_val)` takes frames in, returns a dict out, touches nothing — extracting it is pure win. Keep **state-mutating code** (parquet cache writes, archive INSERTs, mutating a DataFrame column in place) visible and sequential — Carmack's objection is specifically to hiding mutation behind a name.

When reviewing, ask: **is this extraction hiding state mutation, or isolating pure logic?** The first is dangerous. The second is universally beneficial — and in this engine, the second is almost everything worth extracting.

---

## Principle 1: Refactoring is economic — if it won't slow you down, leave it alone

*Fowler: "The point of refactoring is not to create 'clean code', it is purely economic."*
*Carmack: "The function that is least likely to cause a problem is one that doesn't exist."*

### The Design Stamina Hypothesis

Good internal quality pays off in **weeks, not months**. The common "we don't have time to refactor" objection is inverted. But the corollary is equally important: refactoring code you won't change again is pure waste. Fowler: "It's pointless to refactor a system you will never change, because you'll never get a payback."

In Chrollo the engine is under active, evidence-driven tuning — `core/scoring/`, `core/structure/`, the LPS layer change most weeks. That's where structural payback is real. A one-off `tools/` audit script that ran once to dissect SPHR/EQIX and will never run again is the opposite: leave it ugly.

### Reviewer filter

Before flagging any structural issue, ask:
- **Is this code likely to change?** A stable, frozen, byte-parity-locked helper is fine regardless of how it looks.
- **Is the current structure actively making changes harder?** Could the next calibration step be made without confusion?
- **Would this refactoring pay off in weeks?** If only in months, it's probably not worth flagging.

If you can't answer "yes" to at least one of the first two, don't flag it. This filter kills 50% of low-value review comments.

---

## Principle 2: Extract pure logic, keep mutations visible

*Carmack: "The real enemy addressed by inlining is unexpected dependency and mutation of state, which functional programming solves more directly and completely."*
*Fowler: Extract Function is "ninety-nine percent of the time" the right refactoring for long functions.*

### The pure function rule

- **Extracting pure functions** (no side effects, no external state): always safe, always beneficial. The detector measurements (`measure_traversal`, `lps_range_threshold`, `_ramp`) are referentially transparent — same frames in, same numbers out. Extract them, name them, test them in isolation.
- **Extracting impure functions** (yfinance fetches, parquet writes, archive INSERTs, mutating `df['ATR_10'] = ...`): context-dependent. If the extraction hides *which* DataFrame column is mutated and *when*, it's making the pipeline harder to reason about. Keep IO and in-place mutation visible in the calling flow.

### What to check

**Long functions that mix pure and impure code**
- The classic Chrollo shape: a `_evaluate_ticker` path that fetches bars (impure), trims/copies the frame, computes a dozen pure measurements, then writes an archive row (impure). The pure middle should be liftable into named helpers, leaving a readable sequence of side effects at the edges.
- Severity: **P2** if the mixing makes the function hard to modify safely

**Functions that lie about their side effects**
- A helper named like a getter that also mutates the frame in place or warms the parquet cache (Fowler: Mysterious Name meets Carmack: hidden mutation)
- Functions that look pure but mutate through a passed-in DataFrame (pandas views!) — see the copy-vs-view trap in the numerical-correctness doc
- Severity: **P2** — these are bug factories

**Excessive extraction of trivial code**
- Single-use helpers that add a name but no clarity — pure indirection
- Carmack: "if a lot of operations are supposed to happen in a sequential fashion, their code should follow sequentially." A linear detector pass reads better inline than chopped into ten one-line functions you must chase across the module.
- Severity: **P3**

---

## Principle 3: State is the primary source of bugs — minimise and contain it

*Carmack: "A large fraction of the flaws in software development are due to programmers not fully understanding all the possible states their code may execute in."*
*Fowler added Mutable Data, Global Data, and Loops as NEW smells in his 2018 edition — reflecting the same insight.*

Both identify mutable state as the root cause. Carmack pushes toward elimination (pure functions over frames). Fowler pushes toward containment.

### What to check

**Mutable Data (Fowler: new smell, high priority)**
- pandas `SettingWithCopyWarning` is this smell screaming at you: a derived column written back onto a slice that may be a view. Compute on a `.copy()` or build a new frame.
- Calculated/derived values stored as state instead of computed on access (Fowler: "particularly pungent"). In React: screener stats that could be derived from the fetched setup list, not held in a second `useState`.
- Severity: **P2** when scope is wide, **P3** when scope is local

**Global Data (Fowler: new smell)**
- The real Chrollo cautionary tale: module-level `from config import settings` read at import time. Backend cwd (`webapp/backend`) shadows the repo-root `config`, so a module-level `settings` read crashes the service boot while tests pass. **Read screener settings lazily inside functions, not at module scope.**
- Singletons holding mutable engine state across requests in the FastAPI process
- Severity: **P1** if it corrupts cross-request state or breaks boot, **P2** otherwise

**State colocation failures**
- React state living higher in the component tree than necessary (prop drilling the watchlist set through the whole card wall)
- Server data (the ranked setup list) re-duplicated into client state instead of held in one fetch/cache layer
- Severity: **P3** unless causing re-render cascades over the card grid or stale-rank bugs

---

## Principle 4: Names reveal design — bad names mask bad structure

*Fowler: "When you can't think of a good name for something, it's often a sign of a deeper design malaise. Puzzling over a tricky name has often led us to significant simplifications."*
*Carmack: values clarity of intent — through inline sequential code where operations speak for themselves.*

Fowler placed Mysterious Name **first** in his 2nd-edition smell catalog. A name isn't cosmetic — it's a correctness signal. If you can't name it clearly, you probably don't understand what it does. The Chrollo memory log is full of this paying off: `traversal_density`, `last_support_frac`, `coil_floor_pos` — once the measurement had a precise name, the gate that used it became obvious.

### What to check

**Names that lie or mislead**
- Functions whose names don't describe all their effects (especially the side effects — cache warming, archive writes)
- Boolean variables where `true`/`false` aren't obvious — `lps_in_inner` is good; a bare `flag` is not
- Generic names: `data`, `df`, `result`, `process`, `handler` — `df` is unavoidable pandas idiom, but `result` hiding "the LPS detection outcome" is masking unclear responsibility
- Severity: **P2** if the name actively misleads about behavior, **P3** if merely vague

**Comments as deodorant**
- Fowler: "When you feel the need to write a comment, first try to refactor the code so that any comment becomes superfluous."
- Comments explaining WHAT → the code should be clearer
- Comments explaining WHY → keep them. The engine NEEDS these: "don't re-add the absolute-ATR V-arm check (tight-box bias)" is load-bearing institutional memory, not deodorant.
- Severity: **P3** — flag the underlying clarity issue, not the comment

**Inconsistent vocabulary**
- Same concept, different names across the codebase (support/floor/S; LPS zone vs support shelf vs rescue)
- Drift between the engine's field name, the Pydantic response model, and the React prop for the same fact
- Severity: **P3** but compounds over time

---

## Principle 5: Smells that compound — the ones that actually slow you down

Not all smells are equal. These are the ones Fowler flags as highest-cost, filtered through the economic test.

### Feature Envy

*Fowler: "A classic case occurs when a function in one module spends more time communicating with functions or data inside another module than it does within its own module."*

Code in the wrong place. The fundamental rule: **put things together that change together.**
- A scoring function that mostly reaches into `core/structure/` internals to recompute box geometry belongs nearer the structure layer (or that geometry should be handed to it pre-computed — see Data Clumps).
- A FastAPI route handler that does heavy engine work itself instead of calling the service layer in `webapp/backend/`
- Severity: **P2** if it causes shotgun surgery, **P3** if isolated

### Shotgun Surgery

One change requires edits across many files. Fowler's counterintuitive fix: **inline first, then re-extract.** Pull the scattered logic together into one (temporarily large) place, then split along better boundaries.

- The real Chrollo hazard: **twin code paths.** The live `_evaluate_ticker` and the seed `_evaluate_at_date` must score a setup identically, but they were separate. A calibration change meant editing both, and any drift silently broke seed-recall. The fix was the **eval-twins fold** — `select_active_lps`, `descent_tail_drops`, `score_traversal_args`, `lps_range_threshold` extracted so both paths route through one helper and "can never silently diverge." A test now enforces both call the shared helpers.
- Severity: **P2** — this is exactly where velocity (and correctness) dies

### Primitive Obsession

*Fowler: "We find many programmers are curiously reluctant to create their own fundamental types... such as money, coordinates, or ranges."*

- Bare floats where a domain quantity belongs: an ATR-relative measure vs an absolute price passed as the same `float`. The ADR-tightness lesson lived here — flatness rewarded in raw price units until it was rebased ATR-relative. A `(value, units)` discipline or a small dataclass prevents unit-confusion bugs.
- In Pydantic: model the request/response shapes as typed models instead of passing loose dicts across the API boundary.
- Severity: **P3** unless causing unit-confusion bugs (**P2** — and in this engine unit confusion is a correctness bug)

### Data Clumps

*Fowler: "Consider deleting one of the data values. If you did this, would the others make any sense? If they don't, it's a sure sign that you have an object that's dying to be born."*

- The same `(S, R, base_range_threshold, base_len, swing_complete_idx)` tuple threaded through detector and gate code is a box-context object dying to be born. The fold already passes it as one `parent` tuple — a named dataclass is the next step.
- The same 3+ frame/atr/box-width args extracted in multiple eval branches
- Severity: **P3**

### Speculative Generality

*Fowler: "You get it when people say, 'Oh, I think we'll need the ability to do this kind of thing someday.'"*
*Carmack: code size is the best predictor of defects — unused generality is dead weight that breeds bugs.*

- Abstraction layers for one implementation: a "provider" interface with one yfinance adapter is justified ONLY because there's an active migration and a parity gate behind it — otherwise it's speculative.
- Config knobs with one setting; generic parameters always passed the same concrete value
- Detectors that retired rather than generalised: oscillation was rail-blind and got fully erased (column dropped), not abstracted. Deleting beat generalising.
- Fowler's YAGNI test: imagine the refactoring needed to add the feature later. If it's cheap, defer it.
- Severity: **P2** if adding significant complexity, **P3** if just unused parameters

---

## Principle 6: Architecture earns its boundaries

*Fowler: "Almost all the successful microservice stories have started with a monolith that got too big and was broken up."*
*Carmack: "The single most effective strategy for defect reduction is code reduction."*

Both argue against premature structural complexity. Every abstraction boundary is more code, more state, more places for bugs.

### What to check

**Premature modularisation**
- A repository/service/controller cathedral over a SQLite archive with a handful of tables. The `webapp/backend/` service layer earns its place because it wraps the CPU-bound engine and keeps routes thin — but don't add a second layer of indirection under it for one caller.
- Abstraction layers when there are a dozen FastAPI routes
- Severity: **P3** unless the indirection is actively causing confusion (**P2**)

**Missing boundaries where they matter**
- Fowler's test: are different parts of the code changing for different reasons? If yes, separate them. The clean split that earns its keep here: **pure measurement** (`core/structure/metrics.py`) vs **gating/scoring decisions** (`core/scoring/`). Measurements change for data reasons; thresholds change for calibration reasons. Keep them apart.
- Shared mutable state between the engine and the backend that should be independent
- Severity: **P2** if causing divergent change

**Published interfaces that shouldn't be**
- Fowler: "Don't publish interfaces inside a team." Internal `core/` helper signatures treated as frozen contracts when only the pipeline calls them.
- Exporting everything from a package `__init__` when two functions are used externally
- Severity: **P3**

### The Strangler Fig principle

For migrations: wrap and replace incrementally, never big-bang. This is doctrine in Chrollo — engine changes are "small, evidence-driven steps validated against recall/shadow guards, never big blind redesigns." The Yahoo→bulk-EOD provider migration runs behind `get_provider()` with a parity gate that blocks any vendor that changes engine reads. Strangle, measure, then cut over.

---

## Principle 7: The enabling triad — tests, parity, and refactoring are inseparable

*Fowler: "Only if you have testing, continuous integration, and refactoring can you practice simple design effectively."*
*Carmack: "The most important thing I have done as a programmer in recent years is to aggressively pursue static code analysis."*

Both want machine-verified correctness. In Chrollo this triad has a specific, battle-tested shape: **byte-parity / shadow-harness / seed-recall.**

### What to check

**Missing tests on changed code**
- Fowler: "We assume that any non-trivial code without tests is broken."
- A detector or scoring change without a seed-recall run (does the engine still fire on known winners?) is unverified, full stop.
- Severity: **P2** for changed engine code without coverage, **P1** for the detector math on the prime-directive path

**Tests coupled to implementation**
- Tests that break when you refactor without changing behavior actively discourage refactoring. Prefer golden-master / byte-parity tests over detector OUTPUT to tests that assert on internal call order.
- Severity: **P2** — these erode the enabling triad

**Determinism as static analysis**
- Carmack's static-analysis principle, applied to a numerical engine: non-determinism is the blind spot. Unstable sorts, dict-order dependence, an unseeded RNG, or a lookahead leak makes byte-parity impossible — and if you can't byte-compare, you can't safely refactor the engine at all.
- Severity: **P2** for any nondeterministic path on the detector pipeline

**Test sufficiency (Fowler's two-part test)**
- "You rarely get bugs that escape into production" — are the same misses recurring? (The parked SPHR/EQIX/CTOS calibration gaps are tracked precisely so a *cluster* of repeats triggers action.)
- "You are rarely hesitant to change some code for fear it will break things" — is there a detector nobody dares touch?
- Coverage in the upper 80s–90s is expected. Fowler: "I would be suspicious of anything like 100%."
- Severity: **P2** for fear-zones, **P3** for low coverage in stable code

---

## Principle 8: Refactoring is not restructuring — and prove it with byte-parity

*Fowler: "If somebody talks about a system being broken for a couple of days while they are refactoring, you can be pretty sure they are not refactoring."*

### The Two Hats rule

Fowler (via Kent Beck): when adding function, don't change existing code. When refactoring, don't add function. "You can only wear one hat at a time." A PR should not blend a refactor with a behavioral change — the reviewer can verify neither when they're interleaved. In this engine the line is sharp: a refactor must be **bit-identical**; a calibration change is **expected to move output** and must be validated against recall/shadow guards. Never ship them in one commit.

### The capture → fold → byte-parity method

This is the Chrollo refactor protocol, and reviewing a `core/` refactor means checking it was followed:

1. **Capture** the current output of both (or the one) code path — e.g. dump the archive rows / scoring dicts the live and seed evals produce for a fixed universe and date.
2. **Fold** the duplicated logic into a shared helper (the eval-twins helpers; the `_ramp()` DRY fold that collapsed four near-identical bonus ramps into one shape).
3. **Byte-parity compare** the post-fold output against the captured baseline. The `_ramp` fold and the box-primitives extraction were both verified bit-identical, "zero drift." If the bytes differ, it was not a refactor.

### What to check in "refactoring" PRs

- Does the PR change observable engine output? If yes, it isn't a refactor — and it needs the recall/shadow validation, not a parity claim.
- Is the system green at each commit? Refactoring should never break the build or the shadow baseline.
- Was a byte-parity / shadow comparison actually run, or merely asserted?
- Severity: **P2** for PRs labeled "refactoring" that move output without parity proof; **P1** if they move detector output silently

### Against refactoring sprints

Fowler: "In almost all cases, I'm opposed to setting aside time for refactoring." The "simplest necessary logic" cleanup passes in Chrollo work because they're tied to a concrete win (erase oscillation, DRY the ramp) and proven by parity — not a calendar slot. If a dedicated "clean up the engine" sprint is being proposed, the codebase has already drifted; flag it at the meta level.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Structural issue causing correctness bugs | Module-level `settings` read crashing boot (config-vs-cwd), silent twin-path divergence, refactor that moves detector output unproven |
| **P2 — Fix Soon** | Structure actively slowing the team down | Twin-path shotgun surgery, hidden frame mutation, feature envy, speculative abstraction, tests coupled to implementation, "refactoring" PRs without byte-parity |
| **P3 — Consider** | Hygiene that compounds over time | Vague names, box-context data clumps, minor duplication, premature abstraction, low-value extraction |

## The Overriding Filter

Before writing any finding, apply Fowler's economic test: **"Will this code slow us down?"** If the answer is "not really" or "not yet," lower the severity or don't flag it. Carmack would add: **"Is this code hiding state that will surprise someone?"** For the engine specifically, add a third: **"Can this still be byte-parity refactored?"** — if a change quietly destroys determinism, that's the expensive smell. A focused review with 6 sharp findings beats a wall of 20 nitpicks.
