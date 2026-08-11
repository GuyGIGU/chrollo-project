# heal_evidence summary — scan_date repair evidence map

Generated 2026-08-11T23:55:26 | in-scope archive rows: 7476 | cohorts: 86
Price column used as scan_close: `current_price` (engine writes `round(latest Close, 2)`), tolerance 0.1% rel with a $0.0051 absolute floor for the 2dp rounding.
Cache last session: us_equities=2026-08-10, us_sectors=2026-08-10

## Verdict distribution (cohorts)
- **prev**: 46 cohorts, 5457 rows
- **stamp**: 27 cohorts, 242 rows
- **AMBIGUOUS**: 9 cohorts, 1479 rows
- **NO_EVIDENCE**: 4 cohorts, 298 rows

Row votes overall: prev=5331, stamp=349, both=292, neither=1504
Decisive votes: 5680; majority-side agreement rate: 97.8873%

## Cohort table

| scan_date | universe | n | prev | stamp | both | neither | verdict | target | sources |
|---|---|---|---|---|---|---|---|---|---|
| 2026-01-16 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-01-16 | seed:1 |
| 2026-01-28 | us_equities | 3 | 0 | 2 | 0 | 1 | stamp | 2026-01-28 | seed:3 |
| 2026-01-30 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-01-30 | seed:1 |
| 2026-02-11 | us_equities | 2 | 0 | 2 | 0 | 0 | stamp | 2026-02-11 | seed:2 |
| 2026-02-13 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-02-13 | seed:1 |
| 2026-02-17 | us_equities | 2 | 0 | 2 | 0 | 0 | stamp | 2026-02-17 | seed:2 |
| 2026-02-20 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-02-20 | seed:1 |
| 2026-02-23 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-02-23 | seed:1 |
| 2026-02-24 | us_equities | 2 | 0 | 1 | 0 | 1 | stamp | 2026-02-24 | seed:2 |
| 2026-02-25 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-02-25 | seed:1 |
| 2026-02-26 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-02-26 | seed:1 |
| 2026-03-02 | us_equities | 2 | 0 | 1 | 0 | 1 | stamp | 2026-03-02 | seed:2 |
| 2026-03-10 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-10 | seed:1 |
| 2026-03-13 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-13 | seed:1 |
| 2026-03-16 | us_equities | 2 | 0 | 2 | 0 | 0 | stamp | 2026-03-16 | seed:2 |
| 2026-03-17 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-17 | seed:1 |
| 2026-03-18 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-18 | seed:1 |
| 2026-03-19 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-19 | seed:1 |
| 2026-03-27 | us_equities | 1 | 0 | 0 | 0 | 1 | NO_EVIDENCE | — | seed:1 |
| 2026-03-30 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-03-30 | seed:1 |
| 2026-03-31 | us_equities | 2 | 0 | 2 | 0 | 0 | stamp | 2026-03-31 | seed:2 |
| 2026-04-02 | us_equities | 3 | 0 | 2 | 0 | 1 | stamp | 2026-04-02 | seed:3 |
| 2026-04-06 | us_equities | 1 | 0 | 0 | 1 | 0 | NO_EVIDENCE | — | seed:1 |
| 2026-04-07 | us_equities | 2 | 0 | 1 | 0 | 1 | stamp | 2026-04-07 | seed:2 |
| 2026-04-09 | us_equities | 2 | 0 | 2 | 0 | 0 | stamp | 2026-04-09 | seed:2 |
| 2026-04-10 | us_equities | 4 | 0 | 4 | 0 | 0 | stamp | 2026-04-10 | seed:4 |
| 2026-04-16 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-04-16 | seed:1 |
| 2026-04-24 | us_equities | 1 | 0 | 1 | 0 | 0 | stamp | 2026-04-24 | manual:1 |
| 2026-06-01 | us_equities | 152 | 3 | 25 | 0 | 124 | AMBIGUOUS | — | screener:152 |
| 2026-06-02 | us_equities | 152 | 23 | 4 | 2 | 123 | AMBIGUOUS | — | screener:152 |
| 2026-06-03 | us_equities | 247 | 53 | 8 | 3 | 183 | AMBIGUOUS | — | screener:247 |
| 2026-06-04 | us_equities | 198 | 9 | 5 | 0 | 184 | AMBIGUOUS | — | screener:198 |
| 2026-06-05 | us_equities | 242 | 10 | 11 | 2 | 219 | AMBIGUOUS | — | screener:242 |
| 2026-06-08 | us_equities | 81 | 24 | 49 | 8 | 0 | AMBIGUOUS | — | screener:81 |
| 2026-06-15 | us_equities | 30 | 28 | 0 | 1 | 1 | prev | 2026-06-12 | screener:29,seed:1 |
| 2026-06-16 | us_equities | 114 | 9 | 10 | 1 | 94 | AMBIGUOUS | — | screener:114 |
| 2026-06-17 | us_equities | 146 | 85 | 3 | 7 | 51 | prev | 2026-06-16 | screener:146 |
| 2026-06-18 | us_equities | 97 | 88 | 0 | 6 | 3 | prev | 2026-06-17 | screener:97 |
| 2026-06-22 | us_equities | 120 | 108 | 0 | 7 | 5 | prev | 2026-06-18 | screener:120 |
| 2026-06-23 | us_equities | 110 | 104 | 0 | 5 | 1 | prev | 2026-06-22 | screener:110 |
| 2026-06-24 | us_equities | 127 | 116 | 0 | 7 | 4 | prev | 2026-06-23 | screener:127 |
| 2026-06-25 | us_equities | 136 | 46 | 81 | 4 | 5 | AMBIGUOUS | — | screener:136 |
| 2026-06-26 | us_equities | 85 | 81 | 0 | 3 | 1 | prev | 2026-06-25 | screener:85 |
| 2026-06-29 | us_equities | 84 | 79 | 0 | 5 | 0 | prev | 2026-06-26 | screener:84 |
| 2026-06-30 | us_equities | 51 | 47 | 0 | 4 | 0 | prev | 2026-06-29 | screener:51 |
| 2026-07-02 | us_equities | 157 | 42 | 5 | 0 | 110 | AMBIGUOUS | — | screener:157 |
| 2026-07-06 | us_equities | 201 | 2 | 111 | 12 | 76 | stamp | 2026-07-06 | screener:201 |
| 2026-07-07 | us_equities | 124 | 121 | 1 | 2 | 0 | prev | 2026-07-06 | screener:123,seed:1 |
| 2026-07-08 | us_equities | 127 | 121 | 0 | 6 | 0 | prev | 2026-07-07 | screener:127 |
| 2026-07-08 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-07 | screener:2 |
| 2026-07-09 | us_equities | 183 | 171 | 0 | 9 | 3 | prev | 2026-07-08 | screener:183 |
| 2026-07-09 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-08 | screener:2 |
| 2026-07-10 | us_equities | 205 | 188 | 0 | 13 | 4 | prev | 2026-07-09 | screener:205 |
| 2026-07-10 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-09 | screener:2 |
| 2026-07-14 | us_equities | 265 | 252 | 0 | 11 | 2 | prev | 2026-07-13 | screener:265 |
| 2026-07-14 | us_sectors | 2 | 1 | 0 | 1 | 0 | prev | 2026-07-13 | screener:2 |
| 2026-07-15 | us_equities | 299 | 284 | 0 | 13 | 2 | prev | 2026-07-14 | screener:299 |
| 2026-07-15 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-14 | screener:2 |
| 2026-07-16 | us_equities | 279 | 272 | 0 | 6 | 1 | prev | 2026-07-15 | screener:279 |
| 2026-07-16 | us_sectors | 4 | 2 | 0 | 2 | 0 | prev | 2026-07-15 | screener:4 |
| 2026-07-17 | us_sectors | 3 | 3 | 0 | 0 | 0 | prev | 2026-07-16 | screener:3 |
| 2026-07-20 | us_equities | 234 | 219 | 0 | 15 | 0 | prev | 2026-07-17 | screener:234 |
| 2026-07-22 | us_equities | 305 | 292 | 0 | 13 | 0 | prev | 2026-07-21 | screener:305 |
| 2026-07-22 | us_sectors | 4 | 4 | 0 | 0 | 0 | prev | 2026-07-21 | screener:4 |
| 2026-07-23 | us_equities | 292 | 278 | 0 | 14 | 0 | prev | 2026-07-22 | screener:292 |
| 2026-07-23 | us_sectors | 4 | 4 | 0 | 0 | 0 | prev | 2026-07-22 | screener:4 |
| 2026-07-24 | us_equities | 332 | 314 | 0 | 18 | 0 | prev | 2026-07-23 | screener:332 |
| 2026-07-24 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-23 | screener:2 |
| 2026-07-28 | us_equities | 257 | 246 | 0 | 10 | 1 | prev | 2026-07-27 | screener:257 |
| 2026-07-28 | us_sectors | 4 | 4 | 0 | 0 | 0 | prev | 2026-07-27 | screener:4 |
| 2026-07-29 | us_equities | 205 | 195 | 0 | 10 | 0 | prev | 2026-07-28 | screener:205 |
| 2026-07-29 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-28 | screener:2 |
| 2026-07-30 | us_equities | 193 | 184 | 0 | 9 | 0 | prev | 2026-07-29 | screener:193 |
| 2026-07-31 | us_equities | 202 | 185 | 0 | 17 | 0 | prev | 2026-07-30 | screener:202 |
| 2026-07-31 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-07-30 | screener:2 |
| 2026-08-04 | us_equities | 191 | 180 | 0 | 7 | 4 | prev | 2026-08-03 | screener:191 |
| 2026-08-04 | us_sectors | 1 | 1 | 0 | 0 | 0 | prev | 2026-08-03 | screener:1 |
| 2026-08-05 | us_equities | 202 | 195 | 0 | 7 | 0 | prev | 2026-08-04 | screener:202 |
| 2026-08-05 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-08-04 | screener:2 |
| 2026-08-06 | us_equities | 180 | 171 | 0 | 8 | 1 | prev | 2026-08-05 | screener:180 |
| 2026-08-06 | us_sectors | 1 | 1 | 0 | 0 | 0 | prev | 2026-08-05 | screener:1 |
| 2026-08-07 | us_equities | 236 | 223 | 0 | 13 | 0 | prev | 2026-08-06 | screener:236 |
| 2026-08-07 | us_sectors | 2 | 2 | 0 | 0 | 0 | prev | 2026-08-06 | screener:2 |
| 2026-08-10 | us_equities | 255 | 245 | 0 | 10 | 0 | prev | 2026-08-07 | screener:255 |
| 2026-08-11 | us_equities | 294 | 0 | 0 | 0 | 294 | NO_EVIDENCE (advisory: prev) | — | screener:294 |
| 2026-08-11 | us_sectors | 2 | 0 | 0 | 0 | 2 | NO_EVIDENCE (advisory: prev) | — | screener:2 |

