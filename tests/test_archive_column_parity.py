"""
Archive scan-vs-seed column-PARITY guard (hermetic — NO DB, NO scan).

Sibling of ``test_archive_row_assembly.py`` (which checks each writer's
``values = dict(...)`` is a SUBSET of the ORM columns). This one checks the two
writers against *each other*: the live scan writer and the winners-seed writer
are independent hand-written dict literals, so an engine sub-score added to one
and forgotten in the other silently NULLs that column for a whole write path.

That already happened: ``score_traversal_quality`` was archived by scan rows
(``core/archive/writer.py``) but NULL in every seeded row until it was added to
``core/archive/seed.py`` — the seed eval genuinely produces
``sub_scores['traversal_quality']`` (scoring.py -> ``_sub_scores`` ->
``seed_row_from_result`` strips to ``sub_scores``), it was just never mapped.

GUARD: the symmetric difference of the two literals' explicit ``name=...`` keys
must be a SUBSET of an explicit intentional-divergence ALLOWLIST. Anything else
— e.g. a new ``score_*`` sub-score wired into one writer only — fails CI. The
allowlist enumerates exactly the run-level context the scan computes but a
historical replay cannot (``regime_*``/``scope_*``/``fund_*``/RS/breadth) and
the seed-only fields (forward-return ``quality_label`` + scan-row-absent
anchors). Modelled on the manual path's ``_MANUAL_UNMAPPED_COLUMNS`` frozenset.

Fully self-contained: parses the two writer source files with ``ast`` (no
import-time execution of the writers, no shared conftest fixture, no DB).
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


# ── Intentional divergence allowlist ─────────────────────────────────────────
# Columns that legitimately appear as an explicit `name=...` kwarg in ONLY ONE
# of the two writers. Everything else in the symmetric difference is drift.
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
    # Lane-E advisory fundamentals / RS (scan post-pass; absent on replay)
    "fund_eps_growth_yoy", "fund_sales_growth_yoy", "fund_eps_growth_accel",
    "fund_earnings_surprise", "days_to_earnings",
    "rs_rating", "rs_line_latest", "rs_line_new_high", "rs_vs_sector_pct",
})
# SEED-only: fields the seed path fills that the scan-row literal does not.
_SEED_ONLY_ALLOW = frozenset({
    # winners-gallery outcome label (seed only; scan rows mature into it later)
    "quality_label",
    # R/S anchor bars — seed reads best_result anchors; scan row literal has none
    "r_anchor", "s_anchor",
})
_INTENTIONAL_DIVERGENCE = _WRITER_ONLY_ALLOW | _SEED_ONLY_ALLOW


def _literal_kwargs(func) -> frozenset[str]:
    """Statically enumerate the explicit ``name=...`` keys of the writer's
    ``values = dict(...)`` block, ignoring ``**splat`` entries.

    Reads the ACTUAL function source via ``ast`` so a renamed/added key surfaces
    here without a hand-kept list going stale. ``**`` splats are deliberately
    excluded: both writers share the identical ``htf_archive_values`` splat, and
    the remaining splats (``sector_rank_columns`` / ``fwd_returns``) are
    path-specific run-level context, not the hand-written engine sub-scores this
    parity guard protects.
    """
    src = inspect.getsource(func)
    tree = ast.parse(src)

    dict_call = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "values"
                   for t in node.targets):
                call = node.value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                        and call.func.id == "dict":
                    dict_call = call
                    break
    assert dict_call is not None, (
        f"could not locate `values = dict(...)` in {func.__qualname__}; the "
        f"archive column-parity guard is stale — update it to the new shape."
    )
    return frozenset(kw.arg for kw in dict_call.keywords if kw.arg is not None)


def test_scan_and_seed_literals_only_diverge_on_allowlist():
    scan_keys = _literal_kwargs(writer_mod.archive_scan_results)
    seed_keys = _literal_kwargs(seed_mod.seed_archive)

    # Sanity: the shared core must be substantial (both literals are ~130 keys);
    # if this collapses, the AST parse latched onto the wrong dict.
    assert len(scan_keys & seed_keys) > 100, (
        "scan/seed literals share <100 keys — the parity guard is not reading "
        f"the real writer dicts (scan={len(scan_keys)}, seed={len(seed_keys)})."
    )

    divergence = scan_keys ^ seed_keys  # symmetric difference
    unexpected = divergence - _INTENTIONAL_DIVERGENCE
    assert not unexpected, (
        "scan-writer and seed-writer archive-row literals diverge on "
        f"column(s) {sorted(unexpected)} that are NOT on the intentional "
        "divergence allowlist. A column populated by one writer but not the "
        "other is NULL for that whole write path (this is exactly how "
        "score_traversal_quality was silently NULL in every seeded row). Either "
        "map the column in both writers, or, if the divergence is genuinely "
        "path-specific, add it to _WRITER_ONLY_ALLOW / _SEED_ONLY_ALLOW with a "
        "one-line reason."
    )


def test_traversal_quality_now_mapped_in_both_writers():
    """Regression pin for the confirmed drift: score_traversal_quality must be an
    explicit key in BOTH writers (the fix that motivated this guard)."""
    scan_keys = _literal_kwargs(writer_mod.archive_scan_results)
    seed_keys = _literal_kwargs(seed_mod.seed_archive)
    assert "score_traversal_quality" in scan_keys
    assert "score_traversal_quality" in seed_keys


def test_allowlist_has_no_dead_entries():
    """Every allowlisted key must actually be a real divergence — a stale
    allowlist entry (later mapped in both writers, or removed) is dead weight
    that would mask a future re-divergence on the same column."""
    scan_keys = _literal_kwargs(writer_mod.archive_scan_results)
    seed_keys = _literal_kwargs(seed_mod.seed_archive)
    divergence = scan_keys ^ seed_keys
    dead = _INTENTIONAL_DIVERGENCE - divergence
    assert not dead, (
        f"allowlist entries no longer diverge (dead): {sorted(dead)}; remove "
        "them from _WRITER_ONLY_ALLOW / _SEED_ONLY_ALLOW."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
