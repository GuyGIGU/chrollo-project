"""Every number the alpha reader reads, one plain line each with the words that placed it.

The stages read these as ``M.NAME``, never a setting: the stamp (``engine_alpha/stamp.py``) hashes every upper-case
name here, so a changed number moves the night's ``engine_config_version``. A change to HOW the reader reads bumps
``ALPHA_RULESET`` in ``config/reader.py`` instead. Import-free: the stamp reads it on every night's scan.
"""

#: A turn commits when price backs off the running extreme by this many daily ranges: the sweep on his 186 turns (his
#: Q1).
TURN_LINE_FLOOR_ATR = 0.75

#: The ruled rail area, in daily ranges ("rail area is about half a daily range").
LINE_WORD_AREA_ATR = 0.5

# --- The words' numbers, each in the box's OWN daily range, frozen for its life (Fri 02/10/2026) -------------------

#: An upthrust climbs this far over R: between his UNF breach crossed out (Fri 05/06/2026: 1.21) and his smallest
#: named, VIK (Thu 14/05/2026: 1.31).
LINE_WORD_UPTHRUST_MIN_POKE_ATR = 1.25

#: A push covers at least this much ground, launch low to top: his smallest drawn SOS covers 1.33 (SGHT, Mon 21/09 to
#: Tue 22/09/2026), the floor 0.20 on his side.
LINE_WORD_SOS_MIN_GROUND_ATR = 1.13

#: A pause this deep ends a push: 0.21 under the pause before his PBT push of Tue 05/05/2026 (1.24), 0.49 under his
#: shallowest last supper (SILC, 1.52).
LINE_WORD_SUPPER_DIG_ATR = 1.03

#: A last supper is NAMED only when it digs this far: "a noticeable deep correction" (Sat 03/10/2026); his shallowest
#: (SILC, 1.52) less the 0.2 margin.
LINE_WORD_SUPPER_NAMED_DIG_ATR = 1.32

#: His longest last supper, in trading days.
LINE_WORD_SUPPER_MAX_DAYS = 4

# --- Stage 1: the numbers the frame preparation and the line read ---------------------------------------------------

#: The daily range: the true range smoothed by Wilder's rule over this many trading days (ATR_10, the unit every
#: number here is placed in), built on the LONG frame.
DAILY_RANGE_DAYS = 10

#: The trailing window the reader sees; only the frame is cut, the daily range is not recomputed inside it.
READ_WINDOW = "2y"

# --- Stages 2 to 4: the numbers the end of the trend, the walk and the election read --------------------------------

#: The far view's floor, in daily ranges: how far back the reader stands to see the trends. OURS, placed at the
#: listing gate (Sat 26/09/2026), provisional.
FAR_VIEW_FLOOR_RANGES = 1.5

#: A pair of lines is a box no sooner than its fifteenth trading day from the first anchor: "Lets go with 15 days"
#: (Sat 12/09/2026).
BOX_DAYS = 15

#: A pair shorter than this many of its own daily ranges is never a box: his "huge spread" is huge against the box
#: itself ("answer a.", Sun 20/09/2026); the number is OURS.
BOX_MIN_HEIGHT_RANGES = 1.0

#: A pair the bars KNEW before it opened (his HCA, Sat 24/10/2026: "an earlier pair that provides a tighter box
#: leading to more context overall"): the days before its opening that are read ...
KNOWN_RAILS_DAYS = 30
#: ... the share of the pair's daily range a high or low sits within to count at a rail ...
KNOWN_RAILS_AREA_RANGES = 0.25
#: ... and how many highs at its resistance and as many lows at its support. OURS, measured on his 48 drawings + 12
#: fixes: windows 25 to 80, shares 0.2 to 0.33, two or three bars read the same board.
KNOWN_RAILS_MIN_BARS = 2

#: A mini must be strictly smaller than this share of its parent's R-S price height (operator, 2026-10-21).
MINI_MAX_PARENT_HEIGHT_RATIO = 0.8

# --- Stage 6: the numbers the LPS and its trigger read --------------------------------------------------------------

#: A pullback is read on at most this many bars: "2 - 5 bars" (Tue 08/09/2026); of a longer run only the last five,
#: from their highest high.
LPS_MAX_BARS = 5

#: The LPS's unit: the daily range this many trading days before the pullback's last day, the unit his 1.35 and the
#: 2.5 were placed in (ST reads 1.30, his deepest pullback 2.43). OURS.
LPS_UNIT_DAYS_BACK = 5

#: His ceiling: the LPS's low sits at most this many daily ranges over resistance. "Lets go with that ceiling 1.35 I
#: guess...." (Thu 10/09/2026); his farthest, ST, sits 1.30 over.
LPS_CEILING_RANGES = 1.35

#: Deeper than this from its swing's top is a slice of a bigger swing down ("the correction is getting to deep", Tue
#: 08/09/2026; his AEF words, Mon 14/09/2026): 2.5 over his 2.43, then his STGW: "Yes, raise the LPS depth ceiling to
#: 2.75 daily ranges" (Fri 23/10/2026).
LPS_DEPTH_MAX_RANGES = 2.75

#: More than this share of the pullback's high-to-low travel under the support area refuses it: "most of the move is
#: above it and only small parts of it poke out down" (JAZZ, Sun 13/09/2026).
LPS_UNDER_SUPPORT_SHARE = 0.5

# --- The grade (Fri 09/10/2026) -------------------------------------------------------------------------------------
#: The grade is 100 with no empty day and falls in a straight line to 0 at this share of the base: one half, his
#: "mostly dead space" (FRPH, Mon 05/10/2026).
GRADE_EMPTY_ZERO = 0.5

