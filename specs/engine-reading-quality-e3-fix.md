# E3 fix — faithful elected-brick puzzle read + flip-time hardening

**Branch:** `engine/l2-event-reader` (off `main`, NOT merged/pushed).
**Nature:** correctness + hardening fixes to the E3 puzzle sub-score found by an
xhigh code review. All findings are **flag-on only** (`PUZZLE_SCORE_ENABLED` /
`CANDLE_SPREAD_AWARE` both default-off) — production is unaffected today; these
matter the moment the operator flips. The flags STAY default-off after this fix.

## The bug (headline — F1 + F2 coupled)

E3 scores the L2 Wyckoff puzzle by calling
`assemble_box_narrative(df, structure.box, atr)` at the score call site
(`_score_eval_context`, evaluation.py:458). That path re-runs `find_spring` and
`find_lps` on the **parent** box inside `_box_events_with_meta` (metrics.py:1076,
1089).

But `read_structure` (narrative.py:336-345) **elects the tighter inner-box LPS
when present** (`lps_in_inner=True`) and parks the winning brick on
`structure.lps`. So on any inner-LPS fire the puzzle:

- describes a **different** LPS than the one the engine fired, and
- if the parent box yields **no** LPS at all (the reason the engine fell through
  to the inner box), emits **no** `lps` piece → `completeness` drops to ≤3/4 and
  `chronology` cannot be `intact`.

**Perverse result:** a tighter, better-structured (inner-box) setup scores
*lower* on the puzzle bonus than a looser parent-box one. The inline comment
claiming the read "reproduces the fired spring/LPS bit-for-bit" is false for
these fires. The existing object-identity test pins the *frame* (`box is
structure.box`) but never asserts an LPS was actually found, so it slips through.

`structure.spring` is already exactly `find_spring(df, box, atr)` on the parent
box, so re-running it is pure waste (F2 efficiency); `structure.lps` is the
winning brick, so reusing it fixes F1 **and** F2 together. The `Structure`
docstring explicitly invites this: consumers may read `spring`/`lps` "without a
second measurement pass."

## The fix (F1 + F2)

Inject the engine's already-elected bricks into the narrative instead of
re-detecting:

1. `_box_events_with_meta(df, box, atr_val, *, v_bar=None, spring=_DETECT,
   lps=_DETECT)` — add a module-level `_DETECT = object()` sentinel. When a param
   `is _DETECT`, run the detector exactly as today (preserves the measure-only
   `read_box_events` path byte-for-byte). When a param is passed (even `None`),
   USE it: `None` means "the engine elected no such piece" (do **not** re-detect
   and fabricate one).
2. `assemble_box_narrative(...)` gains the same `spring=_DETECT, lps=_DETECT`
   pass-through.
3. evaluation.py:458 → `assemble_box_narrative(df, s.box, atr,
   spring=s.spring, lps=s.lps)` where `s = structure_ctx["structure"]`. Update
   the comment: the read now reproduces the fired spring/LPS by **reusing the
   elected bricks** (parent frame for geometry; the LPS is whichever the engine
   elected, inner or parent).

**Bar-translation correctness (the numerical crux — for the council):**
`structure.lps` carries **absolute** df bar indices whether it was elected on the
inner or parent box. `_box_events_with_meta` translates every brick bar by
`- start` (`start = box.start_bar`, the **parent** start) into the parent base
frame and `_clip`s into `[0, base_n-1]`. Since `inner ⊆ parent`,
`lps.start_bar ≥ parent.start_bar` so `lstart ≥ 0`, and the LPS is right-side so
`lstart > v_bar` holds — the existing gate/translation is already correct for an
inner LPS; no rebasing. Spring is parent-box either way. **Confirm this holds.**

## Bundled flip-time hardening (small, independent)

- **F3 — `upthrust_terminal` held-range gap** (metrics.py:1218): a Phase-D
  `range` R-wave (held near R, no tight consolidation) after the last upthrust
  currently does NOT clear the terminal read. Add `"range"` to the
  `resolved_after` type set so a recovered structure isn't mislabeled a terminal
  upthrust. (Surfaced `_puzzle_upthrust_terminal` field only; not the score.)
- **F4 — dashboard chip** (output/dashboard.py:171): add `puzzle_quality` to the
  `sub_payload` key tuple so the flag-on grade can surface as a "why ranked"
  chip. `.get`-defaulted → harmless flag-off.
- **F5 — `_ramp` zero-divisor guard** (scoring.py:36): `progress = (value -
  zero_at) / (full_at - zero_at)` divides by zero if an operator sets any
  `CANDLE_*_CLEAN == *_MESSY`. Guard: `if full_at <= zero_at: return 0.0` (or
  `cap` — pick the safe neutral). Protects all six ramp callers.
- **B1 — audit tool** (tools/l2_staircase_audit.py:~87): the SOS→`markup`
  reclassification left `markup` waves in no display bucket. Add `markup` to the
  named-event display so the diagnostic tool stops hiding them. (Dev tool only.)

## Invariants that MUST still hold (gates)

- **Flag-off byte-identical**: `PUZZLE_SCORE_ENABLED=False` and
  `CANDLE_SPREAD_AWARE=False` → no change to Score/Tier/any result key. Verified
  by `tools/shadow_diff.py --check` (no canonical drift) + the flag-off scoring
  tests.
- **Measure-only `read_box_events` byte-identical**: default `_DETECT` path
  reproduces current output exactly (E2 tests must stay green untouched).
- **Eval-twins fold**: still one `score_setup` call site; both twins inherit.
- `pytest`, `seed_recall --check` (firing-invariant).

## Out of scope (deferred maintainability, non-blocking)

Schema duplication in the degenerate-empty narrative branch; the shared
`measure_resistance_events`/`measure_support_tests` preamble; the `_clip`
duplicate of `phase_d.py`/`htf.py` clamps; the `events.sort` `.get`-default
strictness (D2). Logged in the backlog, not touched here.
