# Plan — E2: Chronological Assembly + Trace (`assemble_box_narrative`)

**Branch:** `engine/l2-event-reader` · **Lane:** engine (measure-only) · **Spec:** `specs/engine-reading-quality-e2.md`
**Council plan critique:** 5 seats, all **sound-with-changes**, fully convergent. Every must-fix below is baked into the contract.

## Design (council-hardened)

### Shared chokepoint — `_box_events_with_meta(df, box, atr_val, *, v_bar=None) -> (events, v_bar, base_n, has_valley)`
Extract the body of today's `read_box_events` into this private helper (placed immediately **before** `read_box_events`). It builds the staircase **once**, resolves `v_bar = _deepest_valley_bar(swings)` once (iff caller passed None), threads that **same** int into `measure_resistance_events(v_bar=…)` and the LPS Phase-D gate, computes `base_n = len(base_df)` once, and **returns the resolved `v_bar`, `base_n`, and `has_valley`** alongside `events`. (`has_valley` = `any(kind=='valley')` — added during implementation so the assembler can distinguish a *real* V from a defaulted `v_bar==0` when gating phase emission.) Every degenerate early-return yields `([], 0, 0, False)` (never bare `[]`).
`read_box_events(df, box, atr_val, *, v_bar=None)` becomes `return _box_events_with_meta(df, box, atr_val, v_bar=v_bar)[0]` — **public contract unchanged** (events-only, byte-identical; its 3 tests + shadow stay green). *[McKinney #1, Fowler #1/#2, Performance #1/#2/#3, Beck #4 — single source of V, no 2nd staircase build, no desync.]*

### `assemble_box_narrative(df, box, atr_val, *, v_bar=None) -> dict` (placed after `read_box_events`)
Calls the helper **once**, then does a **single linear walk** over `events[]` (already chronologically sorted) — **adds ZERO new detector calls**. The whole spine is selected by **filtering the passthrough `events[]` by `type`** — never re-invoking `find_spring`/`find_lps`/`measure_*`. *[Performance #1, Taxonomy #1, Fowler — reusing E1's already-gated, already-sorted pieces is the single guarantee V / LPS-Phase-D-gate / chronology cannot desync.]*

**Spine (best-of-class, references into `events[]`, no copy):**
- `spring` = the (0/1) `type=='spring'` event.
- `sos` = the **first chronological** confirmed SOS: `min(sos_events, key=(anchor_bar, zone_start, peak_price))` (defensive full key; SOS waves are non-overlapping so `anchor_bar` is already unique). Later held reaches stay in `events[]`. *[McKinney/Fowler tie-break.]*
- `lps` = the (0/1) `type=='lps'` event.
- Slots always present with explicit `None` when absent (stable JSON shape, no `.get()` needed). *[Fowler.]*

**Counters / reads (descriptive grades, NEVER gates):**
- `tests` = `sum(1 for e in events if e['type']=='test')` (held only; `failed`/`in_progress` excluded). *[McKinney #4, Beck.]*
- `completeness` = `(spring is not None)+(sos is not None)+(lps is not None)+(tests>0)` ∈ 0..4 — each canonical class ≤1; the test-slot reuses the SAME `tests>0` filter so the two can't drift. *[McKinney #4.]*
- `chronology`: canonical bar per slot frozen — spring→`anchor_bar`(tip), SOS→`anchor_bar`(=peak_bar), LPS→`anchor_bar`(low_bar). `'intact'` iff all three present **and** `spring.anchor_bar < sos.anchor_bar < lps.anchor_bar` (**strict** `<`); `'partial'` if some present (ties → partial); `'absent'` if none. Bar-ordinal only — documented as a quality signal, never a causal/coupling definition. *[McKinney #3, Beck #1, Taxonomy.]*
- `upthrust_terminal` (pure description, never a suppressor): `bool(upthrusts)` **and** no R-rail `SOS`/`markup`/`in_progress` event with `anchor_bar >= last_upthrust.anchor_bar`. An `in_progress` wave after the upthrust ⇒ `False` (unresolved, NOT terminal — honors E1's right-edge no-lookahead). Must NOT delete/suppress the independently-detected spring/test/LPS. Cross-field invariant: `not (spine.sos is not None and upthrust_terminal)`. *[McKinney #2, Taxonomy #2.]* **Eyeball note:** `markup`-after-upthrust is treated as un-terminal-ing (price advanced and held above R) — surfaced for the operator (open Q).

**Phases (O(1) derivations off the shared `v_bar`/`base_n`; only when ≥1 valley swing exists):**
- `B = [0, v_bar]`; `D = [v_bar+1, base_n-1]` iff **any Phase-D event** exists (`SOS`/`markup`/`lps`) — not tied to the SOS spine slot alone. `B.end+1 == D.start` (no overlap/gap; the V bar belongs to B, matching `in_phase_d = top_bar > v_bar`).
- `C = [spring.zone_start, spring.zone_end]` from the SAME spine spring dict (pure derivation), a **marked sub-zone** that may overlap B — documented as not a partition member.
- Valid box but **zero valleys** (v_bar defaulted to 0) ⇒ all of B/C/D `None`. *[McKinney #5, Taxonomy, Beck.]*

**Trace:** a pure render of the spine/phases (no recomputation, no second code path). One line per populated spine/phase step + a summary line (`→ chronology intact, completeness 3/4`). Interpolate only ints/rounded values (no raw float repr) so byte-parity can't flake. *[McKinney/Beck.]*

**Empty/degenerate:** mirror the helper's guard cascade; return the canonical empty narrative `{events:[], v_bar:0, base_n:0, spine:{spring:None,sos:None,lps:None}, tests:0, upthrust_terminal:False, completeness:0, chronology:'absent', phases:{B:None,C:None,D:None}, trace:[]}`. Every leaf native python (int/str/bool/None/float) — no numpy scalars. *[McKinney #5, Beck #3, Fowler.]*

## Tasks
1. **(metrics.py) Extract `_box_events_with_meta` + delegate `read_box_events`** — output-preserving refactor; degenerate returns `([],0,0)`. *(McKinney/Fowler/Performance)*
2. **(metrics.py) Add `assemble_box_narrative`** — single helper call, single linear pass, spine-by-filter, counters, chronology, upthrust_terminal, phases, trace; native-python leaves. *(all seats)*
3. **(tests) Pin the contract** — (a) `read_box_events` byte-parity unchanged after refactor + `v_bar` equals `_deepest_valley_bar`; (b) clean bullish chronology → intact; (c) TITN upthrust-terminal → spine.sos None, upthrust_terminal True, spring/test/lps present, chronology partial; (d) two-SOS fixture → spine.sos = first-by-bar, both stay in events; (e) completeness = held-test only (2 held + 1 failed → +1), is an int 0..4; (f) **no veto-shaped field** (key allowlist + no bare bool except upthrust_terminal); (g) degenerate box → well-formed empty (shape asserted); (h) no-valley box → phases all None; (i) phases B.end+1==D.start, C==spring zone; (j) determinism via `json.dumps(sort_keys=True)` byte-compare + native-type assertion; (k) import-isolation (core/pipeline imports neither new symbol). Build synthetics offline, monkeypatch `core.structure.bricks.find_spring/find_lps` (mirror the offset-origin test). *(Beck)*
4. **(tools) Extend `l2_staircase_audit.py`** to print the assembled narrative + trace; produce the calibration-set reads (AEF/NMAI/AMRZ/TITN/BHF/SEI) for operator eyeball.
5. **Gates + review + commit** — pytest / `shadow_diff --check` (byte-identical) / `seed_recall --check` after each step; council review fan-out; commit to `engine/l2-event-reader` (NOT merge/push); update memory; surface for eyeball.

## Open questions surfaced for operator eyeball
- `markup`-after-upthrust un-terminal-ing (plan treats it as un-terminal; alternative = leave terminal since no creek-jump SOS confirmed).
- Whether a Phase-C spring should weigh equally with Phase-D pieces in the 0..4 tally (E2 = raw descriptive count; E3 weights).
