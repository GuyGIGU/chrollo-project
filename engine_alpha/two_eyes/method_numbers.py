"""The numbers the new reader's copied pieces read — its OWN, not the old engine's shared settings.

Task 7 of the two-eyes-reader build. The pieces copied from the old engine read these values from
`config.settings` at call time. The copies may not: those keys are SHARED with the frozen originals, so tuning
one for the new reader would silently move the old engine too, and a guard that freezes the old engine's FILES
cannot see a settings value change. So each number is copied here, once, with the value it held at the freeze
base (cd87fcc) and the words that placed it, and the copies read `method_numbers.NAME` where the originals read
`settings.NAME` — the one change a copy makes.

The names are kept as they were, so an original and its copy can be read side by side. Changing a number here
is a change to the new reader's reading, and the version stamp moves with it: `engine_alpha/freeze/manifest.py`
hashes every number in this module. A change to the copies' CODE still needs a `TWO_EYES_RULESET` bump: the
stamp hashes numbers, not reader code.
"""

#: Placed by the sweep on his 186 turns (his Q1 asked for a search): a turn commits when price backs off the
#: running extreme by this many of the bar's own daily range.
TURN_LINE_FLOOR_ATR = 0.75

#: The ruled rail area, in daily ranges ("rail area is about half a daily range").
LINE_WORD_AREA_ATR = 0.5

#: An upthrust climbs this far over R: between the breach he crossed out (his UNF, 0.94) and his smallest (his
#: VIK note, 1.55).
LINE_WORD_UPTHRUST_MIN_POKE_ATR = 1.25

#: His smallest SOS, launch low to top, on his own spans.
LINE_WORD_SOS_MIN_GROUND_ATR = 1.70

#: A last supper digs this far (his ten: 1.75 to 3.76); a pause this deep ends a thrust.
LINE_WORD_SUPPER_DIG_ATR = 1.5

#: His longest last supper, in trading days.
LINE_WORD_SUPPER_MAX_DAYS = 4

#: R15: the breakout day closes this far over R, in daily ranges (his placed margin).
BOX_END_BREAKOUT_ATR = 0.10

# --- Stage 1 (task 8): the numbers the frame preparation and the line read -------------------------

#: The daily range is the true range smoothed by Wilder's rule over this many trading days: the old
#: engine's ATR_10, the unit every number above is placed in (a literal 10 in the old engine, never a
#: setting). It is built on the LONG frame, before the cut to the reading window.
DAILY_RANGE_DAYS = 10

#: What the reader sees: the trailing window the old engine has always read (its DAILY_STRUCTURE_PERIOD),
#: so the yardstick compares like with like. Only the frame is cut; the daily range is not recomputed
#: inside it.
READ_WINDOW = "2y"

# --- Stages 2 and 3 (task 10): the numbers the end of the trend, the walk and the election read ---------

#: The far view's floor, in daily ranges: how far back the reader stands to see the trends. Placed at the
#: listing gate (task 9, Sat 26/09/2026) as the one distance at which the trend into his box is seen at all;
#: OURS and provisional, his sitting settles it.
FAR_VIEW_FLOOR_RANGES = 1.5

#: A pair of lines is a box no sooner than its fifteenth trading day from the first anchor: "Lets go with 15
#: days" (Sat 12/09/2026).
BOX_DAYS = 15

#: A pair shorter than this many of its own daily ranges is listed by the walk but is never a box: bars cannot
#: zigzag inside it (his "huge spread" is huge against the box itself, "answer a.", Sun 20/09/2026). The
#: number is OURS, the listing gate's bound (task 9).
BOX_MIN_HEIGHT_RANGES = 1.0
