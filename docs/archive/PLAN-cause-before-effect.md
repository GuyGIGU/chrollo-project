# Council Plan: Cause-Before-Effect Election Precondition

**Scope:** Add ONE election-time precondition to the chart-reading engine — a box may not be elected
over a live trend that never matured a cause (the MIDD false-positive class). Depth-free,
maturity-keyed, behind a default-off flag.

**Context:** The top-down readers (`market_structure.py` HH/HL, `box_events.py`, `event_map.py`) are
all measure-only and run *after* election on the already-elected box — confirmed by a 4-lane
read-only trace. Election is `read_structure` (`engine_alpha/structure/narrative.py:313`), pure local
box-shape geometry. The engine ALREADY detects MIDD's flaw (`_enforce_climax_terminality`
`bricks.py:514` + the macro-bridge terminality guard `phase_a.py:248-250` both fire on MIDD and
collapse the pair to `(box_open, box_open)`) — it just *repairs the overlay* instead of *vetoing*.
This plan consults a verdict the engine already computes; it is not new detection.

**Boundaries (out of scope):** any excursion-depth cap (proven wrong — CTOS is a blessed 3.59-ATR
throwback); the EGBN S-side band-rails twin (stays parked); scoring/tier weights; the genuine one-bar
climax+AR form (stays sanctioned). No frontend/backend-HTTP/UI surface.

**Design (operator-decided):** BOTH-signals AND-veto. Primary = the box-**independent** macro-bridge
abstention verdict; cross-check = HH/HL `read_swing_map` `pre_box`/`box` `trend_state`. Veto fires
**only when both agree** cause is absent. The AND is deliberately recall-protective.

**The hard constraint (operator, emphatic):** RECALL is the pass/fail gate. Keeping every seeded +
calibrated name the operator marked ALIVE matters MORE than rejecting MIDD. Success order —
① zero seed-recall losses AND zero dropped marks; ② MIDD rejects; ③ full battery green. **If ① and ②
conflict, ① wins and MIDD stays a documented known false positive.**

**Council dispatched:** McKinney (numerical, lead), Fowler (refactoring), Leach (data), Beck (tests),
Performance, Hunt (security — coverage), Friedman (UX). Dropped no-surface: Dodds, Saarinen, Ramírez.

---

## The one decision this plan turns on (read before the tasks)

The genuine one-bar climax (a sanctioned winner form) and MIDD's synthesized collapse produce the
**same output pair** `(box_open, box_open)` through the **same** terminality repair. So the
discriminator can **never** be the pair, the zero length, or any `climax==ar` proxy — it must be the
**provenance**: did a terminal climax→AR bridge *validate*, or did the read *abstain* and the pair
exist only because the repair re-anchored a mid-trend pause to the box open?

And there are **two different "abstained" signals** — only one is recall-safe. The box-**constrained**
resolver's `None` (`bricks._resolve_phase_a_raw`, ~`bricks.py:672-694`) abstains for *benign* reasons
(the AR merely doesn't reach *this box's* rails) → wiring it as "cause absent" would over-veto matured
bases. The operand MUST be the box-**independent** macro read (`phase_a.macro_bridge_zigzag` /
`_validated_bridge`, highs/lows only): "does ANY terminal climax→AR survive in the lead-in at all?"
MIDD abstains there; CTOS/BODI/WES validate there even at depth. **Getting this operand wrong is the
single way this feature becomes a broad recall regression.**

---

## Task Sequence

### 1. Define the cause-maturity predicate — box-independent, depth-free, fail-open, replay-honest
| | |
|---|---|
| **Domain** | Wes McKinney (numerical) × Carmack — Grounding / boundary-validation / no-lookahead |
| **Ref** | `references/quality-llm.md` → P2, P3, P4 |
| **Depends on** | — |

The verdict is `veto = A AND B`. **Operand A** = the box-INDEPENDENT macro-bridge abstained
(`macro_bridge_zigzag`/`_validated_bridge`, highs/lows only) — NOT the box-constrained resolver `None`,
NOT any zero-length proxy. **Operand B** = `read_swing_map` `pre_box.trend_state == 'up'` AND
`box.trend_state == 'up'` (name the enum value explicitly — the set is `{up,down,range}` — never
truthiness). Both operands are **total functions that fail OPEN**: a degenerate/short frame yielding
`range`/unknown → NO veto (absence of a positive cause-absent signal is never a veto). The verdict is
a pure function of `df[:election_bar]` using **committed swings only** (respect `knowable_bar`; never
let an uncommitted right-edge higher-high flip `trend_state` to `up`), so eval-at-T equals live-at-T.
No new `float ==`; NaN highs/lows fail comparisons closed → no veto.

