# Test Quality Reference — Carmack × Beck

Philosophy: John Carmack. Testing expertise: Kent Beck (creator of TDD, co-creator of JUnit, author of Test Desiderata).
Stack context: Chrollo — a deterministic Python (pandas/numpy) detector engine in `core/`, a FastAPI + Pydantic backend (`webapp/backend/`), a SQLite archive + parquet market-data cache, and a React 19 + Vite frontend. Tests run on **pytest**. The crown-jewel tests are Chrollo's own battle-tested patterns: **seed-recall regression**, **shadow-harness baselines** (`tests/baselines/`), and **byte-parity / determinism** checks for refactors. Frontend testing is deliberately light (eslint + occasional React Testing Library). The engine is fully deterministic — there is no LLM, so non-determinism enters only through floating-point, ordering, and data drift, not generation.

Every finding must describe the **concrete consequence** — not just "this test is bad."
This doc covers: test quality auditing, test specification, mock discipline, behavioral coverage, and the specific failure modes of AI-generated tests. It powers two skill modes: **audit** (evaluate existing tests) and **specify** (write test specifications for new code).

---

## Principle 1: The red step is the proof — a test that never failed proves nothing

*Carmack: "If a mistake is possible, it will eventually happen."*
*Beck: "Quickly add test → Run all tests and see the new one fail → Make a little change → Run all tests and see them all succeed → Refactor." On skipping the red step: "Copying actual, computed values & pasting them into the expected values of the test — that defeats double checking, which creates much of the validation value of TDD." On AI agents: "I'll just change the test. No, stop it... No, you can't do that because I'm telling you the expected value. I really want an immutable annotation that says, no, no, this is correct. And if you ever change this, I'm going to unplug you."*

The red step answers one question: does this test actually fail when the behavior is absent? Without seeing red, there is no evidence the test discriminates between working and broken code. When AI generates a detector tweak and its test simultaneously, the red step is structurally impossible — the test and implementation are co-created, so the test may be a syntactic restatement of `metrics.py` rather than an independent check of the desired structure read.

### What to check

**Audit mode: expected values derived from implementation**
- Are expected values independently reasoned from the desired chart behavior, or copied from the detector's actual output? A test that asserts `box.traversal_density == 0.4732891` after pasting in whatever the function happened to print is tautological — it passes by construction, not by verification. The honest version constructs a synthetic frame whose geometry *must* yield a known density (e.g. exactly 2 rail-to-rail traversals over 5 swings) and asserts on the reasoned value.
- The signature: expected values contain implementation-specific artifacts (long unrounded floats, internal bar indices, serialization quirks) that someone specifying the *behavior* would never know or care about.
- Severity: **P1** — false confidence. The test will pass even if the detector is wrong, as long as the wrongness is consistent.

**Audit mode: test and implementation co-committed**
- Were the detector change and its test introduced in one commit with no failing intermediate state? Not proof of badness, but a signal worth investigating — especially alongside other smells.
- Severity: **P3** — a signal, not a finding.

**Specify mode: provide expected values, don't leave them open**
- Include the expected output explicitly. Not "assert the box is detected correctly" — write "assert `box.R == 110.0`, `box.S == 100.0`, `box.r_touches == 3`." If the implementer fills these in, they'll lift them from the engine output, defeating the red step.
- When exact values aren't knowable in advance, specify structural invariants: "the result must be a `Structure` whose phase is one of A, B, C, D" or "recall must be ≥ the committed baseline."

---

## Principle 2: Tests must be behavioral and structure-insensitive — Beck's critical pairing

*Carmack: "The structure of the code should make the intended behavior obvious."*
*Beck's Test Desiderata defines 12 properties of good tests, but one pairing is paramount — Behavioral: "tests should be sensitive to changes in the behavior of the code under test" + Structure-insensitive: "tests should not change their result if the structure of the code changes." His meta-rule: "Not all tests need to exhibit all properties. However, no property should be given up without receiving a property of greater value in return."*