## AMBIGUOUS: 9 cohorts, NO_EVIDENCE: 4 cohorts
- NO_EVIDENCE: 2026-03-27 us_equities n=1
- NO_EVIDENCE: 2026-04-06 us_equities n=1
- AMBIGUOUS: 2026-06-01 us_equities votes={'prev': 3, 'stamp': 25, 'both': 0, 'neither': 124}
- AMBIGUOUS: 2026-06-02 us_equities votes={'prev': 23, 'stamp': 4, 'both': 2, 'neither': 123}
- AMBIGUOUS: 2026-06-03 us_equities votes={'prev': 53, 'stamp': 8, 'both': 3, 'neither': 183}
- AMBIGUOUS: 2026-06-04 us_equities votes={'prev': 9, 'stamp': 5, 'both': 0, 'neither': 184}
- AMBIGUOUS: 2026-06-05 us_equities votes={'prev': 10, 'stamp': 11, 'both': 2, 'neither': 219}
- AMBIGUOUS: 2026-06-08 us_equities votes={'prev': 24, 'stamp': 49, 'both': 8, 'neither': 0}
- AMBIGUOUS: 2026-06-16 us_equities votes={'prev': 9, 'stamp': 10, 'both': 1, 'neither': 94}
- AMBIGUOUS: 2026-06-25 us_equities votes={'prev': 46, 'stamp': 81, 'both': 4, 'neither': 5}
- AMBIGUOUS: 2026-07-02 us_equities votes={'prev': 42, 'stamp': 5, 'both': 0, 'neither': 110}
- NO_EVIDENCE: 2026-08-11 us_equities n=294 — stamped date is beyond the cache's last session (2026-08-10) so no D bar can exist; 294/294 rows match P exactly
- NO_EVIDENCE: 2026-08-11 us_sectors n=2 — stamped date is beyond the cache's last session (2026-08-10) so no D bar can exist; 2/2 rows match P exactly

