# AR-diff re-measure, 2026-08-31

The evidence record for the re-measure owed since 2026-08-19 (`docs/asks.md` row
2026-08-22): re-run the anchor diff against the re-keyed climax so
`AR_FIRST_REACTION_ENABLED`'s 2026-09-15 kill-by is decided on current arithmetic.
Read-only. Branch `claude/queue-sweep-2026-08-30`, worktree
`.claude/worktrees/zen-satoshi-d1122d`, worktree cache `market_data_cache_5y.parquet`
dated 2026-08-28.

**What it settles:** the flip question, for the second time and now against the repaired
anchor — the retarget moved FURTHER from flag-OFF behaviour, not closer, and the re-key
itself is the dominant term in that widening. **What is left is disposal**: delete the
flag, or keep it dark purely as the anchor program's measuring instrument. The kill-by
was NOT re-dated; it stands at 2026-09-15 and deletes if unruled.

Backing artifacts, committed: the fleet scan at
[`tools/fidelity/ar_first_reaction_2026-08-31/scan_2026-08-31.txt`](../tools/fidelity/ar_first_reaction_2026-08-31/scan_2026-08-31.txt),
and the re-key isolation (script + result) in the same directory.

## Commands run

```
& "C:\Users\User\Documents\Projects\Chrollo Project\.venv\Scripts\python.exe" -m tools.ar_first_reaction_diff --scan --no-render
& "...\python.exe" -m tools.operator_marks_diff
& "...\python.exe" -m tools.operator_marks_diff --json <scratch>\operator_marks_diff_2026-08-31.json
& "...\python.exe" <scratch>\rekey_isolation.py 14      # pre-e4471e0 polarity, same cache
& "...\python.exe" <scratch>\span_stats.py <both scans> # span medians from the mover tables
```

`span_stats.py` reproduces the ledger's recorded 2026-08-13 figures exactly
(39 / 24 / 7.5 / 50 / 19 / 59) from the committed `scan_2026-08-13.txt`, which is
the validation that the two dates are being read the same way.

## Fleet scan — recorded vs now

| | 2026-08-13 (ledger) | 2026-08-31 (this run) |
|---|---|---|
| tickers scanned | 5,511 | 5,533 |
| survive baseline | 1,758 | 1,551 |
| fire (have an overlay) | 291 | 335 |
| **overlays that re-anchor** | **100 of 291** (34.4%) | **101 of 335** (30.1%) |
| OFF span median | 39 (24 of 100 at >=58) | **47** (27 of 101 at >=58) |
| ON span median | 7.5 (50 of 100 at <=7) | **5** (62 of 101 at <=7) |
| tighten median / max | 19 / 59 | **35** / 59 |
| tighten total | 2,365 | **3,149** |
| old_span == 60 exactly (the lead-in ceiling) | 11 | 14 |
| OFF span quartiles | 20.2 / 39 / 57 | 26.5 / 47 / 58 |
| tighten quartiles | 8 / 19 / 37 | 9.5 / 35 / 47.5 |

Direction: the smear the flag proposes to fix is BIGGER than recorded, and the
flag's correction is correspondingly BIGGER. The retarget is therefore FURTHER
from flag-OFF behaviour than it was, not closer.

## The marks side — `tools.operator_marks_diff`, today

```
THE FLIP QUESTION — distance from the operator's own AR (7 names)
  flag OFF total |error| : 148 bars   closer on 2 of 7
  flag ON  total |error| : 168 bars   closer on 5 of 7
THE ANCHOR QUESTION (operator-typed dates only)
  segment_trends holds a terminal within 3 bars of his trend end : 2 of 9
  resolved climax EARLIER than his trend end : 5 of 7 (median -18 bars)
  drawn OFF ar_bar == box.start_bar : 5 of 6 live reads
```

vs 2026-08-14 (pre-re-key): |off| 133 closer on 4 of 6; |on| 266 closer on 2 of 6;
climax earlier 6 of 6, median -50.5.

