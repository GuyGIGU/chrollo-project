# Dodds — Frontend seat (webapp/frontend/src/), Council Review 2026-08-22-2250

Scope: consumer map of legacy vs TA_SCORE_V2 grade fields; consumer-side retirement list;
EC-28 sweep; general frontend bug hunt. Evidence: full read of the score/tag/story modules,
mechanical scans (fetch-without-catch, case-twins, inline formatters), the 289-test node
suite (all green), and one executable repro (finding 1). Read-only; no repo files touched.

---

## Part 1 — The consumer map (who reads what)

The wire today carries BOTH families on every live scan (`output/dashboard.py:186-231`):
`score` (legacy raw points) + `sub_scores` (all always-emitted terms, rs/uptrend now
permanently 0) ride beside `ta_grade` / `ta_grade_raw` / `ta_grade_chapters` /
`ta_grade_chapter_fractions` / `ta_grade_warnings` / `fired_tags`, and `tier` is
v2-derived server-side at the flip seam.

**TA_SCORE_V2 (v2 wire) consumers — the keep side:**
- `components/chapterStrip.js` — chapterCells/warningItems, wire-driven, EC-28-clean.
- `components/setupStoryRows.js` — storyRows (v2 chapters + marks). ONE legacy leak: `lpsGrade` (see finding 7).
- `components/SetupStoryPanel.jsx` — grade headline (line 262) + the dual-epoch switch (215, 268-273).
- `components/tagResolver.js` — resolved path (fired_tags = verdicts); consumed by SetupTags.jsx, useScreenerFilters' tag map, the lens. EC-28-clean.
- `components/ArchiveTab.jsx:141` — merges ta_grade/ta_grade_raw/fired_tags onto the lens payload.
- `utils/scoreFormat.js` — the scale-guard formatter (correctly refuses to coalesce the two scales).
- `components/wireVocabulary.js` — CHAPTER_*/WARNING_LABELS/TIER_LETTERS, labels only.
- Every tier surface (theme.tierColor consumers) — fed the v2-derived letter, no client ladder.