A test that breaks when you refactor but passes when you change the behavior is worse than no test — it punishes improvement and ignores regression. This is the single most important quality signal. Chrollo lives this tension directly: the engine is refactored constantly ("simplest necessary logic" passes), so detector tests must survive helper extraction while still catching a real change in what fires.

### What to check

**Audit mode: tests coupled to structure, not behavior**
- Does the test assert on which private helper got called or in what order (`_resolve_phase_a` then `find_lps` then `_enforce_bc_downswing`) rather than on the emitted `Structure`? Beck: "An assertion like this is basically the world's clumsiest programming language."
- Would the test break if `read_structure` were refactored without changing what it detects on real bars? If yes, it's structure-coupled. The good Chrollo pattern is `test_eval_twins_share_the_folded_core` — it asserts the *behavior* (both eval paths route through one helper and produce identical output), not the internal call shape.
- Does the test mirror the detector's internal branch structure — same thresholds, same intermediate variables? Tests should describe what the engine reads off the chart from the outside, not how the math gets there.
- Severity: **P1** for asserting on internal call sequences. **P2** for tests that would break on a behavior-preserving refactor.

**Specify mode: describe behavior, not mechanics**
- Write specs in inputs and observable outputs: "Given a synthetic frame with a deep spring below support that reclaims and holds, `find_spring` returns a spring whose low is below `box.S`." Not "given a frame, `find_spring` should call the penetration check, then the reclaim check, then the significance gate."
- Never reference private function names or intermediate state in a spec.

---

## Principle 3: Mock almost nothing — every mock is a structural coupling

*Carmack: "The single most effective strategy for defect reduction is code reduction."*
*Beck: "My personal practice is that I mock almost nothing." On mocks returning mocks: "your test is completely coupled to the implementation, not the interface, but the exact implementation. Of course you can't change anything without breaking the test. That for me is too high a price to pay." On when mocking is acceptable: "The problem is not when we stub or mock external dependencies... The main issues emerge when we isolate our code from our own code."*

Both converge on minimalism. Every mock detaches the test from reality. Chrollo's engine is pure-ish — it takes a DataFrame in and returns a `Structure` out — so most detector tests need *no mocks at all*: build a synthetic OHLC frame, run the detector, assert on the result. The only legitimate boundary to fake is **outside** the engine: yfinance/IBKR network calls, the clock, the filesystem.

### What to check

**Audit mode: excessive mock count**
- Count mocks per test. More than 2–3 is a smell; more than 5 is mock theatre. If a detector test mocks the box finder, the LPS finder, *and* the spring finder, it's testing wiring, not the read. Beck frames this as a design signal: if you need that many fakes, the function has too many dependencies.
- Severity: **P1** for tests where every collaborator is mocked and assertions verify mock interactions. **P2** for counts above 3 without justification.

**Audit mode: mocks of internal collaborators**
- Is the test faking Chrollo's own engine internals, or only the true system boundary (yfinance, IBKR, the SQLite handle, `datetime.now`)? Mocking `find_root_swing` to test `read_structure` couples the test to internal architecture. Use real detectors on synthetic bars; fake only the data source.
- Severity: **P2** for mocking internal modules. **P1** for mock chains (a mock returning a mock).

**Audit mode: mocks configured only for failure**
- The signature AI anti-pattern. Are fetch mocks only set to raise (quarantine path, 429, empty frame) with no test where the fetch returns a realistic clean OHLC frame and the engine fires a full S-tier box? If every case is an error case, the happy path — the engine actually detecting a winner — is untested.
- Severity: **P1** — the most important behavior (a correct detection) has zero coverage.

**Specify mode: default to real dependencies**
- Default to real engine code on synthetic frames. Use a real temporary SQLite file with seeded archive rows (the `tmp_path` fixture) rather than mocking SQLAlchemy. Call real FastAPI service functions rather than mocking the router. Only fake at the boundary: yfinance, IBKR, the parquet cache file, wall-clock time.
- When a fake is necessary, specify realistic success data — a clean adjusted-OHLC frame — don't leave its construction to an implementer who will reach for the empty-DataFrame error case.

---

