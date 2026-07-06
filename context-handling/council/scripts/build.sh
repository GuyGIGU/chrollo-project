#!/usr/bin/env bash
# Build Council .skill packages from skills/*/ + the shared references/ directory.
# Each .skill is a zip of {SKILL.md, manifest.json, references/<declared refs>}.
# Reference bundling lives in package_skill.py (pure Python) so it is robust across filesystems and
# line endings — do NOT move it back into a shell copy loop (CRLF drops all but the last ref).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REF_DIR="references"
OUT="dist"
mkdir -p "$OUT"

# Validate first (hard errors abort the build; missing refs are soft warnings from the packager).
python3 scripts/quick_validate.py

for skill_dir in skills/*/; do
  name="$(basename "$skill_dir")"
  python3 scripts/package_skill.py "$skill_dir" "$REF_DIR" "$OUT/$name.skill"
done

echo "Done. Packages in $OUT/:"
ls -1 "$OUT"