## Exceptions: 1927 entries
Reasons: price_mismatch=1166, no_bar_D=296, ambiguous_cohort_vote_prev=219, ambiguous_cohort_vote_stamp=198, no_ticker=42, minority_vote_stamp=4, minority_vote_prev=2

## price_mismatch diagnostic (cohorts with >=10 mismatches)

`in_range_D only` = scan_close sits inside D's intraday Low..High but not P's 
(evidence of a PARTIAL/forming bar of session D — data day IS the stamp, price is
mid-session); `match_P2` = scan_close equals the close two sessions back
(provider session-lag).

| scan_date | universe | mismatches | D-range only | P-range only | both ranges | neither range | match P2 |
|---|---|---|---|---|---|---|---|
| 2026-06-01 | us_equities | 123 | 85 | 0 | 37 | 1 | 0 |
| 2026-06-02 | us_equities | 122 | 0 | 43 | 78 | 1 | 2 |
| 2026-06-03 | us_equities | 181 | 60 | 0 | 120 | 1 | 14 |
| 2026-06-04 | us_equities | 184 | 0 | 72 | 111 | 1 | 8 |
| 2026-06-05 | us_equities | 214 | 50 | 36 | 124 | 4 | 6 |
| 2026-06-16 | us_equities | 92 | 34 | 0 | 58 | 0 | 4 |
| 2026-06-17 | us_equities | 49 | 0 | 16 | 33 | 0 | 3 |
| 2026-07-02 | us_equities | 110 | 42 | 0 | 68 | 0 | 2 |
| 2026-07-06 | us_equities | 76 | 0 | 42 | 34 | 0 | 5 |

