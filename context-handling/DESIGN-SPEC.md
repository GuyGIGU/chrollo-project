# Council v2 — Design Spec: Context Core + council-review

**Version:** v0.2 — **LOCKED** (build-ready; folds in the field-scan adoptions from `FIELD-SCAN-and-INSPIRATION.md`)
**Date:** 2026-07-06
**For:** GuyGIGU
**Companion doc:** `context-handling/RESEARCH-and-DESIGN.md` (the research this is built on)

---

## 0. Decisions locked

| # | Decision | Choice |
|---|---|---|
| 1 | Packaging | **Claude Code `.skill` bundles**, installed once globally, tailored per project |
| 2 | First build | **`council-review` on the Core** (port the review skill first) |
| 3 | Personas | **Keep the named experts** (Fowler, Beck, …) |
| 4 | Memory | **Per-project** only (global cross-project memory = future follow-up) |
| 5 | Non-code mode | **Deferred** — prove generality with one later; council-review first |
| 6 | Brand | **"Council"** stays |
| 7 | Invocation | **Suggest-then-confirm** — proposes a review when warranted and waits for the operator's go-ahead before dispatching the fan-out; explicit `/council-review` runs immediately |
| 8 | Cross-model | **No** — Claude only for now (single-model council) |

**Field-scan adoptions folded in (2026-07-06):** bias-controlled synthesis, per-finding validation
(hallucination filter), compaction re-bootstrap, zero-context-worker briefs, and a `drill`-style
eval milestone. Deferred: two-stage worker review → future `council-implement` mode. Dropped:
cross-model pass. (Rationale in `FIELD-SCAN-and-INSPIRATION.md` §3.)

**Amendment 2026-07-06:** decision #7 changed from *auto-trigger* to *suggest-then-confirm* — a council
run is a costly multi-agent fan-out, so the mode proposes a review and the operator approves before any
workers are dispatched (consistent with Context Core phase 1). Explicit `/council-review` still runs immediately.

---

## 1. The thesis: from "copy `.council`" to a self-tailoring Council

Today, giving a new project a council means copying the skill in and hand-editing personas to fit
the stack (you did exactly this for Chrollo: Collina→Ramírez, Willison→McKinney,
Postgres-Leach→data-integrity-Leach, plus stack context rewrites). That works, but it's manual,
drifts per project, and re-implements the same pipeline everywhere.

**Council v2 splits into two layers so the manual part disappears:**

1. **Context Core** — one installed-once skill that owns the *pipeline* (how to handle context:
   map → brief → partition → isolate → synthesize → remember → compact → verify). Stack-agnostic,
   domain-agnostic. Never edited per project.
2. **Modes** — small configs that own the *content* (which experts, which reference docs, which
   output schema, which gates). `council-review` is the first mode.
3. **`council-init`** — the level-up. Point it at any repo and it **auto-tailors the council to that
   project**: detects stack/domain, adapts the expert roster (renames or swaps experts the way you
   did by hand), writes project-local reference notes, and seeds the memory file. The result is a
   custom council per project with zero manual persona surgery.

So: *the pipeline is shared and improved once; the council fits each project automatically; memory
stays laser-focused per project.* That is the "next level" beyond copying `.council` around.

---

## 2. Package & repo layout

Mirrors the Carmack repo's proven structure (shared `references/`, per-skill `SKILL.md` +
`manifest.json`, a `build.sh` that bundles `.skill` files) — extended with the Core and init.

