"""Compatibility model registry; declarations live beside their owning domains."""
from database import Base
from domains.trading.models import TradeLog, Execution, Tag, TradeTag, TradePlan, TradeNote, TradeAttachment
from domains.watchlist.models import Watchlist
from domains.archive.review_models import SetupReview, ReadVerdict
from domains.calibration.models import CalibrationMark, CalibrationMarkEvent
from domains.portfolio.models import PortfolioSnapshotCache
