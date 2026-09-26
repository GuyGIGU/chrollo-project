"""Universe descriptors, symbol selection, and ticker admission."""

from importlib import import_module

__all__ = ['Universe', 'DEFAULT_UNIVERSE_KEY', 'DEFAULT_UNIVERSE_TYPE', 'all_universes', 'default_universe', 'default_universe_type', 'resolve_universe', 'universe_keys', 'drilldown_map']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".descriptor", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
