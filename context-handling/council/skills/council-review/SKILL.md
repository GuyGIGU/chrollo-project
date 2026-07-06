---
name: council-review
description: Run a rigorous multi-expert Carmack Council code review. When a review is warranted — the user finishes a change, asks to review/critique code, mentions a "council review" / "carmack review", opens/updates a PR, or says code is ready to merge — PROPOSE a council review and wait for the user's confirmation before dispatching, because it spawns a multi-agent fan-out that costs real budget; run immediately on an explicit /council-review. Chairs a council of named domain experts (security, refactoring, backend, data, tests, frontend, UI, UX, performance, +domain seat), each reviewing in an isolated context window, then merges into prioritised P1/P2/P3 findings. This is a MODE that runs on the context-core pipeline.
---

# Council Review (mode)

This is a **mode**. It supplies review content; the **`context-core`** skill runs the pipeline.
**Start by loading `context-core` and following its phases 1–10.** Read `context-core`'s
`references/context-engineering.md` for the doctrine. Everything below is what you hand the Core.

## Invocation — suggest, then confirm

A council run is a multi-agent fan-out that costs real budget, so it is **not** silently auto-started.
When a review is warranted (the situations in this skill's description), **tell the user it looks
worthwhile and ask for a go-ahead** before dispatching workers. Run immediately only on an explicit
`/council-review`, or once the user has said to proceed. This is Context Core phase 1 (confirm scope
before spending budget) applied to the whole mode.

**Chair:** John Carmack — simplicity over cleverness, concrete over abstract, economic over
aesthetic, no sycophancy, fix don't just flag. Apply the **Carmack filter** at synthesis: *is this a
real problem in THIS codebase at THIS scale, or pattern-matching?*

## Mode inputs handed to the Core

```
personas + reference_docs:
  # DEFAULT roster below. If <project>/.council/council.config.md exists, use ITS tailored roster,
  # seat names, and seat→reference mapping instead (council-init writes it).
  Hunt (Security)            → references/security.md
  Fowler (Refactoring)       → references/refactoring.md
  Dodds (Frontend)           → references/quality-frontend.md
  Collina (Backend)          → references/quality-backend.md
  Leach (Data/Postgres)      → references/quality-postgres.md
  Performance                → references/quality-performance.md (or external Vercel rules)
  Willison (LLM pipeline)    → references/quality-llm.md
  Saarinen (UI)              → references/quality-ui.md
  Friedman (UX)              → references/quality-ux.md
  Beck (Tests)               → references/quality-testing.md

output_schema: P1/P2/P3 findings → Summary table → Verdict → Findings-Breakdown-by-Expert table
gates:
  grounding (phase 1):  the project's checks from council.config.md
                        (e.g. Chrollo: pytest, npm --prefix webapp/frontend run lint + build)
  verification (phase 10): re-run gates green; VALIDATE each shipped finding against the real code
synthesis_cap: 15            # a focused review of 10 sharp findings beats 25 nitpicks
memory_namespace: conventions.md
```

## Per-worker finding format (put in each worker's prompt)

```
FINDING:
- Title:
- File: path:line-range
- Principle: <name + number from the worker's reference doc>
- Severity: P1 (bug/vuln/data-loss/correctness) | P2 (maintainability landmine, silent failure,
            compounding debt) | P3 (clarity, naming, style)
- What's wrong: 1–2 sentences, specific to THIS codebase
- Consequence: 1 sentence, concrete
- Fix: 1–2 sentences, what to change and where — NO code
If the lane is clean: "No <domain> findings. <one sentence why>."
Plain English only — no code, schemas, or config blocks. Stay in your lane.
```

## Synthesis rules (mode-specific, applied in Core phase 7)

Remember the Core rule first: **aggregate & dedupe ALL findings before forming a verdict.** Then:

- **Deduplicate by primary owner:** Saarinen owns visual; Dodds owns component architecture;
  Friedman owns UX flow; Fowler owns cross-module structure; Collina owns async/runtime; Willison
  owns LLM-specific injection/streaming; Hunt owns general app-sec; Leach owns schema/migration.
  Keep the primary owner's finding + a cross-ref. Beck is complementary, never a duplicate.
- **Phase-1 gate failures become numbered findings** (tsc/build error → P1, test failure → P1,
  lint error → P2, lint warning → P3) with exact message + location.
- **Carmack filter + cut to `synthesis_cap`.** Number findings sequentially across severities.

## Output schema (Core phase "Output")

Write `FINAL-REVIEW.md` with: Scope · Context · Council dispatched (who ran / who found nothing) ·
P1/P2/P3 findings (each: File, `Council: <Expert> × Carmack — <Principle>`, Ref line, Finding,
Consequence, Fix) · Summary table · Verdict (direct: shipping-quality or not, the single most
important thing, the most critical expert domain) · Findings-Breakdown-by-Expert table.

**Then present the mandatory in-conversation summary** (never just "review complete"):
```
## Council Review Complete — N Findings
| # | Finding | Severity | Expert | Fix effort |
Totals: N P1, N P2, N P3
Start with: <1–2 sentence triage>
Full review: .council/review-output/$TS/FINAL-REVIEW.md
```

## Durable memory (Core phase 8)

After the summary, propose convention candidates for `conventions.md`:
- **Accepted Patterns (AP-*)** — intentional code the council should stop flagging ("that's by design").
- **Enforced Conventions (EC-*)** — adopted fixes that become "always/never" rules.
Present ≤8 candidates, numbered; on the user's selection append with provenance + timestamp
(continue AP-/EC- numbering; never duplicate). If the user says "none", skip silently.

## Notes

- Spawn every roster seat even if its slice is empty (proves coverage). No-surface seats return one line.
- Voice: direct, economic, teach-don't-just-flag. No code in the review. No opening flattery.
