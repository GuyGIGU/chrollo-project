"""Engine freeze layer — reproducible, hashable identity of the engine config.

The screener's computed output is a pure function of (market data, engine
constants, detector code). This package captures the *constants* half: a
canonical, hashable manifest of every engine-relevant value in
``config.settings``, so any archived signal can be stamped with the exact
config version that produced it. Pure read-only; no engine math lives here.
"""
