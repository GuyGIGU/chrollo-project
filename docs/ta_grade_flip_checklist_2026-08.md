# TA-Grade flip checklist — the atomic re-bless choreography (build task 15)

**Status: PREPARED, NOT EXECUTED.** The flip is the operator's A/B-eyeball
decision (flag ledger, kill-by 2026-08-31). Everything below happens at the
flip commit and ONLY there — a baseline recapture appearing in any other
diff is the agent-cheating signature and rejects the diff (EC-29).

The build behind this checklist: tasks 1–14 of `PLAN-ta-grade.md`, commits
`9085e93..68540c0` on `claude/gallant-hodgkin-906536` (all reweight-neutral;
every weight/cap/discount/tier-cut remains the operator's, decided here).

## 0 — The A/B eyeball (no flip required)

```bash
python -m tools.ta_grade_ab
```

Per archived fire: stored score/tier vs the would-be 0-100 from the row's
own archived facts, rank deltas over the scan's fire list, `--top` chapter
drill. The affine identity is checked on every run (exit 2 = a bug, never
movement). Optionally `--json output/ta_grade_ab_<date>.json` for the
evidence record. Judge here; nothing changes until step 1.

## 1 — The flip commit (ONE atomic change)

1. `config/settings.py`: `TA_SCORE_V2 = True`, plus the operator-chosen
   weights from the A/B — the `SCORE_STORY_*` / `SCORE_SPRING` caps, the
   `TA_WARN_*` discount factors, and the NEW `TIER_S_STRUCT / TIER_A_STRUCT
   / TIER_B_STRUCT / TIER_C_STRUCT` 0-100 cuts (registered in the manifest
   in the same change).
2. The tier re-base wiring (small, deliberately deferred to this commit so
   no provisional cut ever ships): `compose_ta_grade` emits
   `structure_tier` from `ta_grade` against the `TIER_*_STRUCT` ladder
   (keep the `S_MAX_BOX_WIDTH` S-cap concept); the result/wire/archive
   `Tier` swaps source at this seam; the D-tier vocabulary is unified
   across ScreenerToolbar / FreshSetupsZone / EdgePulse (D exists in
   archive/watchlist vocab but is un-filterable on those three — do not
   fork it further).
3. The scripted re-bless, in this order, all in the flip commit:
   - `python -m tools.shadow_diff --capture` (score/tier/ranking recapture
     — BY DESIGN at this seam),
   - seed-recall + hermetic baseline recapture (informational tier/score
     fields go stale even when green),
   - the marks-corpus re-freeze as an explicit EC-7 event (ratchet stays
     28/33 or better — a regressed pinned hit is a design falsification,
     not a threshold to tune),
   - fresh fold-parity capture,
   - `python -m tools.settings_reference --write` (Quick-Reference; the
     manifest rotation is THE seam).
4. Cost + payload certification (EC-8): re-run the per-fire timing of the
   measurement block (the task-8 instrument measured worst-case 0.31 ms
   median / 0.54 ms max per fire) and record the payload delta of the v2
   block (~1 kB/setup expected vs the 14.8 MB artifact).
5. The 1536×864 lens eyeball on the first flag-on payload (the TaGradePanel
   + chapter strip render on real fires; the card face is unchanged).
6. Same-change docs: `strategy_alpha.md` Reading Model (the grade IS the
   read's number now), `engine_reference.md` Phase-4 section (the 0-100 +
   chapters replace the raw-total table; the stale "~209" goes), the flag
   ledger row updated per EC-15, a `decisions.md` ruling row, and the
   distilled evidence at `docs/ta_grade_flip_<date>.md` (EC-16 — committed
   BEFORE the ledger cites it).

### Expected churn — named in advance so it reads as intended, not as failure
- `engine_config_version` rotates: calibration chip caches recompute; a new
  IS/OOS seam appears in the edge harness.
- The cockpit's "Fresh S-tier" selects a different population under the
  re-based tier — stated flip evidence, never silent drift.
- The mixed-epoch badges (analyze banner, /calibration per-tier `epochs`,
  ArchiveTierCards ⚠) light up the day two epochs coexist — that is them
  working.
- Pre-flip rows keep NULL grade columns FOREVER (no backfill, ever).

## 2 — Staged retirement (a later commit, only after the flip is blessed)

While rollback is possible, the legacy path IS the rollback — nothing below
happens until the operator declares the flip good.

- Delete as ONE unit: `setupScoreMath.js`, `setupTagsData.js`'s fire rules
  + `deriveTags`, `tagFlagsFromWire`, `ScoreBreakdown.jsx` + the remaining
  pill CSS, and the `visual` / `market` / `rs` sorters with their toolbar
  options (any active removed sort resets to the default score order).
  What survives: the presentational catalog (labels/tones/order/copy) and
  `wireVocabulary`.
- Fold the wire's `traversal_density` literal onto the tags helper's one
  derivation.
- Migrate the rich explainTip tooltip copy onto the v2 chips (the resolver
  currently shows label-only titles in the v2 epoch, by design).
- Retire `TA_SCORE_V2` (flag → Retired in the ledger; the legacy scorer
  path and the dual-epoch switches go with it).

## Standing facts this build established (verify nothing regressed)

- No baseline was recaptured anywhere in tasks 1–14 (EC-29 clean); the
  pre-flip manifest rotations were declared no-behavior seams that collapse
  to one at merge.
- Flag-off is byte-identical and compute-free, tripwired at the scorer, the
  wire (149-key snapshot), and the cascade.
- The EC-17 suite (`tests/test_ta_grade_cascade.py`) drives a real fixture
  fire through the full flag-on chain — if the dark grade breaks, the suite
  is red before the flip evening starts.
