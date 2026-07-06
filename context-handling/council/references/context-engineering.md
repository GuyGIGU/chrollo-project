# Context Engineering — the Core doctrine

This is the doctrine the **Context Core** reads at the start of every run. It is short on purpose.
It encodes *how* to spend context; the mode supplies *what* the run is about.

## The one principle

Context is a **finite attention budget with diminishing returns**, not free real estate. Every
token you add dilutes the model's attention over every other token. Your job as orchestrator is to
spend the **smallest set of high-signal tokens** that produces the outcome — nothing more.

More tokens ≠ better. Bigger windows do not save you. This is **context rot**: measured accuracy
falls as input grows, even on simple tasks, even below the window limit. It compounds with
**"lost in the middle"** — facts buried in the middle of a long context are recalled worst.

Two operational consequences, always:
1. **Map, don't ingest.** The orchestrator surveys structure; deep reading is delegated to isolated
   workers. If you're deep-reading, you're doing a worker's job.
2. **Edge-order every brief.** Put the load-bearing instructions at the **top and bottom**;
   reference detail goes in the middle.

## The four levers (how to manage the budget)

- **Write** — save context *outside* the window (briefs, worker files, memory) and reference it.
- **Select** — pull in *only* what's needed, *when* needed (just-in-time reference loading; map first).
- **Compress** — keep only the tokens the task needs (minimal returns, no-code, cut-to-a-cap, compaction).
- **Isolate** — split work into clean sub-contexts (parallel workers, domain-partitioned slices).

## Anti-patterns (do not do these)

- Dumping whole files/dirs into the orchestrator "to be safe." (Violates map-don't-ingest.)
- One giant worker with the whole codebase. (Drowns; produces shallow output.)
- Workers returning their full raw work to the parent. (Floods the orchestrator; return one line.)
- Re-litigating settled decisions each run. (Read durable memory first.)
- The orchestrator forming a verdict *before* collecting worker output. (Becomes a biased extra reviewer.)
- Marking work "done" without validating it against the real artifact. (Ships hallucinations.)

## The ten primitives (the pipeline these produce)

The Core runs these phases; a mode plugs content into them. See `skills/context-core/SKILL.md`.

1. **Scope Gate** — name the decision/deliverable + out-of-scope; confirm before big spend.
2. **Structural Map** — survey without ingesting; hard ceiling on what the orchestrator reads.
3. **Context Brief** — one edge-ordered brief on disk = single source of truth.
4. **Partition + Budget** — assign only-your-slice to each worker, with a size cap.
5. **Isolated Dispatch** — clean windows; JIT reference loading; one-line returns.
6. **Completeness Gate** — confirm every worker output exists; re-dispatch gaps.
7. **Synthesis** — aggregate before judging; merge/dedupe/curate with provenance.
8. **Durable Memory** — read-before, write-after; the compound effect.
9. **Compaction + Resume** — preserve-list + `session-state.md`; re-bootstrap after a reset.
10. **Verification** — validate against the real artifact before "done."

## The mode contract

A mode hands the Core five things:

- `personas` — the lenses/experts (each with a reference doc).
- `reference_docs` — the JIT domain knowledge each lens loads.
- `output_schema` — the shape of the deliverable.
- `gates` — the checks for the Scope/Verification phases.
- `memory_namespace` — which durable-memory file to read/write.

The Core never re-implements phases 2–9. A mode never re-implements the pipeline.
