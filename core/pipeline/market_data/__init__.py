"""Market-data acquisition; provider selection is the public boundary."""

from importlib import import_module

__all__ = ['MarketDataProvider', 'available_providers', 'get_provider']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".providers", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
