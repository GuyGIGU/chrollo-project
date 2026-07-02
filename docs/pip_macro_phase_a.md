# PIP macro Phase-A read — the multi-resolution retry

**Status: built + guarded, flag `PIP_MACRO_PHASE_A_ENABLED` default-OFF, awaiting
the operator eyeball gate.** Sibling to [segmentation_research.md](segmentation_research.md)
(which records why the segmentation layer exists) — this records why the PIP
skeleton gets a second trial, on what evidence the first one ended, and exactly
what is different this time.

---

## The first trial, and what its verdict actually said

| commit | what happened |
|---|---|
| `d537cc7` | PIP substrate built measure-only (`core/structure/pip.py`) |
| `c08e61f` | FLAT wire: `segment_swings` sources its zigzag from `pip_pivots(dist_min=0.03)` behind `PIP_PIVOTS_ENABLED`, default-off. Feeds ONLY the Phase-A overlay (`resolve_phase_a`) — never R/S/score/tier. Universe: fire decisions identical, overlay shifts on 62/106 firing setups. |
| `d43e7fd` | Eyeball gate: **"PIP is a wash on the overlay (fixes some inverted climax→AR, creates others e.g. GBTG/PLSE/CGNX), so it stays default-off."** |

The wash was real — but it was a verdict on **PIP-as-a-flat-zigzag**: one
`dist_min` threshold admits every above-threshold turn at once, producing the
same *class* of object as the order-N zigzag with a different noise profile. Two
mediocre single-resolution reads with **disjoint failure sets** traded failures.
The multi-resolution ranking — the one property PIP has that order-N pivots
cannot have — was never used.

## Why the climax gets stolen (the shared failure mechanism)

`_find_root_swing` / the `resolve_phase_a` bridge search pick the climax as the
**extreme pivot in the dominant direction** and the AR as the **next pivot**.
On a fine skeleton this is fragile in two ways:

1. **Climax theft** — a late range retest a few cents above the true left-side
   climax is in the skeleton, and max-price selection hands it the climax. The
   overlay paints Phase A *inside* the box.
2. **AR theft** — the pivot after the climax is a shallow first dip, not the
   real automatic reaction.

The `_enforce_bc_downswing` repair guard downstream papers over the worst
BC-painted-as-upswing cases — a symptom of the read being wrong at the source.

## The macro read (what is different this time)

`pip.macro_bridge_zigzag`: compute the PIP importance ranking ONCE at
`PIP_MACRO_K_MAX`; because `pip_indices` is strictly nested, every coarser
skeleton is a free prefix. Walk K upward from 4 and **stop at the smallest K
whose zigzag holds a confirmed bridge**:

- dominant direction from the zigzag's net displacement (mirrors
  `_find_root_swing`),
- climax = the extreme pivot in that direction (leftmost on ties),
- **confirmed** = a pivot exists after the climax AND it is interior
  (`bar < last_bar`) — the right edge is "now", an unconfirmed extreme, never
  an AR.

