# Bar-dwell protocol — occupancy measured in the operator's unit (2026-07-25)

Pre-registered BEFORE the fire A/B. Amendment only by operator ruling recorded
in §7. Program authorization: operator GO 2026-07-25 ("Go, just find the
solution to our problem"), following his third statement of the bar-as-unit
ruling: *"I dont care about the actual CLOSE value only the LOW or HIGH since
Im measuring the entire bar and counting it as a single UNIT."*

## §1 Identity pins

| pin | value |
|---|---|
| marks fingerprint | `b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523` |
| baseline manifest | `ab5bf340e46289474bae6439a68ee28237175ae1155c0ae3cc2bfbcfc055fa91` (deliberate reseal 82da91d) |
| ratchet | 26/33 pinned hits, 7 staged misses |
| negative corpus | 18 cases, 0 fires at baseline |
| harness policy | HARNESS_POLICY_VERSION 3 |

## §2 The lever — ONE boolean, ZERO numeric moves

`EQ_DWELL_BAR_BASIS` (new flag, dark build default False). Flag-on, the
worked-equilibrium occupancy dwell trio in `_validate_base_quality` is
measured **bar-as-unit** on the identical window:

- **lower engagement** — bars whose Low reaches the lower box third —
  floor unchanged `EQ_MIN_HALF_DWELL = 0.15`;
- **upper engagement** — bars whose High reaches the upper third —
  floor unchanged `0.15`;
- **mid residency** — bars living entirely interior (touching neither
  end zone) — cap unchanged `EQ_MAX_MID_DWELL = 0.45`.

Everything else is untouched: touches (already bar-basis), boundary respect
(never loosened), coverage (stays close-basis — an explicitly DEFERRED
follow-up, not part of this lever), traversal, all selection policy, every
knob value. **This is a measurement-basis correction, not a threshold move**
— the tested-DEAD floor slides (dwell 0.125/0.10, mid 0.50/0.55, respect
0.75) remain dead and are not re-requested.

## §3 Pre-seal evidence (bar_dwell_probe2, certified judged windows)

- EGBN examined candidate = the drawn box (0.000 bh off): closes 3/23 lower
  (kill), **bars 8/23** — engagements include the operator's named support
  tests 2025-12-24 and 2026-01-02. Sole failing leg flips; trio PASS.
- YPF examined candidate = the drawn box (0.000): both close kills (lower
  2/14, mid 7/14) are dwell legs; **bars 7/14 low, 11/14 up, 0 resident-mid**;
  trio PASS.
- Hits: **26/26 trio PASS** at unchanged floors (binding case MATX +0 bars).
- PKE / ORMP / SKYT still die at respect (0.77 / 0.70 / 0.68) — predicted
  still-miss. NKTR's nearest candidate (0.495 bh off the drawn rails) and
  NOK (selection-stage) become occupancy-clean — possible conversions at
  disclosed non-drawn geometry.
- Junk leg-level disclosure: bar basis admits +209 candidates through the
  dwell LEG overall (830/1647 vs 621); of 54 junk candidates killed by dwell
  legs alone, 46 pass the trio; the bar mid-residency cap saves 0 junk that
  close-mid caught. **Accepted by operator ruling**: the basis change is
  doctrine (measure what the eye measures); junk defense is the conjunction
  of gates, judged at FIRE level by condition B below. This paragraph is the
  §-D-style separation disclosure — eyes open.

## §4 Accept conditions (mechanical, all required for YES)

- **A. Predicted conversions.** EGBN and YPF BOTH convert, each electing at
  drawn-box identity (their examined candidates, 0.000 bh). NKTR and NOK
  conversions are ALLOWED (pre-registered possible, geometry disclosed in
  the record); any other Guided-List status change = FAIL.
- **B. Junk silence.** 18/18 negative-corpus cases still refuse at fire
  level. HARD — one junk fire kills the program.
- **E. Hit identity.** 26/26 pinned hits keep their pinned first_fire AND
  their elected box identity (start_bar, R, S) at that session. HARD — a
  displaced winner fails E even with the fire count intact.

## §5 Flip protocol (only on YES)

Default `EQ_DWELL_BAR_BASIS = True` + STAGE_TAGS drops the converted misses
+ ratchet re-freeze (floor rises to the new hit count) + manifest rotation
recorded as an archive bin seam + strategy_alpha.md occupancy section
rewritten to bar-basis + full battery — ONE commit (one lever = one reseal).

## §6 Falsifiers (any → NO, tested-DEAD record, nothing ships)

- Any junk fire (B) or any hit broken/displaced (E).
- EGBN or YPF fails to convert, or converts at non-drawn geometry.
- An unpredicted Guided-List conversion outside {NKTR, NOK}.

## §7 Changelog

- v1 sealed 2026-07-25 before any flag-on run. No amendments.
