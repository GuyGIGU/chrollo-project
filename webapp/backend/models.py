from sqlalchemy import (
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
    conviction = Column(Integer, nullable=True)   # 1-3 pre-trade conviction
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


class PortfolioSnapshotCache(Base):
    """Last useful read-only IBKR Portfolio snapshot."""

    __tablename__ = "portfolio_snapshot_cache"

    key = Column(String, primary_key=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