## Reading the messy cohorts (evidence-backed interpretation)

- All Jan-Apr 'stamp' cohorts are source=seed (plus one manual): deliberately backdated evaluations whose stamp IS the true session. They must NOT be shifted.
- 2026-07-06 us_equities is a genuine screener 'stamp' cohort (111/113 decisive match D): a Monday-evening rescan upserted final 07-06 closes over an earlier weekend write; its 76 price_mismatch rows are remnants of that weekend write carrying PARTIAL (forming) 07-02 bars - 42 of them sit inside P's intraday range only.
- The 9 AMBIGUOUS cohorts (2026-06-01..06-08, 06-16, 06-25, 07-02) date from the forming-bar cache era (later fixed): scan_close is a mid-session price, so it matches no final close. The mismatch_diagnostic tells WHICH session's intraday range holds it: 06-01 = intraday of D (stamp is the true day); 06-02/06-04 = intraday of P (nightly shift + partial bar); 06-03/06-05/06-08/06-25/07-02 = genuine mixes of two upserted write events - these need row-grain surgery or an operator ruling, not a cohort shift.
- Spot-check (hand-verified against raw cache bars): XMAX/GNK 2026-07-22 match P exactly; MEOH 2026-06-01 61.55 sits inside 06-01's range [60.18,61.70] and outside 05-29's; seed TRS 2026-01-28 equals its stamped close exactly; GFS stamped 2026-07-06 (76.73) sits inside 07-02's range only.
- The two 2026-08-11 cohorts vote all-neither ONLY because the cache's last session is 2026-08-10 (no D bar can exist); every row matches P exactly -> advisory verdict 'prev' (see advisory field).

## read_verdicts / setup_reviews re-point map
- read_verdicts: 2 rows, 1 key-match a shifting cohort, 1 sit on an excluded non-trading date (rows being deleted separately).
  - rv#1 LEVI 2026-08-08/us_equities verdict=agree excluded_date=True will_shift=False target=None
  - rv#2 AAP 2026-08-10/us_equities verdict=agree excluded_date=False will_shift=True target=2026-08-07
