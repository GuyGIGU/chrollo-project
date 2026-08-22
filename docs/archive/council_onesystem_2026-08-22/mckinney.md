# McKinney — numerical correctness (engine_alpha/structure + engine_alpha/scoring)

Run 2026-08-22-2250. Read first: context brief, quality-llm.md (numerical recast),
conventions.md, strategy_alpha.md (Reading Model), decisions.md (Tested-DEAD). All work
read-only; branch content read via `git show`/`git diff`, never checkout. Independent
verification harness in the session scratchpad (oracle_check.py), run on the repo venv.

---

FINDING 1 (the ruling this run must produce):
- Title: `proposal/first-legal-look-fix` (80efa9f) is CORRECT — verdict **MERGE**
- File: engine_alpha/structure/power_play.py:208-257 (branch), engine_alpha/evaluation.py:1190 (live consumer), tools/power_play_census.py:182
- Principle: EC-45 (replay arithmetic derives from the AS-OF state) + quality-llm P4 recast (pin the inputs — a walk may only read what it was handed)
- Severity: P1
- What's wrong: main's `first_legal_look` solves the seeding walls against a prefix read at the as-of day `p` itself, but the collector anchors on the edge-TRIMMED frame — the newest `STRUCTURE_EDGE_SKIP_BARS` (5) sessions are reserve the walk cannot see. Reading at `p` instead of `p - skip` is clairvoyant in one direction (a confirming close printing inside the reserve dates the look up to 5 sessions EARLY) and blind in the other (a low deepening inside the reserve resets the AR-age wall early and dates the look LATE, all the way to the final-AR bound); the old terminal bound could also return a day on which the walk-visible reaction had never confirmed at all. This is live engine code: the species lane's `pp_state` stamping (evaluation.py:1190) and the census both consume it.
- Consequence: the species register and the clock-8 census — the evidence base the 2026-08-18 clock ruling reads — date "when could the engine first have watched this" with a dual-direction bias that opens at exactly the short clocks under study (12.1% of clock-8 looks move, all earlier, median 11 sessions; 96 episodes regain their looks; 5 biased elections evaporate).
- Verification I ran (independent of the branch's own battery): loaded the branch function beside main's and walked the REAL seeder (`collect_root_anchors`, truncate-then-trim per session) as an oracle over 175 randomized decidable synthetic episodes across clocks 8/10/15/20 — **branch 175/175 exact, 0 early, 0 late; main 169/175 with 1 early and 5 late** (both bias directions reproduced). The branch's four hand-reasoned battery cases (457/452/459/464) all agree with the oracle. I also hand-checked that main's pinned tests survive the new arithmetic (test_power_play_census.py:91-92 470/458, :119 452; test_power_play_lane.py:134 458) — they do, because the loop returns before the new `j1-1+skip` terminal bound whenever confirmation and the final low were already walk-visible, which is exactly those fixtures. The wall constants match the collector exactly (climax wall `peak+clock+skip` from `scan_hi = end - min_days`; AR wall `ar+clock+skip-1` from `len(eval_df) - ar < min_days`). NaN closes/lows fail closed in the prefix state. At clocks 20/15 the age walls sit past the whole window's reserve exit, so the paying read is provably untouched — shadow_diff no-drift corroborates.
- Fix: none to the code — it is right. The corrected invariant ("a walk standing on session p never reads the reaction past p − skip") is the Reading Model's own no-lookahead law extended to the reserve, and the EC-45 row this module already cites prescribes exactly this.
- Ruling-recommendation: **MERGE**, with two conditions folded into the merge change (conditions, not parking): (1) EC-15 — the clock-8 census re-runs in the same change so the cohort statistics the 2026-08-18 ruling cites are re-derived on the corrected arithmetic (the branch itself admits the post-fix cohort numbers are unmeasured; a ledger/ruling surface citing pre-fix evidence after the merge is a falsified decision record); (2) the decisions.md row and the MGNX/QLYS/STRZ register eyeball are the operator's, exactly as the commit message reserves them. KILL is indefensible: the defect is real, oracle-confirmed, one-directional on real tape, and leaving it unmerged keeps a second version of live engine arithmetic standing — the disease this run exists to cure.

---

FINDING 2:
- Title: `_clamp` and `_ramp` fail OPEN to FULL points on NaN — every scoring term
- File: engine_alpha/scoring/scoring.py:25-27 (`_clamp`), :30-45 (`_ramp`); call sites throughout `score_setup` (e.g. :168 box_tightness, :202 atr_squeeze); unguarded inputs at engine_alpha/evaluation.py:521-545
- Principle: quality-llm P2 recast (quarantine NaN/inf at the boundary before propagation); EC-2 spirit; the Reading Model's own law "absence is neutral — no read is punished for a measurement the engine could not take" (and certainly never rewarded)
- Severity: P2
- What's wrong: `_clamp(value, cap) = max(0.0, min(cap, value))` — Python's `min(cap, nan)` returns `cap` because `nan < cap` is False, so `_clamp(NaN, cap) = cap`: a NaN input scores the term's MAXIMUM. Verified live on the repo venv: `_clamp(nan, 8) == 8.0`, `_ramp(nan, 0, 1, 10) == 10.0`. `None` is handled correctly (`_ramp` maps None→0 by contract) but NaN — the value an actual bad panel produces (this system explicitly models unreadable NaN bars elsewhere: `episode_nan_bars`, the rail-episode `unreadable` outcome) — silently inverts absence-neutral into absence-maximal on every `_clamp`/`_ramp` term: atr_squeeze, box_tightness, vol_contraction, contraction, ascending_support, the four ramp bonuses.
- Consequence: one NaN reaching a raw input (e.g. `atr_ratio = ATR_10/ATR_50` at evaluation.py:269, `vol_contraction`, `tightness_ratio` — none quarantined at the score_setup call site) awards full-cap points with no trace, silently promoting the least-measurable chart. Latent today, not live: 0 of 9,951 archived rows show the cap-with-anti-squeeze contradiction, and the universe prep's completeness gates make NaN rare — but the failure mode is maximal and invisible when it fires.
- Fix: make the two shared shapes NaN-safe at their single seam — a non-finite `value` reads exactly like `None` (neutral 0.0) in `_clamp` and `_ramp`, with one unit test per shape pinning NaN/±inf. Two functions, no threshold moves, byte-identical on every finite input.
- Ruling-recommendation: FIX (small, in-lane, no A/B needed — no live behavior can change on finite inputs; the flag protocol does not apply to a NaN quarantine).

---

FINDING 3:
- Title: atr_squeeze is NOT the box-tightness rebase twin — measured, recommend KEEP and close the note
- File: engine_alpha/scoring/scoring.py:201-203; engine_alpha/evaluation.py:269; config/settings.py:694-707
- Principle: quality-llm P7 recast (measure before proposing); decisions.md discipline (record nulls so they stop resurfacing)
- Severity: P3
- What's wrong: nothing in the code — the standing "open twin: atr_squeeze not ADR-rebased" note is the defect. Box tightness was ADR-rebased because its raw unit was absolute % width, which anti-correlated with ADR (−0.73: flat low-ADR drifters maxed the term). atr_squeeze's raw input `ATR_10/ATR_50` is already dimensionless and self-relative — the stock's own recent volatility against its own longer horizon — i.e. it already IS the "measured in the stock's own units" form the rebase gave tightness. There is no absolute unit left to rebase; a mechanical "rebase for consistency" would be a category error.
- Measured (live archive, 9,951 rows with both fields, read-only): corr(score_atr_squeeze, adr_pct) = **−0.254** — mild, versus the −0.73 that condemned absolute tightness; post-rebase corr(score_box_tightness, adr_pct) = **+0.113** (the rebase worked). A flat low-ADR drifter takes ~zero credit here by construction (ATR10 ≈ ATR50 → ratio ≈ 1), so the GBTG failure class cannot reproduce. Secondary observation, recorded not proposed: median archived atr_ratio is 1.048 and **6,630/9,951 fires (67%) sit at ratio > 1**, clamped to zero credit — the term is inert on two-thirds of the fleet and discriminates only within the squeezed minority. That is a fact for the next edge read, not a knob request (the 2026-07-15 edge read graded atr_squeeze beneficial; weights move only on an operator A/B).
- Fix: no code change. Add the measured-null row to decisions.md ("atr_squeeze ADR-rebase — not applicable; ratio already self-relative; corr −0.254 vs −0.73") so the open-twin note in the project memory stops re-proposing it.
- Ruling-recommendation: KEEP + record the null.

---

FINDING 4:
- Title: story-form vs ratchet-form after the refused flip — ONE system with a scoped lane, not a fork
- File: engine_alpha/structure/box_primitives.py:706, :741-746 (the one admission seam); engine_alpha/structure/event_map.py:569-601 (the form's one implementation); engine_alpha/evaluation.py:1214 (the scoped override); tests/test_resistance_contraction.py:109 (the paying-read pin)
- Principle: EC-18 (a ruled judgment predicate has exactly ONE implementation) + EC-43 (instruments enter through the same override core); AP-8/AP-10 honored
- Severity: P3
- What's wrong: nothing structural — this is the census answer the brief asked for. After a3397a5's revert, what remains is exactly one election pipeline: the story pool has ONE candidate walk and ONE admission seam, with two NAMED ruled forms consulted in fixed priority — the settled S-test form (`story_admission`) always first, then `species_form and resistance_contraction_admission`. Each form is one function in event_map (EC-18 clean); the O(1) prefilter derives both legs from the same shared predicates so it cannot drift from the reader; the census enters through the same `window_override`/`flag_capture` core (EC-43 clean). The species lane flips `POWER_PLAY_STORY_FORM_ENABLED` ONLY inside its own scoped override (evaluation.py:1214), and the paying read's blindness to the form is pinned by name (`test_paying_read_never_consults_the_species_form`). The refused flip removed a graduation, not code — no duplicated detector, no twin predicate, no second election survives it.
- Consequence: no consolidation work is owed in this lane. The single open item is real but already correctly framed: graduating the contraction form into the paying read is a re-election change (the WCC 2.2×-wider-box drift the shadow guard caught) and needs its own A/B program; the flag sitting dark with the EGBN/PKE acceptance evidence banked is the measure-first protocol working, not a version smell.
- Fix: none. Do not "unify" the two forms into one predicate (they answer different operator rulings) and do not remove the dark flag before its program runs or its kill decision is taken.
- Ruling-recommendation: KEEP-WITH-REASON — the reason is EC-18-compliant single implementation plus a test-pinned paying-read boundary; the graduation program (or an explicit operator kill of the form) is the eventual resolution, and it is already the recorded plan.

---

## Lane summary — is the read ONE pipeline?

Yes, in this lane, with three residuals now dispositioned: (1) the only true second
version of live engine arithmetic was the unmerged `first_legal_look` fix — resolved by
MERGE (Finding 1); (2) the "atr_squeeze rebase twin" dissolves under measurement — not a
twin (Finding 3); (3) the species story form is a scoped lane inside the one admission
seam, not a fork (Finding 4). Climax-anchor state, verified on main: the polarity re-key
landed 2026-08-19 (`bricks._cause_is_up`, keyed on the covering confirmed segment with the
seed label as documented fallback only — the Tested-DEAD `root.kind` keying is gone from
the live path); the remaining defect is the fixed lookback window itself (the "A pinned at
−60" half), which is an open operator-ruling program, not a code defect found here. General
hunt: no lookahead primitives (`shift(-)`, `center=True`, backfill) anywhere in
engine_alpha; `ticker_episodes`' rolling windows are trailing; NaN fails closed in the
episode walls and the departure wall; argmin/dedup tie-breaks are deterministic
left-to-right. The one systemic numerical hazard found is the `_clamp`/`_ramp` NaN
fail-open (Finding 2).

Verification artifacts: scratchpad `oracle_check.py` (branch-vs-main-vs-live-seeder oracle,
175 randomized cases), archive correlations via read-only `mode=ro` SQLite.
