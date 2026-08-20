# The final pre-breakout structure in the canon — volume-free geometric definitions

**Purpose:** ground Event Map Task 8 (the second, holding-shelf LPS completion form) in the
published methodology instead of ad-hoc fitting. Deep-research run 2026-07-10 (19 sources
fetched, 89 claims extracted, 25 adversarially verified by 3-vote panels: 19 confirmed /
6 refuted / 0 unverified). Volume-based criteria were excluded by scope (operator doctrine:
volume is unreliable). Companion to `docs/archive/specs/event-map-causality-contract.md` and
`docs/archive/PLAN-event-tape.md` Task 8.

---

## Verdict

**The two-form LPS thesis is doctrine, not invention.** Three of the four schools explicitly
sanction BOTH final shapes — a pullback that digs and rests, and a flat shelf that holds:

| School | Sanction | Vote |
|---|---|---|
| Wyckoff (StockCharts tutorial + wyckoffanalytics.com, identical sentence) | The back-up "can take on a variety of forms, including **a simple pullback or a new TR at a higher level**"; "there may be more than one LPS" | 3-0 ×2 |
| Qullamaggie (primary source) | Consolidation = "an orderly pullback and consolidation with **higher lows and tightening range**"; valid shapes: "pretty much **flat channels**, symmetrical and **descending triangles**"; duration "usually 2 weeks to 2 months"; **no volume criterion** in the consolidation definition | 3-0 ×3 |
| O'Neil lineage | The flat shelf is valid **as a different named completion**: the cup-WITHOUT-handle (pivot = 10¢ above the left-side high) and Kuhn's "cup-completion cheat" (a flat days-to-weeks pause holding under the left-side overhead) | 3-0, 3-0, 2-1 |
| Wyckoff SMI glossary | The canonical LPS itself is the pullback-that-rests: "the up move constituting the (SOS) and the REACTION FOLLOWING it, the (LPS)"; the back-up "comes to rest (find support) above the creek" | 2-1 ×2 |

