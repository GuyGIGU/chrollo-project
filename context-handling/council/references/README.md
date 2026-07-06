# references/

Single source of truth for reference docs. `build.sh` copies each skill's **declared** references
(from its `manifest.json`) into that skill's package.

## Ships in this repo (Council v2 — authored here)

- `context-engineering.md` — the Context Core doctrine (read by every mode).
- `roster/expert-catalog.md` — seats + "applies when" + recast rules (used by `council-init`).
- `quality-performance.md` — starter for the Performance seat (Vercel rules are external upstream).

## Domain expert docs (tracked in this repo)

The nine domain docs below are the **canonical Carmack Council references** (MIT). They are now
committed here so a fresh clone builds with no fetch step. If you'd rather run your own tuned copies
as the source of truth, edit them in place — e.g. the Chrollo council reuses `quality-llm.md` for the
numerical seat and `quality-postgres.md` for the data-integrity seat.

- `security.md` (Hunt) · `refactoring.md` (Fowler) · `quality-frontend.md` (Dodds)
- `quality-backend.md` (Collina) · `quality-postgres.md` (Leach) · `quality-testing.md` (Beck)
- `quality-llm.md` (Willison — also reused by a numerical seat) · `quality-ui.md` (Saarinen)
- `quality-ux.md` (Friedman)

To refresh them from upstream, re-run **`scripts/fetch-references.sh`** (pulls the canonical versions
from the Carmack repo).

A declared reference that is missing on disk is a **hard validation error** (`quick_validate.py` exits
1) — a packaged skill must never ship with a blind review lane. Per project, `council-init` decides
**which seat uses which of these docs**.
