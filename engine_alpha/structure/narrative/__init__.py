"""The chronological reader and its injectable detector bricks."""

from importlib import import_module

__all__ = ['Structure', 'read_structure']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".reader", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
