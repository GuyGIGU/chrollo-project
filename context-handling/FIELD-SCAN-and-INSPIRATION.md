# Council v2 — Field Scan & Inspiration

**Version:** v0.1
**Date:** 2026-07-06
**For:** GuyGIGU
**Purpose:** Before locking `DESIGN-SPEC.md`, compare Council v2 against the best comparable
skills/frameworks in the wild (GitHub + community) and steal what's worth stealing.

---

## 1. Who else is solving this, and how

Five reference points, from "closest sibling" to "adjacent."

**A. Superpowers** — obra / Jesse Vincent (Prime Radiant). ~246k stars; installable across Claude
Code, Codex, Cursor, Gemini, etc. https://github.com/obra/superpowers
A full *methodology* delivered as auto-triggering skills: `brainstorming` (Socratic spec, shown in
digestible chunks) → `using-git-worktrees` (isolated workspace) → `writing-plans` (bite-sized
2–5 min tasks, each with exact paths + verification) → `subagent-driven-development` (fresh subagent
per task, **two-stage review: spec-compliance then code-quality**) → `test-driven-development`
(RED-GREEN-REFACTOR, deletes code written before its test) → `requesting-code-review` (severity-gated)
→ `finishing-a-development-branch`. Plus meta-skills: `dispatching-parallel-agents`,
`verification-before-completion`, and **`writing-skills`** (authoring + a **`drill` eval harness**
that behaviorally tests skills). Two standout context ideas: (1) skills are **mandatory and
auto-trigger** ("check for relevant skills before any task"), and (2) a **bootstrap is re-injected
at session start *and again after compaction*** so the methodology survives a context reset.