#: The letters' cuts on the grade's 0 to 100: S from 75, A from 50, B from 25, C under (the plan of Fri 09/10/2026).
GRADE_S = 75.0
GRADE_A = 50.0
GRADE_B = 25.0

# --- The traits (Thu 29/10/2026: "I want an actual grading system that pops up the best stock at the top of the
# page"): within the letter, the traits order the setups ---
#: The weights, OURS. TIGHTNESS CARRIES THE SCORE (Thu 29/10/2026, his "wide ass nothing burger stocks all hug the
#: damn S spot"); on his 90 hearts no trait tells his likes from his passes.
TRAIT_WEIGHTS = {"tightness": 60.0, "swings": 5.0, "dead_space": 15.0, "contraction": 5.0, "rails": 10.0,
                 "stage": 5.0}
#: Tightness: the box's height in its own daily ranges, full marks at or under this many ("a box about as tall as its
#: bars is completely fine", Mon 05/10/2026; his boxes run 1.1 to 2.75) ...
TRAIT_TIGHT_FULL_RANGES = 1.25
#: ... and none at or over this many: a wide, nothing-burger box (on the scan of 28/10/2026, 10 of 197 S boxes).
TRAIT_TIGHT_ZERO_RANGES = 3.5
#: Right-side contraction: the last third's mean daily range over the earlier two thirds'; full marks at or under this
#: ratio, none at TRAIT_CONTRACTION_ZERO_RATIO or looser (his 40 run 0.63 to 1.68).
TRAIT_CONTRACTION_FULL_RATIO = 0.7
TRAIT_CONTRACTION_ZERO_RATIO = 1.1
#: The stage, his weekly read (Fri 16/10/2026): stage 2 is the setup's home, stage 1 may be the base before it, a
#: stage-3 or stage-4 base is late or against the tide.
TRAIT_STAGE_FRACTION = {1: 0.5, 2: 1.0, 3: 0.25, 4: 0.0}
#: The letters' bands: the floor each letter builds from and the width it fills; the others stop one point under the
#: next letter's floor.
TRAIT_BANDS = {"S": (75.0, 25.0), "A": (50.0, 24.0), "B": (25.0, 24.0), "C": (0.0, 24.0)}

# --- The walk's switches (Wed 28/10/2026: "we've got to write the engine in a certain way that will allow us to
# easily tune it in the right direction"); all True = the rule as built ---

#: An end may pair with the other end of its OWN bar. Off: never (his AMTB, Wed 28/10/2026; measured 40 -> 39 on his
#: 47, TWLO lost).
ONE_BAR_PAIR = True

#: A bar that gapped clear of the bar before: its own low may be the reaction. Off: a later low is (his EHC and ANF,
#: Sat 24/10/2026).
GAP_BAR_LOW_IS_REACTION = True

#: The other end of one wide bar is listed as a swing's end (his "correct" of Thu 01/10/2026). Off: no wide ends at
#: all.
WIDE_ENDS = True

#: A pair anchored on a trend end's CLIMAX bar may take its second anchor from that same bar: "a single bar can
#: represent the climax and the reaction for that box's root swing" (Wed 28/10/2026). Off: never on the climax bar.
CLIMAX_BAR_OWN_REACTION = True

#: The box must WRAP the bars: a meaningfully tighter pair inside or across it takes its place on the first day the
#: bars have come back to both its rails (his AMTB, Wed 28/10/2026; "we simply must increase the reading accuracy of
#: our Reader to match better with the ranges of the actual price action", Thu 29/10/2026). Off: never.
WRAP_TAKES_OVER = True

# --- The election by respect and the mini's sunset (Fri 30/10/2026: "lets focus on the simple core of the reader for
# now"); both default to the reader as built ---

#: The box is the pair the bars RESPECT most, not the first to become one: his "Close Enough" touches ("plenty of the
#: boxes work because most of the price action was in the area of said rails", Fri 30/10/2026). Off: the chain of
#: hand-overs as built.
RESPECT_ELECTS = False
#: A touch: a bar's end within this many of its OWN daily range of the nearest rail, +1 ("every setup is unique
#: regarding it's bar spread"); wholly beyond a rail by more, -1.
RESPECT_AREA_RANGES = 0.5
#: A pair takes the shown box's place when it leads by this many touches, its own score reaching it too ("the engine
#: misses better more 'Correct' results because it found a more 'lazy' alternative") ...
RESPECT_MARGIN = 3
#: ... over the last this many trading days, one window for every pair.
RESPECT_WINDOW_DAYS = 30

#: The mini stage: a second box inside the parent's right side, the LPS read against it when its low is in, on or near
#: it. OFF since Fri 30/10/2026 on his word ("sun set, mini consolidation detection, i find it to be hard to tune"),
#: measured free: the same 43 fires on his 51, the junk's 47 fire days unchanged.
MINI_ENABLED = False

# --- The grade's trait scales and the stage read
# ----------------------------------------------------------------------

#: Clean swings: the main zigzag's share of the line's travel that earns full marks (the current 48's lower quartile).
CLARITY_SWING_FULL_SHARE = 0.45
#: Rails the turns sit on: the major turns' mean distance from their rail, in box heights, at full marks ...
CLARITY_RAIL_FULL_ERROR = 0.25
#: ... and at none.
CLARITY_RAIL_ZERO_ERROR = 1.0
#: The stage read's average: the 40-week average of the weekly closes (Minervini's 200-day).
STAGE_MA_WEEKS = 40
#: Rising or falling: the average against itself this many weeks earlier.
STAGE_SLOPE_WEEKS = 4
#: An advance week closes at least this far over the 52-week low.
STAGE_OFF_LOW_MIN = 0.30
#: The 52-week low, in weeks.
STAGE_LOW_WEEKS = 52
