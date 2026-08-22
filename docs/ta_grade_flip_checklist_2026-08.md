# TA-Grade flip checklist — the atomic re-bless choreography (build task 15)

**Status: PREPARED, NOT EXECUTED.** The flip is the operator's A/B-eyeball
decision (flag ledger, kill-by 2026-08-31). Everything below happens at the
flip commit and ONLY there — a baseline recapture appearing in any other
diff is the agent-cheating signature and rejects the diff (EC-29).

The build behind this checklist: the 14 build commits `9085e93..68540c0` +
the 2026-08-08 council-review fix commits (chapter vocabulary re-ruled to
Cause → Phase B → Phase C → Phase D → Trend; 15 findings fixed) on
`claude/gallant-hodgkin-906536` — the branch's `git log` is the task
enumeration. All reweight-neutral; every weight/cap/discount/tier-cut
remains the operator's, decided here.

**Every command below runs on the ChrolloDashboard venv interpreter, from
the repo root** — bare `python` is this machine's documented trap (two
colliding 3.14 installs):

```bash
PY="C:\Users\User\Documents\Projects\Chrollo Project\.venv\Scripts\python.exe"
```

(In PowerShell: `$PY = "C:\Users\User\Documents\Projects\Chrollo Project\.venv\Scripts\python.exe"`
then `& $PY -m ...`.)

## 0 — The A/B eyeball (no flip required)

```bash
"$PY" -m tools.ta_grade_ab
```

Per archived fire: stored score/tier vs the would-be 0-100 from the row's
own archived facts, rank deltas over the scan's fire list (`+` = climbed
under v2), `--top` chapter drill. The affine identity is checked on every
run against the PRE-warning ordering (exit 2 + a printed verdict on BOTH
output modes = a bug, never movement; warning-driven reordering reports as
movement). Warnings print with their cost — `:neutral` entries contribute
ZERO until you set their `TA_WARN_*` factors. Optionally
`--json output/ta_grade_ab_<date>.json` for the evidence record (the
identity verdict still prints). Judge here; nothing changes until step 1.

**Judge movement only on a scan archived by the merged code.** Rows from
before the grade columns carry `score_setup_quality` NULL: the replay grades
setup_quality absence-neutral 0 while the stored v1 score still contains its points,
so their rank Δ is the missing setup-quality differential, not the grade's opinion
(first live A/B 2026-08-08: the entire ±31 movers list — LKFN/ELS/CATO −31/−28/−26,
ABBV +26 — decomposed to exactly the wire's setup-quality points, 6/6). The tool
banners this basis on both output modes when such rows are present.

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
   - `"$PY" -m tools.shadow_diff --capture` (score/tier/ranking recapture
     — BY DESIGN at this seam), then `"$PY" -m tools.shadow_diff --check`
     green;
   - `"$PY" -m core.archive.seed_recall --fresh-capture` then
     `--fresh-check` green (informational tier/score fields go stale even
     when green);
   - `"$PY" -m tools.marks_corpus --build-fixture` then `--check` green —
     the re-freeze is an explicit EC-7 event (ratchet stays 28/33 or better
     — a regressed pinned hit is a design falsification, not a threshold to
     tune);
   - `"$PY" -m tools.fold_parity --capture output/flip_fold_parity.json`
     (the fresh fold-parity basis);
   - `"$PY" -m tools.settings_reference --write` (Quick-Reference; the
     manifest rotation is THE seam).
4. Cost + payload certification (EC-8): run the COMMITTED instrument
   `"$PY" -m tools.ta_grade_timing` and record its numbers in the flip
   evidence. Post-review baseline (2026-08-08, after the finding-8 walk
   fix made the ratio honest by always paying the full root budget):
   median 0.64 ms / p90 1.02 / max 1.37 ms per fire on the 32 firing
   fixture tickers — ~0.4 s per 300-fire scan, three orders inside the
   evaluation budget (the task-8 pre-fix figures were 0.31/0.54). Also
   record the payload delta of the v2 block (~1-1.5 kB/setup expected vs
   the 14.8 MB artifact).
5. The 1536×864 lens eyeball on the first flag-on payload (the TaGradePanel
   + chapter strip render on real fires; the card face is unchanged). Two
   named checks: (a) the 26px grade headline is visible in the lens
   WITHOUT scrolling on a graded row — if not, the panel moves UP in its
   section, never the section cap up; (b) chapter hover lights the chart
   region and the cell's is-active border answers.
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
  ArchiveTierCards ⚠) count DISTINCT `engine_config_version` values, and
  the matured archive already spans several manifest rotations — so they
  are lit BEFORE the flip; that is normal, not a defect to hunt. The
  flip-day signal is different: the first rows whose GRADE columns are
  non-NULL (the score-scale seam inside the epoch count).
- Pre-flip rows keep NULL grade columns FOREVER (no backfill, ever).
- The grade-verdict channel (agree / too_high / too_low) is live end-to-end
  on the backend and round-trips on the identity GET, but has NO lens
  control yet — its UI lands at the flip commit beside the read-verdict
  buttons (or gets its own named deferral here). Until then a grade
  judgment can only be recorded via the API.

## 2 — Staged retirement — **EXECUTED 2026-08-23** (operator-delegated 2026-08-22)

Executed as written EXCEPT where later builds had falsified the plan (EC-42),
each falsification found by the 2026-08-22 council review: (a) the delete-unit
no longer closed — the 2026-08-12 lens fusion wired the LIVE LPS grade to
`setupScoreMath.js`'s cap mirror, so the fraction was first serialized
engine-side (`lps_grade_fraction`, EC-28) and only then did the mirror delete
clean; (b) `setupTagsData.js` could not delete whole — the presentational
catalog/tones the RESOLVED path renders were extracted to `tagCatalog.js`
first; (c) the live ladder (`calculate_structure_tier`) had zero direct tests —
its band/width-cap battery was rewritten off the retiring twin BEFORE the
deletion; (d) the ranking still keyed on the legacy raw sum — re-pointed to
`ta_grade` (raw-sum, then ticker, tiebreak) as the wave's first task, and the
seed scan-back election re-keyed to the same basis in the same seam.
Historical plan below, kept verbatim:

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
  **DONE — pulled forward 2026-08-11** (operator flagged the missing hovers at the
  eyeball pass): `components/tagTooltips.js` carries the copy + rebuilds the measured
  suffixes from each fired entry's `detail` facts; the retirement wave should delete
  the legacy copy in `setupTagsData.js`, not this module.
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
