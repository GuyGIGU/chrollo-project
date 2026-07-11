from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    opening_date = Column(String, index=True)
    direction = Column(String)  # "L" or "S"
    ticker = Column(String, index=True)
    entry_price = Column(Float)
    stop_loss = Column(Float)
    quantity = Column(Integer)
    risk_percentage = Column(Float)
    position_size = Column(Float)
    target_r = Column(Float, default=3.0)

    # Take profits
    t1_qty = Column(Integer, nullable=True)
    t1_price = Column(Float, nullable=True)
    t2_qty = Column(Integer, nullable=True)
    t2_price = Column(Float, nullable=True)
    t3_qty = Column(Integer, nullable=True)
    t3_price = Column(Float, nullable=True)
    t4_qty = Column(Integer, nullable=True)
    t4_price = Column(Float, nullable=True)
    t5_qty = Column(Integer, nullable=True)
    t5_price = Column(Float, nullable=True)

    # Closing info
    closing_date = Column(String, nullable=True)
    remaining_qty = Column(Integer, nullable=True)
    exit_price = Column(Float, nullable=True)
    commissions = Column(Float, default=0.0)
    pnl = Column(Float, nullable=True)

    # Multi-leg actions (JSON array of {id, type, date, quantity, price, fee})
    actions_json = Column(Text, nullable=True)

    # IBKR linkage + journal upgrades
    source = Column(String, default="manual", nullable=True)  # "manual" | "ibkr"
    ibkr_account = Column(String, nullable=True, index=True)
    perm_id = Column(String, nullable=True, index=True)
    planned_stop = Column(Float, nullable=True)  # original stop used for R-multiple

    # Intent capture (engine-validation pivot): the minimal per-trade "why".
    conviction = Column(Integer, nullable=True)   # 1-10 pre-trade conviction
    exit_reason = Column(Text, nullable=True)     # one-line "why I exited"

    tags = relationship(
        "Tag",
        secondary="trade_tags",
        back_populates="trades",
        lazy="selectin",
    )
    executions = relationship("Execution", back_populates="trade_log")
    plan = relationship(
        "TradePlan", uselist=False, back_populates="trade_log", cascade="all, delete-orphan"
    )
    notes = relationship(
        "TradeNote", uselist=False, back_populates="trade_log", cascade="all, delete-orphan"
    )
    attachments = relationship(
        "TradeAttachment",
        back_populates="trade_log",
        cascade="all, delete-orphan",
    )


class Execution(Base):
    """Raw IBKR executions. Grouped into TradeLog rows by the auto-import pipeline."""

    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    exec_id = Column(String, unique=True, index=True, nullable=False)
    perm_id = Column(String, index=True, nullable=True)
    order_id = Column(String, nullable=True)
    account = Column(String, index=True, nullable=True)
    symbol = Column(String, index=True, nullable=False)
    sec_type = Column(String, nullable=True)  # STK / OPT / FUT
    side = Column(String, nullable=False)  # BUY / SELL
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    multiplier = Column(Float, nullable=True)
    commission = Column(Float, default=0.0)
    realized_pnl = Column(Float, nullable=True)
    time = Column(DateTime, index=True, nullable=False)
    trade_log_id = Column(Integer, ForeignKey("trade_logs.id"), nullable=True, index=True)
    raw_json = Column(Text, nullable=True)

    trade_log = relationship("TradeLog", back_populates="executions")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, default="custom")  # "setup" | "mistake" | "custom"
    color = Column(String, nullable=True)

    trades = relationship("TradeLog", secondary="trade_tags", back_populates="tags")


class TradeTag(Base):
    __tablename__ = "trade_tags"

    trade_log_id = Column(Integer, ForeignKey("trade_logs.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

    __table_args__ = (
        UniqueConstraint("trade_log_id", "tag_id", name="uq_trade_tag"),
    )


class TradePlan(Base):
    __tablename__ = "trade_plans"

    id = Column(Integer, primary_key=True, index=True)
    trade_log_id = Column(Integer, ForeignKey("trade_logs.id", ondelete="CASCADE"), unique=True)
    thesis = Column(Text, nullable=True)
    entry_plan = Column(Text, nullable=True)
    exit_plan = Column(Text, nullable=True)
    risk_plan = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)

    trade_log = relationship("TradeLog", back_populates="plan")


class TradeNote(Base):
    __tablename__ = "trade_notes"

    id = Column(Integer, primary_key=True, index=True)
    trade_log_id = Column(Integer, ForeignKey("trade_logs.id", ondelete="CASCADE"), unique=True)
    body = Column(Text, nullable=True)
    mood = Column(String, nullable=True)  # free-form, e.g. "focused", "tilted"
    created_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    trade_log = relationship("TradeLog", back_populates="notes")


class TradeAttachment(Base):
    __tablename__ = "trade_attachments"

    id = Column(Integer, primary_key=True, index=True)
    trade_log_id = Column(Integer, ForeignKey("trade_logs.id", ondelete="CASCADE"), index=True)
    kind = Column(String, default="chart")  # "chart" | "other"
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    mime = Column(String, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, nullable=True)

    trade_log = relationship("TradeLog", back_populates="attachments")


class Watchlist(Base):
    """User-curated tickers saved from the screener for later review."""

    __tablename__ = "watchlist"

    ticker = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=True)