### The "closer on 5 of 7" headline over-reads

`report()` computed `wins_off = abs(d_ar_off) < abs(d_ar_on)` and printed the
complement as the ON column, so **ties landed in the ON column** — the tool credited
the flag with wins on names where it moves nothing. Today three of the seven are ties
(the flag is a no-op on them): CYRX -5/-5, BCPC -33/-33, CNI -2/-2. **FIXED in the same
change as this record**: `tools/operator_marks_diff.py` now counts OFF wins, ON wins and
ties separately and prints all three, so the printed line can no longer overstate either
side.
Head-to-head on the four names where the flag actually moves:

| ticker | src | OFF | ON |
|---|---|---|---|
| CATO | recorded | 40 | **18** |
| EC | live | **6** | 65 |
| HTH | recorded | 50 | **4** |
| LZB | recorded | **12** | 41 |
| total | | **108** | 128 |

2 apiece on count; OFF ahead on total. And **only EC is a live read** — CATO/HTH/LZB
fell out of universe today, so the tool honestly falls back to the dates recorded
in the corpus, which were captured on 2026-08-13, i.e. PRE-re-key. Their rows are
not current arithmetic. On the live re-keyed reads the flag is a no-op on three
names and loses badly on the fourth (EC, 6 vs 65).

Also: 8 of the 15 marks are baseline-gated out of universe today (IRMD IART CATO
HTH LZB AMH INVH NRIM). The marks cohort has thinned since the ruling; it was
already 9 uncertified marks the operator declined to certify.

## Mechanism check

- `drawn OFF ar_bar == box.start_bar` still holds on 5 of 6 live reads (was 9/9).
  The one exception is BCPC (AR 2026-01-02 vs box open 2026-01-14).
- The climax is still EARLIER than his trend end more often than not (5 of 7,
  median -18), so the mechanism the 2026-08-14 ruling named survives the re-key —
  weakened but not overturned.
- 14 of 101 movers sit at `old_span == 60` exactly, the `_SEG_LEAD_IN` ceiling, and
  27 at >=58: the drawn climax is still frequently the fixed-window artefact the
  2026-08-19 diagnosis described. The re-key changed WHICH END of the window is
  taken; the window itself is untouched, and that is what the span figures show.

## Confound to state plainly

The 2026-08-13 -> 2026-08-31 fleet delta is NOT the re-key alone. Between those
dates the cache refreshed (universe 5,511 -> 5,533, survivors 1,758 -> 1,551) and
the engine took many live changes: the re-key `e4471e0`, the Power Play preset
flip in the same commit, the pivot-absorption fix `91adf9e`, NaN fail-closed
`a49f9af`, the ONE-vocabulary projection, the legacy score-path retirement. The
`rekey_isolation.py` run separates the re-key term alone, on ONE cache.

## Blast radius if the flag is DELETED (paths)

Engine:
- `config/settings.py` — `AR_FIRST_REACTION_ENABLED` + the four knobs only it reads
  (`AR_RETRACE_FRAC`, `AR_UP_LEG_LOOKBACK`, `AR_BOUNCE_ATR_MULT`, `AR_BOUNCE_DROP_FRAC`)
  and their 18-line comment block.
- `engine_alpha/structure/bricks.py` — `_first_impulse_ar_end()`, its call site in
  `resolve_phase_a()`, and the `first_reaction_after` import.
- `engine_alpha/structure/market_structure.py` — `first_reaction_after()` and
  `elected_trend_leg_base()` become ENGINE-ORPHANS (their only engine consumer is
  `_first_impulse_ar_end`; after deletion only `tools/full_package_render.py` reads
  them). Keep or remove is a second decision.
- `engine_alpha/freeze/manifest.py` — five rows; removing them is a manifest rotation.
- `engine_alpha/structure/phase_a.py`, `engine_alpha/structure/segmentation.py` —
  docstring pointers.

