# Chrollo — project instructions

@AGENTS.md

Where code lives and which way imports run: `docs/architecture.md`. What is live, dark and next:
`docs/current_state.md`.

## Non-negotiable reading rule

Before modifying ANY chart-reading engine code — `engine_alpha/structure/`, `engine_alpha/scoring/`, or
their knobs (detection in `config/engine.py`, scoring in `config/scoring.py`; `config/settings.py` is
only the namespace that re-exports them) — read, in this order:

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

<!-- small-council:begin -->
## Small Council
This repo uses the Small Council (council home: `.council/`). Main session: check `.council/map.md`
when orienting in unfamiliar code; for substantial work, suggest a council mode and get a go-ahead
before any multi-agent run; `council run status` shows open runs. Subagents and council workers:
ignore this section.
<!-- small-council:end -->