class SetupReview(Base):
    """A 'saw & passed' decision on a screener/archive setup.

    Lets the missed-winners analysis tell 'reviewed but skipped' apart from
    'never engaged' — keyed to the setup's (ticker, scan_date) so it works for
    both today's screener cards and historical archive rows.
    """

    __tablename__ = "setup_reviews"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    scan_date = Column(String, nullable=False, index=True)
    verdict = Column(String, nullable=False, default="passed")  # "passed"
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_setup_review"),
    )


class CalibrationMark(Base):
    """One operator verdict about one chart — editable calibration ground truth.

    Grain: one verdict per (ticker, as-of date, label); ``label`` discriminates
    the rare multiple-structures-on-one-chart case and defaults to "" rather
    than NULL so the compound unique key always bites (SQLite treats NULLs as
    distinct). Deliberately UNLIKE the sealed docs/marks corpus (EC-7): the
    operator may edit or hard-delete his own marks; every edit bumps
    ``revision``. Geometry is ISO dates + absolute prices — never bar indices.
    Provenance columns are required so replay can refuse loudly when the data
    under a mark no longer matches what the operator saw.
    """

    __tablename__ = "calibration_marks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    as_of_date = Column(String, nullable=False, index=True)  # ISO; the frame's last bar
    label = Column(String, nullable=False, default="")
    verdict = Column(String, nullable=False)  # "box" | "no_structure" | "engine_wrong"

    # Geometry (required for verdict="box" — enforced below and in the shared
    # validity check; negatives carry no geometry, never null-rail "box" rows).
    resistance = Column(Float, nullable=True)
    support = Column(Float, nullable=True)
    box_start_date = Column(String, nullable=True)  # ISO
    box_end_date = Column(String, nullable=True)    # ISO
    # Rail anchors (2026-07-11): the swing BAR each rail was placed on, plus
    # which rail the operator marked first — together they carry the root
    # swing he was aiming at (comparable to the engine's chronological pair
    # anchors). Nullable: negatives and pre-anchor marks have none.
    r_anchor_date = Column(String, nullable=True)   # ISO
    s_anchor_date = Column(String, nullable=True)   # ISO
    first_rail = Column(String, nullable=True)      # "resistance" | "support"
    rails_source = Column(String, nullable=False, default="operator")  # "operator" | "extraction"
    knowable_from_date = Column(String, nullable=True)  # earliest session the verdict is fairly knowable
    note = Column(Text, nullable=True)  # the operator's reason (negatives especially)

    # Point-in-time provenance — required, never backfilled.
    data_regime = Column(String, nullable=False)
    engine_config_version = Column(String, nullable=False)
    anchor_close = Column(Float, nullable=False)  # the as-of bar's close as rendered
    frame_digest = Column(String, nullable=True)  # bound at save / first harness freeze
    created_at = Column(DateTime, nullable=False)  # UTC
    updated_at = Column(DateTime, nullable=False)  # UTC
    revision = Column(Integer, nullable=False, default=1)

    events = relationship(
        "CalibrationMarkEvent",
        back_populates="mark",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("ticker", "as_of_date", "label", name="uq_calibration_mark"),
        CheckConstraint(
            "verdict IN ('box', 'no_structure', 'engine_wrong')",
            name="ck_calibration_mark_verdict",
        ),
        CheckConstraint(
            "verdict != 'box' OR (resistance IS NOT NULL AND support IS NOT NULL "
            "AND box_start_date IS NOT NULL AND box_end_date IS NOT NULL)",
            name="ck_calibration_mark_box_geometry",
        ),
        CheckConstraint(
            "resistance IS NULL OR support IS NULL OR resistance > support",
            name="ck_calibration_mark_rails_order",
        ),
        CheckConstraint(
            "box_start_date IS NULL OR box_end_date IS NULL "
            "OR box_start_date <= box_end_date",
            name="ck_calibration_mark_span_order",
        ),
        CheckConstraint("revision >= 1", name="ck_calibration_mark_revision"),
    )


class CalibrationMarkEvent(Base):
    """One event mark inside a calibration mark (Phase C span/tip, LPS, spring test)."""

    __tablename__ = "calibration_mark_events"

    id = Column(Integer, primary_key=True, index=True)
    mark_id = Column(
        Integer,
        ForeignKey("calibration_marks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False)  # "phase_c" | "lps" | "spring_test"
    start_date = Column(String, nullable=False)  # ISO
    end_date = Column(String, nullable=False)    # ISO
    tip_date = Column(String, nullable=True)     # the extreme's session (e.g. Phase C tip)
    tip_price = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="operator")  # "operator" | "extraction"

    mark = relationship("CalibrationMark", back_populates="events")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('phase_c', 'lps', 'spring_test')",
            name="ck_calibration_event_type",
        ),
        CheckConstraint("start_date <= end_date", name="ck_calibration_event_span"),
    )


class PortfolioSnapshotCache(Base):
    """Last useful read-only IBKR Portfolio snapshot."""

    __tablename__ = "portfolio_snapshot_cache"

    key = Column(String, primary_key=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
