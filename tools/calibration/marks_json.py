"""The ONE validated loader for the docs/ JSON marks corpora (EC-13).

The file-based operator-marks artifacts (docs/trend_end_marks_2026-08.json,
docs/power_play_marks_2026-08.json, ...) are append-only operator ground
truth, hand-curated during ruling sessions — no tool writes them. Every
instrument that consumes one loads it HERE: a malformed row aborts the batch
naming the offender (a silently skipped mark shrinks every denominator), and
every report stamps the fingerprint of EXACTLY the marks it scored — the
file-family analog of ``tools.calibration.calibration_harness.load_marks`` /
``marks_fingerprint`` for the DB population.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date

# Top-level mark fields validated as ISO dates when present and non-null.
_DATE_FIELDS = ("trend_end", "ar", "climax", "breakout")
# Top-level mark fields validated as [start, end] ISO pairs when present.
_SPAN_FIELDS = ("root_swing_span", "lps_span")
# The species boundary call is a closed set; a mark may also carry no verdict.
VERDICTS = ("keep", "junk")


def _refuse(path: str, i: int, mark, why: str):
    ident = mark.get("ticker") if isinstance(mark, dict) else None
    raise ValueError(
        f"{os.path.basename(path)} mark[{i}] ({ident or '<no ticker>'}): {why}")


def _iso(value) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def load_marks_json(path: str) -> list[dict]:
    """Load + validate one marks corpus; return its marks list verbatim."""
    with open(path, encoding="utf-8") as fh:
        corpus = json.load(fh)
    if not isinstance(corpus, dict) or not isinstance(corpus.get("marks"), list):
        raise ValueError(
            f"{os.path.basename(path)}: a marks corpus is a dict with a 'marks' list")
    for i, mark in enumerate(corpus["marks"]):
        if not isinstance(mark, dict):
            _refuse(path, i, mark, "not a dict")
        for field in ("ticker", "source"):
            if not isinstance(mark.get(field), str) or not mark[field].strip():
                _refuse(path, i, mark, f"missing/empty {field!r}")
        if not _iso(mark.get("as_of")):
            _refuse(path, i, mark, f"as_of {mark.get('as_of')!r} is not an ISO date")
        for field in _DATE_FIELDS:
            value = mark.get(field)
            if value is not None and not _iso(value):
                _refuse(path, i, mark, f"{field} {value!r} is not an ISO date")
        for field in _SPAN_FIELDS:
            span = mark.get(field)
            if span is not None:
                if (not isinstance(span, list) or len(span) != 2
                        or not all(_iso(v) for v in span)):
                    _refuse(path, i, mark,
                            f"{field} {span!r} is not a [start, end] ISO pair")
                # Operator dates arrive in European day-month form and are
                # resolved at transcription — a transposed pair would slice
                # to an EMPTY window downstream, the silently-shrunk
                # denominator this loader exists to abort on (2026-08-17
                # review, Leach).
                if span[0] > span[1]:
                    _refuse(path, i, mark,
                            f"{field} {span!r} starts after it ends")
        verdict = mark.get("verdict")
        if verdict is not None and verdict not in VERDICTS:
            _refuse(path, i, mark, f"verdict {verdict!r} not in {'/'.join(VERDICTS)}")
        if "certified" in mark and not isinstance(mark["certified"], bool):
            _refuse(path, i, mark, "certified must be a bool")
    return corpus["marks"]


def marks_json_fingerprint(marks: list[dict]) -> str:
    """sha256 over EXACTLY the marks scored (order-insensitive) — a changed
    fingerprint says "the ground truth moved, not the engine"."""
    canon = json.dumps(
        sorted(json.dumps(m, sort_keys=True, default=str) for m in marks))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()