**Legacy family consumers — the retirement list, file by file:**
1. `components/setupScoreMath.js` (the frozen mirror) — imported by: `ScoreBreakdown.jsx`,
   `hooks/useScreenerFilters.js`, `components/setupStoryRows.js` (lpsGrade),
   `components/setupTagsData.js`, `setupStoryRows.test.js`. Pinned by
   `tests/test_frontend_score_caps.py` (retires with it — Beck's lane).
2. `components/ScoreBreakdown.jsx` — sole consumer is SetupStoryPanel's legacy branch
   (line 272). DELETE as one unit with that branch.
3. `hooks/useScreenerFilters.js:136-153` — visual/market/rs sorters derive from
   sub_scores via the mirror, on a grid the engine already ranks by ta_grade.
   DELETE or re-point at wire chapter subtotals at retirement (rs is already dead — finding 5).
4. `components/setupTagsData.js` — TAG_DEFS fire rules + deriveTags DELETE at retirement;
   TAG_CATALOG + GROUP_TONES/GROUP_ORDER/GROUP_LABELS + tooltip builders must SURVIVE
   (the resolved path renders through them) — extraction is a retirement precondition (finding 8).
5. `components/tagResolver.js:32-35` — the legacy derive branch deletes; `hasResolvedTags`
   becomes an assertion, not a fork.
6. `components/SetupStoryPanel.jsx:268-273` — the legacy-pills cell ("Deletes as one unit
   at the flag's retirement" — its own comment; correct).
7. Legacy `score` (raw points) DISPLAY consumers — these break the day the backend stops
   serializing `score`; each needs a ruling (show ta_grade, or drop the cell):
   `components/glanceResolvers.js:28` → `components/ui/HoverGlass.jsx:108-116` (hover header);
   `utils/watchlistTable.js:25,44,54` → Watchlist page + `components/ScreenerWatchlistPanel.jsx:113-116`
   (Score column + sort); `components/home/ActionCenter.jsx:170` (fresh-S chips);
   `components/WeeklyReview.jsx:158` (save.score — a SERVER-stored ledger copy; backend ruling);
   `components/archive/ArchiveTable.jsx:147` (books of record — KEEP forever, read per-epoch,
   the cross-epoch caveat is already on the tier cards).
8. Tests to move at retirement: `setupStoryRows.test.js`, `tagResolver.test.js` (legacy-epoch
   cases), plus the Python cap pin above.

Coherence note for Saarinen's lane (inventory only, no duplicate finding): today the operator
sees the legacy raw-point number on the hover glass, ActionCenter chips, both watchlist score
columns, and WeeklyReview, while the grid/lens rank and headline by the 0-100 grade —
two scales on adjacent surfaces, held apart only by scoreFormat's never-coalesce rule.

---

## Part 2 — Findings

FINDING 1:
- Title: Legacy tag path now fires "Strong RS" and "Uptrend" on EVERY row — the EC-8 rollback lane lies
- File: components/setupTagsData.js:47-49,192,197 (with components/setupScoreMath.js:15-16 and components/tagResolver.js:32-35)
- Principle: EC-8 (flag rollback must restore legacy behavior) / EC-34 (no refusing-side case) / quality-frontend P6
- Severity: P2
- What's wrong: `firesAt(scores, key, fraction)` computes its threshold as `fraction × SUB_SCORE_CAPS[key]`; the 2026-08-12 cap-pin correctly set rs_bonus/uptrend_bonus caps to 0, which turns both thresholds into `>= 0` — always true (reproduced by executing deriveTags: a row with rs_bonus 0, or absent entirely, returns ['strong_rs','uptrend']). The file's freeze note ("stale caps deliberately untouched") was falsified by the cap pin moving under it.
- Consequence: any legacy-epoch payload that carries sub_scores wears both trend chips on every card — that is exactly (a) a TA_SCORE_V2 rollback (the mechanism the dual-epoch switch exists to serve, "no frontend redeploy") and (b) a stale pre-flip screener_data.json served from disk. The chips are the operator's "why ranked" surface; universal chips are noise dressed as signal. No committed test sits on the refusing side (EC-34's exact class — the 289-test suite is green over this).
- Fix: short-circuit fraction rules whose cap is 0 to never-fire (one guard in firesAt), and add the wrong-side case; or accept the graveyard answer and delete the two demoted tag defs from TAG_DEFS now.
- Ruling-recommendation: FOLD the guard in now (smallest diff; the freeze already broke), DELETE the whole derive path at the legacy retirement.

FINDING 2:
- Title: Zone-coverage "unreadable" floor re-declared client-side, unpinned — the one live EC-28 breach
- File: components/narrativeRead.js:99-106
- Principle: EC-28 (the wire carries verdicts, never rules)
- Severity: P2
- What's wrong: `ZONE_COVERAGE_UNREADABLE = 0.5` hand-mirrors `settings.STORY_UNREADABLE_ZONE_COVERAGE` and drives the geometry caveat printed by the narrative panel AND the chapter strip. It shipped 2026-08-10, after EC-28 was ratified, using the pre-EC-28 "mirror pattern" its comment cites — and unlike SUB_SCORE_CAPS it has NO pin test (tests/test_frontend_score_caps.py pins only the caps; grep shows no test binds this constant to settings).
- Consequence: recalibrating the engine floor silently splits the engine's story-input routing from the caveat the operator reads — the panel would claim "a quiet read here is geometry" at a floor the engine no longer uses, on the surface that exists to be honest about read quality.
- Fix: serialize the resolved judgment (a boolean like event_map_zone_unreadable, or the floor itself) — EC-28's own remedy; a pin test is the fallback if the wire addition is deferred.
- Ruling-recommendation: FOLD onto the wire (backend serialization addition).

FINDING 3:
- Title: The near-trigger judgment is declared three times — and the copies already disagree on the arithmetic
- File: components/home/ActionCenter.jsx:16,89-101 · components/home/WatchlistZone.jsx:17,110-118 · components/ScreenerStockLens.jsx:43-63 · hooks/useScreenerFilters.js:151-153
- Principle: EC-3 (fold twin code paths); the seven-copies disease EC-28 documents, in a new family
- Severity: P2
- What's wrong: two separately hand-typed 2% constants (NEAR_PCT, NEAR_TRIGGER_PCT), the `live >= trigger` fired rule declared in both home zones, and a third classification vocabulary in the lens (triggerRead: -0.25/0.75/2). Worse, the denominators already diverge: the home zones compute (trigger−live)/trigger while the lens and the sort compute (trigger−price)/price — the same "% to trigger" concept prints different numbers on different surfaces today.
- Consequence: this is a live-price judgment the wire legitimately cannot resolve (prices are client-polled between scans), so it will stay client-side — which is exactly why it must live ONCE: the day one 0.02 moves, Home's two zones disagree about which names are "near trigger", on the operator's action surface.
- Fix: one shared triggerProximity module (constant + fired + distance with ONE denominator convention), consumed by all four sites — the wireVocabulary/tagFlagsFromWire precedent.
- Ruling-recommendation: FOLD.

FINDING 4:
- Title: Inline re-declarations of the house null guard
- File: components/SetupStoryPanel.jsx:38 · components/home/OpenBookZone.jsx:33-38 · components/home/WatchlistZone.jsx:184
- Principle: AGENTS.md null-safety law ("the app's ONE null guard... never re-declare it inline", council 2026-08-17); quality-frontend P1 (AHA — the drift is the cost)
- Severity: P3
- What's wrong: SetupStoryPanel's `fx1` is a hand-rolled `fx(v, 1)` missing the NaN half of the guard; OpenBookZone's `signed` re-implements the null+finite check instead of composing `finiteOrNull`; WatchlistZone:184 renders `Number(row.live).toFixed(2)` behind a null-only ternary (NaN would print "NaN"). MarketPulse/JournalPulseZone do this RIGHT (they compose finiteOrNull — the sanctioned dialect pattern), which is what makes these three the drifting copies the rule names.
- Consequence: each copy is one refactor away from the exact null-crash class the fx guard exists to end; fx1 sits on the panel the operator reads first.
- Fix: replace with fx / compose finiteOrNull; three one-line diffs.
- Ruling-recommendation: FOLD.

FINDING 5:
- Title: "Relative strength" sort is a dead control — it sorts by a term that is 0 on every live row
- File: components/ScreenerToolbar.jsx:222 + hooks/useScreenerFilters.js:144
- Principle: quality-ux P9 (a control that promises what it cannot do); the dead-knob class in the consolidation brief
- Severity: P3
- What's wrong: the sort menu still offers Relative strength, implemented as `sub_scores.rs_bonus` descending — but SCORE_RS_BONUS has been 0 since 2026-07-25, and the wire emits rs_bonus as literal 0 for every row, so the sort is a stable no-op that silently keeps engine-score order while the control claims an RS ordering.
- Consequence: the operator selects it, sees the unchanged order, and either distrusts the control or (worse) reads the unchanged order AS the RS ordering.
- Fix: remove the option (rs/uptrend were demoted on measured evidence — decisions.md), or re-point it at a live RS fact if/when one ships on the wire.
- Ruling-recommendation: DELETE the option.

FINDING 6:
- Title: TIER_RANK is a hand-typed second copy of the tier ladder
- File: utils/watchlistTable.js:11-12 (vs components/wireVocabulary.js:93)
- Principle: EC-33 (reserved vocabularies derive from ONE tuple)
- Severity: P3
- What's wrong: the tier-order map {S:0..D:4} re-types the TIER_LETTERS vocabulary as a second literal in a different module. wireVocabulary's own comment records the precedent: when D became first-class, three surfaces carrying their own S-A-B-C literal simply made D-tier rows invisible.
- Consequence: the next ladder change reaches TIER_LETTERS but not TIER_RANK, and the watchlist sort silently sinks the new letter to rank 99 (below off-scan).
- Fix: derive the rank from TIER_LETTERS.indexOf — one line.
- Ruling-recommendation: FOLD.

FINDING 7:
- Title: lpsGrade is a legacy leak inside a live V2 surface — a hard blocker on setupScoreMath's retirement
- File: components/setupStoryRows.js:70-78 (imports SUB_SCORE_CAPS from setupScoreMath.js)
- Principle: EC-28 (a number the surface needs that isn't on the wire = backend serialization addition)
- Severity: P2
- What's wrong: the fused story panel — a V2-era, live, keep-forever surface — computes its LPS percentage as sub_scores.lps_tightness ÷ the FROZEN mirror's cap. It is the one place the v2 read still depends on the legacy remnant, and it is exactly the dependency that makes "setupScoreMath retires with the legacy path" non-executable today: delete the mirror and the LPS row on every live lens goes dark.
- Consequence: the retirement is wedged behind an undeclared dependency; and until then the LPS percent is only as honest as a JS copy of a Python cap (currently pinned, but the pin retires WITH the file it pins).
- Fix: serialize the resolved LPS fraction (the engine already resolves per-term v2 points — the ta_grade_fields block in evaluation.py); then lpsGrade reads a verdict and the mirror's last live consumer is gone.
- Ruling-recommendation: FOLD onto the wire FIRST, then the mirror's deletion becomes a pure delete.

FINDING 8:
- Title: setupTagsData.js cannot be deleted as promised — the resolved path lives in the same file as the legacy rules
- File: components/setupTagsData.js:11-33,300-302 (TAG_CATALOG, GROUP_TONES/ORDER/LABELS) vs 47-49,67-279 (firesAt + TAG_DEFS fire rules)
- Principle: quality-frontend P7 (things that change together live together — and things that DIE together must, too)
- Severity: P3
- What's wrong: the file's own header promises "deletion at the flip", but TAG_CATALOG (id/label/group — what the RESOLVED path renders chips from), the group tones/order/labels (TagLegend, SetupTags), and the dynamic tooltip builders all live in the same module as the fire rules being retired. tagResolver imports both halves.
- Consequence: executing the promised deletion takes down the v2 chip rendering; not executing it keeps the dead fire rules (and finding 1's bug) alive indefinitely — the exact "parked indefinitely" disease this run exists to end.
- Fix: extract the presentational half (catalog + tones + tooltips) into the tagResolver/tagTooltips side, leaving a file that IS the legacy path and deletes clean.
- Ruling-recommendation: FOLD (extract), then DELETE the remainder with the legacy path.

FINDING 9:
- Title: Archive lens legacy dress is starved — the per-term points are ON the row, under a name the panel doesn't read
- File: components/ArchiveTab.jsx:128-149 (merge list) + components/SetupStoryPanel.jsx:272 + components/setupStoryRows.js:70
- Principle: quality-ux P2 (the data exists; the surface can't see it)
- Severity: P3
- What's wrong: the archived SetupOut row carries every term as `score_*` fields (archive_schemas.py:37-136), but the lens's legacy pills, legacy chips, and the LPS row all read `sub_scores.*` — which neither the archive chart endpoint nor the ArchiveTab merge supplies. Pre-flip archived rows therefore render permanently-dashed Visual/Market pills and no chips; even v2 archived rows lose their LPS percentage.
- Consequence: the archive review surface — where the operator judges old reads — shows less than the archive knows; honest dashes, but a standing capability gap the 2026-08-08 finding-9 fix (grade epoch rides the merge) only half-closed.
- Fix: map score_* → sub_scores in the ArchiveTab merge (a dozen-line adapter), or rule that pre-flip archive rows render headline-only and delete the starved legacy-pills branch there.
- Ruling-recommendation: KEEP-WITH-FIX — pick one of the two honestly; the current half-state is neither.

---

## Part 3 — Clean checks (verified, no findings)

- **Fetch discipline**: mechanical scan of every fetch site — all catch-handled (promise chains
  end in .catch; awaits sit in try/catch; glanceResolvers' rejections are handled by
  useHoverGlance's two-argument then; useWatchlistHistory.fetchReplay's one caller catches).
- **SSE**: useSSE.js and useScanRunner.js both keep the EventSource in a ref, close on unmount,
  and clear retry timers; visibility pause correct.
- **Stores (EC-41)**: screenerStore and watchlistCandlesStore both serve-stale-then-revalidate,
  key by generation, keep old object references on no-change arrivals, record terminal cells for
  unanswered batch names (EC-40), and never downgrade a good cell on a failed revalidate.
  watchlistStore's mutation-epoch guard is sound.
- **Case-twin trap**: scripted scan — exactly one twin pair (powerPlayRegister.js /
  PowerPlayRegister.jsx), zero ambiguous extensionless imports; HomeView imports with the
  explicit .jsx and documents why.
- **Error boundaries**: top-level ErrorBoundary in main.jsx plus granular ones (HomeView);
  StrictMode off is documented and deliberate (lightweight-charts canvases).
- **Tier vocabulary**: TIER_LETTERS is the one ladder everywhere except finding 6.
- **EC-28 elsewhere**: chapterStrip, setupStoryRows, tagResolver resolved path, narrativeRead's
  status grammar, powerPlayRegister, useWatchlistHistory grouping, watchlistChartData —
  all read resolved verdicts; marketRegimeFormat's tone cut-points are presentational tones
  (EC-28's sanctioned lookup class).
- **Frontend node suite**: 289/289 green.

Totals: 9 findings — 0 P1, 4 P2 (1, 2, 3, 7), 5 P3 (4, 5, 6, 8, 9).
