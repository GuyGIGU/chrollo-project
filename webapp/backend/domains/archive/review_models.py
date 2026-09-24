"""Archive database models."""
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
    # A CLOSED SET of two, and they are mutually exclusive by construction —
    # the unique constraint below allows exactly one review row per setup, so
    # liking a setup you had passed replaces the verdict rather than stacking.
    #   "passed" — saw it and skipped it (feeds the missed-winners report)
    #   "liked"  — saw it and it is the kind of setup you want more of
    #              (operator 2026-09-02; a preference signal for RANKING, never
    #              a detection threshold — it must not reach scoring until it is
    #              measured against the archive, house rule "measure-first")
    verdict = Column(String, nullable=False, default="passed")
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


