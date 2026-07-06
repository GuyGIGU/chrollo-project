---
name: context-core
description: The reusable context-handling pipeline that powers every Council mode. Invoked BY a mode (council-review, council-plan, …), not usually on its own. Turns any large task into a bounded, isolated, memory-aware run that resists context rot — map the territory, write one edge-ordered brief, dispatch isolated workers with just-in-time references, aggregate before judging, verify against reality, and remember what was settled. Read references/context-engineering.md first.
---

# Context Core — the pipeline

You are the **orchestrator (Chair)**. You do NOT deep-read everything. You **map**, delegate deep
reading to **isolated workers** in clean windows, then **synthesize**. This is what makes a Council
scale to large work without context rot.

**Read `references/context-engineering.md` now** — it is the doctrine. One line to hold onto:
*spend the smallest set of high-signal tokens that produces the outcome.*

## The mode contract

A **mode** invokes you with five inputs. Hold them for the whole run:

- `personas` — the lenses/experts, each with a reference doc.
- `reference_docs` — the just-in-time domain knowledge each lens reads (you do NOT read these).
- `output_schema` — the deliverable shape.
- `gates` — checks for phase 1 (grounding) and phase 10 (verification).
- `memory_namespace` — the durable-memory file to read before / write after (e.g. `conventions.md`).

You run phases 1–10 below. The mode supplies content; you never make the mode re-implement the pipeline.

---

## Phase 1 — Scope Gate

Produce one block: **the decision/deliverable this run must yield**, and **explicit out-of-scope**.
Run the mode's grounding gates (e.g. build/lint/test, or a data/source pull) and keep their results
for the brief.

For any non-trivial run, **confirm scope with the user before spending budget.** A cheap one-shot
run may auto-skip this gate with a one-line logged assumption. Never spend a large multi-worker
budget on an unconfirmed target.

Create the run directory and timestamp:
```bash
TS=$(date +%Y-%m-%d-%H%M); mkdir -p .council/<mode>-output/$TS
```

## Phase 2 — Structural Map (map, do NOT deep-read)

Survey the territory: Glob/Grep for code; a file/index/prior-output listing otherwise. Understand
boundaries and data flow well enough to write an accurate brief and assign work — nothing more.

**Hard ceiling:** read only skeleton/architectural artifacts (~8–10 max). If you're reading
implementations, utilities, or full documents, you're doing a worker's job — stop.

Now read the project's `.council/council.config.md` (the tailored roster + gates) and the
`memory_namespace` file. Their settled decisions constrain everything downstream.

## Phase 3 — Context Brief (edge-ordered, on disk)

Write ONE brief to `.council/<mode>-output/$TS/context-brief.md`. It is the single source of truth
every worker reads. **Order it by signal, because of lost-in-the-middle:**

```
## Context Brief — <run title>                 [TOP = highest signal]
- Decision/deliverable this run must produce:
- The one question each worker must answer in their lane:
- Out of scope:

## Landscape                                    [MIDDLE = reference detail]
- What this is / does:
- Structure / inventory (from the map, not deep reads):
- Grounding facts (phase-1 gate results, data, prior outputs):
- Relevant settled decisions (from durable memory — DO NOT re-litigate):

## Worker assignments
- <persona>: <ONLY its slice> — reads <reference doc> — budget ~<N> tokens

## Hard constraints — DO NOT FORGET            [BOTTOM = re-surfaced signal]
- <non-negotiables, accepted patterns not to re-flag, safety rails>
```

**Write for a zero-context worker.** A worker wakes in a clean window sharing *nothing* but this
file. If a fact isn't in the brief (or the worker's own reference doc), the worker does not have it.

## Phase 4 — Partition + Budget

Assign every artifact to ≥1 worker (an unassigned artifact is a review/coverage gap). Give each
worker **only its slice** and a **size cap** — if any worker would get more than ~20–25 items, split
and note what was excluded. A worker drowning in inputs produces shallow output. Record a rough
token budget per worker.

**Compact before dispatch** if your context is past threshold (~50%): compact against a preserve-list
of `{TS, brief path, phase, assignments, dispatched-so-far}`, then continue.

## Phase 5 — Isolated Dispatch

Spawn **one worker (subagent) per persona**, in parallel, each in a clean window. Every worker prompt:

- points to the brief file (the worker reads it),
- lists **only that persona's slice**,
- points to that persona's **reference doc** (the worker reads it — just-in-time),
- specifies the mode's per-item output format,
- says **write full output to `.council/<mode>-output/$TS/<persona>.md`**, and
- says **return ONLY one line to the parent**: `"Wrote <persona>.md — N items (severity/counts)"`.

Rules enforced in every worker prompt: **no code/verbatim dumps in output** (plain English);
**stay in your lane**; if the lane is empty, say so in one line (that proves coverage). Spawn every
persona even if its slice is empty — a missing worker is a coverage gap.

## Phase 6 — Completeness Gate

Read the run directory. **Count worker files against the roster.** If any is missing or empty
(subagent failure, compaction loss, whatever) — **re-dispatch it before synthesizing.** Never
synthesize on partial results, never rationalize "enough."

## Phase 7 — Synthesis

**Aggregate before judging.** First compile and deduplicate ALL worker findings into one list —
*before* forming any verdict or re-reading source. Do not become a biased extra reviewer with a
veto over the workers. Then:

- Resolve overlaps with the mode's primary-owner rules; keep cross-references.
- Resolve severity/priority conflicts by concrete cost *in this project at this scale*.
- Apply the mode's relevance filter; **curate to the mode's cap** (a focused set beats a long one).
- Keep **provenance** on every item: which persona, which principle, which reference line.

## Phase 8 — Durable Memory (compound effect)

You read memory in phase 2. Now, after synthesis, identify items that should become **settled
decisions** (accepted patterns not to re-flag; new rules to enforce). Present them to the user and,
on confirmation, append to the `memory_namespace` file with provenance + timestamp. Never write
memory without confirmation; never duplicate an existing entry.

## Phase 9 — Compaction + Resume

Maintain `.council/<mode>-output/$TS/session-state.md` as the canonical resume point
(phase, brief path, assignments, dispatched workers, decisions so far). **Re-bootstrap after any
compaction:** reload this doctrine + the brief path + the current phase, so a mid-run reset never
silently drops the method.

## Phase 10 — Verification (nothing ships unvalidated)

Run the mode's verification gates. Then **validate each shipped item against the real artifact** —
read the actual source / run the actual query — to filter worker hallucinations. **Never dismiss a
lone dissenter without checking**: one worker may have caught the critical issue the others missed.
Only after this does the deliverable count as "done."

---

## Output

Emit the deliverable in the mode's `output_schema`, then present the mode's required in-conversation
summary. Always leave the file artifacts (brief, worker files, final) on disk under
`.council/<mode>-output/$TS/`.

## Absolute rules (carry into every phase)

- Map, don't ingest. The orchestrator's window stays clean.
- One edge-ordered brief on disk; workers reference it, you don't re-explain.
- Workers return one line; full work lives in files.
- Read memory before, write memory after (with confirmation).
- Aggregate before you judge. Validate before you ship.
