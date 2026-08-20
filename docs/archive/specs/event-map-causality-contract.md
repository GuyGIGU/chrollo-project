# Event Map — the causality contract

**Status:** binding implementation contract for every Event Map task (PLAN-event-tape.md Task 2).
Merges into `docs/strategy_alpha.md` (Reading Model) in the same change that ships the first tape
behavior — until then, this file is the contract the code is built and reviewed against.

**Why this exists:** the swing skeleton is confirmation-lagged and repainting by construction — a
pivot of order *k* needs *k* later bars to exist; the last zigzag leg moves as new bars print; the
amplitude collapse can retroactively merge a swing away; the R-rail wave typer reclassifies a whole
wave by its terminal outcome (an in-progress climb becomes an upthrust days later). A role label
that ignores this replays better than it screens: the backtest shows narratives the nightly scan
could never have seen on that date, and every corpus grade and calibration read built on it is a
lookahead artifact. This contract is what makes "left-to-right" mean *causal*, not merely loop order.

---

## 1. Every label carries two bar stamps

Every swing/event label the Event Map emits records:

- **`describes_bar`** — the bar (or span) the label is about;
- **`knowable_bar`** — the first bar at whose close the label could have been assigned by a reader
  who has seen nothing after that bar.

The knowable stamp is derived from the label's real confirmation mechanics — pivot order, hold
windows, reclaim requirements — never assumed equal to `describes_bar`. Examples: an order-*k*
pivot's `knowable_bar` is at least *k* bars after its extreme; a "shelf held" verdict's
`knowable_bar` is the last bar of its hold-evidence window; a wave's terminal-outcome type is
knowable only when the outcome bar has printed.

**The as-of rule:** the label set "as of date D" is exactly the labels with `knowable_bar ≤ D`.
No consumer — detector, scorer, archive writer, overlay payload — may read a label whose
`knowable_bar` lies after the evaluation date. This is the single invariant Beck's
truncate-and-relabel tests (plan Task 5) assert.

## 2. Future-dependent states are tri-valued, never binary

Any state whose definition needs bars that may not have printed yet resolves to one of
**`held` / `failed` / `in_progress`** — the discipline the rail readers already enforce
(resistance waves and support tests resolve exactly this way). Applies at minimum to: the
holding-shelf LPS hold, the back-up region past the right rail, wave terminal outcomes, and the
Last Supper (by definition "the final run-up before the real pullback" — unknowable until the
pullback prints; before that it is `in_progress`, at most "run-up, outcome pending").

- A hold-evidence window that runs past the last printed bar is **unconfirmed, full stop** — it is
  `in_progress`, and `in_progress` never satisfies a completion predicate.
- The archive records the resolution value itself. A later maturation from `in_progress` to `held`
  is a **new observation** (a later row / a maturation tick), never a rewrite of the archived row.
- At the right edge — exactly where the live scan operates — `in_progress` is the expected, honest
  answer, not an error.

## 3. One frame contract

The Event Map is a **pure function of the bar frame ending at the evaluation date, under the exact
live trim**. Concretely:

- The live pipeline trims to `DAILY_STRUCTURE_PERIOD` (two years) before reading structure
  (`_prepare_eval_frame`); every replay, harness, and tool computes tape labels on **the identical
  trim**. The Part-2 audit-tool parity defect (5y frame vs the live 2y) is the standing cautionary
  case — frame choice silently moves every pivot, box position, and label.
- **Frame-end equals evaluation date.** The existing LPS detector's "still holding" checks read to
  the frame's last bar and are correct *only because* of this invariant. It is now written down:
  any code path that evaluates "as of D" hands the reader a frame whose last bar is D.
- **Left-edge rule:** a swing near the trim boundary whose confirmation depends on trimmed-away
  bars is treated as *not knowable inside this frame* — it gets no role label (it may still exist
  mechanically). Rationale: the alternative (peeking left of the trim) makes the label depend on
  which frame length a caller happened to load, breaking purity. The mechanical layer may mark such
  swings `edge_uncertain` so downstream readers know the silence is a boundary effect.

## 4. Determinism conventions (replay ≡ live, cross-platform)

- **Election across LPS forms:** precedence between the two completion forms (pullback-and-rest vs
  holding shelf) settles on **integer and categorical keys only**; float quality scores compare only
  *within* a single form. Cross-form float ties are apples-to-oranges and epsilon-fragile.
- **Interval conventions:** the LPS detector scans end-exclusive windows; the box-event zones are
  end-inclusive (the seam the code already guards with an assertion). Every new tape component
  states which convention it uses at its seam and converts explicitly — never implicitly.
- **Compare on emitted values:** the staircase deliberately tie-breaks on its emitted four-decimal
  rounded box positions; new tape components comparing against staircase output compare on those
  same emitted values, never recomputed raw floats. No new derived float is compared with `==`.
- The tape introduces **no clock, no randomness, no ordering dependence on dict/set iteration** —
  identical frame in, identical labels out, on every platform and every run.

## 5. NaN policy

Highs, lows, and volumes are coerced to float **once at tape entry** (the existing readers'
pattern). Every gate is written so a NaN can never pass it: each reject-if-greater comparison
decides explicitly whether a NaN window is *rejected* or reported *unreadable* — silence is not an
option. New archived cells follow EC-2 (NaN-scrub at the pandas boundary; NULL means "not
measured", never zero).

## 6. Vocabulary note (operator ruling, 2026-07-10)

Trend-structure terms are **plain price action**: a trend *ends* when a low takes out the last
higher-low (mirror for downtrends); a new trend *starts* at the opposite break. The abbreviations
BOS/CHoCH may survive as internal shorthand only — they import no Smart-Money-Concepts semantics,
and user-facing wording (UI, docs, the Reading Model) says it plainly.

## 7. Enforcement

- **Truncation invariance (plan Task 5):** label a frame, truncate at a cut date, relabel — every
  label with `knowable_bar ≤ cut` is identical. Run across corpus frames with cuts stepping through
  each setup's LPS window and trigger.
- **Legal-order assertion:** emitted role labels appear in chronologically legal narrative order and
  reference only earlier swings.
- **The marks-corpus ratchet** (`tools/marks_corpus.py`) grades acceptance on point-in-time replays
  that inherit this contract via the shared eval chain.
- Violations are correctness defects (McKinney lane), not style findings.
