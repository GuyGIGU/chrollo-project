"""The numbers the new reader's copied pieces read — its OWN, not the old engine's shared settings.

Task 7 of the two-eyes-reader build. The pieces copied from the old engine read these values from
`config.settings` at call time. The copies may not: those keys are SHARED with the frozen originals, so tuning
one for the new reader would silently move the old engine too, and a guard that freezes the old engine's FILES
cannot see a settings value change. So each number is copied here, once, with the value it held at the freeze
base (cd87fcc) and the words that placed it, and the copies read `two_eyes_numbers.NAME` where the originals read
`settings.NAME` — the one change a copy makes.

The names are kept as they were, so an original and its copy can be read side by side. Changing a number here
is a change to the new reader's reading, and the version stamp moves with it: `engine_alpha/freeze/manifest.py`
hashes every number in this module. A change to the copies' CODE still needs a `TWO_EYES_RULESET` bump: the
stamp hashes numbers, not reader code.

It sits OUTSIDE `engine_alpha/two_eyes/` and imports nothing, for the reason `two_eyes_roles.py` does: the version
stamp reads it on every night of the old reader's scan, and a module inside the package runs the package's door,
which loads every stage. A broken stage would then stop the old reader's night with the switch off (it lived at
`engine_alpha/two_eyes/method_numbers.py` until the council review of Fri 09/10/2026, finding 1). Keep it
import-free. The readers still call it `M`.
"""

#: Placed by the sweep on his 186 turns (his Q1 asked for a search): a turn commits when price backs off the
#: running extreme by this many of the bar's own daily range.
TURN_LINE_FLOOR_ATR = 0.75

#: The ruled rail area, in daily ranges ("rail area is about half a daily range").
LINE_WORD_AREA_ATR = 0.5

# THE UNIT OF THE WORDS (build task 12b, Fri 02/10/2026; ours): the story measures every word of a box in that
# box's OWN daily range, the range of the day its second line was anchored: the same range its two rail areas
# are measured in, frozen for the box's whole life, so a word never changes because today's bars were wide. The
# three numbers below were first placed in another range (the one six bars back from the read day) and are
# re-derived here from his own marked bars in the box's range (tests/engine/test_two_eyes_story.py holds each to
# them). The rail area above is HIS number and did not move.

#: An upthrust climbs this far over R: between the breach he crossed out (his UNF, Fri 05/06/2026: 1.21 of the
#: box's ranges) and the smallest he named (his VIK, Thu 14/05/2026: 1.31). The band is 0.09 wide in this range:
#: a knife edge on both sides, said so in the decisions record. Not re-placed.
LINE_WORD_UPTHRUST_MIN_POKE_ATR = 1.25

#: A push covers at least this much ground, launch low to top. His smallest drawn SOS covers 1.33 of the box's
#: ranges (SGHT, Mon 21/09 to Tue 22/09/2026); the floor sits 0.20 on his side of it (1.70 as first placed).
LINE_WORD_SOS_MIN_GROUND_ATR = 1.13

#: A pause this deep ends a push (and a last supper digs at least this far). His shallowest drawn last supper digs
#: 1.52 of the box's ranges (SILC), and the pause before his PBT push of Tue 05/05/2026 is 1.24: the number sits
#: 0.21 under that pause, so his push is read as he drew it, and 0.49 on his side of his shallowest supper (1.5 as
#: first placed).
LINE_WORD_SUPPER_DIG_ATR = 1.03

#: A last supper is NAMED only when it digs this far: "a noticeable deep correction" (his word, Sat 03/10/2026).
#: His shallowest drawn last supper (SILC, 1.52 of the box's ranges) less the 0.2 margin the floors keep; the
#: push-ending floor above stays where his PBT push needs it.
LINE_WORD_SUPPER_NAMED_DIG_ATR = 1.32

#: His longest last supper, in trading days.
LINE_WORD_SUPPER_MAX_DAYS = 4

# R15's breakout margin (BOX_END_BREAKOUT_ATR, 0.10 ranges over R by the close) left with the copied box-end
# reader at task 11: the new reader's box ends by swings alone, and reads no close anywhere.

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

#: A pair the bars KNEW before it opened: in this many trading days before its opening, at least
#: KNOWN_RAILS_MIN_BARS highs at its resistance and as many lows at its support, each within this share of the
#: pair's daily range. His HCA (Sat 24/10/2026): "an earlier pair that provides a tighter box leading to more
#: context overall". The three numbers are OURS, measured on his 48 drawings + 12 fixes: every window from 25 to 80
#: days, every share from 0.2 to 0.33 and two or three bars read the same board (HCA and ACCO his, nothing lost).
KNOWN_RAILS_DAYS = 30
KNOWN_RAILS_AREA_RANGES = 0.25
KNOWN_RAILS_MIN_BARS = 2

