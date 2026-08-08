"""
Archive scan-vs-seed column-PARITY guard (hermetic — NO DB, NO scan).

Sibling of ``test_archive_row_assembly.py`` (which checks each writer's assembled
columns are a SUBSET of the ORM columns). This one checks the two writers against
*each other*: an engine sub-score populated by one write path and forgotten in
the other silently NULLs that column for a whole population.

That already happened: ``score_traversal_quality`` was archived by scan rows
(``core/archive/writer.py``) but NULL in every seeded row until it was added to
``core/archive/seed.py`` — the seed eval genuinely produces
``sub_scores['traversal_quality']`` (scoring.py -> ``_sub_scores`` ->
``seed_row_from_result`` strips to ``sub_scores``), it was just never mapped.

The two writers assemble their rows differently now:

  * the live scan writer is still one hand-written ``values = dict(...)`` (plus
    its ``htf_archive_values`` / ``sector_rank_columns`` ``**`` splats);
  * the seed writer builds its row through the model-driven mapper —
    ``archive_row_from_result(best_result, overrides=dict(...))`` — so its
    populated columns are the mapper's auto-mapped flat columns PLUS the
    ``overrides`` special-cases PLUS its ``htf_archive_values`` / ``fwd_returns``
    ``**`` splats.

GUARD: compute each writer's FULL effective populated-column set (literal keys +
resolved ``**`` splats, and for seed the mapper's auto-mapped columns too), then
require their symmetric difference to be a SUBSET of an explicit intentional-
divergence ALLOWLIST. Anything else — e.g. a new ``score_*`` sub-score wired into
one path only — fails CI. The allowlist enumerates exactly the run-level context
the scan computes but a historical replay cannot (``regime_*`` / ``scope_*`` /
breadth) and the seed-only fields (forward-return outcomes computed immediately
for a historical date, plus ``quality_label`` / ``notes`` / scan-row-absent
anchors). Modelled on the manual path's ``_MANUAL_UNMAPPED_COLUMNS`` frozenset.

Fully self-contained: parses the two writer source files with ``ast`` and drives
the pure splat/mapper helpers hermetically (no import-time execution of the
writers, no shared conftest fixture, no DB).
"""
from __future__ import annotations

import ast
import inspect
import os
import sys

# ── project paths (mirror the writers' own bootstrap; kept local to this
# test — no shared conftest fixture touched). ──
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


# ── Intentional divergence allowlist ─────────────────────────────────────────
# Columns that legitimately appear in ONLY ONE of the two writers' effective
# populated-column sets. Everything else in the symmetric difference is drift.
#
# WRITER-only: run-level / advisory context computed during a live scan that a
#   historical single-date replay (seed) has no source for.
_WRITER_ONLY_ALLOW = frozenset({
    # live universe breadth — None at a replay date (seed passes breadth_pct=None)
    "breadth_pct",
    # market-regime snapshot (scan-run level, resolved live)
    "regime_state",
    "regime_breadth_50_pct", "regime_breadth_200_pct",
    "regime_distribution_days",
    "regime_spy_above_50", "regime_spy_above_200", "regime_spy_50d_slope_pct",
    "regime_qqq_above_50", "regime_qqq_above_200", "regime_qqq_50d_slope_pct",
    # phase-scoping descriptive bands (writer maps from _phase_*_date; seed omits)
    "scope_phase_a_date", "scope_phase_b_date", "scope_phase_c_date",
    "scope_phase_d_date", "scope_has_mini", "scope_confidence",
})
# SEED-only: fields the seed path fills that the scan-row literal does not.
_SEED_ONLY_ALLOW = frozenset({
    # winners-gallery outcome label (seed only; scan rows mature into it later)
    "quality_label",
    # curator note column — auto-mapped to None on the seed path, never set by
    # the scan literal (the manual route sets it; scan/seed leave it NULL).
    "notes",
    # R/S anchor bars — seed reads best_result anchors; scan row literal has none
    "r_anchor", "s_anchor",
    # Forward-return / triple-barrier outcomes: the seed path computes them
    # immediately (historical bars after the signal already exist) and splats
    # **fwd_returns; the live scan writes the row BEFORE any forward bars exist,
    # so these mature in later (they are absent from the scan literal).
    "triggered", "trigger_date", "trigger_volume_ratio",
    "fwd_return_1d", "fwd_return_5d", "fwd_return_10d", "fwd_return_20d",
    "fwd_return_60d",
    "mfe_20d", "mae_20d", "mfe_60d", "mae_60d", "mfe_20d_date", "mae_20d_date",
    "mfe_to_date", "mae_to_date", "ret_to_date", "bars_to_date",
    "abnormal_ret_to_date",
    "r_multiple_20d", "r_multiple_60d",
    "days_to_trigger", "days_to_2_5r", "days_to_15pct", "days_to_stop",
    "barrier_label", "win_barrier",
})
_INTENTIONAL_DIVERGENCE = _WRITER_ONLY_ALLOW | _SEED_ONLY_ALLOW