### 2. House the verdict as a small immutable object; do NOT widen the frozen `resolve_phase_a`
| | |
|---|---|
| **Domain** | Martin Fowler (refactoring) × Carmack — Names reveal design; Data Clumps; one predicate not three |
| **Ref** | `references/refactoring.md` → P4, P5 (also P1) |
| **Depends on** | Task 1 |

`resolve_phase_a` answers "where do I DRAW Phase A" and is frozen overlay-only
(`engine_alpha/freeze/manifest.py`, `bricks.py:538-541`). Do NOT overload its `(int,int)` return to
carry a fire/no-fire gate — that makes the name lie and turns archive-facing repaired anchors into
election inputs. Add a **separate, side-effect-free, box-independent** cause-maturity function with its
own name/type that `read_structure` calls alongside `resolve_phase_a`. Return a tiny frozen value
(`matured`, `bridge_abstained`, `trend_state`) — the two sub-signals always travel together and the
audit (Task 11) needs to show *which* fired. **Compose** the already-computed macro-bridge abstain;
do not write a third copy of the terminality arithmetic (it already exists inline at `bricks.py:557-560`
and in the guard at `phase_a.py:248-250`).

### 3. Place the veto at the shared election seam; abstain with `return None`
| | |
|---|---|
| **Domain** | Martin Fowler (refactoring) × Carmack — Architecture earns its boundaries; contain state |
| **Ref** | `references/refactoring.md` → P6, P3 |
| **Depends on** | Task 2 |

Consult the verdict at `narrative.py:410-423` (after the LPS is confirmed, before `return Structure`).
`read_structure`'s only caller is the documented live+seed twin (`_resolve_structure_context` →
`_run_eval_chain`, EC-3), so the veto is inherited by both paths with no second implementation. On
veto, **`return None`** (not `continue`) — matching the existing abstain exit (`narrative.py:443`) and
the operator's "no setup at all": the box is *emergent* (same R/S reachable from many later roots), so
a `continue` risks re-electing the identical vetoed geometry or falling onto a weaker still-causeless
box. `return None` is stronger than `continue`, so it is safe ONLY behind the AND-gate — the recall
guard lives in the Task-1 predicate, not the control flow.

### 4. Short-circuit the AND; evaluate once per elected box; reuse the shared swing-map machinery
| | |
|---|---|
| **Domain** | Pipeline Performance × Carmack — budget the critical path; right-size over real n |
| **Ref** | `references/quality-performance.md` → P4, P3, P6 |
| **Depends on** | Task 1, Task 3 |

Consult the cheap terminality verdict (already computed as a byproduct of the single
`resolve_phase_a` call at `narrative.py:410`) FIRST; invoke the O(n) `read_swing_map` full-frame pivot
walk **only when the cheap signal already reads cause-absent** (if cause is present the AND can never
veto). Guarantee the veto runs **once per elected box, not once per candidate root** — the `return
None` of Task 3 caps the `_MAX_ANCHORS=64` re-election multiplier. Reuse the one shared `read_swing_map`
path (EC-3 forbids a forked lite reader); no cross-scan swing-map cache (every frame differs). Do not
recompute Phase A.

### 5. Ship behind a default-off flag with the full EC-8 protocol; flag-off byte-identical + compute-free
| | |
|---|---|
| **Domain** | Kent Beck (tests) × Carmack — behavioral variants; the enabling triad — with Leach (data) |
| **Ref** | `references/quality-testing.md` → P2, P5 ; conventions EC-8 |
| **Depends on** | Task 3 |

