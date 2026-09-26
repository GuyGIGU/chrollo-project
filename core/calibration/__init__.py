"""Replaying the operator's calibration marks against the engine.

Production code the calibration workbench and the calibration tools share, so
the backend's chips and ``python -m tools.calibration.*`` can never measure
the same mark two ways:

    replay     -> point-in-time frame prep, the day-snapped election, the
                  fired-window policy, flag capture, the sealed-corpus fixture
    agreement  -> the pure per-mark agreement grade and its closed outcome set
"""