**The one doctrinal tension — and its resolution:** strict O'Neil cup-WITH-handle doctrine
demands the handle drift DOWN along its lows ("the handle should drift lower along its lows…
a shakeout") and calls flat-or-rising-lows handles failure-prone. But the same school validates
the flat pause as a *separate* completion that holds **high in the structure** (cup-without-handle,
the cheat pause under overhead). Net design rule: **a flat shelf is a legitimate final only with a
position condition** — resting at/above the worked support, high in the base — never as a slack
mid-base drift.

## Verified quantitative envelope (volume-free)

| Threshold | Canon value | Source / vote |
|---|---|---|
| Final-structure duration | **≥ 5 trading days hard floor** ("if it's shorter than five days, it's not a handle"); generally > 1–2 weeks; ideally complete in 1–4 weeks; Qullamaggie: 2 wk – 2 mo | IBD + StockCharts, 3-0 ×2 |
| Position in the base | Handle **midpoint > base midpoint** (explicit computable test: midpoint = (structure high + structure low) / 2, same formula both levels); handle above the 50-day/10-week MA | IBD, 3-0 ×2 |
| Wyckoff position | The back-up must come to **rest ABOVE the just-broken resistance ("creek")**; falling back below = failure. Refinement: completes between the range's halfway point and the creek top | SMI, 2-1 |
| Overshoot above the left-side high | Valid finals may perch **up to ~7–8 % above** the prior high (Kuhn "high handle": TNCR +3.5 %, COMS +8.6 %, both sound bases) | Kuhn TASC 1995, 3-0 |
| Invalidation level | The final structure's low = **the last higher low**; a decline below it negates the setup ("use the handle low for your risk point") | Kuhn, 3-0 |
| Cup depth (context) | Normal left-side depth **12–33 %** (Ask Jeeves's 49 % named as a flaw) | IBD, 3-0 |

## Named failure geometries (all 3-0)

1. **Upward-wedging final** — lows drifting HIGHER instead of down: "Avoid bases that carry an
   upward-wedging handle; this is a flaw." O'Neil extends it: handles that "go straight sideways
   along their lows… have a much higher probability of failing" *(in the cup-with-handle context)*.
2. **Final in the lower half of the base** (midpoint test) — the Ask Jeeves case study (breakout
   week 1999-10-22, −38 % in four months).
3. **V-shaped recovery** into the final — "avoid those because they're more prone to failure."
4. **Too-deep left side** (49 % vs the normal 12–33 %).

## Refuted (do NOT cite)

- "Handle retraces at most ~1/3 of the cup's advance" — **0-3**. There is **no verified
  depth ceiling** for the final structure in this evidence set.
- "The LPS is purely the terminal low of the pullback" / "the LPS lands exactly on former
  resistance" — both 0-3 as *stated*; the confirmed forms are broader.
- **THE MINERVINI GAP:** no Minervini-primary claim survived verification. The famous VCP
  numbers (each contraction ≈ half the prior; final contraction < ~10 %; 2–4 contractions, nT
  notation) are **ungrounded here** — they circulate only through secondary blogs. His two books
  are the primary source and were not verifiable online. Closest surviving proxies: Qullamaggie
  (his stated lineage) and the O'Neil handle rules.

## Mapping onto the engine's knobs

| Canon | Engine today | Task-8 implication |
|---|---|---|
| Two sanctioned forms | ONE form (`_pullback_rest_low_verdict` + depth floor) | The shelf form is doctrine-backed; build it |
| Wedging/rising-lows failure | Already encoded: `rising_march` classification + markup gate `LPS_RESCUE_MAX_ADVANCE_BOX = 0.21` | Keep as the shelf's hard guard — canon-aligned; the OHI hole stays closed |
| Position condition for flat finals | `zone_type` machinery (support zone / above-R) exists | The shelf predicate should require rest at/above the worked S (or above broken R for above-R shelves) — not accepted anywhere in the box |
| Overshoot envelope ~7–8 % above prior high | `LPS_INSIDE_HIGH_EXTENSION_BOX_MAX 0.35` / `_ATR_MAX 0.75` | Comparable intent; canon gives a %-of-price cross-check for above-R / high shelves |
| Invalidation = final low breach | `LPS_HOLD_TOLERANCE = 0.95` | Same concept (5 % crash budget below the LPS low) |
| Duration ≥ 5 days (whole final structure) | `LPS_LENGTH_MIN 2 / MAX 7` (the *window*, i.e. the tail rest) | **Mapping caveat:** the engine's window is the final REST, not the whole handle — the operator's marked shelves run 3–5 sessions (WTS 3, PBT 4, DRTS 4–5), under IBD's 5-day handle floor precisely because the window is the tail. Do not blind-import the floor onto the window; if anything the *structure containing* the shelf should satisfy it |
| No verified depth ceiling | `LPS_PULLBACK_PROFILE_MAX = 4.50` | Stays engine-calibrated (unchallenged by canon) |
| Depth floor 1.25 overshoot-R | — (no canon equivalent; the refuted 1/3 rule was the closest) | The floor is the engine's own; the shelf form exists precisely because gentle finals are canon-valid |

## Open questions (operator can close several)

1. **Minervini's primary-text numbers** — the books (Trade Like a Stock Market Wizard; Think &
   Trade Like a Champion) are on the operator's shelf; the final-contraction depth/tightness and
   shakeout-allowance passages would close the headline gap.
2. **Undercut/shakeout budget** — how deep below the shelf/handle low may price poke and reclaim
   before invalidation (spring vs failure)? No quantitative source survived.
3. **The shelf position gate** — inferred from the reconciliation above, not stated verbatim
   anywhere; operator's marked examples are the calibration set.
4. More operator-marked **shelf-style LPS examples** → a frozen Part-3 corpus for Task 8.

## Sources (verified-claim carriers)

wyckoffsmi.com glossary (primary) · stockcharts.com Wyckoff tutorial + cup-with-handle
(secondary, canonical) · wyckoffanalytics.com (secondary) · qullamaggie.com setups page
(primary) · IBD/Yahoo-syndicated handle-flaw articles ×3 (primary/secondary) · Kuhn,
"Trading With The Cup-With-Handle," TASC V13 1995 (PDF, secondary) · nasdaq.com IBD
cup-without-handle (primary). Minervini-angle sources (finermarketpoints, traderlion, an
X post) contributed claims that FAILED verification and are cited nowhere above.
