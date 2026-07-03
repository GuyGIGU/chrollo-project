# Council Plan: E3 fix — faithful elected-brick puzzle read + flip-time hardening

**Scope:** Fix the inner-LPS faithfulness bug (the puzzle describes a different LPS than the
engine fired, understating completeness on the tightest inner-box setups) + 4 bundled flip-time
hardening fixes. All flag-on only; `PUZZLE_SCORE_ENABLED`/`CANDLE_SPREAD_AWARE` stay default-off.
**Council dispatched:** McKinney, Fowler, Ramírez, Hunt, Performance (all returned recs, fully
convergent). UI/UX/frontend/data seats: no surface (a backend/engine fix; F4 is a one-key display
tuple addition, no schema).

## Convergent design (all seats)
- **`_DETECT = object()` sentinel + loose bricks.** `_box_events_with_meta` and
  `assemble_box_narrative` gain `*, spring=_DETECT, lps=_DETECT`. `is _DETECT` → detect (today's
  behavior); a brick → use it; `None` → engine elected no such piece (never fabricate). Compare
  with `is`, never `==` (no dataclass `__eq__`). Pass loose bricks, NOT the `Structure` (keeps the
  `metrics→bricks` dependency one-way). No adapter — two-hop pass-through mirrors `v_bar`.
- **Inject only at the single site** `_score_eval_context` (evaluation.py:458):
  `assemble_box_narrative(df, s.box, atr, spring=s.spring, lps=s.lps)`. Both eval-twins inherit
  through `_run_eval_chain` (confirmed: seed `_evaluate_at_date` → `_run_eval_chain`).
- **`read_box_events` unchanged** (omits the kwargs → `_DETECT` → byte-identical measure-only path).

## Tasks

### 1. Sentinel + elected-brick injection (McKinney × Fowler × Ramírez × Performance)
Add the module sentinel; thread `spring`/`lps` through both functions; at the call site reuse
`structure.spring`/`structure.lps`. Reusing the elected bricks fixes faithfulness AND removes 2
redundant detector passes per fire (incl. `find_lps`'s full-length `df.assign(Spread)`). **Depends on:** —

### 2. Pin the inner-LPS translation invariant with an assertion (McKinney P4)
On the injected path, `assert lps.start_bar >= box.start_bar` (inner ⊆ parent ⇒ `lstart ≥ 0`, no
rebasing). Crash loud if a future inner-box change breaks the subset geometry. **Depends on:** 1

### 3. Make the late-V dropped-LPS observable (McKinney P1+4)
The `lstart > v_bar` Phase-D gate stays (do NOT loosen — it's the Phase-D placement guard). But when
an *injected* LPS is dropped by it (rare late-V parent), surface a `lps_pre_v_dropped` diagnostic +
trace line so the completeness understatement is auditable, not silent. **Depends on:** 1

### 4. Correct the false docstrings + comment (Fowler P4 × Ramírez P4)
Rewrite `_box_events_with_meta`/`assemble_box_narrative` docstrings ("no new find_spring/find_lps
calls" is now conditional) and evaluation.py:452 ("reproduces the fired spring/LPS bit-for-bit" →
"reuses the engine's elected bricks; the LPS may be the inner-box election"). These comments hid the
bug — fixing them ships in THIS diff. **Depends on:** 1

### 5. F5 — `_ramp` zero-divisor guard (McKinney × Hunt)
`if full_at <= zero_at: return 0.0` placed BEFORE the `value <= zero_at` early-return. Return `0.0`
(the polarity-safe neutral — two callers invert via `1.0 - _ramp(...)`, so `cap` would become a
spurious penalty). Dead code for all six shipped anchors (verified `full_at > zero_at` strictly), so
byte-identical for live settings. **Depends on:** —

### 6. F3 — `upthrust_terminal` held-range with Phase-D guard (McKinney)
Add `"range"` to the resolved-after set BUT only when `anchor_bar > v_bar` (genuine Phase-D held
range), so a Phase-B `range` (left of V) can't clear a terminal upthrust. Apply the guard to the new
`range` term only — leave the existing `markup`/`in_progress` path untouched (behavior-preserving).
**Depends on:** —

### 7. F4 — dashboard `puzzle_quality` chip (Ramírez, Hunt-cleared) & B1 — audit-tool `markup` bucket
Add `'puzzle_quality'` to `output/dashboard.py` `sub_payload` (`.get(k,0)` → no-op flag-off, Hunt
confirmed no serialization-by-presence leak). Add `markup` to the l2_staircase_audit named-event
display. **Depends on:** —

### 8. Tests (Ramírez × Hunt × Beck-in-review)
- Thread `spring=`/`lps=` through `_nar_spy`; assert the narrative's LPS **matches `structure.lps`**
  (bars) on an **inner-LPS** fixture (parent find_lps differs/None) + `completeness` includes the LPS.
- Golden before/after: `read_box_events` output byte-identical (default `_DETECT` path).
- `_ramp` returns the guard-neutral only when `full_at <= zero_at`; not-taken at every live anchor.
- F3: a Phase-D held-range clears terminal; a Phase-B range does not; TITN stays terminal.
- Keep the flag-off `_boom`/zero-compute test green (zero narrative work flag-off). **Depends on:** 1-6

## Landing gates (Hunt — the release gate)
One green run, DEFAULT config (both flags off): full `pytest`, `tools/shadow_diff.py --check`
(no canonical drift), `seed_recall --check` (firing-invariant), untouched E2 measure-only tests.
Then re-run `tools/puzzle_ab.py` to confirm inner-LPS fires now read the fired LPS. Council-review,
commit to `engine/l2-event-reader` (NOT merge/push).

## Verdict
The most important decision is McKinney's: the inner-LPS translation is correct **as-is** with no
rebasing — the fix is pure brick-reuse, not new math — so the risk is a *silent* re-understatement,
which tasks 2+3 (assert + observable) convert into a loud crash / an auditable field. Start at task 1;
the whole thing is one tight, byte-parity-provable diff on the flag-on path.
