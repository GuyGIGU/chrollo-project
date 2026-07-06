#!/usr/bin/env python3
"""Zip a skill (SKILL.md + manifest.json + declared references) into a .skill package.

Usage: package_skill.py <skill_dir> <references_dir> <out_path.skill>

Reference bundling lives here in pure Python — NOT in a shell copy loop — on purpose. A bash loop
that reads a `python -c` reference list loses every entry except the last to CRLF translation on
Windows (`references/<ref>\r` matches no file), which silently ships packages missing their refs.
Doing the manifest read + copy in one process avoids that round-trip entirely.
"""
import json
import os
import sys
import zipfile


def main():
    skill_dir, refs_dir, out = sys.argv[1], sys.argv[2], sys.argv[3]
    name = os.path.basename(os.path.normpath(skill_dir))
    manifest_path = os.path.join(skill_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    declared = [r.strip() for r in manifest.get("references", []) if r.strip()]
    missing = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(skill_dir, "SKILL.md"), "SKILL.md")
        z.write(manifest_path, "manifest.json")
        for ref in declared:
            parts = ref.split("/")
            if os.path.isabs(ref) or ".." in parts:
                missing.append(ref)  # refuse a path-escaping ref; never read or emit a traversal entry
                continue
            src = os.path.join(refs_dir, *parts)  # ref uses posix separators in the manifest
            if not os.path.isfile(src):
                missing.append(ref)
                continue
            z.write(src, "references/" + ref)

    for ref in missing:
        print(
            f"WARN: declared reference 'references/{ref}' not available for skill '{name}' — it must "
            "ship in references/ (fetch-references.sh only supplies the external upstream domain docs)",
            file=sys.stderr,
        )
    print(f"  packaged {out} ({len(declared) - len(missing)}/{len(declared)} refs)")


if __name__ == "__main__":
    main()