def _model_columns() -> frozenset[str]:
    from archive_models import SetupArchive  # backend model
    return frozenset(SetupArchive.__table__.columns.keys())


def _dict_literal(func, var: str):
    """Return the ``ast.Call`` node for the ``<var> = dict(...)`` assignment
    inside ``func`` (the live writer's ``values`` or the seed writer's
    ``overrides``). Reads the ACTUAL function source via ``ast`` so a renamed key
    surfaces here without a hand-kept list going stale."""
    src = inspect.getsource(func)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == var for t in node.targets):
                call = node.value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                        and call.func.id == "dict":
                    return call
    raise AssertionError(
        f"could not locate `{var} = dict(...)` in {func.__qualname__}; the "
        "archive column-parity guard is stale — update it to the new shape."
    )


def _literal_kwargs(func, var: str = "values") -> frozenset[str]:
    """Explicit ``name=...`` keys of the writer's ``<var> = dict(...)`` block,
    ignoring ``**splat`` entries."""
    call = _dict_literal(func, var)
    return frozenset(kw.arg for kw in call.keywords if kw.arg is not None)


def _splat_names(func, var: str) -> list[str]:
    """The callable/name behind each ``**expr`` splat in the ``<var> = dict(...)``
    block (e.g. 'htf_archive_values', 'sector_rank_columns', 'fwd_returns')."""
    call = _dict_literal(func, var)
    names: list[str] = []
    for kw in call.keywords:
        if kw.arg is not None:
            continue
        v = kw.value
        if isinstance(v, ast.Call) and isinstance(v.func, ast.Name):
            names.append(v.func.id)
        elif isinstance(v, ast.Name):
            names.append(v.id)
        else:  # pragma: no cover - defensive
            names.append(ast.dump(v))
    return names


# ── Hermetic splat/mapper column resolvers ───────────────────────────────────