#: A mini must be strictly smaller than this share of its parent's R-S price height (operator, 2026-10-21).
MINI_MAX_PARENT_HEIGHT_RATIO = 0.8

# --- Stage 6 (task 12a): the numbers the LPS and its trigger read --------------------------------------

#: A pullback is read on at most this many bars, its top day and its receding days: "2 - 5 bars" (Tue
#: 08/09/2026). Of a longer run of receding days only the last five are read, from their highest high.
LPS_MAX_BARS = 5

#: The unit the LPS is measured in: the daily range as it stood this many trading days before the pullback's
#: last day, so the pullback's own days never move their own yardstick. It is the unit his 1.35 and the 2.5
#: below were placed in (the old engine's sample day): in it his six lows over resistance read what they read
#: when he ruled (ST 1.30) and his deepest pullback 2.43. OURS.
LPS_UNIT_DAYS_BACK = 5

#: His ceiling: the LPS's low sits at most this many daily ranges over resistance. "Lets go with that ceiling
#: 1.35 I guess...." (Thu 10/09/2026); his farthest, ST, sits 1.30 over.
LPS_CEILING_RANGES = 1.35

#: A fall deeper than this from the top of its swing is a slice of a bigger swing down, not a pullback (his AEF
#: words, Mon 14/09/2026; "the correction is getting to deep", Tue 08/09/2026). The sentence is his; the number
#: is OURS, the daily-range yardstick he ruled that day placed over his deepest drawn pullback: 2.5 over the
#: sealed drawings' 2.43, then 2.75 over his STGW (Fri 23/10/2026: the rest of 19 to 21/10 on the box's top, 2.62
#: under the spike of 13/10, drawn as his LPS; "Yes, raise the LPS depth ceiling to 2.75 daily ranges").
LPS_DEPTH_MAX_RANGES = 2.75

#: More than this share of the pullback's high-to-low travel under the support area refuses it: "most of the
#: move is above it and only small parts of it poke out down" (his JAZZ answer, Sun 13/09/2026).
LPS_UNDER_SUPPORT_SHARE = 0.5

# THE GRADE (build task 14, Fri 09/10/2026; the decisions rows of that day). The grade is 100 when no day of the
# base is empty his way and falls in a straight line to 0 at this share: one half, his "mostly dead space" (FRPH,
# Mon 05/10/2026). The end is his word; the straight line and the cuts below are the plan's, his to approve.
GRADE_EMPTY_ZERO = 0.5

#: The letters' cuts on the grade's 0 to 100: S from 75, A from 50, B from 25, C under (the plan's task 14).
GRADE_S = 75.0
GRADE_A = 50.0
GRADE_B = 25.0

# --- The walk's switches (Wed 28/10/2026): his candidate rules, each a named switch -------------------------
# His word that day: "we've got to write the engine in a certain way that will allow us to easily tune it in the
# right direction". Each switch names ONE reading of the walk that was tried as a monkeypatch and is NOT ruled on;
# all of them default to the rule as built, so the as-built path reads exactly as before. A reading is measured as
# one switch off plus one run of `tools.calibration.fires_board` on his live drawings. Flipping one for good is a
# ruling (decisions.md) and moves the version stamp like any number here. The walk reads them at call time.

#: Sentence 3's pair: an end may pair with the other end of its OWN bar (the climax bar's own high and low as the
#: climax and its reaction). Off: never (his AMTB, Wed 28/10/2026; measured 40 -> 39 on his 47, TWLO lost).
ONE_BAR_PAIR = True

#: A bar that gapped clear of the bar before (its low over that bar's high): its own low may be the reaction, as
#: a wide end and as the running low under its top. Off: its low is where the rise landed, not the reaction, so a
#: later low is (his EHC and ANF, Sat 24/10/2026; the GU2 reading, rise only: the mirror cost his EGBN).
GAP_BAR_LOW_IS_REACTION = True

#: The other end of one wide bar is listed as a swing's end (sentence 3, his "correct" of Thu 01/10/2026). Off:
#: no wide ends at all (the W reading of Sat 24/10/2026, for scale).
WIDE_ENDS = True

#: A pair whose first anchor is a trend end's CLIMAX bar may take its second anchor from that same bar: the one
#: bar is the climax and the reaction of that box's root swing. His words (Wed 28/10/2026): "a climax and its
#: reaction are never on one bar as in a true climax's end and its reaction, but when choosing a box, a single bar
#: can represent the climax and the reaction for that box's root swing". Off: never on the climax bar (one-bar
#: pairs elsewhere stay; measured on his 47: the board unchanged, his AMTB's one-bar box gone).
CLIMAX_BAR_OWN_REACTION = True
