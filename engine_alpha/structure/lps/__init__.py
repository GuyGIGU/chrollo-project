"""Last-point-of-support detection and completion geometry."""

from importlib import import_module

__all__ = ['detect_lps', 'detect_lps_candidates', 'detect_lps_tests', 'lps_range_threshold', 'select_active_lps_candidate']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".detection", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