def _htf_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(htf_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _event_map_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(
        event_map_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _ta_grade_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(
        ta_grade_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _sub_score_cols() -> frozenset[str]:
    return frozenset(sub_score_archive_values({}).keys())


def _election_trace_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(
        election_trace_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _strategy_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(
        strategy_archive_values((lambda _k: None), prefixed=prefixed).keys())


def _sector_rank_cols() -> frozenset[str]:
    ranking = {"composite": {"XLK": 92.0}, "ranked": ["XLK", "XLF"]}
    fields = sector_rank_fields("XLK", ranking)
    assert fields, "synthetic sector ranking must produce fields (guard fixture)"
    return frozenset(k.lstrip("_") for k in fields)


def _fwd_return_cols() -> frozenset[str]:
    """The forward-return family columns the seed ``**fwd_returns`` splat can
    contribute — enumerated from the model's forward-return column families so
    the guard covers the splat without running the returns computation."""
    model = _model_columns()
    fwd_prefixes = ("fwd_return_", "mfe", "mae", "r_multiple_", "days_to_",
                    "trigger", "win_barrier", "barrier_label", "ret_to_date",
                    "bars_to_date", "abnormal_ret_to_date")
    return frozenset(c for c in model if c.startswith(fwd_prefixes))


def _mapper_auto_cols() -> frozenset[str]:
    """The flat columns ``archive_row_from_result`` auto-maps from the eval
    result (everything on the model except ``id`` / ``_MANUAL_UNMAPPED_COLUMNS``).
    These are populated on the seed row whether or not they carry a real value —
    part of the seed path's effective column set."""
    from services.archive_queries import archive_row_from_result
    return frozenset(archive_row_from_result({}, overrides={}))


def _scan_effective_cols() -> frozenset[str]:
    """Every column the live scan writer populates: its ``values`` literal keys +
    its ``htf_archive_values`` (prefixed) + ``sector_rank_columns`` splats."""
    literal = _literal_kwargs(writer_mod.archive_scan_results, "values")
    splats = set(_splat_names(writer_mod.archive_scan_results, "values"))
    assert splats == {"htf_archive_values", "event_map_archive_values",
                      "ta_grade_archive_values", "sub_score_archive_values",
                      "election_trace_archive_values",
                      "strategy_archive_values", "sector_rank_columns"}, (
        f"unexpected scan **splat(s): {sorted(splats)}; extend the parity guard."
    )
    return (literal | _htf_cols(prefixed=True)
            | _event_map_cols(prefixed=True)
            | _ta_grade_cols(prefixed=True)
            | _sub_score_cols()
            | _election_trace_cols(prefixed=True)
            | _strategy_cols(prefixed=True) | _sector_rank_cols())


def _seed_effective_cols() -> frozenset[str]:
    """Every column the seed writer populates through the mapper: the mapper's
    auto-mapped flat columns + the ``overrides`` literal keys + its
    ``htf_archive_values`` (unprefixed) + ``fwd_returns`` splats."""
    literal = _literal_kwargs(seed_mod.seed_archive, "overrides")
    splats = set(_splat_names(seed_mod.seed_archive, "overrides"))
    assert splats == {"htf_archive_values", "event_map_archive_values",
                      "ta_grade_archive_values", "sub_score_archive_values",
                      "election_trace_archive_values",
                      "strategy_archive_values", "fwd_returns"}, (
        f"unexpected seed **splat(s): {sorted(splats)}; extend the parity guard."
    )
    return (_mapper_auto_cols() | literal | _htf_cols(prefixed=False)
            | _event_map_cols(prefixed=False)
            | _ta_grade_cols(prefixed=False)
            | _sub_score_cols()
            | _election_trace_cols(prefixed=False)
            | _strategy_cols(prefixed=False) | _fwd_return_cols())


def test_scan_and_seed_only_diverge_on_allowlist():
    scan_cols = _scan_effective_cols()
    seed_cols = _seed_effective_cols()

    # Sanity: the shared core must be substantial; if this collapses, an AST
    # parse or a splat resolver latched onto the wrong thing.
    assert len(scan_cols & seed_cols) > 100, (
        "scan/seed effective column sets share <100 columns — the parity guard "
        f"is misreading the writers (scan={len(scan_cols)}, seed={len(seed_cols)})."
    )

    divergence = scan_cols ^ seed_cols  # symmetric difference
    unexpected = divergence - _INTENTIONAL_DIVERGENCE
    assert not unexpected, (
        "scan-writer and seed-writer effective archive columns diverge on "
        f"column(s) {sorted(unexpected)} that are NOT on the intentional "
        "divergence allowlist. A column populated by one path but not the other "
        "is NULL for that whole population (this is exactly how "
        "score_traversal_quality was silently NULL in every seeded row). Either "
        "map the column in both paths, or, if the divergence is genuinely "
        "path-specific, add it to _WRITER_ONLY_ALLOW / _SEED_ONLY_ALLOW with a "
        "one-line reason."
    )


def test_traversal_quality_now_populated_by_both_paths():
    """Regression pin for the confirmed drift: score_traversal_quality must be
    populated by BOTH write paths (the fix that motivated this guard).

    Scan: an explicit ``score_traversal_quality=...`` key in its ``values``
    literal. Seed: it lives in the mapper's ``_MANUAL_UNMAPPED_COLUMNS`` (the
    manual route leaves it NULL), so the seed path must re-add it explicitly in
    its ``overrides`` — assert it is present there so a future edit can't drop it
    back to NULL for the seed population."""
    # Task-6 fold: BOTH batch writers now populate it through the ONE nested-
    # dict producer (sub_score_archive_values), so the original drift class —
    # a literal dropped from one path — is structurally dead. The pin survives
    # as: the producer covers the column, and both effective sets carry it.
    assert "score_traversal_quality" in _sub_score_cols()
    assert "score_traversal_quality" in _scan_effective_cols()
    assert "score_traversal_quality" in _seed_effective_cols()


def test_all_score_subscores_covered_by_exactly_one_producer():
    """The WHOLE ``score_*`` family must be VALUE-mapped by exactly one of the
    two registry-driven producers — never left to the auto-mapper.

    History: the sub-scores arrive NESTED under ``best_result["sub_scores"]``,
    while the auto-mapper only tries the flat ``best_result.get("score_X")`` —
    which silently resolved to None when a hand literal was dropped (the
    score_traversal_quality bug, then generalized). The task-6 fold cures the
    class structurally: ``sub_score_archive_values`` reads the NESTED dict
    directly for every always-emitted term, and ``ta_grade_archive_values``
    carries the flag-gated term points (flat, archive-ready names). This guard
    keeps the cure honest: every ``score_*`` model column is covered by
    exactly ONE producer (disjoint, no gaps) — a new registry term whose
    column neither producer emits fails here at add time."""
    score_cols = frozenset(c for c in _model_columns() if c.startswith("score_"))
    assert len(score_cols) >= 15, (
        f"expected the full score_* family (~20 columns); found only "
        f"{sorted(score_cols)} — the model changed shape or the guard is stale."
    )
    sub_covered = _sub_score_cols()
    ta_covered = frozenset(c for c in _ta_grade_cols(prefixed=False)
                           if c.startswith("score_"))
    assert not (sub_covered & ta_covered), (
        f"columns claimed by BOTH producers: {sorted(sub_covered & ta_covered)}"
        " — a dict() with a key from two splats raises TypeError in the writer."
    )
    uncovered = score_cols - sub_covered - ta_covered
    assert not uncovered, (
        f"score_* column(s) {sorted(uncovered)} are covered by NEITHER "
        "sub_score_archive_values NOR ta_grade_archive_values — the column "
        "would silently NULL for every population. Add the term's column to "
        "the producer that owns its data shape."
    )


def _manual_overrides_dict():
    """The ``overrides = {...}`` ast.Dict inside the manual-add route."""
    from routers import archive_actions
    src = inspect.getsource(archive_actions.add_setup_manually)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "overrides" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return node.value
    raise AssertionError("manual route `overrides = {...}` literal not found")


def test_manual_route_score_coverage_with_declared_exclusions():
    """Closes the unguarded-manual-route gap (task 6): the THIRD writer's
    score_* coverage is registry-driven, and its deliberate NULLs are DECLARED
    twice-coherently — in the route's ``exclude`` and in the mapper's frozen
    ``_MANUAL_UNMAPPED_COLUMNS`` — never hand-omitted. A new score_* column
    neither producer covers on this path fails here at add time."""
    from services.archive_queries import _MANUAL_UNMAPPED_COLUMNS
    d = _manual_overrides_dict()
    literal_keys = {k.value for k in d.keys
                    if k is not None and isinstance(k, ast.Constant)}
    splat_calls = [v for k, v in zip(d.keys, d.values)
                   if k is None and isinstance(v, ast.Call)]
    splat_names = {c.func.id if isinstance(c.func, ast.Name)
                   else getattr(c.func, "attr", "?") for c in splat_calls}
    assert "sub_score_archive_values" in splat_names, (
        "the manual route no longer splats the ONE sub-score producer")
    # BOTH family producers, not one (council review 2026-08-08, finding 1:
    # the route shipped with only the sub-score splat, so fired_tags reached
    # the model pass as a raw Python list — a guaranteed flag-on bind error —
    # and the EC-19 closed-set refusals never ran on this writer).
    assert "ta_grade_archive_values" in splat_names, (
        "the manual route no longer splats the TA-grade family producer — "
        "fired_tags would bind as a raw list and the closed-set refusals "
        "would not guard this writer (2026-08-08 review, finding 1)")
    # The declared exclusion, read from the route's own source.
    declared_excl: set = set()
    for call in splat_calls:
        name = call.func.id if isinstance(call.func, ast.Name) \
            else getattr(call.func, "attr", "?")
        if name != "sub_score_archive_values":
            continue
        for kw in call.keywords:
            if kw.arg == "exclude":
                for node in ast.walk(kw.value):
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        declared_excl.add(node.value)
    assert declared_excl == {"score_traversal_quality"}, (
        f"manual route's declared exclusion drifted: {sorted(declared_excl)}")
    assert declared_excl <= _MANUAL_UNMAPPED_COLUMNS, (
        "the route's exclusion and the mapper's frozen _MANUAL_UNMAPPED_COLUMNS "
        "disagree — the two declarations of the same deliberate NULL must match")
    # Full score_* coverage on this path: the sub producer (minus the declared
    # exclusion) + the TA-grade family splat's score_* columns (produced, no
    # longer left to the model pass) + any literal keys.
    score_cols = {c for c in _model_columns() if c.startswith("score_")}
    ta_flat = {c for c in _ta_grade_cols(prefixed=False) if c.startswith("score_")}
    covered = ((_sub_score_cols() - declared_excl)
               | (ta_flat - _MANUAL_UNMAPPED_COLUMNS)
               | (literal_keys & score_cols))
    missing = score_cols - covered - _MANUAL_UNMAPPED_COLUMNS
    assert not missing, (
        f"score_* column(s) {sorted(missing)} are neither produced nor "
        "declared-unmapped on the manual route — a silent NULL population.")


def test_allowlist_has_no_dead_entries():
    """Every allowlisted key must actually be a real divergence — a stale
    allowlist entry (later mapped in both paths, or removed) is dead weight that
    would mask a future re-divergence on the same column."""
    divergence = _scan_effective_cols() ^ _seed_effective_cols()
    dead = _INTENTIONAL_DIVERGENCE - divergence
    assert not dead, (
        f"allowlist entries no longer diverge (dead): {sorted(dead)}; remove "
        "them from _WRITER_ONLY_ALLOW / _SEED_ONLY_ALLOW."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
