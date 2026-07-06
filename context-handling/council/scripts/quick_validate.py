#!/usr/bin/env python3
"""Validate the Council repo before packaging.

Hard errors (exit 1): a skill missing SKILL.md/manifest.json, malformed manifest JSON,
SKILL.md without a name+description frontmatter, a manifest name mismatch, or a declared
reference file that does not exist on disk (a packaged skill must never ship a blind lane).
Reference paths are resolved the same way package_skill.py resolves them (posix-split), so the
validator and the packager agree by construction.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
REFS = os.path.join(ROOT, "references")

errors, warnings = [], []


def frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    return m.group(1) if m else None


for name in sorted(os.listdir(SKILLS)):
    sdir = os.path.join(SKILLS, name)
    if not os.path.isdir(sdir):
        continue
    skill_md = os.path.join(sdir, "SKILL.md")
    manifest = os.path.join(sdir, "manifest.json")

    if not os.path.isfile(skill_md):
        errors.append(f"{name}: missing SKILL.md")
        continue
    if not os.path.isfile(manifest):
        errors.append(f"{name}: missing manifest.json")
        continue

    fm = frontmatter(skill_md)
    if not fm or "name:" not in fm or "description:" not in fm:
        errors.append(f"{name}: SKILL.md frontmatter needs name + description")

    try:
        data = json.load(open(manifest, encoding="utf-8"))
    except json.JSONDecodeError as e:
        errors.append(f"{name}: manifest.json invalid JSON ({e})")
        continue

    if data.get("name") != name:
        errors.append(f"{name}: manifest name '{data.get('name')}' != folder '{name}'")

    for ref in data.get("references", []):
        if not os.path.isfile(os.path.join(REFS, *ref.split("/"))):
            errors.append(f"{name}: declared reference missing on disk -> references/{ref}")

for w in warnings:
    print(f"WARN  {w}")
for e in errors:
    print(f"ERROR {e}")

if errors:
    print(f"\nvalidation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1)
print(f"\nvalidation OK: {len(warnings)} warning(s)")
