# Council v2 — a context-handling framework for Claude Code

Council v2 turns the Carmack Council into a general **context-handling** system: a reusable pipeline
(`context-core`) that resists context rot, plus **modes** that plug into it. One install behaves like
a **bespoke council per project**, because `council-init` tailors the roster to each repo.

Built from the research in `../RESEARCH-and-DESIGN.md`, the design in `../DESIGN-SPEC.md`, and the
field scan in `../FIELD-SCAN-and-INSPIRATION.md`.

## The pieces

| Skill | What it is |
|---|---|
| **context-core** | The reusable 10-phase pipeline (map → brief → partition → isolate → synthesize → remember → compact → verify). Every mode runs on it. |
| **council-review** | Mode: multi-expert code review (P1/P2/P3). Suggests a review when warranted, then waits for your go-ahead before dispatching. |
| **council-init** | Tailors the council to a project: detects stack, selects/recasts the expert roster, detects gates, writes `.council/council.config.md`. |
| **using-council** | Bootstrap: keeps the Council active at session start and re-injects after compaction. |
| **council-plan** | Mode: interactive feature discovery → parallel expert fan-out → a sequenced, attributed implementation plan (no code). |
| **council-implement** | Executes a council plan task by task, loading the relevant expert's reference doc per task and verifying against the project's gates between tasks. |
| **test-architect** | Carmack × Beck test quality — audit existing tests, specify shortcut-proof test suites, or fix test theatre. |
| **spec-writer** | Stack-agnostic structured specs (Job Stories, Gherkin ACs, three-tier boundaries). |

## The idea in one line

The **pipeline** is shared and improved once; the **council fits each project automatically**;
**memory stays per-project**. That's the level-up over copying `.council/` around and hand-editing
personas.

## Design principles baked in

- Attention is a finite budget — spend the smallest set of high-signal tokens (Anthropic).
- Map, don't ingest; delegate deep reading to isolated workers in clean windows.
- One edge-ordered brief on disk; workers return one line; read memory before / write after.
- Aggregate before you judge; validate each finding against the real artifact before shipping.
- Re-bootstrap after compaction so the method survives a context reset.

## Build

```bash
cd context-handling/council
# 1) get the domain reference docs (or copy your own tuned ones into references/)
bash scripts/fetch-references.sh
# 2) validate + package
bash scripts/build.sh          # -> dist/*.skill
# 3) (optional) run structural evals
python3 evals/run_structural.py
```

Each `dist/*.skill` is a self-contained zip (SKILL.md + manifest.json + bundled references),
installable via Claude Code's skill install. Install `context-core` and `using-council` once
globally; run `council-init` once per project; then `council-review` (and future modes) use the
tailored config.

## Repo layout

```
council/
├── README.md
├── references/                 # shared docs (context-engineering.md, roster/expert-catalog.md,
│   └── roster/                 #  quality-performance.md ship here; domain docs fetched/brought)
├── skills/
│   ├── context-core/           # the pipeline  (SKILL.md + manifest.json)
│   ├── council-review/         # review mode
│   ├── council-init/           # per-project tailoring
│   └── using-council/          # bootstrap
├── scripts/                    # build.sh, quick_validate.py, fetch-references.sh
├── evals/                      # drill-style checks (structural + behavioral drills)
└── dist/                       # built .skill packages (git-ignored)
```

## Status

M1 shipped + dogfooded on Chrollo: `context-core` + `council-review` + `council-init` + `using-council` + evals.
The rest of the Carmack suite — `council-plan`, `council-implement`, `test-architect`, `spec-writer` — is now
unified into this package (carried in with v2 manifests + light `context-core`/`council.config.md` integration),
so Ultra Council fully replaces the standalone Carmack install. Next: rewire plan/implement onto `context-core`
proper, then a first non-code mode (research / writing / ops) to prove generality.
