# evals/

Two layers, following Superpowers' idea that a skill isn't done until it's tested.

## 1. Structural evals — runnable now

```bash
python3 evals/run_structural.py
```

Checks the framework's invariants without an LLM: all four skills present and valid; the Core
exposes the mode contract and all ten phases (including the four folded-in rules); `council-review`
rides the Core and auto-triggers; `council-init` tailors via the catalog and detects gates; the
bootstrap re-injects after compaction. A build must never break these.

## 2. Behavioral drills — run in Claude Code

See `behavioral-drills.md`. These need a live agent + subagents, so they can't be scripted here.
They verify the things that actually matter:

- **D1 Roster fit** — `council-init` on Chrollo reproduces the hand-tuned roster
  (Ramírez/McKinney/data-integrity-Leach) and gates (`pytest`, frontend lint/build).
- **D2 Triggering** — `council-review` fires when a change is ready, and stays quiet on unrelated chat.
- **D3 Bug caught** — a seeded bug in a fixture is reported (right severity, right expert).
- **D4 Memory respected** — a seeded accepted-pattern in `conventions.md` is NOT re-flagged.

`fixtures/` holds the seeds for D3/D4. No skill ships to `main` until D1–D4 pass by hand at least once.
