"""
THE MEASURING STICK — record outcomes and learn from them.

This package is NOT part of the live screen. It captures every setup the
engine finds, fills in what actually happened afterward (forward returns,
MFE/MAE, whether it triggered), and provides tools to study which setups won.

Modules (run most as ``python -m core.archive.<name>``):
    writer          -> persist a scan's results into the setup_archive table
    seed            -> bootstrap the archive with cherry-picked historical setups
    forward_returns -> backfill outcomes once setups are old enough
    analyze         -> read-only analysis: winner fingerprint, predictor correlations
    purge           -> drop uncurated rows, keeping the archive a clean regression suite
"""