**B. Code Review Turbo ("triple agent")** — nolanlawson (gist).
https://gist.github.com/nolanlawson/4150b0ca9640654c256b324fac0d5253
One review skill that runs **three *independent* reviewers** — Cursor Bugbot + a Claude sub-agent +
Codex — on the **exact same prompt**, then cross-references. Its two brilliant moves:
(1) **Cross-model triangulation to filter hallucinations** — a finding's credibility rises with
agreement across independent reviewers (but "don't dismiss a lone dissenter — sometimes they found
the critical bug"). (2) **Bias-controlled synthesis**: the orchestrator is *forbidden from
investigating the code until all reviewers have returned* — "if you investigate first, you become a
biased 4th agent with a veto." Compile findings first, *then* validate each against the real code
(read source, run `EXPLAIN ANALYZE`) before reporting. Ends with an **agent-agreement matrix** +
merge recommendation.

**C. GitHub Spec Kit / spec-driven development** (covered in `RESEARCH-and-DESIGN.md` §3.4).
Specs as "super-prompts" that compress context and separate planning from implementation;
"context-grounding hooks" re-anchor each phase in repo evidence.

**D. Anthropic multi-agent research system** — orchestrator holds the plan; sub-agents explore in
clean windows and return **1–2k-token distilled summaries**, not raw work. (The pattern the Council
and Superpowers both use.)

**E. Subagent libraries** — VoltAgent `awesome-claude-code-subagents` (100+ role agents), rshah515
(133+), wshobson `agents` (multi-harness marketplace). These are **catalogs of role-specialized,
isolated-context subagents** — a menu, not an orchestration. Useful as a source of persona
definitions, not as a competing method.

---

## 2. Comparison matrix (context-handling mechanisms)

Legend: ✅ has it · ◑ partial · ➖ no · **★** = notably strong

| Mechanism | Council v2 (proposed) | Superpowers | Triple-Agent | Spec Kit | Subagent libs |
|---|---|---|---|---|---|
| Curated context **brief** as single source of truth | ✅ ★ (edge-ordered) | ◑ (design doc) | ◑ (shared prompt) | ✅ (the spec) | ➖ |
| **Isolated** parallel workers, clean windows | ✅ ★ | ✅ | ✅ | ◑ | ✅ |
| **Distilled** minimal returns to orchestrator | ✅ ★ | ✅ | ◑ | ➖ | ◑ |
| Persistent **memory / compound effect** | ✅ ★ (`conventions.md`) | ◑ (plans/docs) | ➖ | ✅ (specs) | ➖ |
| **Per-project auto-tailoring** of the roster | ✅ ★ (`council-init`) | ➖ | ➖ | ➖ | ➖ |
| Deep **domain grounding** (named experts + ref docs) | ✅ ★ | ◑ | ➖ | ➖ | ✅ |
| **Cross-model** triangulation (hallucination filter) | ➖ → **adopt** | ➖ | ✅ ★ | ➖ | ➖ |
| **Bias-controlled** synthesis (aggregate-before-judging) | ◑ → **adopt** | ➖ | ✅ ★ | ➖ | ➖ |
| **Compaction-survival** re-bootstrap | ◑ (preserve-list) → **adopt** | ✅ ★ | ➖ | ➖ | ➖ |
| **Auto-trigger / mandatory** invocation | ◑ → **consider** | ✅ ★ | ➖ | ◑ | ◑ |
| **Verification** before "done" | ✅ (mode gates) | ✅ ★ | ✅ ★ | ◑ | ➖ |
| **Evals** for the skill itself | ➖ → **adopt** | ✅ ★ (`drill`) | ➖ | ➖ | ➖ |
| Multi-harness portability | ➖ | ✅ ★ | ◑ | ◑ | ◑ |

The pattern: **Council v2 leads on brief quality, memory, and per-project tailoring; the field
leads on triangulation, bias control, compaction-survival, and — importantly — testing the skill
itself.**

---

## 3. What to steal (adopt / consider / skip)

### Adopt — high value, aligned with the design

1. **Bias-controlled synthesis (from Triple-Agent).** Add a hard rule to Core **phase 7**: the Chair
   compiles and deduplicates all worker findings *before* forming its own opinion or re-reading
   code; only then validates. Prevents the orchestrator from becoming a biased extra reviewer.
   *Cheap, pure win, no new machinery.*
2. **Finding-validation / hallucination filter (from Triple-Agent).** In Core **phase 10
   (verification)**, each P1/P2 finding must be confirmed against the real artifact (read the
   source, run the query) before it ships — and "never dismiss a lone dissenter without checking."
   Directly attacks subagent pattern-matching, which the Carmack filter only partially catches.
3. **Compaction re-bootstrap (from Superpowers).** Upgrade Core **phase 9** from a passive
   preserve-list to an *active re-injection*: after any compaction, reload the Core doctrine + the
   current brief path + phase, so a mid-run reset doesn't quietly drop the method.
4. **"Zero-context worker" brief principle (from Superpowers' plans).** Make explicit in Core
   **phases 3–4** that every worker assignment must be self-contained enough for a worker "with no
   project context" — because that is literally the worker's situation in a clean window. Tightens
   what the brief must carry.
5. **Skill evals (from Superpowers' `drill` / `writing-skills`).** Add an **eval milestone** to the
   build plan: a small fixture repo + expected-behavior checks that verify (a) `council-init`
   reproduces the right roster/gates, (b) `council-review` triggers when intended, (c) a known bug
   is caught and a known accepted-pattern is *not* re-flagged. This is the single biggest lever for
   "truly optimize our results" — right now nothing tests the Council.

### Consider — good, but a judgement call

6. **Optional cross-model pass (from Triple-Agent).** Keep the Council single-model by default, but
   let a mode optionally route one or two seats through a *different* model/harness (e.g. Codex) for
   true independence on high-stakes reviews. Adds cost/complexity; make it an opt-in flag, not default.
7. **Auto-trigger / mandatory framing (from Superpowers).** Sharpen each mode's `description` so the
   Council fires proactively (not just on `/council-review`), and add a lightweight `using-council`
   bootstrap. Powerful, but you may *prefer* explicit invocation for a heavy multi-agent run —
   your call.
8. **Two-stage worker review (from Superpowers).** For the future `council-implement` mode: check
   spec-compliance (cheap) before code-quality (expensive). Not relevant to `council-review` first.

### Skip (for now) — misaligned with your locked decisions

- **Multi-harness portability** — real work, and you chose Claude Code `.skill`. Park it.
- **Global subagent catalogs as-is** — you keep *named experts + reference docs* (decision #3),
  which is deeper than generic role agents. Mine them only for new persona ideas via `council-init`.
- **Full TDD/worktree/branch methodology (Superpowers' SDLC)** — that's a whole dev methodology;
  the Council is a context-handling layer. Borrow the *ideas* (verification, evals), not the SDLC.

---

## 4. Where Council v2 is already ahead (keep these; they're the moat)

- **Per-project auto-tailoring (`council-init`)** — none of the comparables adapt the *reviewer
  roster and gates to the specific project* automatically. This is genuinely novel and is your
  differentiator.
- **Named-expert domain grounding + reference docs** — deeper, more opinionated review than generic
  "code-reviewer" subagents; grounded in real practitioners' published principles.
- **`conventions.md` compound memory** — the "don't re-flag accepted patterns; get smarter every
  run" loop. Superpowers persists plans/designs, Triple-Agent persists nothing. Yours is stronger.
- **Edge-ordered, rot-aware brief** — an explicit answer to context rot that the others don't state.

---

## 5. Net effect on the design (proposed edits to `DESIGN-SPEC.md`)

If you approve, I'll fold these five "Adopt" items in before locking:

1. Core **phase 7** → add the *aggregate-before-judging* bias rule.
2. Core **phase 10** → add per-finding *validation against the real artifact* + lone-dissenter rule.
3. Core **phase 9** → *active re-bootstrap* after compaction, not just a preserve-list.
4. Core **phases 3–4** → state the *zero-context worker* requirement for briefs/assignments.
5. Build plan → add an **eval milestone** (fixture repo + triggering/behavior/memory checks),
   modeled on Superpowers' `drill`.

Items 6–8 (cross-model opt-in, auto-trigger bootstrap, two-stage worker review) I'd hold as
flagged options pending your call in §3.

---

## 6. Sources

- Superpowers — https://github.com/obra/superpowers · release note: https://blog.fsck.com/2025/10/09/superpowers/
- Code Review Turbo (triple-agent) — https://gist.github.com/nolanlawson/4150b0ca9640654c256b324fac0d5253
- Anthropic — *Multi-agent research system* — https://www.anthropic.com/engineering/multi-agent-research-system
- GitHub Spec Kit / SDD — https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html · https://developer.microsoft.com/blog/spec-driven-development-spec-kit
- Subagent libraries — https://github.com/VoltAgent/awesome-claude-code-subagents · https://github.com/wshobson/agents · https://github.com/rshah515/claude-code-subagents
- Curated index — https://github.com/hesreallyhim/awesome-claude-code
- Source framework — Carmack Council — https://github.com/SamJHudson01/Carmack-Council
