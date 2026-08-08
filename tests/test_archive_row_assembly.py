"""
Archive row-assembly column-drift guard (hermetic — NO DB, NO scan).

The two real archive writers assemble a SetupArchive row two different ways now:

  * ``core/archive/writer.py`` -> ``archive_scan_results`` (live screener path)
    still hand-writes a ~130-key ``values = dict(...)`` then ``SetupArchive(**
    values)``.
  * ``core/archive/seed.py`` -> ``seed_archive`` (winners seed path) builds its
    row through the model-driven mapper — ``archive_row_from_result(best_result,
    overrides=dict(...))`` (the SAME single-source assembler the manual-add
    route uses). Its hand literal is now the ``overrides = dict(...)`` block,
    carrying only the special-cased seed keys; the mapper flat-maps the rest from
    ``SetupArchive.__table__``.

Every *other* test in the suite monkeypatches these writers away, so a stray or
renamed key (``foo=...`` where the model has no ``foo`` column) raises
``TypeError`` only during a real live scan/seed — i.e. in production, never in CI.

This test closes that gap statically. For the live writer it parses the ``values
= dict(...)`` source with ``ast`` and asserts its keys are a SUBSET of the ORM
columns. For the seed writer it pins the mapper's auto-mapped column set EXACTLY
(model columns minus ``id`` minus the frozen ``_MANUAL_UNMAPPED_COLUMNS``) so a
mapper that drops or over-skips a column is caught, and asserts the ``overrides =
dict(...)`` keys are all real columns. Nothing is executed against
a database and no scan runs; the literal ``dict(...)`` calls are read directly
from source, and the ``**splat`` helpers are driven hermetically (pure functions
given synthetic inputs) so the columns THEY contribute are covered as well.

APPROACH (reported to the orchestrator): asserted STATICALLY via AST key
enumeration + hermetic splat-helper resolution + the model-driven mapper. The
live writer's dict interleaves per-row ``**`` splats with closures over scan-wide
state (market_ctx, sector_ranking, engine_config_version, universe_type), so a
safe byte-identical extraction was not worth the risk to the flag-off path; the
seed writer was collapsed onto ``archive_row_from_result`` (proven byte-identical
at the persisted-row level). The AST approach tracks the real source, so it keeps
guarding after future edits without a hand-maintained key list.
"""
from __future__ import annotations

import ast
import inspect
import os
import sys

# ── project paths (mirror the writers' own bootstrap; backend dir holds the
# ORM model). Kept local to this test — no shared conftest fixture touched. ──
_PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import pytest  # noqa: E402

from core.archive import seed as seed_mod  # noqa: E402
from core.archive import writer as writer_mod  # noqa: E402
from core.regime.scan_context import sector_rank_fields  # noqa: E402
from engine_alpha.scoring.scoring import (  # noqa: E402
    sub_score_archive_values,
    ta_grade_archive_values,
)
from engine_alpha.structure.event_map import event_map_archive_values  # noqa: E402
from engine_alpha.structure.htf import htf_archive_values  # noqa: E402
from engine_alpha.structure.strategy_read import strategy_archive_values  # noqa: E402
from engine_alpha.structure.trace_export import election_trace_archive_values  # noqa: E402


def _model_columns() -> frozenset[str]:
    """Column names of the SetupArchive ORM table (the ``**values`` sink)."""
    from archive_models import SetupArchive  # backend model
    return frozenset(SetupArchive.__table__.columns.keys())


