# The operator's trend-end marks, and what they rule — 2026-08-14

The operator was asked two things on 2026-08-13: eyeball the twelve
`AR_FIRST_REACTION_ENABLED` renders and rule the flip, and supply dated
trend-end labels to unblock `TREND_TERMINAL_BOX_GATE_ENABLED`. On 2026-08-14 he
answered both at once — three hand-drawn charts (IRMD, IART, CYRX) and a written
ruling on nine of the twelve renders.

The marks themselves are recorded, append-only, in
[`trend_end_marks_2026-08.json`](trend_end_marks_2026-08.json). This document is
what they measure against the engine, and the two rulings that follow.

## What he actually marks

> "The point of this is finding the Last 'Trending' Before the Consolidation
> starts and that's why they go hand in hand."

Not two independent events — one transition **zone**: the last trend peak, and
the low a handful of bars later where the base opens. On the three hand-drawn
charts he states the identity outright: the AR low **is** the root swing **is**
where the consolidation starts. On AMH and INVH he points at a single engine dot
and calls it the climax *and* the consolidation start.

His climax→AR spans are **1, 2, 2, 2, 3, 4, 5, 5, 5 bars**. Nine marks, none
wider than a trading week.

He also declined to give a clean verdict, and the reason is recorded because it
bounds how hard these may be leaned on:

> "there isn't one concrete answer Im 100% sure is correct, their just very ugly
> structures (most of them) so i cant be sure"

## The measurement

Faithful live read on the 2026-08-13 cache (`apply_baseline_filters` →
`_trim_to_period` → `read_structure`), captured with the flag off and on. Six of
the nine dated names have both reads computable; distances are in bars, signed
against his own AR mark.

| ticker | his trend end | his AR | engine climax | Δ climax | AR **off** | Δ | AR **on** | Δ |
|---|---|---|---|---|---|---|---|---|
| BCPC | 2026-02-17 | 2026-02-20 | 2025-10-17 | −82 | 2026-01-14 | **25** | 2025-10-21 | 83 |
| CATO | 2025-11-24 | 2025-11-26 | 2025-10-29 | −18 | 2026-01-27 | 40 | 2025-10-31 | **18** |
| CNI | 2026-07-17 | 2026-07-21 | 2026-04-29 | −54 | 2026-07-21 | **0** | 2026-04-30 | 55 |
| EC | 2026-06-01 | 2026-06-08 | 2026-03-04 | −61 | 2026-05-29 | **6** | 2026-03-05 | 65 |
| HTH | 2026-04-09 | 2026-04-15 | 2026-03-31 | −6 | 2026-06-26 | 50 | 2026-04-09 | **4** |
| LZB | 2026-06-17 | 2026-06-18 | 2026-04-10 | −47 | 2026-07-08 | **12** | 2026-04-21 | 41 |

Totals: **|off| = 133 bars, |on| = 266 bars.** Median 18.5 vs 48. The flag-off
drawing is closer to his mark on four of six.

## Ruling 1 — `AR_FIRST_REACTION_ENABLED` stays DARK

**Do not flip.** On the operator's own marks the retarget is roughly twice as far
from his AR as what is already drawn, on the cohort deliberately selected to be
where the flag moves the most (these twelve renders are the twelve largest
tighteners in the universe). A cohort chosen to flatter the proposal does not.

The mechanism matters more than the verdict, because it is not "the retarget is
badly built":

- The raw fallback pins `ar_bar` to `box.start_bar` — measured on every one of
  the nine names that fire, the drawn AR **is** the box open, exactly.
- The operator's AR **is also the box open**, by his own definition. He says so
  three times: the AR low is the root swing is where the consolidation starts.
- So the off-drawing satisfies his identity *by construction*, and is right for
  a reason that has nothing to do with reading a reaction.
- The retarget breaks that identity. It re-attaches the AR to a short reaction
  off `climax_bar` — which is the correct Wyckoff move, and would be the right
  answer if `climax_bar` were the trend end. It is not.

The retarget's **shape** is nonetheless vindicated: its spans are 1–7 bars
against his 1–5. It measures the right kind of object. It measures it from the
wrong place.

Its span is right and its anchor is wrong, so flipping it trades an accidentally
correct drawing for a principled incorrect one. The flag's blocking condition
changes from "awaiting the operator's eye" to **"blocked on the climax anchor"**
— it cannot be ruled on its own merits until `climax_bar` lands on a trend end.

## Ruling 2 — the box gate's 2026-07-28 ruling is corroborated

`TREND_TERMINAL_BOX_GATE_ENABLED` was ruled DO-NOT-FLIP on 2026-07-28 on the
grounds that `segment_trends` is box-blind. That ruling existed only in an agent
memory, with no row in this repo — which is how a later session came to tell the
operator the gate was still unruled.

His fresh 2026-08-14 label for IRMD is **2026-06-10**, identical to the date
recorded in that memory, produced independently three weeks later from a chart
he drew by hand. The memory is faithful. A `decisions.md` row is appended today.

## The defect both rulings point at

`segment_trends` holds a terminal within 3 bars of his trend end on **2 of 9**
dated marks. And the engine's `climax_bar` is earlier than his trend end on
**6 of 6** measurable names — never once later. Median error −50.5 bars. That is a
directional bias, not scatter.

Two distinct failures, and they need separating before anything is built:

**(a) The pivot isn't found.** On IRMD, IART, CYRX, CNI, EC, HTH, CATO the peak
he marks is not in the pivot set at all. `segment_trends` elects
`terminal_bar` as a segment's extreme pivot, so a later upthrust to the box's own
R — a higher high, but one the operator reads as *inside* the consolidation —
swallows the true trend end and drags the terminal forward into the base. This is
the same box-blind mechanism already measured from the other side on 2026-08-13
(9 of 9 contested terminals above the box's own R).

**(b) The pivot is found and Phase A cannot reach it.** On BCPC and LZB his
terminal *is* in the pivot set — BCPC to the bar, both of his marks. Phase A
anchors months earlier anyway, because the elected box opens before his trend
end and the chronological invariant `ar_bar <= box.start_bar` forbids Phase A
from reaching forward into it.

(b) is the more interesting failure, because no amount of work on the trend
reader fixes it. On those names the **box** is the binding constraint, and the
operator's own note is the consolation: *"on most of these the engine knows how
to read the consolidation starting formation box correctly."*

## Open

- **Nine dated marks is a direction of travel, not an acceptance set** — and the
  operator explicitly declined to certify them. Do not seal a gate against this
  file. More marks on *clean* structures would be worth more than more marks on
  these; he called most of this cohort ugly and said so unprompted.
- NRIM, SFL and OXY were not ruled.
- IRMD and CYRX are out of universe today (both fail the `sma50` baseline gate),
  so their marks cannot currently be checked against a live `read_structure`.
- Whether (a) and (b) are one program or two is unruled.

## Re-measure

Every figure above is reproduced by one command, reading the marks corpus
directly, so this document cannot quietly go stale the way the 2026-07-27
eyeball sheet did:

```
python -m tools.operator_marks_diff
```

Two cautions it prints for itself. Elections are not stable day to day — a name
that fired when the marks were taken may not fire today, and those fall back to
the dates recorded in the corpus, labelled `recorded` rather than silently mixed
with a live read. And AMH, INVH and LMNR are **excluded from the anchor
statistics as circular**: their trend ends were read back off an engine dot
(`ar_off`, which equals `box.start_bar`), so scoring `segment_trends` or the
climax against them would be measuring the engine against itself.