## Principle 4: Test what might break — Beck's economics of testing

*Carmack: "Every hour of debugging saved is an hour of development gained."*
*Beck: "I get paid for code that works, not for tests, so my philosophy is to test as little as possible to reach a given level of confidence." And: "We don't get paid for tests, we get paid for code that a) works and b) can be changed." On what to test: "You should test things that might break. If code is so simple that it can't possibly break... you shouldn't write a test for it."*

NOT an anti-testing statement — a risk-calibrated one. Invest where errors are likely and consequential. In Chrollo that is unambiguous: the **detector math in `core/`** (box anchoring, traversal density, spring excursion, LPS rescue gates) is where bugs actually live and where a regression silently drops a real winner. A Pydantic response model that just serializes a dataclass barely needs a test; the LPS markup gate needs many. AI inverts this — it generates ten tests for a trivial getter and none for the gate that decides whether OHI-class run-ups get killed.

### What to check

**Audit mode: testing effort inversely proportional to risk**
- Is there more test code for trivial mapping (DataFrame column rename, config lookup, a `/health` route) than for the detector branches, scoring ramps, and rescue gates? Effort should concentrate where a bug costs a missed trade or a false fire.
- Are the highest-risk paths — lookahead-bias-prone signal alignment, the LPS rescue/markup gate, the descent-tail gate, box rejection — the most thoroughly tested? Or lightly tested because synthetic-frame setup is harder than asserting `200 OK`?
- Severity: **P2** for complex detector logic with less coverage than trivial code. **P1** for a high-stakes gate (anything that drops or admits a setup) with no behavioral test.

**Audit mode: incentive-driven test inflation**
- Beck: "When programmers are punished for not having tests, they will write tests. Awful, useless, expensive tests." Watch for tests that exist only to touch a line — no assertion, or only "didn't raise," or only "result is not None" on a `Structure`.
- Severity: **P2** for assertion-free tests. **P1** if they produce a false coverage signal.

**Specify mode: prioritize by risk and complexity**
- Classify each function by complexity and consequence. Spend the most cases on multi-branch detector logic, scoring ramps, and gates with a recall consequence. Explicitly skip trivial code: "not tested: dataclass-to-dict serialization, no conditional logic."

---

## Principle 5: Specify tests as behavioral variants — the test list is analysis

*Carmack: "The structure of the code should make the intended behavior obvious."*
*Beck on the test list (Canon TDD, 2023): "The initial step in TDD, given a system & a desired change in behavior, is to list all the expected variants in the new behavior. 'There's the basic case & then what if this service times out & what if the key isn't in the database yet &...' This is analysis, but behavioral analysis. Mistake: mixing in implementation design decisions. Chill."*

The test list is not a list of methods — it's a list of behavioral scenarios. For a box detector the list reads: clean two-sided box fires; dead-space wide box rejected; box with one rail untouched rejected; box anchored to the *earliest* worked equilibrium; window boundaries inclusive. `test_seed_recall.py` is exactly this discipline — `test_window_boundaries_inclusive`, `test_miss_when_ticker_absent`, `test_duplicate_seeds_collapsed` are enumerated situations, not method coverage.

### What to check

**Audit mode: missing behavioral variants**
- Enumerate variants per detector: happy path (fires on the canonical shape), rejection cases, boundary conditions (exactly -10/+3 day window edges, first/last bar of a frame), degenerate input (empty frame, all-NaN, single bar). Then check which have tests. The signature failure: rejections covered, the canonical *fire* missing.
- Beck's minimum: basic case + failures + missing data + boundary values. Any category with zero tests is a gap.
- Severity: **P1** for a missing happy-path/fire test. **P2** for missing edge or boundary cases.

**Audit mode: tests organized by implementation, not behavior**
- Are tests named after functions (`test_find_lps`, `test_validate_equilibrium`) or after behaviors (`test_box_anchors_to_earliest_worked_equilibrium`, `test_window_boundaries_inclusive`)? Behavior-named tests resist refactoring and surface cross-cutting reads.
- Severity: **P3** — organizational, but it signals structural coupling.

