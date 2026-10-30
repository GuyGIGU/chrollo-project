"""The scan's return sentinels: the failed-read marker and the closed table of chart state words.

``EVAL_ERROR`` is returned when a read THREW and was swallowed; a plain ``None`` is a chart with no setup.
The screener counts the two apart and appends neither. It MUST be an Enum member, not a bare ``object()``:
the per-ticker read runs in a ProcessPoolExecutor worker and its return value crosses the process boundary
via pickle. A bare ``object()`` unpickles to a NEW instance, so ``is`` identity would fail in the parent and
the count would silently stay 0. Enum members pickle by qualified name and round-trip to the SAME singleton,
so ``result is EVAL_ERROR`` holds across processes.

``WATCH_WIRE_STATES`` is the one table of state words a chart the door admits may carry (his words, the state
table of docs/final_method_2026-09.md point 22, and precedence row 5 of point 6 for the open right edge); the
wire carries them verbatim, never a slug the frontend must translate.
"""
from __future__ import annotations

from enum import Enum


class _EvalSkip(Enum):
    ERROR = "error"


EVAL_ERROR = _EvalSkip.ERROR

WATCH_WIRE_STATES = ("fired", "crossed", "lines, no LPS yet", "forming N of 15",
                     "root candidate, unconfirmed", "beyond R, undetermined",
                     "under S, undetermined", "broke down", "not scanned", "no lines")
