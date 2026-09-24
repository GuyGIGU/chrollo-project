"""Calibration database models."""
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
            "'mini_consolidation', 'last_supper')",
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


