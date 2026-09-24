"""Council 2026-06-30 Finding 1 — the equities-default scope must have ONE
definition (conventions.md EC-1).

Every surface that defaults to the equities population (the descriptor, the
SetupRow grouping default, the SQLAlchemy server_default + CHECK, and the
archive read defaults) must agree on the universe_type string. Before this guard,
each site re-pinned the bare literal "us_equities" independently, so a rename or
a 4th universe could silently orphan equities rows from a read surface while every
per-site test stayed green. This pins the agreement centrally so drift at any one
site fails loudly here.
"""
from __future__ import annotations

import inspect
import sys

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "webapp" / "backend"))

from core.archive.episodes import SetupRow
from core.pipeline.universe.descriptor import (
    DEFAULT_UNIVERSE_TYPE,
    _build_registry,
    default_universe,
    default_universe_type,
)


def test_descriptor_constant_and_accessor_agree():
    assert DEFAULT_UNIVERSE_TYPE == "us_equities"
    assert default_universe().universe_type == DEFAULT_UNIVERSE_TYPE
    assert default_universe_type() == DEFAULT_UNIVERSE_TYPE


def test_each_universe_type_pinned_and_key_split_preserved():
    reg = _build_registry()
    assert reg["us_stocks"].universe_type == "us_equities"
    assert reg["us_sectors"].universe_type == "us_sectors"
    assert reg["commodities_etf"].universe_type == "commodities_etf"
    # AP-1: the deliberate key != universe_type split on the default must survive a
    # tidy-up — collapsing it to one token is the seam's most-flagged trap.
    assert reg["us_stocks"].key == "us_stocks"
    assert reg["us_stocks"].key != reg["us_stocks"].universe_type


def test_setuprow_grouping_default_matches():
    row = SetupRow(id=1, ticker="X", scan_date="2026-06-01", setup_type="LPS")
    assert row.universe_type == DEFAULT_UNIVERSE_TYPE


def test_archive_model_write_side_matches_constant():
    from archive_models import SetupArchive

    col = SetupArchive.__table__.c.universe_type
    assert DEFAULT_UNIVERSE_TYPE in str(col.server_default.arg)
    checks = [
        str(c.sqltext) for c in SetupArchive.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert any(DEFAULT_UNIVERSE_TYPE in text for text in checks)


def test_read_surface_defaults_route_through_the_constant():
    from domains.archive.browse import _resolve_universe_type
    from domains.archive.queries import _apply_setup_filters

    # the filter helper's default scope is the constant, not a bare literal
    default = inspect.signature(_apply_setup_filters).parameters["universe_type"].default
    assert default == DEFAULT_UNIVERSE_TYPE
    # the browse escape-hatch resolves a missing param to the same default,
    # and 'all' lifts the filter
    assert _resolve_universe_type(None) == DEFAULT_UNIVERSE_TYPE
    assert _resolve_universe_type("all") is None
