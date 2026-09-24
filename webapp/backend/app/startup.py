"""Import-time database initialization; never starts background services."""
from __future__ import annotations

import archive_models
import models
from database import engine
from app.migrations.additive import (
    _MIGRATIONS, _MIGRATED_ARCHIVE_MODELS, _apply_migrations,
    _apply_model_add_columns, model_add_column_migrations,
)
from app.migrations.archive import migrate_universe_type, migrate_near_miss_framing_identity
from app.migrations.watchlist import migrate_watchlist_ledger
from app.migrations.calibration import migrate_calibration_event_types
from app.reconciliation import _reconcile_orphaned_runs


def initialize_database() -> None:
    models.Base.metadata.create_all(bind=engine)
    archive_models.SetupArchive.metadata.create_all(bind=engine)
    _apply_migrations(engine)
    # Non-additive one-off (widen the identity key); must run BEFORE the ADD-only
    # auto-migrator so the latter sees universe_type already present and skips it.
    migrate_universe_type(engine)
    # Non-additive one-off: watchlist ticker-PK -> dated event ledger (rebuild).
    migrate_watchlist_ledger(engine)
    # Non-additive one-off: take the rail PRICES out of the near-miss episode
    # identity (rebuild + dedupe to the date-anchored framing key).
    migrate_near_miss_framing_identity(engine)
    # Non-additive, self-renewing: widen the drawn-event vocabulary / add its
    # columns (the calibration tables are not in _MIGRATED_ARCHIVE_MODELS, so the
    # ADD-only pass below can never reach them).
    migrate_calibration_event_types(engine)
    _apply_model_add_columns(engine)
    # Clear any scan_runs row orphaned in 'running' by a prior hard kill, so
    # latest_run() reflects reality and the live-price fallback gate unsticks.
    _reconcile_orphaned_runs(engine)