```
council/
├── README.md
├── STACK.md                     # per-project assumptions live in the PROJECT, not here (see §5)
├── scripts/
│   ├── build.sh                 # reads each manifest, copies refs, packages .skill → dist/
│   ├── package_skill.py
│   └── quick_validate.py
├── references/                  # single source of truth for shared reference docs
│   ├── context-engineering.md   # NEW: the Core's own doctrine (attention budget, rot, W/S/C/I)
│   ├── security.md  refactoring.md  quality-backend.md  quality-frontend.md
│   ├── quality-postgres.md  quality-testing.md  quality-llm.md
│   ├── quality-ui.md  quality-ux.md
│   └── roster/                  # NEW: expert-roster building blocks for council-init (see §5)
│       └── expert-catalog.md    # canonical experts + when each applies + its reference doc
├── skills/
│   ├── context-core/            # NEW — the reusable pipeline
│   │   ├── SKILL.md
│   │   └── manifest.json        # bundles references/context-engineering.md
│   ├── council-init/            # NEW — per-project auto-tailoring
│   │   ├── SKILL.md
│   │   └── manifest.json        # bundles references/roster/expert-catalog.md
│   └── council-review/          # ported: mode config that calls the Core
│       ├── SKILL.md
│       └── manifest.json        # bundles the 10 quality-*/security/refactoring refs
└── dist/                        # built .skill packages
    ├── context-core.skill
    ├── council-init.skill
    └── council-review.skill
```

**Install model:** the three `.skill` files install once (globally, `~/.claude/skills/`). Per
project, the user runs `council-init` once to lay down the project-local config + memory; from then
on `council-review` (and future modes) read that config. Nothing in `council/` is edited per project.

**What lives in the project (written by `council-init`), not in the skill:**

```
<project-root>/
├── .council/
│   ├── council.config.md        # the tailored roster + stack context for THIS project
│   └── review-output/…          # timestamped run outputs (as today)
└── conventions.md               # per-project durable memory (as today)
```

---

## 3. The Context Core skill (`skills/context-core/SKILL.md`)

The Core is written as a **callable pipeline** a mode invokes. It contains no personas and no
stack knowledge — only the ten primitives from the research, rendered as concrete phases. A mode
hands the Core five things: `{personas, reference_docs, output_schema, gates, memory_namespace}`.

### Core doctrine (top of the SKILL, the "right altitude" system framing)
> Context is a finite attention budget with diminishing returns; more tokens ≠ better (context
> rot). Your job as orchestrator is to spend the *smallest set of high-signal tokens* that produces
> the outcome. You **map, you do not ingest**. Deep reading is delegated to isolated workers.
> Highest-signal instructions go at the **top and bottom** of every brief (lost-in-the-middle).

### The ten phases (each maps to a research primitive)

1. **Scope Gate** — Produce a one-block statement: *the decision/deliverable this run yields* +
   *explicit out-of-scope*. For non-trivial runs, confirm with the user before spending budget.
   (Cheap/one-shot runs may auto-skip with a logged assumption.)
