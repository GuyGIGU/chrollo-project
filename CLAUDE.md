# Chrollo — project instructions

@AGENTS.md

## Non-negotiable reading rule

Before modifying ANY chart-reading engine code — `engine_alpha/structure/`, `engine_alpha/scoring/`, or
their detection/scoring knobs in `config/settings.py` — read, in this order:

1. **`docs/strategy_alpha.md`** — the THEORY (Reading Model at minimum). The source of truth for
   how we understand chart analysis; the code implements it, not the other way around.
2. **`docs/decisions.md`** — the operator's rulings and the **Tested-DEAD table**. Several
   plausible levers in this engine were built, measured and removed; re-proposing one costs a
   full A/B cycle. Check it before suggesting any new knob, threshold, or heuristic.
3. **`docs/engine_reference.md`** — how it is currently built, and why it took that shape.

When your change moves behavior, **update the matching doc in the same change** (theory →
`strategy_alpha.md`, implementation → `engine_reference.md`, ruling or falsified lever →
`decisions.md`). Drift between the docs and the engine is a defect, not a chore to defer.
`decisions.md` is **append-only** — never rewrite or delete a row.

<!-- ultra-council:begin -->
## Ultra Council

This repo uses the **Ultra Council** — a context-engineering pipeline (`context-core`) with a
self-tailoring council of expert modes. Before substantial work, load **`using-council`** and check
for a fitting mode:

- reviewing / critiquing / merging code → **`council-review`**
- planning a feature → **`council-plan`**, then executing it → **`council-implement`**
- auditing or specifying tests → **`test-architect`**; writing a spec → **`spec-writer`**

Each mode runs on `context-core` and reads this repo's tailored roster + gates from
**`.council/council.config.md`**. A council run is a multi-agent fan-out that costs real budget, so a
mode **proposes and waits for your go-ahead** before dispatching (an explicit `/council-review` runs
immediately). After a context compaction, reload `using-council`; if a run was interrupted, resume via
`.council/active-run`.
<!-- ultra-council:end -->