Tools:
- `tools/ar_first_reaction_diff.py` — the whole tool (its reason to exist is the flag).
- `tools/operator_marks_diff.py` — `_read_under()` + the entire "THE FLIP QUESTION"
  section; the ANCHOR QUESTION half survives.
- `tools/full_package_render.py` — the AR on/off overlay and its two status lines.
- `tools/fidelity/ar_first_reaction_2026-08-13/` — README + scan txt (renders already
  untracked by the 2026-08-20 bloat ruling).

Tests:
- `tests/test_bricks.py` (2 monkeypatch sites + the first-impulse cases),
  `tests/test_market_structure.py` (13 lines across the `first_reaction_after` /
  `elected_trend_leg_base` block), `tests/test_analyze_anchor_seam.py` (docstring
  reference only — the seam itself stays, the climax-terminality repair alone
  justifies `PHASE_A_ANCHOR_FEATURES`).

Docs (chair-owned):
- `docs/flag_ledger.md` row -> Retired; `docs/engine_reference.md` "Phase A —
  First-reaction AR anchor" section; `docs/strategy_alpha.md` two mentions;
  `docs/decisions.md` a new ruling row; `docs/asks.md` close the 2026-08-22 row.
- `core/archive/analyze.py` comment cites "100 of 291, measured 2026-08-13" — the
  partition stays either way, the sentence needs the new number or a delete note.

## Stale numbers spotted — ALL THREE FIXED in the same change as this record

- `engine_alpha/freeze/manifest.py:78` — "a flip re-anchors the drawn AR on 19/140
  fires". That is the 2026-07-05 figure; measured today it is 101/335.
- `core/archive/analyze.py:175` — "100 of 291 firing overlays, measured 2026-08-13";
  today 101 of 335. Date-stamped, so honest, but superseded.
- `docs/strategy_alpha.md` known-gap note still quotes "climax earlier on 6 of 6,
  median -50.5", the PRE-re-key figure. The re-key (2026-08-19) moved it and the
  note was not updated in that change; today's run reads 5 of 7, median -18.

## The re-key isolated — ONE cache, one prep, only `bricks._cause_is_up` differs

`rekey_isolation.py` monkeypatches the pre-`e4471e0` polarity (root.kind BC/SC only)
into the pool workers and re-runs the identical capture. Nothing in the repo changed.

| | legacy polarity (pre-e4471e0) | current (re-keyed) |
|---|---|---|
| fire (have an overlay) | 335 | 335 (identical — the repair is overlay-only, it cannot move an election) |
| **overlays that re-anchor** | **121** | **101** |
| OFF span median | 40 (22 at >=58) | 47 (27 at >=58) |
| ON span median | 7 (69 at <=7) | 5 (62 at <=7) |
| tighten median / max | 22 / 59 | 35 / 59 |
| tighten total | 3,080 | 3,149 |
| old_span == 60 exactly | 12 | 14 |
| OFF span mean | 36.5 | 40.0 |

Mover-set churn: only **69 of the movers are shared**; 32 move only under the
re-keyed climax, 52 only under the legacy one. On 15 of the 69 shared movers the
OFF span itself differs, in both directions and by a lot (JOE 58 -> 8, STRA 40 -> 4,
DMRA 29 -> 3 vs VZ 23 -> 60, DFIN 27 -> 60, CQP 17 -> 58).

**Attribution of the 2026-08-13 -> 2026-08-31 drift.** Tighten median 19 (recorded)
-> 22 (legacy polarity on today's cache) -> 35 (re-keyed): cache + other live engine
changes account for +3, the re-key for +13. OFF span median 39 -> 40 -> 47: +1 then
+7. **The re-key is the dominant term in the widening**, which is the honest answer
to the ask.

**Two-sided reading, stated because it is the fair one.** The re-key made the flag
apply to FEWER charts (121 -> 101, -16.5%) — the drawn AR is smeared less often —
but on the charts where it still applies the two reads disagree by MORE (tighten
median 22 -> 35). Net: the retarget is FURTHER from flag-OFF behaviour than before,
not closer.