New default-off flag (e.g. `CAUSE_BEFORE_EFFECT_VETO_ENABLED`). In the SAME change: register it (and
any threshold the predicate reads) in `engine_alpha/freeze/manifest.py` `ENGINE_SETTINGS_KEYS`
(:43) **before any code reads it**, so a flip rotates `manifest_hash()` from day one — the existing
`test_every_scoring_settings_symbol_is_in_manifest` mechanically forces this; a dated dark-flag ledger
row (mechanically forced by `test_flag_ledger_matches_the_default_off_engine_flags`); an inert
unit test proving flag-off returns the byte-identical `Structure`; a flag-off frozen-fixture
shadow/parity replay; and **`read_swing_map` must not run at all at flag-off** (verify via a ~0
scan-metrics evaluation-phase delta). Follow the `AR_FIRST_REACTION_ENABLED`/`EVENT_MAP_ENABLED`
pattern (spread `{}` → byte-identical off).

### 6. Rotate `engine_config_version` as two seam events; vetoed = row ABSENT; survivors byte-identical; epoch-gate pooled reads
| | |
|---|---|
| **Domain** | Brandur Leach (data integrity) × Carmack — constraints are assertions; migrations are operations |
| **Ref** | `references/quality-postgres.md` → P1, P3, P4, P5 ; conventions EC-4 |
| **Depends on** | Task 5 |

