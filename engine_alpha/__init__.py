"""Engine Alpha — Chrollo's chart-reading engine as a standalone package.

The pure frame->reading chain: structure (geometry, measure-only), scoring
(the tunable opinion layer), and — as the extraction proceeds — the frozen
settings manifest (engine identity) and the per-frame evaluation chain.
Other components (pipeline, webapp, tools, tests) SUMMON the engine through
this package; the engine imports nothing back from them. Its only sanctioned
outward reads are ``config.settings`` (the mutable-singleton override seam)
and the documented flag-gated advisory seam in the eval chain.
"""
