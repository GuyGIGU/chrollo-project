"""Watchlist database models."""
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from database import Base


class Watchlist(Base):
    """Dated watchlist save events — one row per star; un-star keeps history.

    Event-ledger grain (Finviz plan Task 5): the ACTIVE set is the subset with
    ``unstarred_at IS NULL``, held to at most one row per ticker by a partial
    unique index; un-starring stamps ``unstarred_at`` instead of deleting, so
    history survives as a database fact. The pin quadruple is copied VERBATIM
    from the screener artifact at save time — all four or none (a half-pin
    cannot exist; the all-NULL pin is the honest "starred without a setup"
    state). ``snapshot_json`` holds the versioned wire-shape chart payload the
    operator was looking at ({"snapshot_version": 1, ...}), JSON-validated and
    size-capped at write time; ``saved_at`` is an audit stamp only — grouping
    and identity always key off ``save_date`` / the pin, never the clock.
    """

    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    save_date = Column(String, nullable=False)     # ISO date of the save event
    saved_at = Column(DateTime, nullable=False)    # audit-only UTC stamp
    unstarred_at = Column(DateTime, nullable=True)  # NULL = active watch
    origin = Column(String, nullable=False, default="user")  # 'user' | 'legacy'
    pin_scan_date = Column(String, nullable=True)
    pin_universe_type = Column(String, nullable=True)
    pin_setup_type = Column(String, nullable=True)
    pin_engine_config_version = Column(String, nullable=True)
    snapshot_json = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "save_date", name="uq_watchlist_save_event"),
        # EC-19: the closed origin vocabulary is enforced, not just documented.
        CheckConstraint("origin IN ('user', 'legacy')",
                        name="ck_watchlist_origin"),
        CheckConstraint(
            "(pin_scan_date IS NULL AND pin_universe_type IS NULL "
            "AND pin_setup_type IS NULL AND pin_engine_config_version IS NULL) "
            "OR (pin_scan_date IS NOT NULL AND pin_universe_type IS NOT NULL "
            "AND pin_setup_type IS NOT NULL "
            "AND pin_engine_config_version IS NOT NULL)",
            name="ck_watchlist_full_pin",
        ),
        # ~256KB cap against ~50KB observed payloads; json_valid guards fresh
        # creates (SQLite cannot retrofit CHECKs, so the rebuild is what gets
        # the live DB these assertions).
        CheckConstraint(
            "snapshot_json IS NULL OR (json_valid(snapshot_json) "
            "AND length(snapshot_json) <= 262144)",
            name="ck_watchlist_snapshot",
        ),
        Index(
            "ux_watchlist_active_ticker",
            "ticker",
            unique=True,
            sqlite_where=text("unstarred_at IS NULL"),
        ),
    )