- setup_reviews: 37 rows (table has NO universe_type; matched on scan_date alone), 27 match a shifting cohort, 6 sit on an excluded non-trading date.
  - sr#1 EGBN 2026-06-03 excluded_date=False will_shift=False [us_equities=AMBIGUOUS]
  - sr#2 XMAX 2026-06-18 excluded_date=False will_shift=True [us_equities=prev]
  - sr#3 MG 2026-06-21 excluded_date=True will_shift=False [no cohort]
  - sr#4 PKBK 2026-06-18 excluded_date=False will_shift=True [us_equities=prev]
  - sr#5 LFUS 2026-06-18 excluded_date=False will_shift=True [us_equities=prev]
  - sr#6 MYRG 2026-06-18 excluded_date=False will_shift=True [us_equities=prev]
  - sr#7 TTI 2026-06-14 excluded_date=True will_shift=False [no cohort]
  - sr#8 EIX 2026-06-18 excluded_date=False will_shift=True [us_equities=prev]
  - sr#9 MXF 2026-06-21 excluded_date=True will_shift=False [no cohort]
  - sr#10 MPLX 2026-06-25 excluded_date=False will_shift=False [us_equities=AMBIGUOUS]
  - sr#11 AYA 2026-07-09 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#12 IX 2026-07-08 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#13 NSA 2026-07-09 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#14 ISSC 2026-07-09 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#15 MSGE 2026-07-11 excluded_date=True will_shift=False [no cohort]
  - sr#16 AMBQ 2026-07-11 excluded_date=True will_shift=False [no cohort]
  - sr#17 MOV 2026-07-02 excluded_date=False will_shift=False [us_equities=AMBIGUOUS]
  - sr#18 CTOS 2026-07-18 excluded_date=True will_shift=False [no cohort]
  - sr#19 SAN 2026-07-14 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#20 PSTL 2026-07-10 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#21 DHX 2026-06-25 excluded_date=False will_shift=False [us_equities=AMBIGUOUS]
  - sr#22 AMD 2026-07-24 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#23 ICHR 2026-07-24 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#24 IMVT 2026-07-22 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#25 ARKO 2026-07-24 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#26 BIIB 2026-07-22 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#27 PII 2026-07-22 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#28 PBI 2026-07-23 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#29 CGEM 2026-07-22 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#30 MIDD 2026-07-28 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#31 FLNG 2026-07-22 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#32 EWBC 2026-07-23 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#33 RLYB 2026-07-30 excluded_date=False will_shift=True [us_equities=prev]
  - sr#34 GIII 2026-07-28 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#35 AAP 2026-07-30 excluded_date=False will_shift=True [us_equities=prev]
  - sr#36 VTMX 2026-07-28 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]
  - sr#38 FXNC 2026-08-07 excluded_date=False will_shift=True [us_equities=prev; us_sectors=prev]

---

## Executed 2026-08-12 00:2x IL (tools/heal_scan_dates_2026_08.py --defer-ambiguous --apply)

Operator ruling 2026-08-11: "purge & heal". Root fix merged same day (306c34c —
scan_date now copies the panel's last bar, EC-37). This surgery healed the legacy rows:

- **Purged 2,905** screener rows on 16 non-trading dates (weekends + 2026-07-03 observed
  holiday). The 17th census date, 2026-02-01, is a lone SEED row (ST, LPS/A) — an operator
  hand-dating slip (Sunday), exempt from the heal, left for the operator to re-date.
- **Shifted 4,807** screener rows across 39 cohorts to their evidenced true session
  (previous trading session of the stamp). Seed/manual rows exempt everywhere.
- **Merged-out 124** same-session duplicates (incumbent wins): the 2026-07-07 cohort
  overlapping the stamp-true 2026-07-06 evening-rescan cohort, plus row-level collisions
  with seed rows sitting on target dates.
- **Re-pointed 1 read_verdict** (AAP 2026-08-10 → 2026-08-07) and **22 setup_reviews**
  with their rows. LEVI's verdict on purged 2026-08-08 rows stays as an accepted orphan
  (2026-08-05 ruling).
- **Deferred 2,299 rows** (9 AMBIGUOUS June forming-bar-era cohorts + 8 cascade-blocked
  neighbors, 2026-06-01..06-30 + 07-02): mixed write-events that cannot be cohort-shifted;
  row-grain surgery awaits an operator ruling. Their labels remain stamp+1.
- Rows after: **7,353** (10,382 − 2,905 − 124), zero screener rows on non-trading dates,
  zero duplicate (ticker, scan_date, universe_type) keys.
- Backup: `webapp/backend/trading_journal.pre_scan_date_heal_2026-08-11.db`.
- Forward returns re-matured against the corrected dates:
  `python -m core.archive.forward_returns --min-age 0 --force`.

Seam note: edge reads spanning the deferred June block mix true-session labels
(post-heal) with stamp+1 labels (deferred cohorts). Within-cohort comparisons are
unaffected; absolute-date joins against June should mind the seam.
