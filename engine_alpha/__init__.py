"""Engine Alpha — Chrollo's chart-reading engine as a standalone package.

The pure frame->reading chain: the alpha reader (``two_eyes``, measure and judgment in one
record), its adapter to the scan's result shape, the one door (``reader``), the universe
door, the shared metrics and the frozen settings manifest (engine identity).
Other components (pipeline, webapp, tools, tests) SUMMON the engine through
this package; the engine imports nothing back from them. Its only sanctioned
outward reads are ``config.settings`` (the mutable-singleton override seam)
and the documented flag-gated advisory seam in the eval chain.
"""