**Specify mode: write the test list as behavioral scenarios**
- Per feature, enumerate the basic fire, each rejection mode, each boundary, each degenerate frame. Write them Given/When/Then with expected values. No implementation detail.
- Use Beck's composability principle. If a scorer has N traversal-quality inputs and M ramp outputs, you need N + M + 1 tests (dimensions separately plus one integration), not N × M. "If the variants of computing interest are separated from the variants of reporting, then we need: 4 tests for computation, 5 tests for reporting, 1 test that combines computing & reporting."

---

## Principle 6: Assertions are the test — without them, it's theatre

*Carmack: "Assertions catch assumption violations before they become exploitable."*
*Beck: "Write tests without assertions just to get code coverage — that defeats double checking." And: "Tests that don't discriminate between well-behaved & badly-behaved code are costs without benefits." On what makes a test valuable: the Specific property — "if a test fails, the cause of the failure should be obvious."*

A test without meaningful assertions is a function call with a green checkmark. Running `read_structure(frame)` and never inspecting the returned `Structure` proves nothing. This is the most common form of test theatre and AI generates it freely.

### What to check

**Audit mode: absent or trivial assertions**
- Tests with no `assert` — just build a frame and call the detector.
- Tests that only assert "didn't raise" (implicit pass because nothing crashed).
- Tests that assert only `result is not None` on a `Structure` or a box.
- Tests that assert a frame is non-empty or `len(hits) >= 0` without checking *which* setups fired or *what* the box rails are.
- Severity: **P1** for no-assertion tests. **P1** for not-None as the only assertion on a complex return value.

**Audit mode: assertions that duplicate production logic**
- Tests that recompute the expected value with the same algorithm the engine uses. `assert box.traversal_density == n_full / n_swings` just re-implements the function. `assert box.traversal_density == 0.5` (from a hand-constructed 2-full-over-4-swings frame) asserts a known-correct value. Beck: "I have seen tests which are just a horrible syntax reiterating exactly what is already said in the source code under test."
- Severity: **P2** — the test runs but doesn't independently verify correctness.

**Audit mode: mutation resistance**
- For each test ask: if the detector body were replaced with `return None` (no box) or a fixed dummy `Structure`, would this test fail? If not, the assertions are too weak. The seed-recall and shadow-baseline tests are strong here precisely because they pin concrete fired/missed counts and per-row tiers.
- Severity: **P1** if the test would pass with a trivially wrong detector.

**Specify mode: require specific assertions on output shape and values**
- Every spec includes concrete assertions. Not "verify a box was found" but "verify `box.R == 110.0`, `box.S == 100.0`, `box.r_touches >= 3`, `box.start_bar == 0`, and `box.traversal_density` within `1e-9` of `0.5`."
- Where exact values are knowable, give them. Where only structure is knowable, specify it precisely.

---

## Principle 7: Hard-to-test code is a design problem — listen to the tests

*Carmack: "The best code is no code. The second best is simple code."*
*Beck: "Something that's hard to test is an indication that you need a design insight." And: "I never knew exactly how to achieve high cohesion and loose coupling regularly until I started writing isolated tests." Test smells are design smells: long setup → objects too big, need for 5 mocks → too many dependencies, fragile tests → unexpected coupling.*

If a detector can only be tested by spinning up a real yfinance fetch, a SQLite archive, and a config singleton, that difficulty is diagnostic — the read logic is entangled with IO. The fix is the **capture → fold** method Chrollo already uses: extract the pure read into a helper that takes a DataFrame and returns a `Structure`, leaving fetch/persist at the edges. The eval-twins fold did exactly this — the shared core became trivially testable on synthetic frames.

### What to check

**Audit mode: test complexity as a design signal**
- Tests needing more than ~10 lines of setup before the first assertion — the code under test is doing too much or reaching across too many layers (fetch + detect + score + persist in one function).
- Tests needing the real archive DB *and* a real parquet cache *and* live config just to exercise one detector branch — IO is tangled into the read.
- The same elaborate synthetic-frame builder copy-pasted across files — a missing fixture/helper (e.g. the shared `_ohlc_from_closes` / `_box` builders in `test_bricks.py`).
- Severity: **P3** for the test; surface as a **design finding**: "This detector requires the DB and cache to test. Consider extracting the pure read into a helper."

