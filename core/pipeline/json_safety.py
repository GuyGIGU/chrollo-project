"""Helpers for making scan-derived payloads safe for stdlib JSON."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import math
import numbers

import pandas as pd


def _is_missing_scalar(obj) -> bool:
    try:
        missing = pd.isna(obj)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    if hasattr(missing, "item"):
        try:
            return bool(missing.item())
        except (TypeError, ValueError):
            return False
    return False


def _json_key_safe(key):
    value = to_json_safe(key)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def to_json_safe(obj):
    """Return a recursively JSON-safe version of common scan payload values."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, Mapping):
        return {_json_key_safe(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_json_safe(v) for v in obj]
    if _is_missing_scalar(obj):
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, numbers.Integral):
        return int(obj)
    if isinstance(obj, numbers.Real):
        value = float(obj)
        return value if math.isfinite(value) else None
    if hasattr(obj, "item"):
        try:
            return to_json_safe(obj.item())
        except (TypeError, ValueError):
            pass
    if hasattr(obj, "tolist"):
        try:
            return to_json_safe(obj.tolist())
        except (TypeError, ValueError):
            pass
    return str(obj)