A value-semantics rotation, **not** a schema migration — reuse the existing
`bin_a_*`/`bars_since_bc`/`descent_length` columns, no `ALTER`. Sequence as **two boundaries**:
rotation-1 = registration (flag default-off ships, hash rotates once, fires byte-identical — a
deliberate no-op boundary, annotated so IS/OOS doesn't misread it as a regime change); rotation-2 =
the operator flip (hash rotates again — the ONLY boundary where MIDD abstains). The veto lives in the
shared election path both writers (`archive_scan_results` screener + `seed_archive`) call, so live and
seed can't diverge under one hash (EC-4); `forward_returns` needs no change. Make it a tested
invariant that a vetoed name writes **ZERO** rows (never NULL, never a zombie), a surviving name's
Phase-A anchors are **byte-identical** across the flip (the veto must never re-anchor a survivor), and
that `analyze.py`/`seed_recall.py` pooled reads over the `bin_a` family are epoch-annotated (pre-flip
MIDD-class rows carry repaired-synthetic values; post-flip they're absent — a pooled mean would
double-standard them). State the boundary in `strategy_alpha.md`. **Marks are READ-only** — no path
re-stamps or backfills a mark's `engine_config_version` (EC-9).

### 7. Recall-safety PRE-FLIGHT: prove the AND is false on the whole corpus (measure-only A/B) BEFORE arming the veto
| | |
|---|---|
| **Domain** | Wes McKinney (numerical) × Carmack — prove it on the fixed set — with Beck (tests) |
| **Ref** | `references/quality-llm.md` → P7 |
| **Depends on** | Task 1, Task 5 |

The go/no-go for the whole feature. Compute **both** booleans measure-only over the WHOLE acceptance
corpus (every seed-recall winner + every operator calibration mark — EC-9's two populations) and
assert the AND predicate is **FALSE on every one**: each survivor either has a validated
box-independent terminal bridge (A false) OR does not read a live up-staircase (B false). Render the
before/after A/B the operator's incremental loop mandates. If any winner satisfies the AND, the
**predicate** is wrong (narrow it) — never the corpus. This assertion is the numerical statement of
recall gate ① and decides whether MIDD is rejected (gate ②) or stays a known false positive.

### 8. Recall acceptance battery flag-ON (three instruments green), THEN confirm MIDD rejects
| | |
|---|---|
| **Domain** | Kent Beck (tests) × Carmack — test what breaks; predictive — with Hunt (integrity) |
| **Ref** | `references/quality-testing.md` → P4 ; conventions EC-7/EC-9 |
| **Depends on** | Task 7 |

With the flag ON, all three recall instruments stay green: hermetic seed-recall (`--hermetic-check`,
no winner lost), the sealed marks-corpus ratchet (`--check`), and the editable `calibration_marks` A/B
(zero marks flipping fired→not-fired). Assert both population **seals are byte-identical** across the
change (`marks_fingerprint` + corpus `sha256`) — a re-graded mark must not move (Hunt). Only after all
three are green does the plan assert MIDD rejects. If any marked/seeded winner would drop, **the veto
stays flag-off and MIDD remains documented as a known false positive** — the fix is always the engine,
never a mark edit or a widened matcher window (EC-7).

### 9. Freeze MIDD as a negative bite-proof — only once zero-winner-loss is proven; place it EC-7/EC-9-safe
| | |
|---|---|
| **Domain** | Kent Beck (tests) × Carmack — the red step is the proof; the spec is the constraint |
| **Ref** | `references/quality-testing.md` → P1, P10 ; conventions EC-7/EC-9 |
| **Depends on** | Task 8 |

MIDD is a payload false positive with no existing mark. Freeze a committed MIDD frame with a bite
proof: veto ON → `read_structure` returns None (no box over the up-leg); veto OFF → the SAME frame
still elects the bad box. Placement (operator/integrity-gated): either the **operator** adds MIDD to
editable `calibration_marks` as a negative verdict (human-gated, never the agent), OR a self-contained
negative fixture under `tests/baselines/` used only by the veto's regression test. Never reinterpret,
widen, or edit a sealed `docs/marks/` entry to manufacture the rejection.

### 10. Add the doctrine-gate invariant "an elected box has a matured cause preceding it"
| | |
|---|---|
| **Domain** | Kent Beck (tests) × Carmack — assertions / mutation resistance |
| **Ref** | `references/quality-testing.md` → P6 |
| **Depends on** | Task 3 |

Extend `tools/doctrine_audit.py`: for every elected `Structure` with a BC/SC root, assert the cause
matured (the box does not predate its climax over a live up-staircase) — catching the *inverse* of the
veto (a synthesized-collapse box that slips the AND and reappears in a future payload, the FLXS defect
class the gate exists for). Two cautions: (i) avoid tautology — assert from the emitted anchors + the
raw tape, NOT a literal re-run of the veto predicate against itself; (ii) resolve the refusal seam —
the gate fails on `s is None` as a coverage hole, so a now-legitimately-abstaining name in a stale
`screener_data.json` must be taught as an expected non-election, or the gate re-run after a fresh scan.

### 11. Make "cause_absent" a first-class trace outcome; correct the premature "complete"; distinguish veto-drops in the agreement report
| | |
|---|---|
| **Domain** | Vitaly Friedman (UX) × Carmack — reasoning visibility; design every state |
| **Ref** | `references/quality-ux.md` → P9, P2, P1 |
| **Depends on** | Task 2, Task 3 |

When the engine abstains a name vanishes; during calibration the operator must be able to tell a
correct MIDD kill from a silently-eaten winner (this directly backs the recall guarantee). Add a fourth
terminal trace outcome (`cause_absent`) at the veto seam. Critically, `rec['outcome']` is set to
`'complete'` at `narrative.py:403` **before** the veto point — when the veto fires the record must be
**corrected** to `cause_absent`, else the audit shows COMPLETE for a box that never fired. The "why"
data (`pre_box`/`box` trend + bridge-abstained) is the Task-2 verdict object (don't re-derive it). In
the calibration agreement report a vetoed mark currently grades as `engine_no_read` — the same bucket
as no-root/no-box — so add a distinct outcome (e.g. `vetoed_cause_absent`) to the closed, loud-on-
unknown OUTCOMES set so the marks-ratchet diff attributes each dropped mark to the veto. All of this
lives on the existing `if trace is not None` branch — zero hot-path cost, so it ships in-change.

### 12. Correct the doctrine + Reading Model in the same change
| | |
|---|---|
| **Domain** | Carmack (chair) — doctrine drift is a defect (project law) |
| **Ref** | `CLAUDE.md` non-negotiable reading rule ; `docs/strategy_alpha.md` |
| **Depends on** | Task 3 |

`strategy_alpha.md:121-127` currently cites **MIDD as the exemplar of the *sanctioned* one-bar form** —
the operator's ruling reverses this. Correct it: MIDD is the exemplar of the **synthesized-collapse
case the veto REJECTS**; the genuine one-bar climax+AR (a real wide bar that breached the extreme AND
corrected within its own range) stays sanctioned but MIDD is not an instance of it. Add the
cause-before-effect precondition to the Reading Model (a matured cause must precede any elected box;
the discriminator is macro-bridge validation, never depth or zero length). Ships in the same change as
the code — not deferred.

---

## Risks & Watchpoints
- **McKinney — the two-abstention trap:** wiring the box-CONSTRAINED resolver `None` (benign
  "AR doesn't reach these rails") as the operand over-vetoes matured bases. The operand MUST be the
  box-INDEPENDENT `macro_bridge_zigzag`/`_validated_bridge` abstention. This is the #1 recall hazard.
- **McKinney — fail-open on missing data:** a degenerate/short/`range`/unknown frame must yield NO
  veto. A veto on absence-of-signal is a recall loss with no diagnosable cause.
- **Fowler — Two-Hats commit split:** any shared-predicate extraction is behavior-preserving and
  proven byte-identical FIRST (refactor commit), then the veto is added behind the flag SECOND
  (feature commit). Never interleave — an interleaved commit makes flag-off non-byte-identical and the
  shadow gate can no longer attribute a dropped winner to the veto vs the refactor.
- **Leach — no-op boundary mislabel:** the registration hash-rotation (rotation-1) fires
  byte-identical; annotate it so IS/OOS doesn't credit the edge change to the wrong epoch.
- **Hunt — ground-truth invariance tripwire:** no migration/startup step may re-stamp a mark's
  `engine_config_version`; both population seals byte-identical across the change. A dropped mark is
  never "expected" — the fix is always the engine.
- **Beck — doctrine-gate refusal semantics:** a legitimately-abstaining name in a stale payload must
  not read as a coverage-hole refusal; re-run the gate after a fresh scan or teach it the expected
  non-election.
- **Performance — emergent-box 64×:** verify a re-election cannot re-invoke `read_swing_map` up to
  `_MAX_ANCHORS` times for one ticker; the `return None` of Task 3 is what caps it.

## External Setup Required
| # | What | Why | Blocking task |
|---|------|-----|---------------|
| 1 | Operator flips `CAUSE_BEFORE_EFFECT_VETO_ENABLED` live + runs `update_dashboard.bat` | Loading code + arming the veto is the operator's gate (the agent never boots the service) | After Task 8 |
| 2 | Operator adds MIDD as a negative `calibration_marks` verdict (if placement (a) chosen) | EC-9 marks are human-gated; the agent may not write a mark | Task 9 (only if option a) |

No code-external services, keys, or webhooks. Pure engine change.

## Summary
| # | Task | Domain | Depends on |
|---|------|--------|------------|
| 1 | Cause-maturity predicate (box-independent, depth-free, fail-open, replay-honest) | McKinney | — |
| 2 | Verdict value object; don't widen frozen `resolve_phase_a`; compose the existing abstain | Fowler | 1 |
| 3 | Place veto at the shared election seam; `return None` | Fowler | 2 |
| 4 | Short-circuit AND; once per elected box; reuse swing-map machinery | Performance | 1, 3 |
| 5 | Default-off flag + full EC-8 protocol; flag-off byte-identical + compute-free | Beck / Leach | 3 |
| 6 | Archive: two-event rotation, vetoed=row-absent, survivors byte-identical, epoch-gated reads | Leach | 5 |
| 7 | Recall pre-flight: AND false on the whole corpus, measure-only A/B, BEFORE arming | McKinney / Beck | 1, 5 |
| 8 | Recall battery flag-ON (3 instruments green), THEN MIDD rejects | Beck / Hunt | 7 |
| 9 | Freeze MIDD negative bite-proof, EC-7/EC-9-safe placement | Beck | 8 |
| 10 | Doctrine-gate invariant "elected box has a matured cause" (non-tautological) | Beck | 3 |
| 11 | `cause_absent` trace outcome + correct premature "complete" + agreement-report distinction | Friedman | 2, 3 |
| 12 | Correct `strategy_alpha.md` Reading Model in the same change | Carmack | 3 |

## Verdict
The single most important decision is the **operand of the veto**, and the council's numerical seat
earned the whole run by pinning it: the discriminator is **macro-bridge ABSTENTION from the
box-INDEPENDENT read** — not the collapsed pair, not the zero length, not the box-constrained
resolver's `None`. Get that one operand right and the feature is a small, safe "consult a boolean the
engine already computes"; get it wrong and it is a broad recall regression dressed as a bug fix. Start
at Task 1 and do not let it move until the Task-7 pre-flight proves the AND is false on every marked
and seeded winner — that measure-only proof, not the MIDD rejection, is the real deliverable, because
the operator's constraint is explicit: a live false positive is tolerable, a dropped winner is not.
The critical seat during build is McKinney (predicate correctness + replay honesty); keep Fowler on
hand for the frozen-contract boundary and Beck for the recall-first sequencing. This is one clean
fold at one seam — resist every temptation to make it more.
