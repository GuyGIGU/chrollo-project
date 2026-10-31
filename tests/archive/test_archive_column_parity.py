"""
Archive scan-vs-seed column-PARITY guard (hermetic — NO DB, NO scan).

Sibling of ``test_archive_row_assembly.py`` (which checks each writer's assembled
columns are a SUBSET of the ORM columns). This one checks the two writers against
*each other*: a column populated by one write path and forgotten in the other
silently NULLs that column for a whole population.

That already happened: ``score_traversal_quality`` was archived by scan rows
(``core/archive/writer.py``) but NULL in every seeded row until it was added to
``core/archive/seed.py``.

The two writers assemble their rows differently:

  * the live scan writer is one hand-written ``values = dict(...)`` (plus its
    ``two_eyes_archive_values`` / ``retired_columns_null`` / ``sector_rank_columns``
    ``**`` splats);
  * the seed writer builds its row through the model-driven mapper —
    ``archive_row_from_result(best_result, overrides=dict(...))`` — so its
    populated columns are the mapper's auto-mapped flat columns PLUS the
    ``overrides`` special-cases PLUS its ``two_eyes_archive_values`` /
    ``retired_columns_null`` / ``fwd_returns`` ``**`` splats.

GUARD: compute each writer's FULL effective populated-column set (literal keys +
resolved ``**`` splats, and for seed the mapper's auto-mapped columns too), then
require their symmetric difference to be a SUBSET of an explicit intentional-
divergence ALLOWLIST. Anything else fails CI. The allowlist enumerates exactly the
run-level context the scan computes but a historical replay cannot (``regime_*`` /
``scope_*`` / breadth) and the seed-only fields (forward-return outcomes computed
immediately for a historical date, plus ``quality_label`` / ``notes`` /
scan-row-absent anchors). Modelled on the manual path's ``_MANUAL_UNMAPPED_COLUMNS``
frozenset.

The old engine's families are RETIRED (Fri 30/10/2026, decision H): every writer
sets their columns to None on every write through the ONE frozen literal
``RETIRED_COLUMNS``, so a re-scan over an old-reader date re-stamps the row whole.
This file pins that the literal covers every retired column (the whole ``score_*``
family among them) and that both batch writers splat it.

Fully self-contained: parses the two writer source files with ``ast`` and drives
the pure splat/mapper helpers hermetically (no import-time execution of the
writers, no shared conftest fixture, no DB).
"""
from __future__ import annotations

import ast
import inspect
import os
import sys

from _paths import REPO_ROOT