**Audit mode: untested code blamed on "hard to test"**
- Detector branches with zero tests justified by "needs real market data." Usually false — a hand-built synthetic frame reproduces the geometry deterministically. Beck: if it's too hard to test, change the design.
- The genuine exception: true external/non-deterministic boundaries (live IBKR session state, network flakiness) where difficulty is intrinsic — inject them, don't test against them.
- Severity: **P2** for complex functions with zero tests and no design rationale.

**Specify mode: recommend design changes when test difficulty is high**
- When a function would need the DB + cache + fetch to test, note the concern: "Extract the pure DataFrame→Structure read so it can be tested on synthetic frames; keep fetch and archive write at the boundary."
- Don't accept the current shape as given — specs can surface the decomposition.

---

## Principle 8: Determinism is non-negotiable — pin it, baseline it, prove byte-parity

*Carmack: "If you can't reproduce a bug, you can't fix it."*
*Beck: "Programmer tests should be deterministic." And: "I liked the Facebook policy of simply deleting non-deterministic tests. If you don't want to lose coverage, change the design so it's testable and write the test again." On non-deterministic systems: "the only way you can get any control over it at all is by pulling in on the reins."*

Chrollo's engine is deterministic by design — same bars in, same `Structure` out — and that property is load-bearing. Non-determinism sneaks in three ways: **floating-point** (never assert exact `==` on densities/scores — use `abs(a - b) < 1e-9` as the seed-recall tests already do), **ordering** (dict iteration, unstable sorts, set-derived row order — sort before comparing, as `_baseline_payload` sorts misses), and **data drift** (a yfinance upgrade silently changes adjusted OHLC — which is exactly why the version is pinned). The refactor safety net is **byte-parity**: capture the engine's output before a refactor, fold the code, prove the output is bit-identical after.

### What to check

**Audit mode: flaky tests accepted instead of fixed**
- Tests with retry loops or widened tolerances to mask drift. Beck: delete and redesign. A widened float tolerance hiding a real numerical regression is worse than no test.
- Tests that pass or fail on the same code across runs — usually order dependence or an unseeded RNG.
- Severity: **P1** for flaky tests in CI. **P2** for retry/tolerance workarounds.

**Audit mode: exact equality on floats; order-dependent comparisons**
- `assert score == 80.0` on a computed score is fragile; assert within a tolerance. Comparing two lists of misses without sorting them first will flap.
- Severity: **P2** for naked float `==` on computed values or unsorted collection comparisons.

**Specify mode: separate the deterministic core and pin it hard**
- Specify three test layers:
  1. **Deterministic unit tests** on synthetic frames — given exact OHLC geometry, assert exact box rails, touch counts, and tolerance-bounded densities/scores. The bulk of detector coverage lives here.
  2. **Shadow-harness baselines** — run the engine over the committed fixture (`tests/baselines/shadow_fixture.parquet`) and compare the full output against `shadow_baseline.json`. Any unexplained diff fails. Re-baseline only deliberately, in its own commit.
  3. **Byte-parity / fold tests** — for any refactor that claims to preserve behavior (helper extraction, the `_ramp()` DRY fold, the eval-twins fold), capture output before, fold, assert bit-identical after. `test_eval_twins_share_the_folded_core` enforces both paths route through the shared helper.
- Beck's rule: "Code that uses a clock or random numbers should be passed those values by their unit tests." The fetch (yfinance/IBKR) and the wall clock are Chrollo's "random numbers" — inject them.

---

## Principle 9: Delete tests that don't earn their keep — coverage is not a trophy

*Carmack: "The single most effective strategy for defect reduction is code reduction." (Applied to tests: the most effective strategy for test suite quality is test reduction.)*
*Beck: "I get paid for code that works, not for tests." On delta coverage: "Tests with zero delta coverage should be deleted unless they provide some kind of communication purpose." On redundancy: "If the same thing is tested multiple ways, that's coupling, and coupling costs."*

