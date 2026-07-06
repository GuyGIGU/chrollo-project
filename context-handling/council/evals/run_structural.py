#!/usr/bin/env python3
"""Structural evals for Council v2 — runnable without an LLM.

Verifies the framework is wired correctly: skills present, the Core contract intact, council-review
is a mode that rides the Core and proposes-then-confirms, council-init has the tailoring phases, and the
bootstrap re-injects after compaction. These are the invariants a build must never break.

Behavioral drills (does it actually catch a bug, tailor the roster, keep quiet when idle) require a
live Claude Code run — see behavioral-drills.md.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")

results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))


def read(path):
    return open(path, encoding="utf-8").read() if os.path.isfile(path) else ""


# 1. All skills present with SKILL.md + manifest.json
for skill in ["context-core", "council-review", "council-init", "using-council",
              "council-plan", "council-implement", "test-architect", "spec-writer"]:
    sd = os.path.join(SKILLS, skill)
    check(f"{skill}: SKILL.md exists", os.path.isfile(os.path.join(sd, "SKILL.md")))
    check(f"{skill}: manifest.json exists", os.path.isfile(os.path.join(sd, "manifest.json")))

# 2. Manifests valid + names match folders
for skill in os.listdir(SKILLS):
    mf = os.path.join(SKILLS, skill, "manifest.json")
    if os.path.isfile(mf):
        try:
            data = json.load(open(mf, encoding="utf-8"))
            check(f"{skill}: manifest name matches", data.get("name") == skill, data.get("name", ""))
        except json.JSONDecodeError as e:
            check(f"{skill}: manifest valid JSON", False, str(e))

core = read(os.path.join(SKILLS, "context-core", "SKILL.md"))
review = read(os.path.join(SKILLS, "council-review", "SKILL.md"))
init = read(os.path.join(SKILLS, "council-init", "SKILL.md"))
boot = read(os.path.join(SKILLS, "using-council", "SKILL.md"))
catalog = read(os.path.join(ROOT, "references", "roster", "expert-catalog.md"))
doctrine = read(os.path.join(ROOT, "references", "context-engineering.md"))

# 3. Core contract: doctrine + all ten phases present
check("core: reads the doctrine", "context-engineering.md" in core)
check("core: mode contract present", all(k in core for k in
      ["personas", "reference_docs", "output_schema", "gates", "memory_namespace"]))
for n in range(1, 11):
    check(f"core: phase {n} present", f"Phase {n}" in core)
check("core: aggregate-before-judging rule", "Aggregate before judging" in core)
check("core: per-finding validation rule", "Validate each shipped" in core or "validate each shipped" in core.lower())
check("core: re-bootstrap after compaction", "Re-bootstrap after" in core or "re-bootstrap" in core.lower())
check("core: zero-context worker rule", "zero-context worker" in core.lower())
check("core: map-don't-ingest rule", "map" in core.lower() and "ingest" in core.lower())

# 4. council-review is a Core-riding, auto-triggering mode
check("review: rides context-core", "context-core" in review)
check("review: suggest-then-confirm invocation",
      "confirm" in review.lower() and ("propose" in review.lower() or "suggest" in review.lower()))
check("review: P1/P2/P3 schema", all(p in review for p in ["P1", "P2", "P3"]))
check("review: conventions.md memory", "conventions.md" in review)
_review_manifest = json.load(open(os.path.join(SKILLS, "council-review", "manifest.json"), encoding="utf-8"))
check("review: manifest requires context-core", "context-core" in _review_manifest.get("requires", []))

# 5. council-init has the tailoring phases and uses the catalog
check("init: reads the expert catalog", "expert-catalog.md" in init)
check("init: detects gates (not hard-coded tsc/vitest)", "council.config.md" in init and "gates" in init.lower())
check("init: recast rules for domain fit", "recast" in init.lower())
check("catalog: has Chrollo worked example", "Chrollo" in catalog and "McKinney" in catalog)

# 5b. Carried suite skills have real instruction bodies (not frontmatter-only stubs)
plan = read(os.path.join(SKILLS, "council-plan", "SKILL.md"))
impl = read(os.path.join(SKILLS, "council-implement", "SKILL.md"))
ta = read(os.path.join(SKILLS, "test-architect", "SKILL.md"))
sw = read(os.path.join(SKILLS, "spec-writer", "SKILL.md"))
check("plan: has dispatch-council phase", "Dispatch Council Members" in plan)
check("implement: has implementation log", "Implementation Log" in impl)
check("test-architect: has specify mode", "Mode 2: Specify" in ta)
check("spec-writer: mandates gherkin ACs", "Gherkin" in sw)

# 6. Bootstrap re-injects after compaction
check("bootstrap: re-bootstrap after reset", "compaction" in boot.lower() and "session-state" in boot.lower())

# 7. Doctrine states the four levers
check("doctrine: four levers", all(l in doctrine for l in ["Write", "Select", "Compress", "Isolate"]))

# Report
passed = sum(1 for ok, *_ in results if ok)
for ok, name, detail in results:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f"  ({detail})" if detail and not ok else ""))
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
