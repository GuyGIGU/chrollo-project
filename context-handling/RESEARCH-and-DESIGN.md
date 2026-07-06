# Context Handling Skill — Research & Design Brief

**Version:** v0.1 (research + proposed design; not the final skill)
**Date:** 2026-07-06
**Author:** Claude (Cowork), for GuyGIGU
**Goal:** Evolve the Carmack/Chrollo Council into a general-purpose *context-handling* skill —
a stack-agnostic **Context Core** plus **modes** (code review being one of them) — so that every
future workflow benefits from deliberate context engineering and resists "context rot."

> This document is the **research report + design proposal** you asked for. The next step (a
> separate pass) is to turn the accepted parts of Section 5 into the actual `SKILL.md` files.
> Section 7 lists the decisions I need from you before building.

---

## 0. Scope of this document

You have a mature, opinionated multi-agent framework — the **Carmack Council**
(`github.com/SamJHudson01/Carmack-Council`), which you've adapted into this Chrollo repo
(personas swapped to fit a deterministic numerical engine: Collina→Ramírez for backend,
Willison→McKinney for numerical, Postgres-Leach→data-integrity-Leach). You want to turn it into
"the ultimate context handling skill" for *all* future work.

The insight this document is built on: **the Council's most valuable, most transferable asset is
not code review — it's its context engineering.** The review output is the visible product; the
orchestration machinery underneath (map-don't-read, brief, partition, isolate, distil, remember)
is a near-textbook implementation of what the field now calls context engineering. That machinery
is what we extract and generalize.

---

## 1. TL;DR (the one-screen version)

- **One principle** governs everything (Anthropic): *find the smallest set of high-signal tokens
  that maximize the likelihood of the desired outcome.* Context is a finite "attention budget,"
  not free real estate.
- **One enemy** (Chroma's *Context Rot* study): model accuracy degrades as input grows — even on
  trivial tasks, even below the window limit, with a "lost in the middle" dip. More tokens ≠ better.
- **Four levers** to manage it (LangChain's taxonomy): **Write** (offload to disk), **Select**
  (pull in only what's needed, just-in-time), **Compress** (summarize / clear / cut), **Isolate**
  (split work into clean sub-contexts).
- **The Council already pulls all four levers** — expertly, but only for one domain (code) and one
  stack (Next.js). See the mapping in Section 2.
- **Proposal (Section 5):** extract a thin **Context Core** — the brief + partition + isolated
  dispatch + synthesis + durable memory + compaction/verification machinery, stack- and
  domain-agnostic — and make code review one **mode** (preset) that plugs into it, alongside
  research, writing, planning, and ops modes.

---

## 2. The current Council, decoded as context engineering

The Council's five skills (`spec-writer → council-plan → council-implement → council-review`, plus
a standalone `test-architect`) share one architecture, stated explicitly in `council-review/SKILL.md`:

> *"The Chair orchestrates. The experts read code. You never deep-read every file in scope. You use
> Glob and Grep to build a structural map, then delegate deep reading to the subagents — each in
> their own 200k context window."*

That single sentence is the whole discipline. Here is every context-engineering mechanism the
Council already implements, and the principle each one serves:

| Council mechanism (from the real SKILL.md files) | Context principle it implements | Lever |
|---|---|---|
| Chair builds a **structural map with Glob/Grep**, never deep-reads | Map, don't ingest; keep the orchestrator's window clean | Select |
| **Hard cap: "~8–10 files max. If you're reading more, you're doing the experts' job."** | Explicit budget ceiling on the orchestrator | Compress |
| **Context brief** written to `.council/.../context-brief.md` as the single source of truth | Distil once, reference many times; offload to disk | Write |
| **Domain file assignment** — each expert gets *only* its slice, "no expert gets more than ~25 files… a subagent drowning in files produces shallow findings" | Per-worker context budgeting; partition to avoid overload | Isolate |
| **Parallel sub-agents, each in an independent 200k window** | Context isolation; parallel exploration without cross-pollution | Isolate |
| Each expert **reads its own reference doc** (`references/*.md`) at dispatch time | Just-in-time domain knowledge, not front-loaded | Select |
| **Minimal return values** — experts write full findings to a file, return *one line* to the Chair ("prevents eight verbose Task outputs from flooding the Chair's context window") | Sub-agent returns a distilled summary, not its raw work | Compress |
| **"NO CODE in any subagent output"** — plain English only | Strip low-signal tokens (code blocks) from the aggregation | Compress |
| **Compact before dispatch** if context > 50%, with an explicit preserve-list | Compaction as a deliberate phase, not an accident | Compress |
| **"Compact Instructions"** section naming exactly what to preserve across a compaction event | Checkpoint/resume state so compaction is lossless where it matters | Write |
| **Phase 0 automated gates** (tsc/lint/tests) run first, results fed into the brief | Ground the reasoning in deterministic facts, not vibes | Select |
| **Pre-synthesis completeness gate** — confirm all N output files exist, re-dispatch on gaps | Robustness against sub-agent failure / compaction loss | — |
| **Synthesis: merge, dedupe, apply the "Carmack filter," cut to ≤15** | Curate the *output* the same way you curate the input | Compress |
| **Provenance** — every finding traces to expert + principle + reference line | Attribution survives aggregation; nothing is unsourced | Write |
| **`conventions.md`** read before every review; accepted patterns never re-flagged | Durable cross-session memory; the "compound effect" | Write |
| **Interactive hard gate** in council-plan (Feature Scope Summary + explicit "Ready to dispatch?") | Confirm the target before spending a large context budget | — |

**The flow, in one breath:** deterministic gates first → structural map (bounded) → a written
brief that becomes the single source of truth → partitioned, isolated, parallel deep-reads with
just-in-time domain docs → one-line returns → completeness check → curated synthesis with
provenance → settled decisions written to durable memory so the next run starts smarter.

That is a context-engineering pipeline that happens to output code reviews. **Swap the personas,
reference docs, output schema, and gates, and the same pipeline outputs anything.**

---

## 3. The research: principles, taxonomy, evidence

### 3.1 The core principle, and the enemy

**The principle (Anthropic, *Effective context engineering for AI agents*, Sep 2025).** Context
engineering is the successor to prompt engineering: the discipline of "curating and maintaining
the optimal set of tokens during inference." Because a transformer lets every token attend to
every other token (n² relationships), a model has a finite **attention budget** with *diminishing
marginal returns* — "every new token depletes this budget by some amount." The goal is therefore
"the smallest possible set of high-signal tokens that maximize the likelihood of the desired
outcome." System prompts should sit at the **right altitude** (neither brittle hardcoded logic nor
vague hand-waving); tools should be **token-efficient** and non-overlapping; few-shot examples
should be a few **canonical** ones, not an edge-case dump.

**The enemy (Chroma, *Context Rot*, 2025).** Across 18 leading models (GPT-4.1, Claude 4,
Gemini 2.5, Qwen3…), reliability *decreases as input length grows* — even on tasks as simple as
retrieval or text replication, and even when the window is nowhere near full. This compounds the
well-documented **"lost in the middle"** effect: accuracy is highest when the needle is at the
*start or end* of the context and sags in the middle. Practical implication for our brief design:
**put the highest-signal material at the top and bottom, not buried in the middle.**

**Long-horizon reality (Anthropic).** For tasks that exceed a window, waiting for bigger windows
won't save us — "context windows of all sizes will be subject to context pollution." The three
named remedies are **compaction**, **structured note-taking**, and **sub-agent architectures**
(more below).

### 3.2 A unifying taxonomy: Write / Select / Compress / Isolate

LangChain's framing is the cleanest mental model and maps 1:1 onto what the Council already does.
Analogy: the LLM is a CPU; its context window is RAM with limited capacity. The four moves:

| Lever | Definition | Council already does it via… | General-skill opportunity |
|---|---|---|---|
| **Write** | Save context *outside* the window | context-brief, per-expert files, `conventions.md`, FINAL-REVIEW | Generalize `conventions.md` → a durable "decisions + glossary + do-not-repeat" memory for any project |
| **Select** | Pull in *only* what's needed, when needed | Glob/Grep map, JIT reference docs, Phase-0 gate results | Add a reference **index** + JIT loader for non-code domains (docs, data, prior work) |
| **Compress** | Keep only the tokens the task needs | one-line returns, NO-CODE rule, compact-at-50%, cut-to-15 | Add explicit **budget accounting** + a standard compaction/resume artifact |
| **Isolate** | Split work into clean sub-contexts | parallel domain sub-agents, ≤25-file partitions | Make isolation a first-class Core primitive any mode can call, not review-only |

### 3.3 Technique catalog (grouped by lever)

**Write (offload & remember)**
- *Structured note-taking / scratchpad* — a `NOTES.md` / to-do list the agent maintains outside
  the window and re-reads after a reset (Anthropic; LangChain "Write"). Claude Code's to-do list
  and "Claude plays Pokémon" tallies are the reference examples.
- *Agentic memory / memory tool* — a file-based store the agent writes to and consults across
  sessions to build a knowledge base (Anthropic memory tool, public beta).
- *Decision/convention log with provenance* — the Council's `conventions.md` generalized: settled
  decisions, accepted patterns, and glossary, each traceable to when/why it was decided.

**Select (retrieve just-in-time)**
- *Just-in-time / agentic search* — hold lightweight identifiers (file paths, queries, links) and
  load content on demand rather than pre-loading everything (Anthropic). Glob/grep over a codebase
  is the canonical case; file names, folder structure, and timestamps are themselves signal.
- *Progressive disclosure* — let the agent discover context layer by layer through exploration,
  keeping only what's necessary in working memory.
- *Hybrid retrieval* — pre-load a little for speed (e.g. `CLAUDE.md`), explore for the rest.
- *Canonical few-shot examples* — a few high-signal examples beat an exhaustive rule list.
- *Right-altitude system prompt* — specific enough to steer, flexible enough to generalize.

**Compress (shrink without losing signal)**
- *Compaction* — summarize a near-full window and reinitialize with the summary + the few most
  relevant artifacts; tune for recall first, then precision (Anthropic).
- *Tool-result clearing* — the lightest-touch compaction: drop raw tool outputs once consumed
  (now a Claude Developer Platform feature).
- *Distilled sub-agent returns* — a sub-agent may burn tens of thousands of tokens but returns
  1–2k of distilled findings (Anthropic multi-agent research system).
- *Output curation* — the Council's "cut to ≤15 findings" and "Carmack filter": curate what you
  *emit*, not just what you ingest.

**Isolate (split into clean contexts)**
- *Sub-agent architectures* — a lead agent holds the high-level plan; specialized sub-agents do
  deep work in clean windows and return summaries. Best for parallelizable, read-heavy work like
  research (Anthropic; LangChain "Isolate").
- *Orchestrator/worker separation* — the Council's Chair/expert split.
- *Domain partitioning* — give each worker only its relevant slice; cap the slice size.

### 3.4 Adjacent pattern: spec-driven development

Spec-driven development (spec-kit, Kiro, Tessl) is context engineering wearing a different hat.
Its core move — **separate requirements/planning from implementation** — "compresses the context
into specs" that act as **"super-prompts"** aligned to the agent's window, preserving intent
across sessions and reducing hallucinated APIs in large repos. The Council's `spec-writer →
plan → implement` chain is exactly this, and *"Spec Kit Agents"* research adds **context-grounding
hooks**: read-only probes that re-anchor each phase (Specify/Plan/Tasks/Implement) in repository
evidence — worth borrowing as a general "re-ground before each phase" primitive.

### 3.5 Long-running harness: the "resume artifact" pattern

Anthropic's *Effective harnesses for long-running agents* (Nov 2025) tackles the case where a task
spans *many* context windows — "each new session begins with no memory of what came before, like
engineers working in shifts." Compaction alone proved insufficient (agents either one-shot the
whole task and run out mid-feature, or later declare victory prematurely). Their fix is a set of
durable, on-disk artifacts that any new session reads to get its bearings:

- A **progress log** (`claude-progress.txt`) + **git history** — the canonical "what happened so far."
- An **`init.sh`** — how to stand the environment up, so no session re-derives it.
- A **feature checklist** (`feature_list.json`) where items start marked *failing* and only flip to
  *passing* after **end-to-end self-verification** — this simultaneously prevents "do too much at
  once" and "mark done without testing."
- A fixed **get-up-to-speed ritual** at session start: read progress, read the checklist, read git
  log, run a smoke test *before* touching new work.

This is direct evidence for two Core primitives below: a **standard session-state artifact**
(primitive 9) and a **verification-before-done gate** (primitive 10). Notably, the article's own
"future work" calls out generalizing this harness beyond web apps to "scientific research or
financial modeling" and adding specialized sub-agents (testing/QA/cleanup) — i.e. exactly the
"general Core + modes" direction proposed here.

---

## 4. Gap analysis — what to change for a *general* skill

The Council is excellent at what it does; the gaps below are all about **generality and
portability**, not defects. Each is an opportunity for the Context Core.

| # | Gap in the current Council | Why it matters for "all future workflows" | Candidate fix in the Core |
|---|---|---|---|
| G1 | **Stack/domain lock-in** — personas, reference docs, output schema, and Phase-0 gates are Next.js/code-specific | A general context skill must serve research, writing, and ops too | Separate *mechanism* (the pipeline) from *content* (personas/refs/schema/gates), which becomes a **mode** |
| G2 | **Memory is review-only** — `conventions.md` stores "don't re-flag" patterns | Every workflow accumulates settled decisions worth remembering, not just reviews | Generalize to a **durable memory** model: decisions log + glossary + do-not-repeat + open-questions, per project |
| G3 | **No explicit budget accounting** — only heuristics (>50%, ~25 files, ≤15 findings) | Heuristics don't compose across task types; you can't see where the budget went | A lightweight **budget ledger**: declare a target, track what each phase spends, compact when a threshold trips |
| G4 | **Brief ordering isn't rot-aware** — the brief is well-structured but doesn't deliberately place highest-signal at the edges | Chroma's "lost in the middle" says middle-buried facts are recalled worst | **Edge-ordered brief**: decision/question at top, must-not-forget constraints at bottom |
| G5 | **Retrieval is glob/grep only** — perfect for code, thin for prose/data/prior-work | Non-code modes need to find the right *documents*, not the right *files* | A general **reference index + JIT loader** (paths, queries, links, prior outputs) any mode can populate |
| G6 | **Verification is code-specific** (tsc/lint/tests) | Research and writing need verification too (fact-checks, source-checks, counterarguments) | A general **verification primitive**: a verifier sub-agent or self-check phase, mode supplies the checks |
| G7 | **Scope gate exists only in `plan`** | Every expensive run should confirm its target first | Promote the **scope gate** to a universal Core phase (skippable for cheap tasks) |
| G8 | **Compaction/resume is described in prose**, not a standard artifact | Long-horizon runs of any kind need a reliable resume point | A standard **session-state file** (`session-state.md`) as the canonical compaction preserve-target |

---

## 5. Proposed design: a **Context Core** + **modes**

### 5.1 Architecture in one picture

```
                        ┌───────────────────────────────────────────┐
                        │             CONTEXT CORE (skill)           │
                        │  stack-agnostic, domain-agnostic pipeline  │
                        │                                            │
   MODE (preset) ─────► │  1 Scope Gate   → 2 Structural Map         │
   supplies:            │  3 Context Brief (edge-ordered, on disk)   │
   • persona set        │  4 Partition + Budget                      │
   • reference docs     │  5 Isolated Dispatch (JIT refs, min return)│
   • output schema      │  6 Completeness Gate                       │
   • gates/checks       │  7 Synthesis (merge/dedupe/curate, cite)   │
   • memory namespace   │  8 Durable Memory (read-before/write-after)│
                        │  9 Compaction + Resume                     │
                        │  10 Verification                           │
                        └───────────────────────────────────────────┘
        modes: code-review · plan · implement · research · write · ops · (your own)
```

The Core is **one skill** that knows *how* to handle context. A **mode** is a small config that
tells the Core *what* this run is about. `council-review` becomes the `code-review` mode with
almost no change to its content — it just stops re-implementing the pipeline, because the pipeline
now lives in the Core.

### 5.2 The Core primitives (reusable by every mode)

1. **Scope Gate** — State the *decision or deliverable* this run must produce, plus explicit
   out-of-scope boundaries; for non-trivial runs, confirm with the user before spending budget.
   (Generalizes council-plan's hard gate; skippable for cheap one-shot tasks.)
2. **Structural Map** — Survey the territory without ingesting it (Glob/Grep for code; an index /
   file listing / prior-output scan for docs). Enforce a **map budget ceiling** ("if you're
   reading deeply, you're doing a worker's job").
3. **Context Brief** — Write one **edge-ordered** brief to disk as the single source of truth:
   *top* = the decision + the question each worker must answer; *middle* = architecture / facts /
   inventory; *bottom* = hard constraints and "do-not-forget" items (G4). Everyone references the
   file, not a re-explanation.
4. **Partition + Budget** — Slice the work into worker assignments, each with only its relevant
   material and a **size cap**; declare a rough token budget per worker (G3).
5. **Isolated Dispatch** — Spawn workers in clean windows. Each reads the brief + its own
   reference doc **just-in-time**, does deep work, writes full output to its own file, and returns
   **one line** to the orchestrator. (Directly the Council's pattern, made mode-agnostic.)
6. **Completeness Gate** — Confirm every expected worker output exists and is non-empty;
   re-dispatch gaps before synthesizing. Never synthesize on partial results.
7. **Synthesis** — Merge, deduplicate (with explicit primary-owner rules), resolve conflicts,
   apply a relevance filter, **curate to a cap**, and keep **provenance** on every item.
8. **Durable Memory** — Before the run, read the project's memory (decisions, accepted patterns,
   glossary, open questions); after the run, offer to write newly-settled items back. This is the
   generalized `conventions.md` and the source of the **compound effect** (G2).
9. **Compaction + Resume** — When the budget threshold trips, compact against a **preserve-list**
   and keep a standard `session-state.md` so any run can resume losslessly (G8).
10. **Verification** — A final self-check or verifier sub-agent runs the mode's checks (code:
    build/lint/test; research: source & claim check; writing: brief-conformance) before delivery (G6).

### 5.3 The mode system

A **mode** is the smallest possible config that specializes the Core. Concretely, a mode declares:

- **Personas / lenses** — the review council's 10 experts are one persona set. A *research* mode
  might use lenses like "primary-source hunter / skeptic / synthesizer / fact-checker." A *writing*
  mode might use "structure / voice / evidence / cut-the-fat."
- **Reference docs** — the domain knowledge each lens loads JIT (the Council's `references/*.md`;
  a research mode's methodology notes; your own writing-style profile).
- **Output schema** — review uses P1/P2/P3 + breakdown table; plan uses sequenced tasks; research
  uses a findings brief with citations; writing uses a draft + change log.
- **Gates & checks** — review runs tsc/lint/tests at Phase 0 and verification; research runs a
  source-credibility pass; each mode supplies its own.
- **Memory namespace** — which durable-memory file this mode reads/writes (code review →
  `conventions.md`; research → `research-log.md`; etc.).

**Code review is just `mode: code-review`.** Everything in today's `council-review/SKILL.md` that
isn't the pipeline (the 10 experts, the overlap-resolution rules, the P1/P2/P3 schema, the
`conventions.md` update flow) becomes the mode's config; everything that *is* the pipeline moves to
the Core. This is a refactor, not a rewrite — the review behavior you rely on is preserved.

### 5.4 Durable-memory model (the compound-effect engine, generalized)

Generalize `conventions.md` into a small, per-project memory set the Core reads before and writes
after every run:

- **Decisions / accepted patterns** — settled choices that must not be re-litigated (today's `AP-*`).
- **Enforced rules** — things that must always/never happen (today's `EC-*`).
- **Glossary** — project-specific vocabulary so briefs stay short (a term instead of a paragraph).
- **Open questions** — known unknowns carried across sessions so they aren't rediscovered.

Each entry keeps provenance (when, why, which run). Read-before-run prevents re-work and re-flagging;
write-after-run (with user confirmation, as council-review already does in Phase 7) makes every
session start smarter than the last.

### 5.5 A task-agnostic Context Brief template

```
## Context Brief — <run title>            [TOP = highest signal]
- Decision/deliverable this run must produce:
- The one question each worker must answer in their lane:
- Out of scope:

## Landscape                               [MIDDLE = reference detail]
- What this is / what it does:
- Structure / inventory (from the map, not deep reads):
- Relevant prior decisions (from durable memory):
- Automated/factual grounding (gate results, data, prior outputs):

## Worker assignments
- <lens/persona>: <only its slice> — reads <reference doc> — budget ~<N> tokens

## Hard constraints — DO NOT FORGET       [BOTTOM = re-surfaced signal]
- <non-negotiables, accepted patterns not to re-flag, safety rails>
```

Top and bottom carry the load-bearing instructions (rot-aware); the middle carries reference
detail that workers can skim.

---

## 6. Migration path (next session, once you approve a shape)

1. **Lift the pipeline** out of `council-review/SKILL.md` into a new `context-core` skill (the ten
   primitives in 5.2), keeping the exact wording that already works (map-don't-read, ≤N caps,
   minimal returns, compact-at-threshold, completeness gate).
2. **Reduce `council-review` to a mode config** that points at the Core and supplies the 10
   experts + P1/P2/P3 schema + overlap rules + `conventions.md` namespace.
3. **Add one non-code mode** (I'd suggest `research`) as the proof that the Core generalizes.
4. **Generalize memory**: keep `conventions.md` for code review; add per-mode memory files.
5. **Package** per your answer in Section 7 (Claude Code `.skill` bundles like the Carmack repo,
   vs. a Cowork-native skill) and validate.

---

## 7. Open decisions for you (before I build)

I'll ask these as pickable questions after you've read this, but here they are in writing:

1. **Packaging** — Build as Claude Code `.skill` bundles (matching the Carmack repo's
   `references/ + skills/ + build.sh` layout) or as a Cowork-native skill in this project?
2. **Blast radius** — Refactor the existing 5 Carmack skills onto the Core, or build the Core
   fresh and port only `council-review` first (lower risk)?
3. **Persona grounding for non-code modes** — Keep the "named real expert" device (Fowler, Beck…)
   for research/writing lenses too, or use plain functional lens names there?
4. **Memory scope** — Per-project memory only (like `conventions.md` today), or also a global
   cross-project memory for durable preferences?
5. **First non-code mode to prove generality** — research, writing, or ops/automation?
6. **Naming** — Keep "Council" as the umbrella brand, or name the general skill something like
   "Context Core" / "Context Handler" with Council as the code-review mode?

---

## 8. Sources

- Anthropic — *Effective context engineering for AI agents* (Sep 29, 2025): https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic — *Effective harnesses for long-running agents*: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic — *How we built our multi-agent research system*: https://www.anthropic.com/engineering/multi-agent-research-system
- Anthropic — *Writing tools for AI agents*: https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic — *Context management / memory tool* (news): https://www.anthropic.com/news/context-management
- Chroma — *Context Rot: How Increasing Input Tokens Impacts LLM Performance*: https://research.trychroma.com/context-rot
- LangChain — *Context Engineering for Agents* (Write/Select/Compress/Isolate): https://www.langchain.com/blog/context-engineering-for-agents
- Martin Fowler — *Understanding Spec-Driven Development: Kiro, spec-kit, and Tessl*: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- Microsoft for Developers — *Diving into Spec-Driven Development with GitHub Spec Kit*: https://developer.microsoft.com/blog/spec-driven-development-spec-kit
- Source framework under study — *Carmack Council*: https://github.com/SamJHudson01/Carmack-Council
- In-repo evidence — `.council/review-output/**` (context-brief.md, FINAL-REVIEW.md, per-expert files) and `conventions.md`