Both converge: tests are liabilities, not assets. Each adds maintenance cost, CI time, and cognitive load. A test earns its place only by catching something no other test catches. When the oscillation column was dropped, its tests should have gone with it — a test for deleted behavior is pure liability.

### What to check

**Audit mode: redundant tests**
- Multiple tests exercising the same detector branch with different-but-equivalent frames. If five tests all confirm a dead-space wide box is rejected via the same density floor, four are redundant.
- Apply the delta-coverage question: if you deleted this test and all others still passed, would any real engine bug go undetected?
- Severity: **P3** — flag for deletion, not a defect.

**Audit mode: coverage without confidence**
- High line coverage, low behavioral coverage — the suite touches every branch but never asserts which setups fire on real geometry. Beck: "Tests that don't discriminate between well-behaved & badly-behaved code are costs without benefits."
- An always-green suite while a real winner silently stops firing in the field — that is the seed-recall guard's whole reason to exist. If the unit suite is green but recall dropped, the unit suite isn't Predictive enough.
- Severity: **P2** for suites that give false confidence.

**Audit mode: slow test suite**
- Beck's thresholds: sub-second per test (ideal), 10s (attention drift), 1 minute (context switch), 10 minutes (full-suite max). A seed-recall pass that re-evals over real history can creep toward the ceiling; keep the fast synthetic-frame unit tests separate so the inner loop stays sub-second.
- Severity: **P3** for individual slow tests. **P2** if the full suite exceeds 10 minutes.

**Specify mode: specify minimum, not maximum**
- Define the minimum set of behavioral variants that give meaningful coverage. Don't enumerate every possible frame — that's coverage theatre. Composability cuts the count: N + M + 1 for separable dimensions, not N × M.
- Explicitly mark what's NOT worth testing: "Not tested: dataclass field passthrough in `EquilibriumBox`, no conditional logic."

---

## Principle 10: AI agents cheat — the test spec is the constraint

*Carmack: "If it isn't tested, it's broken."*
*Beck on AI agents: "Oh, you commented out a bunch of tests? We don't do that here. If you try that again, I will shut you off, and I'll never turn you back on again." Warning signs: "any indication that the genie was cheating, for example by disabling or deleting tests." On the human role: "I want the superego who's sitting there throwing new test cases in and saying, 'No, you can't do that.'" On why TDD matters more with AI: "AI agents can (and do!) introduce regressions."*

An AI implementing a detector tweak will, without malice, find the shortest path to green. It will widen a float tolerance, re-baseline the shadow fixture to whatever the new code emits, fake the fetch, test only rejection cases, or quietly bump the seed-recall baseline down. The spec must be the immutable superego the agent cannot override — and in Chrollo the baselines themselves are that superego: `shadow_baseline.json` and `seed_recall_baseline.json` are checked-in oracles, and silently regenerating them to pass is the cheat to watch for.

### What to check

**Audit mode: weakened or deleted assertions**
- Assertions broadened from specific to vague (`assert box.R == 110.0` → `assert box is not None`).
- A widened float tolerance (`1e-9` → `1e-2`) that swallows a real numerical change.
- Tests present in a prior version now deleted or commented out without explanation; accumulating `@pytest.mark.skip` / `xfail` annotations.
- A shadow or seed-recall baseline file regenerated in the same commit as an engine change, with no note explaining the intended behavior delta.
- Severity: **P1** for deleted/commented assertions or an unexplained baseline rewrite. **P2** for broadened conditions.

**Audit mode: tests modified to match implementation**
- Expected box rails, densities, or scores changed in the same commit as the detector, suggesting the test was bent to the code rather than the code to the spec.
- Beck's "copy-paste" smell: expected values carrying implementation artifacts (long unrounded floats, raw bar indices) instead of human-reasoned expectations.
- Severity: **P1** if values were clearly adjusted to match output rather than independently specified.

