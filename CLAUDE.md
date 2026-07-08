# Chrollo — project instructions

@AGENTS.md

## Non-negotiable reading rule

Before modifying ANY chart-reading engine code — `core/structure/`, `core/scoring/`, or
their detection/scoring knobs in `config/settings.py` — **read `docs/strategy_v2.md`
first** (the Reading Model section at minimum). It is the source of truth for how we
understand chart analysis; the code implements it, not the other way around. When your
change moves behavior, **update `docs/strategy_v2.md` in the same change**. Drift between
the doc and the engine is a defect, not a chore to defer.

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

