# Behavioral drills (run in Claude Code)

Run each once by hand before shipping a change to the skills. Record pass/fail + a note.

## D1 — Roster fit (`council-init`)
**Setup:** in the Chrollo repo with no `.council/council.config.md` (or a scratch copy).
**Run:** `council-init`.
**Pass if:** it detects Python engine + FastAPI + SQLite/parquet + React and proposes a roster that
recasts backend→Ramírez, LLM→McKinney (numerical, reusing `quality-llm.md`), Postgres→data-integrity
Leach, and keeps Hunt/Fowler/Beck/Dodds/Saarinen/Friedman + a pipeline Performance seat; and detects
gates `pytest` + `npm --prefix webapp/frontend run lint`/`build` (NOT tsc/vitest/cypress).
**Fail if:** it hard-codes the Next.js roster or the tsc/vitest/cypress gates.

## D2 — Triggering (`council-review` / `using-council`)
**Pass if:** the review mode engages when the user says "review this" / finishes a change / opens a
PR, WITHOUT an explicit slash command; and does NOT fire during unrelated conversation.
**Fail if:** it never auto-fires, or it fires on idle chatter.

## D3 — Bug caught (fixture)
**Setup:** point a review at `fixtures/` (see `fixtures/README.md`), which contains a seeded
off-by-one / null-deref style bug.
**Pass if:** the bug appears as a P1 (or P2) finding, attributed to the correct expert, with a
concrete fix and NO code snippet.
**Fail if:** the bug is missed, or the run emits code in the review.

## D4 — Memory respected (fixture)
**Setup:** `fixtures/conventions.md` contains an accepted pattern (AP-1) covering an intentional
choice in the fixture.
**Pass if:** the review does NOT re-flag AP-1 (proves read-before + the compound effect).
**Fail if:** it flags the accepted pattern as a finding.

## Context-hygiene spot checks (any real run)
- The Chair never deep-read every file (check it used Glob/Grep + a bounded set).
- Each worker returned ~one line to the parent; full findings live in `.council/review-output/$TS/*.md`.
- A `context-brief.md` exists and is edge-ordered (decision at top, constraints at bottom).
- After any compaction, the run resumed from `session-state.md` rather than restarting.