Stopping at the smallest confirming K **is** the theft protection: at the
stop-K, the skeleton contains only the macro turns elected so far, so the late
retest / shallow dip is *not in the skeleton to be chosen*. No confirmed bridge
by `k_max` (fresh climax whose reaction hasn't held) → fall back to the finest
prefix and let `resolve_phase_a`'s existing fallbacks behave as today.

Unit-proofed in `tests/test_pip.py`: a synthetic markup→AR→range frame with a
planted late poke *above* the true climax — the macro read confirms at K=4 with
the true climax→AR and the thief never enters the skeleton; mirrored for SC
(downtrend) roots; fresh-climax falls back with `k=None`.

## Scope and blast radius (deliberately narrow)

- Same safe surface as the flat wire: `segment_swings` → `resolve_phase_a` →
  the drawn/archived Phase-A overlay. Nothing else.
- `read_market_structure` (event labels, feeds the L2 puzzle) deliberately does
  NOT get the macro read — **event labels want the fine skeleton, the Phase-A
  bridge wants the coarse one. Same substrate, different zoom.** That sentence
  is the whole thesis.
- The flat wire stays reachable (`PIP_PIVOTS_ENABLED`) purely for A/B
  reference; macro wins precedence if both flags are on.
- Both new settings are in the freeze manifest.

## Guards (all green at build time)

| gate | result |
|---|---|
| `pytest` full suite | pass |
| `tools/shadow_diff --check` (defaults) | pass — no canonical drift |
| shadow with `PIP_MACRO_PHASE_A_ENABLED` forced ON | **byte-identical** — the wire provably cannot drift a canonical field |
| `core.archive.seed_recall --hermetic-check` | pass — recall held, no winners lost |

## The flip gate (operator decision, not a build step)

`tools/phase_a_pip_diff.py` (restored from `d43e7fd`'s pruned 2-way and extended
to 3-way: **OFF / FLAT / MACRO** on the faithful live 2y frame) is the judge:

    python -m tools.phase_a_pip_diff              # scan + render top movers
    python -m tools.phase_a_pip_diff --scan --no-render

It reports overlay shifts (off↔macro, with off↔flat as the d43e7fd reference)
and a programmatic proxy — **stolen climaxes** (climax bar ≥ box start) per
mode. The flip criterion mirrors the original gate, with teeth: macro must
*reduce* stolen climaxes and read better on the movers' charts, without
creating new inversions the way flat did. GBTG/PLSE/CGNX and the archive's
over-long-base cases (CACC/MSCI/BMRN/CWT, edge-read Finding 5) no longer fire
on today's frame, so the judgement set is today's movers — or as-of replays via
`structure_case_audit` if a historical re-litigation is wanted.

## First universe read (2026-07-02, 5y cache of Jun 30)

Full 3-way scan, 5,502 tickers → 1,932 survive baseline → **79 fire**:

| measurement | result |
|---|---|
| off ↔ MACRO overlay changes | **57 / 79** |
| off ↔ FLAT overlay changes | 47 / 79 (the d43e7fd reference read) |
| stolen climaxes (climax ≥ box start) | **0 / 0 / 0** — blatant theft absent in all modes on this frame |

**The live failure taxonomy turned out to be degenerate STUBS, not thefts.**
On the big movers the current read paints 1–6-bar climax→AR stubs parked at
the right edge (GOOD 466→467, BYD 414→415, PH 453→456 …): the bridge search
finds only micro-wiggles near the box start at order-N resolution, because the
real AR leg either ends outside `_SEG_AR_TOL` or is fragmented. The macro read
re-anchors those to 15–35-bar genuine reactions (GOOD 415→439, BYD 382→397,
SAFE 418→443) — same protection mechanism (only macro legs exist in the
skeleton), different symptom than predicted. Rendered eyeball on
GOOD/BYD/SAFE/ATI: macro's climax→AR is the visually correct trend→range
bridge on all four; on ATI (climax moves LATER, +29) flat independently agrees
with macro against the current read — the "fixes some" half of the d43e7fd
wash, kept. No new inversions observed in the eyeballed set.

**Verdict so far: strongly macro-favorable, pending the operator's own pass
over `tools/fidelity/pip_phase_a/` before flipping
`PIP_MACRO_PHASE_A_ENABLED`.** (House rule: the operator flips, not the build.)

---

# The full engine comparison (2026-07-02): pick one or merge?

The operator asked the bigger question: which SKELETON should the engine read
charts with, judged by "tighter = better for Box, LPS, Bar Spread, Uptrend"?
Answered with a three-front evidence campaign (multi-agent chart juries +
code analysis + a full-stack substrate A/B, `tools/substrate_ab.py`).

## Scope fact first: what each criterion actually depends on

LPS detection (`lps.py`) imports no pivots — pure bar geometry. Bar spread,
ATR, volume, ADR, RS, breadth: bar-level. The MA/return uptrend context:
bar-level. **Only the BOX (box_primitives) and the zigzag-derived measures
(contraction / ascending-support / traversal in metrics.py) are
substrate-dependent** — plus the Phase-A overlay and the L2 event labels.

## Front 1 — full-stack substrate A/B (the real pipeline, both skeletons)

5,498 tickers through `_evaluate_ticker` twice (A = shipped pivots, B = PIP
election patched into box_primitives+metrics only): A fires 73, B fires 95
(both 66, only-A 7, only-B 29); on the 35 common fires whose box moved, B is
numerically tighter 25:9 (median −0.0033 width).

**The chart jury reversed the numbers.** On the 12 most divergent boxes
(2 lenses each): **A wins 18:6 lens-votes; B flagged FALSELY TIGHT in 14/24
judgements** — B buys width by slicing rails through real excursions (BCH's R
overrun by ~8% twice; SANM's R through the right-edge chop; GOOD's R through a
real high cluster). Mechanism (code analysis, `pip-failure-modes`, BLOCKER):
hl2-chord election + a dist_min floor that starves small coil swings in
VCP-shaped windows + rails anchored off the true High/Low bar + gap phantom
limbs + 1–2 orders of magnitude cost. B's honest wins (BBT, PAGP) are the
known "S anchored on a one-time birth low" class. Of B's 7 drops, 5 were
WRONG (RPRX's base scored 7.5/10); of its 29 new fires, 4/8 sampled were junk
dilution (the traversal gate's floors are order-1-census-calibrated —
swapping the skeleton silently changes the gate's meaning; the extra fires
are largely an artifact). Calibration coupling is concentrated in
`TRAVERSAL_*`; the `EQ_*`/touch/respect gates are bar-level and
substrate-neutral.

**DECISION — Box/LPS substrate: the shipped engine WINS. Full migration
REJECTED on evidence.** The one open idea worth parking: PIP as an
*additional candidate generator* feeding the existing substrate-neutral
validity gates (never a substrate swap), for the BBT/PAGP/ECL/HRI gap class.

## Front 2 — Phase-A overlay: MERGE, implemented as guarded macro

Chart jury on 10 movers (Wyckoff purist + macro-skeptic per chart, unanimous
pairs): macro sweeps 6 (OFF = degenerate stubs, 1–2/10), OFF wins 4 — macro's
failure classes: bridging across a crash (TNC), SC-story-vs-BC-root
inversion (POCI), and right-edge stubs on fresh-breakout charts (ATI/AXTA).

The merge contract, now built into the macro read (all flag-gated dark):

1. **Guard-validated bridge** (`pip._validated_bridge`): climax candidates by
   descending extremity (not just the argmax — an unconfirmable fresh
   right-edge higher-high must not kill the read); AR EXTREMITY (the AR is
   its own leg's extreme — kills crash-spanning bridges); CLIMAX TERMINALITY
   (post-AR excess bounded by `PIP_MACRO_MAX_POST_EXCESS` × bridge height —
   kills taken-out climaxes).
2. **Binding validation**: the story handed downstream is truncated at the
   validated AR (`story[-2]` = climax, `story[-1]` = AR) so no downstream
   swing-search can draw an unvalidated sibling swing.
3. **Explicit root**: `segment_swings` (macro branch) emits the validated
   bridge AS `root_swing` with the story's own direction — never re-derived
   from the window's net sign (the GOOD failure).
4. **Box relation** (via `resolve_phase_a`): the story must match the
   canonical root kind (BC/SC — else `_enforce_bc_downswing` fights it), its
   AR may not land beyond the box birth + tolerance, and its AR must reach
   the box's level. Any failure → ABSTAIN → the calibrated order-N read
   speaks.

Jury-set outcome of the merged read vs the INCUMBENT: better on GOOD (+6)
and SAFE (+6.2), fixes TNC/ATI by abstention, ties (= incumbent) on
BYD/SABS/MTRX/PH, one known miss (POCI, SC-story accepted, 2/10 vs 5/10).
The four ties are recoverable upside: the unguarded macro won them 5.8–8.2,
so the kind/end-max/level constraints are candidates for LOOSENING — a
calibration pass over the full 57-mover census with the operator's eyeball,
per the incremental-loop discipline. Guard knobs are individually visible in
`resolve_phase_a`'s call; the census tool is `tools/phase_a_pip_diff.py`.
