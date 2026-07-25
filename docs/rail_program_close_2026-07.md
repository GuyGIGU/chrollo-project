# Rail Program — close-out (2026-07-25)

> **PROGRAM EXECUTED 2026-07-25 — do not re-request any lever below.**
> Every experiment ran under `docs/rail_program_protocol_2026-07.md`, sealed
> BEFORE the first measurement. Every answer was NO. The evidence is
> committed and re-runnable; a re-proposal must beat the sealed protocol as
> written, and the instruments below show it cannot.

## Scoreboard

**26/33 → 26/33 (unchanged).** Fingerprint `b671e056…`, engine `aaf853bd…`,
no settings moved, no reseal, no hash rotation, no service restart needed.
The ratchet's contribution to this program was the SHIELD: three of the six
variant runs looked locally like conversions (YPF tier S! PKE tier S!) and
were exposed as election displacement, pinned-hit breakage, or junk
admission by the elections+rails diff.

## The verdict lines (one per case, sealed templates)

- **EGBN:2026-01-15** — the dwell floor cannot move to 0.125 without the
  junk band crossing the same leg (KWR ×3, BBVA-throwback ×2,
  BMRN/OHI/NVT/RLGT/GOOD candidates newly pass where EGBN's 3/23 passes with
  zero bars to spare) — EGBN stays a correct miss. *It is the ONE borderline
  in the program: fire evidence was clean (tier B, 26/26 hits kept, 18/18
  junk reject); only the sealed separation condition failed. Converting it
  is one operator ruling away (amend condition D via the protocol
  changelog) — a ruling, never a default.*
- **YPF:2026-05-18** — converts only jointly with the mid-dwell cap at 0.50,
  and that cap move breaks four pinned hits (BWA/EWTX/MS fire on different
  days; **MATX stops firing entirely**) — YPF stays a correct miss.
- **PKE:2026-02-24** — the respect floor cannot move to 0.75 without
  admitting FLG and BBVA-throwback, and PKE still misses anyway: respect
  passes, then occupancy kills it (upper-third dwell 1/22). The "one bar
  short" diagnosis is superseded — PKE is respect AND upper-third dead
  space, structural. The one-bar tolerance framing has an identical
  allowance at n=22 and was answered NO without a build.
- **NKTR:2026-04-10** — the cluster-rail statistic (outermost supported
  extreme, any k, any tolerance) is tested-DEAD: 20/66 drawn rails matched
  (needed 60) and on NKTR the cluster level EQUALS the wick anchor
  (`docs/cluster_rail_validation_2026-07.md`). The real finding: the
  operator's rail is a representative INTERIOR bar's extreme — future
  placement work must model the anchor-BAR choice. (Recorded evidence, not
  a lever: NKTR fires unpredicted at dwell floor 0.10 — a value dead on
  ratchet breakage.) NKTR stays a correct miss.
- **NOK:2026-02-17 / ORMP:2026-05-08** — out of scope by operator boundary
  (launch form dead at n=1; downstream arbitration).
- **SKYT:2026-04-13** — universe gate (below SMA50), operator strategy
  call, unchanged.

## Junk counter-cases carrying lever names (already frozen)

All named admissions are EXISTING negative-corpus members, so the tripwire
against re-proposal is already mechanical: **DGII** (mid cap 0.55 fire),
**FLG + BBVA-throwback** (respect 0.75 fires), the ten dwell-leg crossers
(dwell 0.125, listed in the margin instrument's junk table). No corpus
rebuild was needed.

## What this program leaves behind

- `docs/rail_program_protocol_2026-07.md` — the sealed constitution
  (unamended; outcome recorded in its changelog).
- `tools/rail_margin_evidence.py` — the count-distribution instrument
  (drawn / examined / elected / junk populations; self-certifying against
  the election's own trace).
- `tools/rail_margin_ab.py` — the variant grid driver (per-variant manifest
  stamps, elections+rails diff).
- `engine_alpha/structure/rail_qualification.py::cluster_rails` +
  `tools/cluster_rail_validation.py` — the tested-DEAD statistic and its
  sealed-acceptance validator (measure-only, no live caller).
- Records: `strategy_alpha.md` (margin campaign + cluster statistic
  tested-DEAD), `tools/marks_corpus.py` STAGE_TAGS comment (tags now mark
  correct misses, not pending work).

## Operator actions

None required. No engine behavior changed; nothing to restart. The one open
decision is optional: **the EGBN ruling** (accept dwell 0.125 by amending
sealed condition D — fire evidence is clean; the sealed distribution
evidence is why it was refused). Saying nothing keeps the floor where it is.
