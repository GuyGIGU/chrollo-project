"""The reader's own settings: its ruleset stamp, its reading window and the ADR window.

Edit defaults here; runtime consumers use config.settings so scoped overrides
and existing monkeypatches continue to share one settings namespace.
"""

# The reader's ruleset version, BUMPED BY HAND with every change to how it reads: the version stamp hashes
# settings and numbers but no reader code. A string once used is SPENT (SPENT_RULESETS in
# tests/engine/test_two_eyes_adapter.py; docs/flag_ledger.md, "The engine stamps of the flip").
TWO_EYES_RULESET = "two-eyes-0.12.0-one-reader"

DAILY_STRUCTURE_PERIOD = "2y"    # the trailing window the daily chart is read on; part of the frozen engine contract
ADR_WINDOW = 20                  # bars used for the Average Daily Range %
