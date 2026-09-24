"""Full-output parity instrument for the Purity Pass (PLAN-engine-purity-pass Task 1).

The shadow guard (``tools.shadow_diff``) deliberately compares only nine
canonical fields rounded to 6 dp - the right arbiter for measure-first
ADDITIONS, the wrong one for a pass whose contract is "byte-identical reading
behavior": a fold that perturbs a diagnostic sub-score or a 7th-decimal value
passes it clean. This tool captures the COMPLETE per-ticker result dicts off
the same frozen fixture, at full float precision, and compares them EXACTLY
(NaN == NaN; a reject-vs-fire flip is a diff like any other).

Fold commits:   capture before the fold, ``--compare`` after - zero diffs allowed.
Rename commits: ``--compare --mapping old_to_new.json`` - the mapping (a strict
                old-name -> new-name bijection) is applied to the CAPTURED
                dicts' keys first; a key present on only one side after mapping
                is a finding, not a footnote.

Captures are working state under the implement run dir (gitignored); the tool
itself is battery machinery and is committed. Hermetic: frozen fixture only.

    python -m tools.fold_parity --capture <run-dir>/captures/pre.json
    python -m tools.fold_parity --compare <run-dir>/captures/pre.json
    python -m tools.fold_parity --compare pre.json --mapping rename_map.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd

try:  # works under both `python -m tools.fold_parity` and `python tools/fold_parity.py`
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output  # type: ignore

configure_path()

from engine_alpha.evaluation import EVAL_ERROR
from core.pipeline.screening.screener import _evaluate_ticker
from tools.shadow_diff import _load_fixture

_REJECT = "__REJECT__"
_ERROR = "__EVAL_ERROR__"


# ------------------------------------------------------------------
# Pure logic (unit-tested; no IO)
# ------------------------------------------------------------------
def jsonable(obj):
    """Recursively convert a result value into a JSON-serializable twin
    without losing float precision (numpy scalars unwrap; NaN survives)."""
    if isinstance(obj, dict):
        return {str(k): jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [jsonable(v) for v in obj.tolist()]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return repr(obj)


def apply_mapping(node, mapping: dict):
    """Rename dict keys per ``mapping`` at every depth (rename-commit proof)."""
    if isinstance(node, dict):
        return {mapping.get(k, k): apply_mapping(v, mapping) for k, v in node.items()}
    if isinstance(node, list):
        return [apply_mapping(v, mapping) for v in node]
    return node


def exact_equal(a, b) -> bool:
    """Exact equality with NaN == NaN (the one place == is wrong for floats
    here is NaN; everything else must match bit-for-bit after JSON round-trip)."""
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(exact_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(exact_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def diff_paths(a, b, path: str = "", out: list | None = None, limit: int = 200) -> list[str]:
    """Human-readable list of paths where ``a`` and ``b`` differ."""
    if out is None:
        out = []
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                out.append(f"{p}: ONLY IN CURRENT = {b[k]!r}")
            elif k not in b:
                out.append(f"{p}: ONLY IN CAPTURE = {a[k]!r}")
            elif not exact_equal(a[k], b[k]):
                if isinstance(a[k], (dict, list)) and isinstance(b[k], (dict, list)):
                    diff_paths(a[k], b[k], p, out, limit)
                else:
                    out.append(f"{p}: {a[k]!r} -> {b[k]!r}")
            if len(out) >= limit:
                break
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: list length {len(a)} -> {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                if not exact_equal(x, y):
                    diff_paths(x, y, f"{path}[{i}]", out, limit)
                if len(out) >= limit:
                    break
    elif not exact_equal(a, b):
        out.append(f"{path}: {a!r} -> {b!r}")
    return out


# ------------------------------------------------------------------
# Fixture run (full dicts - the whole point)
# ------------------------------------------------------------------
def run_full() -> dict:
    frames, scalars = _load_fixture()
    spy_6m = float(scalars.get("spy_6m_return", 0.0))
    breadth = scalars.get("breadth_pct")
    breadth = float(breadth) if breadth is not None else None

    results: dict = {}
    for ticker in scalars["tickers"]:
        df = frames.get(ticker)
        if df is None:
            continue
        result = _evaluate_ticker(ticker, df, spy_6m, breadth)
        if result is EVAL_ERROR:
            results[ticker] = _ERROR
        elif result is None:
            results[ticker] = _REJECT
        else:
            results[ticker] = jsonable(result)
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Full-output byte parity over the frozen shadow fixture.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--capture", metavar="PATH", help="run the fixture and write complete result dicts here")
    g.add_argument("--compare", metavar="PATH", help="run the fixture and compare against this capture")
    ap.add_argument("--mapping", metavar="PATH", default=None,
                    help="old->new key bijection JSON applied to the CAPTURE before comparing (rename commits)")
    a = ap.parse_args()

    if a.capture:
        refuse_sealed_output(a.capture)
        results = run_full()
        with open(a.capture, "w", encoding="utf-8") as f:
            json.dump(results, f, sort_keys=True, indent=1)
        print(f"captured full output for {len(results)} tickers -> {a.capture}")
        return

    with open(a.compare, "r", encoding="utf-8") as f:
        captured = json.load(f)
    if a.mapping:
        with open(a.mapping, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        if len(set(mapping.values())) != len(mapping):
            print("FAIL - mapping is not a bijection (duplicate new names).")
            sys.exit(1)
        captured = apply_mapping(captured, mapping)

    current = run_full()
    lines: list[str] = []
    for ticker in sorted(set(captured) | set(current)):
        if ticker not in captured:
            lines.append(f"{ticker}: ONLY IN CURRENT ({'fires' if isinstance(current[ticker], dict) else current[ticker]})")
        elif ticker not in current:
            lines.append(f"{ticker}: ONLY IN CAPTURE")
        else:
            for d in diff_paths(captured[ticker], current[ticker]):
                lines.append(f"{ticker}.{d}")

    print("=" * 64)
    print("  FULL-OUTPUT PARITY - complete result dicts, exact equality")
    print("=" * 64)
    if lines:
        for ln in lines[:200]:
            print(f"  {ln}")
        print(f"\nFAIL - {len(lines)} difference(s). A fold commit must show ZERO; "
              "a rename commit must show zero AFTER its mapping.")
        sys.exit(1)
    print(f"PASS - {len(current)} tickers byte-identical to the capture.")


if __name__ == "__main__":
    main()