def _values_dict_keys(func, var: str = "values") -> tuple[frozenset[str], list[str]]:
    """Statically enumerate the keys the writer's ``<var> = dict(...)`` assigns.

    ``var`` is ``values`` for the live writer's hand literal and ``overrides`` for
    the seed writer, which now builds its row through the model-driven mapper
    (``archive_row_from_result(best_result, overrides=dict(...))``) instead of a
    full hand literal — the ``overrides = dict(...)`` block carries only the
    special-cased seed keys.

    Returns (literal_keys, splat_call_names) where:
      * literal_keys      = every ``name=...`` keyword the dict() call passes,
      * splat_call_names  = the callable names behind each ``**expr`` splat
                            (e.g. 'htf_archive_values', 'sector_rank_columns',
                            'fwd_returns' for a bare name).

    This reads the ACTUAL function source, so a renamed key surfaces here without
    a hand-kept list going stale.
    """
    src = inspect.getsource(func)
    tree = ast.parse(src)

    # Find the `<var> = dict(...)` assignment inside the function body.
    dict_call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t for t in node.targets if isinstance(t, ast.Name)]
            if any(t.id == var for t in targets):
                call = node.value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                        and call.func.id == "dict":
                    dict_call = call
                    break
    assert dict_call is not None, (
        f"could not locate `{var} = dict(...)` in {func.__qualname__}; the "
        f"archive row-assembly guard is stale — update the test to the new shape."
    )

    literal_keys: set[str] = set()
    splat_names: list[str] = []
    for kw in dict_call.keywords:
        if kw.arg is not None:
            literal_keys.add(kw.arg)
            continue
        # **splat — record the callable/name so we can resolve its columns.
        val = kw.value
        if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
            splat_names.append(val.func.id)
        elif isinstance(val, ast.Name):
            splat_names.append(val.id)
        else:  # pragma: no cover - defensive
            splat_names.append(ast.dump(val))
    return frozenset(literal_keys), splat_names


