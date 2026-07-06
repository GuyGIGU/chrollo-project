# Council v2 — build, install & dogfood (paste into Claude Code)

> Run this from inside the Chrollo Project repo. It builds the new Council v2 skill framework,
> installs it, and proves it on this repo. It must NOT modify the Chrollo trading engine.

---

You are working in the Chrollo Project repo (`C:\Users\User\Documents\Projects\Chrollo Project`).
A new context-handling skill framework, **Council v2**, has been built at `context-handling/council/`.
Your job: get it working and prove it on this repo, end to end, then report. Follow this repo's
`AGENTS.md` hard safety rules — do not run the backend, do not touch the broker, do not modify the
engine. Only create files under `context-handling/` and `.council/` unless I approve otherwise.
Use `python` or `python3` (whichever exists) and Git Bash/WSL for the `bash` scripts.

## 0. Orient (read before doing anything)
Read, in order, and hold the design in your head:
- `context-handling/RESEARCH-and-DESIGN.md` — the research (why context engineering).
- `context-handling/DESIGN-SPEC.md` — the LOCKED design: the 10 Context Core phases, the mode
  system, `council-init`, per-project memory.
- `context-handling/FIELD-SCAN-and-INSPIRATION.md` — the adopted ideas (bias-controlled synthesis,
  finding validation, compaction re-bootstrap, zero-context briefs, evals).
- `context-handling/council/README.md` and all four `context-handling/council/skills/*/SKILL.md`.
- `context-handling/council/references/context-engineering.md` and `references/roster/expert-catalog.md`.
- This repo's `AGENTS.md`, `CLAUDE.md`, and `conventions.md` — so you know the existing hand-tuned
  council roster and gates you must reproduce.

## 1. Get the 9 domain reference docs
`council-review` needs: `security.md, refactoring.md, quality-frontend.md, quality-backend.md,
quality-postgres.md, quality-testing.md, quality-llm.md, quality-ui.md, quality-ux.md`. They are
intentionally NOT committed.
1. FIRST search this machine for the versions the current Carmack/Chrollo council already uses
   (referenced in `conventions.md`, e.g. `references/refactoring.md`, `references/quality-llm.md`,
   `references/quality-postgres.md`) — likely under your Claude Code skills dir
   (`~/.claude/skills/**/references/`) or an installed Carmack council. If found, COPY them into
   `context-handling/council/references/` (prefer these — they may be tuned to this project).
2. OTHERWISE run `bash context-handling/council/scripts/fetch-references.sh` (pulls the canonical
   MIT versions from the Carmack repo).
Confirm all 9 now exist in `council/references/`.

## 2. Validate + build
```
cd context-handling/council
python scripts/quick_validate.py     # expect: validation OK (0 warnings once the 9 refs are present)
python evals/run_structural.py       # expect: 40/40 checks passed
bash scripts/build.sh                # expect: dist/*.skill (4 packages), exit 0, no missing-ref warnings
```
If anything fails, fix it and re-run before continuing.

## 3. Install the four skills into Claude Code
Install so you can invoke them: `context-core`, `using-council`, `council-init`, `council-review`.
Use your normal skill-install flow — e.g. unzip each `dist/<name>.skill` into your Claude Code
skills directory (`~/.claude/skills/<name>/`, each with its `SKILL.md` + bundled `references/`),
then reload so they're discovered. Confirm all four are visible/invocable.

## 4. Dogfood D1 — `council-init` tailors to Chrollo
Run `council-init` on this repo. It should:
- detect: Python engine (pandas/numpy/parquet) + FastAPI/SQLAlchemy/SQLite + React frontend;
- propose a roster that recasts **backend→Ramírez**, **LLM→McKinney** (numerical, reusing
  `quality-llm.md`), **Postgres→data-integrity Leach**, keeps Hunt/Fowler/Beck/Dodds/Saarinen/
  Friedman + a **pipeline Performance** seat;
- detect gates `pytest`, `npm --prefix webapp/frontend run lint`, `npm --prefix webapp/frontend run build`
  (NOT tsc/vitest/cypress);
- write `.council/council.config.md`.
Compare the generated roster + gates against the existing hand-tuned setup implied by `conventions.md`.
**PASS** if they match. If not, report the diff and adjust `council-init` (or the config) until they do.
Do not overwrite existing `.council/review-output/` history — init only writes `council.config.md`.

## 5. Dogfood D3 + D4 — bug caught, memory respected (fixtures)
Create the fixtures per `context-handling/council/evals/fixtures/README.md`:
- `evals/fixtures/sample.py` with the two functions (an `average()` with an empty-input
  divide-by-zero bug; a `last_or_none()` that uses explicit `len-1` indexing on purpose).
- `evals/fixtures/conventions.md` with AP-1 accepting the explicit-index style.
Run `council-review` scoped to that fixture folder, using `fixtures/conventions.md` as its memory.
- **D3 PASS:** the divide-by-zero is reported (P1/P2, correct expert, concrete fix, NO code in the finding).
- **D4 PASS:** `last_or_none` is NOT flagged (AP-1 respected).

## 6. Dogfood — a real review on a small Chrollo slice
Pick one small, self-contained module (e.g. a single file in `core/pipeline/` or
`webapp/backend/services/`). Run `council-review` on just that slice. Verify the context-hygiene
invariants from `evals/behavioral-drills.md`:
- the Chair used Glob/Grep + a bounded read, and did NOT deep-read everything;
- `.council/review-output/<TS>/context-brief.md` exists and is edge-ordered (decision at top,
  constraints at bottom);
- each expert wrote its own file and returned ~one line to the Chair;
- findings are validated against the real code, attributed to expert + principle, with no code snippets;
- nothing already accepted in `conventions.md` was re-flagged.
Then compare quality against a known-good past review under `.council/review-output/`.

## 7. Report back
Give me a concise report:
- build + structural-eval results;
- D1 with the ACTUAL generated roster + gates; D3/D4 pass/fail with the fixture findings;
- the real-slice review summary + any hygiene invariant that failed;
- every change you made to the skills, and anything still open.
Do NOT commit anything unless I say so. Do NOT modify the Chrollo engine.
