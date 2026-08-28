"""Guided List graduation — calibration-marks DB -> sealed docs/marks corpus (EC-9).

The ONE legal crossing between the two mark populations (EC-9): the operator's
EDITABLE calibration marks graduate into the SEALED EC-7 corpus that
``tools.marks_corpus`` gates on. One-way, operator-gated, and fingerprint-pinned:
the export REFUSES unless the live marks-DB fingerprint equals the
operator-approved pin below — an edit made after sign-off would silently seal a
corpus nobody approved (the trust boundary the re-freeze crosses exactly once).

Provenance rides the artifact: the corpus file records the pinned fingerprint,
the engine manifest hash at export, and the authorization, so any future auditor
can answer "which marks, approved when" from the file alone.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.guided_list_export
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

try:
    from tools._bootstrap import configure_path
except ModuleNotFoundError:
    from _bootstrap import configure_path

_PROJECT_ROOT = configure_path(backend=True)

import database  # noqa: E402  binds the live SQLite engine + SessionLocal

from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402

# The shared judgments (EC-3): the harness's validated ORM loader + the SAME
# canonicalization/fingerprint recipe it stamps on every report — never a
# second loader, never a second fingerprint recipe.
from tools.calibration_harness import load_box_marks  # noqa: E402

# Operator-approved seal for THIS graduation event (sign-off: "GO" 2026-07-24,
# PLAN-guided-list-gap-breach Task 1). Any post-sign-off edit to a covered
# field changes the fingerprint and the export refuses. KNOWN COVERAGE GAPS
# (council review 2026-07-24; harness review 2026-08-28): the frozen seal
# recipe (calibration_harness._SEAL_MARK_KEYS/_SEAL_EVENT_KEYS) does NOT
# include trigger_date/trigger_price or the mini-consolidation band columns
# (band_high/band_low), so those fields edited after sign-off pass the pin
# unchanged — widening the recipe rotates EVERY fingerprint, so it is an
# operator re-pin decision, recorded here until made. A future graduation
# re-pins deliberately, never silently. (Validation is NOT gapped: since
# 2026-08-28 the shared judgment sees the complete dict, bands and trigger
# included — only the seal's hash input is frozen.)
OPERATOR_APPROVED_FINGERPRINT = (
    "b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523"
)
AUTHORIZATION = "operator GO 2026-07-24 — Guided List = THE engine-test standard"

OUT_PATH = os.path.join(_PROJECT_ROOT, "docs", "marks", "guided_list_2026-07.json")

_ABOUT = (
    "The Guided List — the operator's curated engine-test standard (33 setups / 31 tickers), "
    "graduated one-way from the editable calibration-marks DB (EC-9) on the pinned fingerprint "
    "below. Dates ISO. Each setup carries the frozen-frame digest it was drawn on; the ratchet "
    "fixture freezes THOSE bars (as-drawn basis), never a live re-fetch. Supersedes the seed "
    "corpus dates and docs/marks/part2_2026-07.json as the gate population (operator ruling "
    "2026-07-24: names kept, old dates retired; part2 stays on disk as EC-7 history)."
)


def export() -> str:
    session = database.SessionLocal()
    try:
        # The shared validated loader: every mark passes the ONE validity
        # judgment (EC-11 etc.) before anything is sealed, and the
        # fingerprint recipe is the harness's own.
        marks, fingerprint = load_box_marks(session)
        if fingerprint != OPERATOR_APPROVED_FINGERPRINT:
            raise RuntimeError(
                "REFUSING to export: the calibration-marks DB fingerprint\n"
                f"  {fingerprint}\n"
                "does not match the operator-approved pin\n"
                f"  {OPERATOR_APPROVED_FINGERPRINT}\n"
                "The ground truth moved since sign-off (EC-9 marks are editable). "
                "Re-approve the current set with the operator and re-pin deliberately."
            )
        if os.path.exists(OUT_PATH):
            raise RuntimeError(
                f"REFUSING to export: {OUT_PATH} already exists. The corpus is EC-7 "
                "append-only ground truth — a re-graduation is a new deliberate event, "
                "never an overwrite."
            )

        setups: list[dict] = []
        for m in marks:
            lps_events = sorted(
                (e for e in m.events if e.event_type == "lps"),
                key=lambda e: str(e.start_date),
            )
            if not lps_events:
                raise RuntimeError(
                    f"REFUSING to export: {m.ticker}@{m.as_of_date} has no LPS event "
                    "(EC-11: a gate setup needs its marked entry window)."
                )
            if len(lps_events) > 2:
                raise RuntimeError(
                    f"REFUSING to export: {m.ticker}@{m.as_of_date} carries "
                    f"{len(lps_events)} LPS events but the corpus schema seals at "
                    "most two (lps + lps2) — silently dropping a marked shelf "
                    "would misrepresent the ground truth and narrow the fired "
                    "window. Extending the schema is a deliberate EC-7 event."
                )
            if not m.trigger_date:
                raise RuntimeError(
                    f"REFUSING to export: {m.ticker}@{m.as_of_date} has no trigger "
                    "(all Guided List setups carry the operator's buy; a silent "
                    "grace-window fallback would widen the acceptance semantics)."
                )
            setup = {
                "ticker": m.ticker,
                # Unique, stable identity label (NGL and ORMP appear twice).
                "setup": str(m.as_of_date),
                "source": "operator",
                "as_of": str(m.as_of_date),
                "frame_digest": m.frame_digest,
                "lps": [str(lps_events[0].start_date), str(lps_events[0].end_date)],
                "trigger": str(m.trigger_date),
                "rails_drawn": {"R": float(m.resistance), "S": float(m.support)},
            }
            if len(lps_events) > 1:
                setup["lps2"] = [str(lps_events[1].start_date), str(lps_events[1].end_date)]
            if m.knowable_from_date:
                # Carried so the ratchet's fired-policy window honors the same
                # override the agreement harness does.
                setup["knowable_from"] = str(m.knowable_from_date)
            if m.note:
                setup["notes"] = m.note
            setups.append(setup)
    finally:
        session.close()

    labels = [f"{s['ticker']}:{s['setup']}" for s in setups]
    dupes = sorted({k for k in labels if labels.count(k) > 1})
    if dupes:
        raise RuntimeError(
            "REFUSING to export: two box marks share a (ticker, as_of) identity "
            f"({dupes}) — the sealed setup label is the as_of date, so they "
            "would collide. Deriving a richer label is a deliberate corpus-"
            "schema decision, not a silent fallback."
        )

    doc = {
        "_about": _ABOUT,
        "_provenance": {
            "population": "guided-list",
            "marks_fingerprint": fingerprint,
            "engine_config_version": manifest_hash(),
            "authorization": AUTHORIZATION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_setups": len(setups),
        },
        "setups": setups,
    }
    # Atomic + self-checking seal: write to a temp sibling, load THAT file
    # through the gate's own corpus loader (the artifact must satisfy the
    # rules its consumers enforce BEFORE it becomes immutable), then rename
    # into place — a crash mid-write can never leave a torn file posing as
    # ground truth that the refuse-if-exists check would then protect.
    # newline="\n": the EC-7 seal hashes RAW BYTES and .gitattributes pins
    # docs/marks/*.json to eol=lf — LF on disk keeps the digest identical
    # across every checkout.
    tmp_path = OUT_PATH + ".exporting"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    try:
        from tools.marks_corpus import load_corpus
        load_corpus((tmp_path,))
    except Exception:
        os.remove(tmp_path)
        raise
    os.replace(tmp_path, OUT_PATH)
    print(f"Graduated {len(setups)} Guided List setups -> {OUT_PATH}")
    print(f"  marks_fingerprint: {fingerprint}")
    return OUT_PATH


if __name__ == "__main__":
    try:
        export()
    except RuntimeError as e:
        print(str(e))
        sys.exit(2)
