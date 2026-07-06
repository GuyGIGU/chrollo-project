---
name: using-council
description: Bootstrap that keeps the Council active. Loads at session start and re-loads after any compaction. Ensures the agent checks for a relevant Council mode BEFORE starting work, and re-establishes the context-core discipline after a context reset so the method never silently drops mid-run.
---

# Using the Council

The Council is a **context-handling system**: it turns large work into bounded, isolated,
memory-aware runs that resist context rot. It is made of a reusable pipeline (`context-core`) and
**modes** that plug into it.

## Before starting any substantial task, check for a mode

- Reviewing / critiquing / merging code → **`council-review`**.
- (Future) planning a feature → `council-plan`; executing a plan → `council-implement`;
  auditing tests → `test-architect`; research / writing / ops → later modes.
- If a mode fits, **suggest it** — say so and, for anything that dispatches workers (a review/plan),
  get the user's go-ahead before spending the budget. The modes are the right way to do this work; the
  multi-agent fan-out is opt-in, not automatic.
- If the project has no `.council/council.config.md` yet, run **`council-init`** first so the
  council is tailored to this repo.

## Always, even outside a formal mode

Hold the `context-core` doctrine (`references/context-engineering.md`): spend the smallest set of
high-signal tokens; **map, don't ingest**; delegate deep reading to isolated workers; write one
edge-ordered brief; workers return one line; read memory before, write after; aggregate before you
judge; validate before you ship.

## After a compaction / context reset — RE-BOOTSTRAP

A reset is where methodology silently dies. Immediately:
1. Reload this bootstrap and the `context-core` doctrine.
2. If a run is in flight, read `.council/<mode>-output/$TS/session-state.md` to recover the phase,
   brief path, assignments, and dispatched workers.
3. Resume at the recorded phase. Do NOT restart from scratch and do NOT skip the completeness gate.

## Invocation — suggest, then confirm

When a mode's situation is detected, **propose** it and wait for the user's confirmation before
dispatching a multi-agent fan-out (it costs real budget). Modes run immediately on an explicit
`/council-review`, `/council-init`, etc. When in doubt, prefer suggesting the mode over an ad-hoc pass.