2. **Structural Map** — Survey without ingesting: Glob/Grep for code; index/listing/prior-output
   scan otherwise. **Hard ceiling** on files/artifacts read here ("if you're deep-reading, you're
   doing a worker's job"). Read the project `.council/council.config.md` + memory now.
3. **Context Brief (edge-ordered)** — Write ONE brief to `.council/<mode>-output/$TS/context-brief.md`:
   *top* = decision + the question each worker must answer; *middle* = landscape/inventory/facts;
   *bottom* = hard constraints + "do-not-forget" (accepted patterns not to re-flag).
   **Write for a zero-context worker** — the brief must stand alone; a worker in a clean window
   shares nothing but this file (Superpowers' "plan for someone with no project context").
4. **Partition + Budget** — Slice work into worker assignments, each with only its slice, a **size
   cap**, and a rough token budget. Every artifact assigned to ≥1 worker (unassigned = a gap).
5. **Isolated Dispatch** — Spawn workers in clean windows. Each reads the brief + its own reference
   doc **just-in-time**, writes full output to its own file, returns **one line** to the orchestrator.
   Compact the orchestrator before dispatch if over threshold, preserving the brief path + phase.
6. **Completeness Gate** — Confirm every expected worker file exists and is non-empty; re-dispatch
   gaps. Never synthesize on partial results.
7. **Synthesis** — **Aggregate before judging:** first compile and dedupe ALL worker findings
   *before* forming any verdict or re-reading source — the Chair must not become a biased extra
   reviewer with a veto (Triple-Agent). Then resolve conflicts (mode supplies primary-owner rules),
   apply a relevance filter, **curate to a cap**, keep **provenance** on every item.
8. **Durable Memory** — Read-before (done in phase 2); after the run, offer to write newly-settled
   items back to the memory namespace (the `conventions.md` Phase-7 flow, generalized).
9. **Compaction + Resume** — On budget threshold, compact against a preserve-list; maintain a
   standard `session-state.md` so any run resumes losslessly. **Re-bootstrap after compaction:**
   actively reload the Core doctrine + brief path + current phase after any reset, so the method
   never silently drops mid-run (Superpowers re-injects its bootstrap post-compaction).
10. **Verification** — Run the mode's checks (code: build/lint/test; research: source/claim check)
    before delivery; nothing is "done" until it passes. **Validate each shipped finding against the
    real artifact** (read the source / run the query) to filter subagent hallucinations — and never
    dismiss a lone dissenter without checking; sometimes one worker caught the critical issue (Triple-Agent).

**What the Core exposes to modes (the contract):** phase hooks + the five inputs above. A mode
never re-implements phases 2–9; it only supplies content and the phase-1/phase-10 specifics.

---

## 4. `council-review` as a mode (port, don't rewrite)

Everything in today's `council-review/SKILL.md` that is *pipeline* moves to the Core. What remains
is a compact **mode config** — essentially the parts you already rely on:

```
mode: council-review
invocation: SUGGEST-THEN-CONFIRM — propose a review when warranted, wait for the operator's go-ahead before dispatch; explicit /council-review runs immediately
chair: John Carmack (philosophy + the "Carmack filter" at synthesis)
personas: [Hunt, Dodds, Collina, Leach, Vercel, Saarinen, Friedman, Fowler, Willison, Beck]
          # per-project roster comes from .council/council.config.md (see §5) — this is the DEFAULT
reference_docs: references/{security, quality-frontend, quality-backend, quality-postgres,
                            quality-ui, quality-ux, refactoring, quality-llm, quality-testing}.md
output_schema: P1/P2/P3 findings + Summary table + Verdict + Findings-Breakdown-by-Expert
gates:
  phase_0: [type-check, lint, unit/integration, e2e]   # supplied per project by council-init
  verification: re-run gates green after any in-loop fixes
dedupe_rules: <the existing Saarinen/Dodds, Friedman/Dodds, Fowler/Collina, Willison/Hunt, … rules>
memory_namespace: conventions.md   # AP-*/EC- read-before, write-after (Phase 7 unchanged)
synthesis_cap: 15
subagent_rules: [NO CODE in output, minimal one-line return, stay-in-lane]
```

The review's *behavior is preserved exactly* — same experts, same P1/P2/P3, same overlap
resolution, same conventions.md compound effect. It just stops carrying the pipeline. This is the
low-risk first port you chose (decision #2).

---

## 5. `council-init` — the per-project auto-tailoring (the level-up)

Run once when the Council lands in a new project. It removes the manual persona-surgery step.

**Inputs:** the target repo. **Output:** `.council/council.config.md` + a seeded `conventions.md`.

**What it does:**

1. **Detect stack & domain** — map the repo (manifest files, languages, frameworks, presence of a
   DB, a frontend, an LLM pipeline, a numerical engine, etc.). *Map, don't ingest.*
2. **Tailor the roster from the expert catalog** (`references/roster/expert-catalog.md`). The
   catalog lists canonical experts, *when each applies*, and its reference doc. Init selects and
   adapts:
   - Drop experts with no surface (no frontend → no Dodds/Saarinen/Friedman).
   - **Swap by domain fit**, encoding the judgement you made by hand for Chrollo, e.g.:
     - deterministic numerical/data engine → swap the LLM-pipeline seat (Willison) for a
       **numerical** seat (McKinney); keep its reference doc as `quality-llm.md`→`quality-numerical.md`.
     - SQLite/parquet instead of Postgres → recast Leach as **data-integrity** rather than Postgres.
     - generic backend (not Node/tRPC) → recast Collina as a general **backend** seat (Ramírez).
   - Propose the roster to the user for confirmation (keep names per decision #3).
3. **Write project stack context** — the per-project `STACK.md`-style block into
   `council.config.md` (what today lives hard-coded in each SKILL's "Stack Context").
4. **Wire the gates** — detect the project's real check commands (e.g. `pytest`, `npm run lint`,
   `tsc`, cypress/none) and record them as the mode's Phase-0 + verification gates, so review isn't
   hard-coded to `tsc/vitest/cypress`.
5. **Seed memory** — create `conventions.md` with any obvious accepted patterns discovered (or
   empty with the standard header).

**Why this is the differentiator:** the pipeline is maintained once in the Core; the *fit* to each
project is generated, not copied; and because the roster/gates/stack live in a project-local config,
the same installed skill behaves like a bespoke council everywhere without edits to the skill itself.

---

## 6. Per-project memory model (decision #4)

Keep it exactly as focused as today, generalized only enough to serve the Core:

- **`conventions.md`** at project root stays the memory namespace for `council-review`
  (`AP-*` accepted patterns / `EC-*` enforced conventions, with provenance + timestamp).
- Read-before-run (Core phase 2), write-after-run with user confirmation (Core phase 8 = today's
  Phase 7). Unchanged compound effect.
- **No global/cross-project memory** now. Each project's council knows only its own project. (The
  multi-project "command center" idea is parked as a future follow-up, per your note.)
- Future modes get their own namespace file (e.g. `research-log.md`) — but that's later.

---

## 7. Build & validation plan

1. Author `references/context-engineering.md` (Core doctrine) + `references/roster/expert-catalog.md`.
2. Write `skills/context-core/SKILL.md` (the ten phases) + manifest.
3. Port `skills/council-review/SKILL.md` → mode config that calls the Core + manifest.
4. Write `skills/council-init/SKILL.md` + manifest.
5. `scripts/build.sh` → `dist/*.skill`; run `quick_validate.py`.
6. **Suggest-then-confirm + bootstrap:** write a `using-council` bootstrap (injected at session start
   and re-injected after compaction) and tune each mode's `description` so the Council *proposes* a run
   when warranted and waits for the operator's go-ahead before dispatching (explicit `/council-review`
   runs immediately).
7. **Evals (`drill`-style):** build a small fixture repo + behavioral checks — (a) `council-init`
   picks the right roster/gates, (b) `council-review` triggers when intended and stays quiet when
   not, (c) a seeded bug is caught, (d) a seeded accepted-pattern is NOT re-flagged. Modeled on
   Superpowers' eval harness. **No skill ships without passing.**
8. **Dogfood on Chrollo:** run `council-init` here, confirm it reproduces your current hand-tuned
   roster (Ramírez/McKinney/data-integrity Leach) and gates (`pytest`, `npm run lint`), then run a
   `council-review` and diff against a known-good past review in `.council/review-output/`.

---

## 8. Milestones / next actions

- **M1 (next):** build the Core (with the 4 folded-in rules) + `council-review` mode + `council-init`
  + `using-council` suggest-then-confirm bootstrap + `drill`-style evals, package, and dogfood on Chrollo
  (steps 1–8 above). This is the whole "council-review first" scope.
- **M2:** add one non-code mode (research | writing | ops — your pick) to prove the Core generalizes;
  bring in the deferred **two-stage worker review** when `council-implement` lands.
- **M3 (someday):** optional global cross-project memory. (Cross-model review stays dropped unless revisited.)

---

## 9. Open micro-decisions (non-blocking; defaults chosen)

1. **`council-init` re-runs** — on stack change, re-tailor and *merge* into `council.config.md`
   (default) or regenerate fresh? *Default: merge, show a diff.*
2. **Core doctrine location** — one `references/context-engineering.md` the Core reads each run
   (default) vs inlined into the Core SKILL. *Default: reference doc, so it's tunable without
   touching the pipeline.*
3. **Expert catalog authority** — seed `expert-catalog.md` from the 10 Carmack experts + your
   Chrollo adaptations (default), and grow it as new project types appear.
