# Chrollo — project instructions

@AGENTS.md

## Non-negotiable reading rule

Before modifying ANY chart-reading engine code — `core/structure/`, `core/scoring/`, or
their detection/scoring knobs in `config/settings.py` — **read `docs/strategy_v2.md`
first** (the Reading Model section at minimum). It is the source of truth for how we
understand chart analysis; the code implements it, not the other way around. When your
change moves behavior, **update `docs/strategy_v2.md` in the same change**. Drift between
the doc and the engine is a defect, not a chore to defer.
