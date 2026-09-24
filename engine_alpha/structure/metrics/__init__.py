"""Shared pivots, indicators, and measurements of an already-detected base."""

from importlib import import_module

__all__ = ['measure_bar_compression', 'measure_contractions', 'measure_support_slope', 'measure_touch_volume', 'measure_equilibrium', 'measure_dwell_balance', 'measure_gate_margins']


def __getattr__(name):
    if name in __all__:
        return getattr(import_module(".base", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