def _htf_splat_keys(*, prefixed: bool) -> frozenset[str]:
    """Columns the HTF ``**`` splat contributes (driven hermetically)."""
    return frozenset(htf_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _ta_grade_splat_keys(*, prefixed: bool) -> frozenset[str]:
    """Columns the TA-grade family ``**`` splat contributes (hermetic)."""
    return frozenset(
        ta_grade_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _sub_score_splat_keys() -> frozenset[str]:
    """Columns the per-term sub-score ``**`` splat contributes (hermetic)."""
    return frozenset(sub_score_archive_values({}).keys())


def _event_map_splat_keys(*, prefixed: bool) -> frozenset[str]:
    """Columns the Event Map ``**`` splat contributes (driven hermetically)."""
    return frozenset(
        event_map_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _election_trace_splat_keys(*, prefixed: bool) -> frozenset[str]:
    """Columns the election-trace ``**`` splat contributes (driven hermetically)."""
    return frozenset(
        election_trace_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _strategy_splat_keys(*, prefixed: bool) -> frozenset[str]:
    """Columns the strategy-read ``**`` splat contributes (driven hermetically)."""
    return frozenset(
        strategy_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _sector_rank_splat_keys() -> frozenset[str]:
    """Columns the sector-rank ``**`` splat contributes.

    ``sector_rank_columns`` in the writer is ``{k.lstrip('_'): v}`` over
    ``sector_rank_fields``; drive the pure field builder with a synthetic ranking
    so both ``sector_rank_pct`` / ``sector_rank_pos`` are produced, then strip the
    leading underscore exactly as the writer closure does.
    """
    ranking = {"composite": {"XLK": 92.0}, "ranked": ["XLK", "XLF"]}
    fields = sector_rank_fields("XLK", ranking)
    assert fields, "synthetic sector ranking must produce fields (guard fixture)"
    return frozenset(k.lstrip("_") for k in fields)


def _fwd_return_splat_keys() -> frozenset[str]:
    """Columns the seed ``**fwd_returns`` splat can contribute (hermetic).

    ``fwd_returns`` comes from ``forward_returns._compute_returns``; enumerate its
    full possible key set from the model's forward-return family so the guard
    covers seed's splat without running the returns computation.
    """
    model = _model_columns()
    fwd_prefixes = ("fwd_return_", "mfe", "mae", "r_multiple_", "days_to_",
                    "trigger", "win_barrier", "barrier_label")
    return frozenset(
        c for c in model
        if c.startswith(fwd_prefixes)
    )


# ── The two guards ──────────────────────────────────────────────────────────

def test_writer_values_dict_is_subset_of_model_columns():
    model = _model_columns()
    literal, splats = _values_dict_keys(writer_mod.archive_scan_results)

    # 1. Every literal key is a real column.
    stray = literal - model
    assert not stray, (
        f"archive_scan_results assigns non-column key(s) {sorted(stray)}; a live "
        f"scan would raise TypeError on SetupArchive(**values)."
    )

    # 2. The **splats are the ones we resolve hermetically below (fail loudly if
    #    a new/renamed splat appears so the guard is extended, not silently blind).
    assert set(splats) == {"htf_archive_values", "event_map_archive_values",
                           "ta_grade_archive_values", "sub_score_archive_values",
                           "election_trace_archive_values",
                           "strategy_archive_values",
                           "sector_rank_columns"}, (
        f"unexpected **splat(s) in archive_scan_results: {splats}; extend the "
        f"row-assembly guard to resolve their columns."
    )
    splat_cols = (_htf_splat_keys(prefixed=True)
                  | _event_map_splat_keys(prefixed=True)
                  | _ta_grade_splat_keys(prefixed=True)
                  | _sub_score_splat_keys()
                  | _election_trace_splat_keys(prefixed=True)
                  | _strategy_splat_keys(prefixed=True)
                  | _sector_rank_splat_keys())
    stray_splat = splat_cols - model
    assert not stray_splat, (
        f"writer **splat contributes non-column key(s) {sorted(stray_splat)}."
    )

    # Whole assembled key set is a subset of the model columns.
    assert (literal | splat_cols) <= model


def test_seed_values_dict_is_subset_of_model_columns():
    """Seed row-assembly column-drift guard, now on the model-driven mapper.

    ``seed_archive`` no longer hand-writes the full ~161-key ``values = dict(...)``;
    it builds the row through ``archive_row_from_result(best_result, overrides=dict(
    ...))`` (the same single-source mapper the manual-add route uses). The row's
    columns are therefore: the mapper's auto-mapped flat columns, PLUS the seed
    ``overrides`` (special-cased keys), PLUS the ``**`` splats inside ``overrides``.
    Every one of those must be a real SetupArchive column."""
    from services.archive_queries import (
        _MANUAL_UNMAPPED_COLUMNS,
        archive_row_from_result,
    )

    model = _model_columns()

    # 1. Pin the mapper's auto-mapped column set EXACTLY. With empty
    #    result/overrides the mapper flat-maps every model column except the
    #    auto-increment ``id`` and the frozen ``_MANUAL_UNMAPPED_COLUMNS`` (route
    #    splat / deliberately-NULL). Asserting equality (not just ⊆) makes this a
    #    real drift guard: a mapper that silently drops a column (under-maps) or
    #    stops skipping one it should (over-maps) breaks the equality here.
    auto_mapped = frozenset(archive_row_from_result({}, overrides={}))
    expected_auto_mapped = model - {"id"} - _MANUAL_UNMAPPED_COLUMNS
    assert auto_mapped == expected_auto_mapped, (
        "archive_row_from_result no longer auto-maps exactly "
        "(model columns) - {id} - _MANUAL_UNMAPPED_COLUMNS; the mapper drifted. "
        f"missing={sorted(expected_auto_mapped - auto_mapped)} "
        f"extra={sorted(auto_mapped - expected_auto_mapped)}"
    )

    # 2. The seed `overrides = dict(...)` literal keys are all real columns.
    literal, splats = _values_dict_keys(seed_mod.seed_archive, var="overrides")
    stray = literal - model
    assert not stray, (
        f"seed_archive overrides assign non-column key(s) {sorted(stray)}; a live "
        f"seed would raise TypeError on SetupArchive(**archive_row_from_result(...))."
    )

    # 3. The **splats inside overrides are the ones we resolve hermetically (fail
    #    loudly on a new/renamed splat so the guard is extended, not blind).
    assert set(splats) == {"htf_archive_values", "event_map_archive_values",
                           "ta_grade_archive_values", "sub_score_archive_values",
                           "election_trace_archive_values",
                           "strategy_archive_values", "fwd_returns"}, (
        f"unexpected **splat(s) in seed_archive overrides: {splats}; extend the "
        f"row-assembly guard to resolve their columns."
    )
    splat_cols = (_htf_splat_keys(prefixed=False)
                  | _event_map_splat_keys(prefixed=False)
                  | _ta_grade_splat_keys(prefixed=False)
                  | _sub_score_splat_keys()
                  | _election_trace_splat_keys(prefixed=False)
                  | _strategy_splat_keys(prefixed=False)
                  | _fwd_return_splat_keys())
    stray_splat = splat_cols - model
    assert not stray_splat, (
        f"seed **splat contributes non-column key(s) {sorted(stray_splat)}."
    )

    # 4. The whole assembled column set (auto-map ∪ overrides ∪ splats) ⊆ model.
    assert (auto_mapped | literal | splat_cols) <= model


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
