"""Portfolio database models."""
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


class PortfolioSnapshotCache(Base):
    """Last useful read-only IBKR Portfolio snapshot."""

    __tablename__ = "portfolio_snapshot_cache"

    key = Column(String, primary_key=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=True)
