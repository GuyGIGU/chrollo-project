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


class ReadVerdict(Base):
    """The operator's verdict on the ENGINE'S READ of a chart (Surface the
    Read) — a third axis, deliberately its own table: it judges the READ, not
    the setup (a correct read of junk and a wrong read of a winner are both
    legal), so it must never collide with the card's 'considered' mark or the
    archive's 'saw & passed' skip (whose verdict column is NOT NULL and whose
    rows feed missed-winners). Keyed VERBATIM to the archive identity triple
    (ticker, scan_date, universe_type) — the payload's scan_identity, never a
    client-derived date. ``engine_config_version`` stamps the evidence the
    operator actually saw: setup_archive upserts in place, so a same-day
    re-scan under a rotated manifest replaces the narrative — the concordance
    reader flags verdicts whose stored version no longer matches the row it
    joins (council review 2026-08-05, finding 6)."""

    __tablename__ = "read_verdicts"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, nullable=False, index=True)
    scan_date = Column(String, nullable=False, index=True)
    universe_type = Column(String, nullable=False, index=True)
    verdict = Column(String, nullable=False)   # 'agree' | 'disagree'
    # The GRADE channel (TA-grade build task 14, the ruled closed vocabulary):
    # 'read right, grade wrong' must be separable from a reading error, or the
    # harvested corpus cannot tell the two apart. NULL = the grade was not
    # judged; the READ verdict above stays about the read. Live-DB constraint
    # = the router's write-time refusal (the ALTER path strips CHECKs).
    grade_verdict = Column(String, nullable=True)  # 'agree'|'too_high'|'too_low'
    note = Column(Text, nullable=True)         # read-reason (rails/story/posture/…)
    # Evidence provenance — nullable, never backfilled (a version stamped after
    # the fact is not what the operator saw).
    engine_config_version = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", "universe_type",
                         name="uq_read_verdict"),
        # Closed set, all three EC-19 legs: this CHECK (free on a NEW table —
        # create_all builds it on live DBs too), the router's write-time
        # assertion, and the refusing test in test_backend_services.
        CheckConstraint("verdict IN ('agree', 'disagree')",
                        name="ck_read_verdict_vocabulary"),
        CheckConstraint(
            "grade_verdict IS NULL OR "
            "grade_verdict IN ('agree', 'too_high', 'too_low')",
            name="ck_read_verdict_grade_vocabulary"),
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

    # The Trigger — the operator's BUY: the day price breaks above the High of the
    # LPS's FINAL bar. Its only placement rule is "strictly after the last LPS bar"
    # (requires an LPS); it may sit before/on/after as-of — the operator marks the
    # real breakout and locks the snapshot separately (relaxed 2026-07-22). Nullable
    # with NO default — a null trigger is the real "no buy marked yet" state. The
    # requires-LPS and after-last-LPS-bar rules live in the shared marks_validity
    # (SQLite cannot retrofit these onto the live corpus DB); the row-local CHECKs
    # below are fresh-DB defence-in-depth only.
    trigger_date = Column(String, nullable=True)   # ISO; > last LPS bar, <= frame_end (no as_of floor)
    trigger_price = Column(Float, nullable=True)   # the last-LPS-bar High (tool-snapped, editable)

    # Point-in-time provenance — required, never backfilled.
    data_regime = Column(String, nullable=False)
    engine_config_version = Column(String, nullable=False)
    anchor_close = Column(Float, nullable=False)  # the as-of bar's close as rendered
    frame_digest = Column(String, nullable=True)  # always bound at save (validate_mark requires a sha256); nullable is legacy-DDL only — see review 2026-07-12 (NOT NULL rebuild deferred)
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
        # Trigger (fresh-DB defence-in-depth; the live DB enforces via marks_validity).
        CheckConstraint(
            "(trigger_date IS NULL AND trigger_price IS NULL) "
            "OR (trigger_date IS NOT NULL AND trigger_price IS NOT NULL)",
            name="ck_calibration_mark_trigger_paired",
        ),
        CheckConstraint(
            "trigger_date IS NULL OR verdict = 'box'",
            name="ck_calibration_mark_trigger_box_only",
        ),
        # No as_of floor on the trigger (relaxed 2026-07-22): the buy may precede
        # the snapshot, so the former ck_calibration_mark_trigger_after_as_of is
        # gone. "After the last LPS bar" is enforced in marks_validity (it needs
        # the event rows, which a row-local CHECK cannot see). The live corpus DB
        # never carried this CHECK — the trigger columns were added CHECK-less via
        # ALTER TABLE — so no migration is required.
        CheckConstraint(
            "trigger_price IS NULL OR trigger_price > 0",
            name="ck_calibration_mark_trigger_price_positive",
        ),
    )


class CalibrationMarkEvent(Base):
    """One event mark inside a calibration mark — the vocabulary is
    ``marks_validity.EVENT_TYPES`` (kept in sync by test_marks_validity).

    Two shapes share this row. Most types are a SPAN (start/end, optional tip):
    Phase C, LPS, spring test, and the SOS — whose span IS its measurement, the
    launch low to the swing top, because "decisive" is ground covered over days
    (operator ruling 2026-08-26). ``mini_consolidation`` is the exception: it is
    a small BOX, so it also carries a price band the way the parent mark carries
    its rails. Prices the span implies (the low of the start bar, the high of the
    end bar) are NOT stored — they re-derive from the frozen frame, the same
    contract the rail anchors already rely on.
    """

    __tablename__ = "calibration_mark_events"

    id = Column(Integer, primary_key=True, index=True)
    mark_id = Column(
        Integer,
        ForeignKey("calibration_marks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String, nullable=False)  # see marks_validity.EVENT_TYPES
    start_date = Column(String, nullable=False)  # ISO
    end_date = Column(String, nullable=False)    # ISO
    tip_date = Column(String, nullable=True)     # the extreme's session (e.g. Phase C tip)
    tip_price = Column(Float, nullable=True)
    # The price band — mini_consolidation only (a small box has a top and a
    # bottom). Nullable: every other type is a span, not a band.
    band_high = Column(Float, nullable=True)
    band_low = Column(Float, nullable=True)
    source = Column(String, nullable=False, default="operator")  # "operator" | "extraction"

    mark = relationship("CalibrationMark", back_populates="events")

    __table_args__ = (
        # Frozen defence-in-depth DDL; marks_validity.EVENT_TYPES is the
        # authoritative list. Widening it rebuilds this table on the next boot
        # (startup.migrate_calibration_event_types) — SQLite cannot ALTER a CHECK.
        CheckConstraint(
            "event_type IN ('phase_c', 'lps', 'spring_test', 'sos', "
            "'mini_consolidation')",
            name="ck_calibration_event_type",
        ),
        CheckConstraint("start_date <= end_date", name="ck_calibration_event_span"),
        CheckConstraint(
            "(band_high IS NULL AND band_low IS NULL) OR "
            "(band_high IS NOT NULL AND band_low IS NOT NULL AND band_high > band_low)",
            name="ck_calibration_event_band_paired",
        ),
        CheckConstraint(
            "event_type != 'mini_consolidation' OR band_high IS NOT NULL",
            name="ck_calibration_event_mini_band",
        ),
    )


class PortfolioSnapshotCache(Base):
    """Last useful read-only IBKR Portfolio snapshot."""

    __tablename__ = "portfolio_snapshot_cache"

    key = Column(String, primary_key=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
