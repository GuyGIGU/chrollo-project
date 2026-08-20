# Spec — Engine Reading-Quality Pass E3: Puzzle-Quality Graded Sub-Score (flag-gated)

**Tier:** Feature · **Lane:** engine (serial; owns shadow + seed-recall baselines) · **Branch:** `engine/l2-event-reader`
**Nature:** the first **baseline-moving** L2 wire-in — built **flag-gated, default-off** (flag-off byte-identical),
A/B surfaced for operator eyeball. The live flip and the forward-return validation are **out of scope** (gated on
the operator's eyeball *and* the ~07-15+ matured/multi-regime data that does not exist yet).

## Problem & Why

E1 produced the independent Wyckoff event pieces; E2 assembled them into a chronological puzzle + trace
(`assemble_box_narrative`) — both **measure-only**, wired into nothing live. The operator's stated goal for this
layer is: *"the more high-quality pieces, the higher it scores, regardless of recall."* E3 is the wire-in: turn the
assembled puzzle into a **graded additive sub-score** the engine actually uses.

This must respect the project's two hard disciplines:
- **Grades, not vetoes.** Geometry is the only thing allowed to veto a setup. The puzzle read enters as a
  **bonus-only additive term** (like `s_contraction` / `s_ascending` / `s_adr`) — it can only *raise* a score, never
  reject or filter a structurally-clean setup. This makes it **recall-safe by construction** (no min-score fire gate
  is touched).
- **Measure-first, flag-gated, default-off.** Sibling of `TIGHTNESS_ADR_AWARE` and `CANDLE_SPREAD_AWARE`: the term
  lives entirely behind a new default-off flag, so flag-off Score/Tier are byte-identical and the operator decides the
  flip from a chart eyeball + the matured-data validation.

## Scope

**In scope**
- A new `PUZZLE_SCORE_ENABLED = False` flag + a `SCORE_PUZZLE_QUALITY` cap (and the formula anchors) in `config/settings.py`.
- A `_puzzle_quality(narrative) -> float` helper in `core/scoring/scoring.py` returning a `[0, 1]` composite from the
  E2 narrative's **descriptive grades** — primarily `completeness` (0..4) and `chronology` (intact/partial/absent),
  optionally a light per-event cleanliness term (spring undercut / SOS hold tightness / LPS) if it stays simple and
  bounded. Neutral (0.0 → no bonus) on a missing/empty narrative.
- `score_setup` gains a `narrative: Optional[dict] = None` param; the new `s_puzzle = _clamp(_puzzle_quality(narrative)
  * SCORE_PUZZLE_QUALITY, SCORE_PUZZLE_QUALITY)` term is added to `total` **only inside `if settings.PUZZLE_SCORE_ENABLED`**
  and surfaced in the breakdown dict (`'puzzle_quality'`), so flag-off `total` and the breakdown are textually unchanged.
- Obtain the narrative **once** in the shared eval chain (`_score_eval_context` / `_run_eval_chain`) so **both
  eval-twins** (live `_evaluate_ticker` + seed `_evaluate_at_date`) inherit it through the single `score_setup` call
  site (EC-3 fold) and can never diverge. Computed only when the flag is on (flag-off ⇒ zero new computation).
- An A/B measurement surface (flag off vs on over real fires: which setups move, by how much, any tier flips,
  the score-lift distribution) + an eyeball brief.
- Tests: flag-off byte-identical; flag-on awards the bonus monotonically with completeness/chronology; neutral on
  empty narrative; the term is bonus-only (never negative, never a gate); both twins fold; determinism.

**Out of scope (non-goals)**
- Flipping `PUZZLE_SCORE_ENABLED` live, choosing the final weight, or validating the score-lift against forward
  returns — all gated on the operator eyeball *and* the matured data (~mid-July).
- Any veto/gate on the puzzle read; any change to which setups fire, to eligibility, or to the fire/min-score gates.
- Re-calibrating E1/E2 (the SOS thresholds, the detectors, `assemble_box_narrative`); re-weighting existing
  sub-scores; the larger ~100-pt scoring rehaul (this is one additive term, not the rehaul).
- Merging/pushing to `main`; touching the E0 `analyze.py` work or the unrelated `market-sector-health-board.md`.

**Assumptions (unconfirmed — flag if wrong; the council plan must resolve #1)**
1. **Box source (THE key risk).** The narrative must read the **same elected structure the engine fired on** — the
   same spring/LPS, not a re-derived one. `assemble_box_narrative(df, box, atr)` internally calls
   `find_spring`/`find_lps`, which read `box.{start_bar, base_len, R, S, box_width, r_anchor_bar, s_anchor_bar}`
   (anchors box-relative, start_bar absolute). The plan must determine the correct, drift-free way to obtain that box
   in the eval chain — **preferably reusing the engine's own box object** (`structure.box` / the box already passed to
   `find_spring`/`find_lps` inside `read_structure`) rather than reconstructing one, so the scored narrative cannot
   read a different structure than the live engine. The parent equilibrium box (not the inner box) is the puzzle frame.
2. The puzzle term is additive/bonus-only (recall-safe), shipped default-off, decided by the same eyeball gate the ADR
   and candle flips use.
3. First cut computes + scores the narrative behind the flag (flag-off fully inert); the A/B is measured by a flag-flip
   harness (mirror the candle A/B via `_evaluate_ticker` both ways). Archiving the puzzle fields for accrual is a plan
   decision (behind-flag for maximal containment vs always-measure for validation accrual).

---

## Story 1 — A puzzle-quality bonus that rises with the read

**When** a setup assembles a richer, cleaner Wyckoff puzzle (more high-quality pieces in bullish order), **I want** it
to score higher, **so** the screener rewards a complete spring→SOS→LPS story over a bare box — without rejecting the
bare box.

- **Given** the flag is **on** and a narrative with higher `completeness` / an `intact` chronology, **When** scored,
  **Then** `s_puzzle` is strictly greater than for a lower-completeness / `absent`-chronology narrative (monotonic).
- **Given** the flag is **on**, **When** any setup is scored, **Then** `s_puzzle ∈ [0, SCORE_PUZZLE_QUALITY]` — a
  bonus only, never negative, never a penalty, never a gate.
- **Given** a missing/empty narrative (degenerate box, no pieces), **When** the term is computed, **Then** it is
  neutral (0.0 bonus) — absence never demotes a setup below its geometry merits.
- **Negative** — **Given** the puzzle read, **When** it is applied, **Then** it changes only the additive score; it
  never alters which setups fire, the eligibility/validity gates, or the min-score fire threshold.

## Story 2 — Flag-off is byte-identical; the flip is the operator's

**When** the flag is off (default), **I want** Score, Tier, ranking, and the breakdown byte-identical to today, **so**
nothing moves until I eyeball the A/B and the matured data says the lift is real.

- **Given** `PUZZLE_SCORE_ENABLED` is **off**, **When** the full pipeline runs, **Then** `shadow_diff --check` shows no
  canonical drift and `seed_recall --check` holds (the term and its computation live entirely behind the flag).
- **Given** the flag is **on**, **When** the same setup is scored in both eval-twins (live + seed), **Then** both
  produce the identical `s_puzzle` (single shared `score_setup` call site; no twin divergence).
- **Negative** — **Given** flag-off, **When** the eval chain runs, **Then** no new heavy computation
  (`assemble_box_narrative`) is performed (zero cost when off).

## Story 3 — Read the same structure the engine fired on

**When** the puzzle term scores a setup, **I want** it computed on the **exact** elected box (same spring/LPS the live
engine read), **so** the bonus reflects the structure that actually fired, not a re-derived approximation.

- **Given** a fired setup, **When** the narrative is assembled for scoring, **Then** it is read on the engine's own
  elected (parent equilibrium) box, and the spring/LPS in the spine match the structure the engine resolved.
- **Negative** — **Given** the box construction, **When** it is done, **Then** it does not silently read a different
  frame/anchor than `read_structure` used (no off-by-one / absolute-vs-relative anchor mismatch).

## Story 4 — Surface the A/B before any flip

**When** the term changes scores, **I want** the affected setups rendered (flag off vs on, score lift, tier flips)
surfaced for review, **so** I sign off on the lift, not the engine.

- **Given** the live fires, **When** the A/B is produced, **Then** it lists per-setup `s_puzzle`, the off→on Score
  delta, and any Tier change, with the completeness/chronology that drove each.
- **Negative** — **Given** an unresolved operator disagreement or the matured-data validation not yet run, **When**
  deciding whether to flip `PUZZLE_SCORE_ENABLED` live, **Then** it is **not** flipped — the term stays default-off.

---

## Boundaries

✅ **Always**
- Keep the puzzle term **additive/bonus-only** and **behind the default-off flag**; flag-off byte-identical.
- Route the narrative through the single shared `score_setup` call site so both eval-twins fold (EC-3).
- Read the narrative on the engine's **own elected box** (drift-free); keep `pytest` / `shadow_diff --check` /
  `seed_recall --check` green after every step.
- Surface the A/B and wait for the operator's read + the matured-data validation before any flip.

⚠️ **Ask first** (surface, do not auto-decide)
- The flip, the final weight (`SCORE_PUZZLE_QUALITY`), and the formula shape are operator decisions — surfaced via the
  A/B, not committed-on.
- Anything that would move a canonical shadow field with the flag **off**.

🚫 **Never**
- Make the puzzle read a veto/gate, or let it touch firing/eligibility/min-score.
- Reconstruct a box that could read a different structure than the live engine fired on.
- Re-weight existing sub-scores, re-calibrate E1/E2, merge/push to `main`, or touch the E0 / market-sector-health work.

## Success Metrics
- Flag-off: `shadow_diff` no canonical drift, `seed_recall` PASS (byte-identical, recall held).
- Flag-on: `s_puzzle` rises monotonically with completeness/chronology, is bonus-only and bounded, both twins agree,
  and the narrative reads the engine's elected structure (spring/LPS match).
- A/B surfaced (per-setup lift + tier flips); committed to `engine/l2-event-reader`, not merged/pushed; the flip and
  the matured-data validation left explicitly gated.

---
*After implementing, compare results against each acceptance criterion above and list any unmet requirements.*
