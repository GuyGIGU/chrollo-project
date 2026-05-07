"""IBKR integration package (ib_async-based)."""
from .service import IBKRService, get_ibkr_service  # re-export

__all__ = ["IBKRService", "get_ibkr_service"]
