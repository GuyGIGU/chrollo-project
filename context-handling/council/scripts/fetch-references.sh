#!/usr/bin/env bash
# Fetch the domain expert reference docs into references/.
# These are the canonical Carmack Council references (MIT-licensed). The two Council-v2 docs
# (context-engineering.md, roster/expert-catalog.md) and quality-performance.md ship in this repo.
#
# If you already run an adapted council, copy YOUR references/*.md over these instead —
# your versions may be tuned to your projects.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/references"
BASE="https://raw.githubusercontent.com/SamJHudson01/Carmack-Council/main/references"

mkdir -p "$DEST"

DOCS=(
  security.md
  refactoring.md
  quality-frontend.md
  quality-backend.md
  quality-postgres.md
  quality-testing.md
  quality-llm.md
  quality-ui.md
  quality-ux.md
)

for doc in "${DOCS[@]}"; do
  echo "fetching $doc"
  curl -fsSL "$BASE/$doc" -o "$DEST/$doc" || echo "WARN: could not fetch $doc" >&2
done

echo "Done. (quality-performance.md ships locally as a starter — Vercel perf rules are external upstream.)"