# ── project paths (mirror the writers' own bootstrap; kept local to this
# test — no shared conftest fixture touched). ──
_PROJECT_ROOT = str(REPO_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


from core.archive import seed as seed_mod  # noqa: E402
from core.archive import writer as writer_mod  # noqa: E402
from core.archive.writer import RETIRED_COLUMNS, retired_columns_null  # noqa: E402
from core.regime.scan_context import sector_rank_fields  # noqa: E402
from engine_alpha.archive import two_eyes_archive_values  # noqa: E402
from core.archive.r_outcomes import R_COLUMNS  # noqa: E402


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
    # The Power-Play species family, RETIRED with its lane (the final method,
    # build step 12, point 25, Sat 19/09/2026): no writer names these any more,
    # so the seed mapper auto-maps the model columns as NULL while the scan
    # literal never carries them. NULL on both paths from here on; the columns
    # stay for the rows the lane wrote (2026-08-19 to the deletion).
    "pp_state", "pp_clock", "pp_climax_date", "pp_ar_date", "pp_pole_gain",
    "pp_shelf_start_date", "pp_shelf_end_date", "pp_shelf_bars",
    "pp_lower_third_bars", "pp_zone_coverage", "pp_zone_collided",
    # The R outcome (his rolling LPS rule, core/archive/r_outcomes.py, 2026-10-28):
    # written by the nightly backfill from the price cache, by NEITHER writer, so
    # the seed mapper auto-maps the model columns as NULL while the scan literal
    # never names them. Taken from the module's own list so the two stay in step.
    *R_COLUMNS,
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

def _retired_cols() -> frozenset[str]:
    return frozenset(retired_columns_null().keys())


def _two_eyes_cols(*, prefixed: bool) -> frozenset[str]:
    return frozenset(
        two_eyes_archive_values((lambda _k: None), prefixed=prefixed).keys())


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
    from domains.archive.queries import archive_row_from_result
    return frozenset(archive_row_from_result({}, overrides={}))


def _scan_effective_cols() -> frozenset[str]:
    """Every column the live scan writer populates: its ``values`` literal keys +
    its ``two_eyes_archive_values`` (prefixed) / ``retired_columns_null`` /
    ``sector_rank_columns`` splats."""
    literal = _literal_kwargs(writer_mod.archive_scan_results, "values")
    splats = set(_splat_names(writer_mod.archive_scan_results, "values"))
    assert splats == {"retired_columns_null", "two_eyes_archive_values",
                      "sector_rank_columns"}, (
        f"unexpected scan **splat(s): {sorted(splats)}; extend the parity guard."
    )
    return (literal | _retired_cols() | _two_eyes_cols(prefixed=True)
            | _sector_rank_cols())


def _seed_effective_cols() -> frozenset[str]:
    """Every column the seed writer populates through the mapper: the mapper's
    auto-mapped flat columns + the ``overrides`` literal keys + its
    ``two_eyes_archive_values`` (unprefixed) / ``retired_columns_null`` /
    ``fwd_returns`` splats."""
    literal = _literal_kwargs(seed_mod.seed_archive, "overrides")
    splats = set(_splat_names(seed_mod.seed_archive, "overrides"))
    assert splats == {"retired_columns_null", "two_eyes_archive_values",
                      "fwd_returns"}, (
        f"unexpected seed **splat(s): {sorted(splats)}; extend the parity guard."
    )
    return (_mapper_auto_cols() | literal | _retired_cols()
            | _two_eyes_cols(prefixed=False) | _fwd_return_cols())


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


def test_ta_grade_is_written_by_both_paths_and_is_not_retired():
    """The one column of the old TA-grade family that lives on: the reader's 0-100 grade,
    written from the row's own ``_ta_grade`` (scan) / ``ta_grade`` (seed) by name."""
    assert "ta_grade" not in RETIRED_COLUMNS
    assert "ta_grade" in _literal_kwargs(writer_mod.archive_scan_results, "values")
    assert "ta_grade" in _literal_kwargs(seed_mod.seed_archive, "overrides")


def test_the_retired_literal_covers_every_old_family_column_and_both_writers_splat_it():
    """Decision H: the frozen literal names every column the seven retired families wrote
    (the whole ``score_*`` family, the HTF, Event Map, sentence, election-trace and strategy
    families, and the old grade's companions) — all real model columns, no duplicates — and
    both batch writers splat it so an upsert over an old-reader row empties them."""
    model = _model_columns()
    retired = frozenset(RETIRED_COLUMNS)
    assert len(RETIRED_COLUMNS) == len(retired) == 68
    assert retired <= model, sorted(retired - model)
    assert {c for c in model if c.startswith("score_")} <= retired
    assert {c for c in model if c.startswith(("htf_", "event_map_", "sentence_", "strategy_"))} <= retired
    assert {"election_trace", "ta_grade_raw", "fired_tags", "setup_chronology"} <= retired
    assert "retired_columns_null" in _splat_names(writer_mod.archive_scan_results, "values")
    assert "retired_columns_null" in _splat_names(seed_mod.seed_archive, "overrides")
    assert retired_columns_null() == {c: None for c in RETIRED_COLUMNS}


def _manual_overrides_dict():
    """The ``overrides = {...}`` ast.Dict inside the manual-add route."""
    from domains.archive import actions as archive_actions
    src = inspect.getsource(archive_actions.add_setup_manually)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "overrides" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return node.value
    raise AssertionError("manual route `overrides = {...}` literal not found")


def test_manual_route_splats_only_the_readers_family():
    """The THIRD writer (the manual add) carries the reader's own family through the ONE
    producer and names no retired producer: a writer left to a raw model pass bypasses the
    family's serialization, scrubbing and closed-set refusals (EC-30, per writer). The
    mapper it builds its row through auto-maps every other model column from the result,
    so the retired columns land NULL on a manual row by construction."""
    d = _manual_overrides_dict()
    splat_calls = [v for k, v in zip(d.keys, d.values)
                   if k is None and isinstance(v, ast.Call)]
    splat_names = {c.func.id if isinstance(c.func, ast.Name)
                   else getattr(c.func, "attr", "?") for c in splat_calls}
    assert "two_eyes_archive_values" in splat_names, (
        "the manual route no longer splats the reader's family producer")
    retired_producers = {"sub_score_archive_values", "ta_grade_archive_values", "htf_archive_values",
                         "event_map_archive_values", "sentence_archive_values",
                         "election_trace_archive_values", "strategy_archive_values"}
    assert not (splat_names & retired_producers), sorted(splat_names & retired_producers)


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