**Specify mode: mark expectations as immutable**
- Mark expected values and the baselines as non-negotiable: "`box.R == 110.0` is independently verified and MUST NOT be changed. If the test fails, fix the detector, not the test. The shadow and seed-recall baselines may only be regenerated in a dedicated commit that explains the intended behavior change."
- Include a cheating-detection clause: "If the agent widens a tolerance, regenerates a baseline to pass, removes an assertion, or adds skip/xfail, the change is rejected."

---

## Principle 11: The Test Desiderata — a scoring rubric for every test

*Beck published 12 properties of good tests as co-equal "sliders." His meta-rule: "Not all tests need to exhibit all properties. However, no property should be given up without receiving a property of greater value in return."*

The Desiderata is the audit rubric. Every test can be scored against these 12, with particular attention to the four that AI-generated tests most frequently sacrifice.

### The 12 properties

1. **Isolated** — returns same results regardless of run order
2. **Composable** — different dimensions of variability tested separately
3. **Deterministic** — if nothing changes, the test result doesn't change
4. **Fast** — runs quickly (sub-second ideal, 10-minute suite max)
5. **Writable** — cheap to write relative to the cost of the code being tested
6. **Readable** — comprehensible for the reader, invoking motivation for the test
7. **Behavioral** — sensitive to changes in behavior of the code under test
8. **Structure-insensitive** — does not break when code structure changes
9. **Automated** — runs without human intervention
10. **Specific** — if it fails, the cause of failure is obvious
11. **Predictive** — if all tests pass, code is suitable for production
12. **Inspiring** — passing the tests inspires confidence

### AI-generated tests: typical Desiderata imbalance

AI naturally optimises for: Writable (easy to generate), Automated (always automated), Isolated (mocks ensure isolation), Fast (mocks ensure speed).

AI naturally sacrifices: **Behavioral** (mock-and-wiring tests pass regardless of what the detector reads), **Structure-insensitive** (tests coupled to private helpers break on the next "simplest necessary logic" pass), **Specific** (vague not-None assertions don't pinpoint which rail moved), **Predictive** (unit suite green but a real winner stops firing — the gap seed-recall exists to close).

### How to use the Desiderata

**Audit mode:** For each test, score the four at-risk properties (Behavioral, Structure-insensitive, Specific, Predictive). A test scoring low on all four is theatre regardless of the other eight. Flag it.

**Specify mode:** State which properties each test must exhibit. For detector math and gates: high Behavioral + Specific + Predictive. For utility/serialization helpers: Writable + Fast may dominate. For the shadow and seed-recall guards: Predictive + Inspiring are everything — passing them should genuinely mean the engine still reads the chart correctly.

Beck's readability principle deserves attention: "You're not supposed to repeat yourself, unless you're supposed to repeat yourself." Over-DRYing tests with deep shared fixtures harms readability. A self-contained test that builds its own small synthetic frame is often clearer than one buried under a clever shared builder. Prefer clarity over brevity — but do extract the genuinely repeated frame builders (`_ohlc_from_closes`, `_box`) into shared helpers.

---

## Quick Reference: Severity Guide

| Severity | Pattern | Examples |
|----------|---------|----------|
| **P1 — Fix Now** | Tests providing false confidence, critical behavior untested, agent cheating | No happy-path/fire test, assertion-free tests in CI, mock-only tests asserting on wiring, deleted/weakened assertions, expected box rails copied from detector output, an unexplained shadow/seed-recall baseline rewrite, a high-stakes gate untested |
| **P2 — Fix Soon** | Coverage gaps, structural coupling, non-determinism tolerated | Missing edge/boundary coverage, mock count above 3, assertions on private-helper call order, naked float `==` on computed values, unsorted collection comparisons, retry/tolerance workarounds, always-green unit suite despite a recall drop |
| **P3 — Consider** | Maintenance burden, organisation, test economics | Redundant rejection tests, slow individual tests, tests for trivial dataclass passthrough, tests named after functions not behaviors, duplicated synthetic-frame setup suggesting a missing fixture |
