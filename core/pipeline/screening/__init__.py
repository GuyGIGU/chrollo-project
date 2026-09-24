"""Scan orchestration; imports stay lazy so data-only consumers do not load the reader."""

from importlib import import_module

__all__ = ['run_screener']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".screener", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
