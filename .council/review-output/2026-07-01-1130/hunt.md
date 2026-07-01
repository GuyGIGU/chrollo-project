# Hunt — Integrity / Byte-Parity Containment Review

**Scope:** E3 inner-LPS faithfulness fix on `engine/l2-event-reader`. Lane: integrity of the
flag-off / measure-only byte-parity invariants + the sentinel/assertion containment. No web-attack
surface (local single-user engine), so SQLi / auth / CORS / broker-mode principles are N/A here.

**Verdict: containment holds.** Every new path is inert flag-off and byte-identical on the
measure-only path. I traced the complete caller set of all three touched functions and both other
`_sub_scores` consumers. One P3 clarity note on a shape change; no P1/P2 findings.

---

## Verification trail (what I proved, not just asserted)

**F1 — flag-off inertness.** The injection at `evaluation.py:461-466` is inside
`if settings.PUZZLE_SCORE_ENABLED`. In `scoring.py` both the `+ s_puzzle` arithmetic (270-277) and
the `puzzle_quality` result key (296-297) live only inside the same flag. `_ramp` guard
(`scoring.py:40-41`) returns before the divide only when `full_at <= zero_at`; I read all seven live
anchor pairs (uptrend 0.30→0.60, RS 0.0→0.30, 52w −0.20→−0.05, breadth 0.35→0.60, candle box
CLEAN 0.35→MESSY 0.60, candle ATR 0.90→1.40, tightbar 0.30→0.65) — every one has `full_at > zero_at`,
so the guard is genuinely unreachable and cannot move a live bonus. For a well-formed band the guard
is False and control falls through to the exact original two lines → bit-identical.

**F2 — measure-only byte-identity.** `read_box_events` (`metrics.py:1148`) forwards NO spring/lps
kwargs → both default `_DETECT` → both re-detect via `find_spring`/`find_lps` exactly as before.
`_DETECT` is a module-level `object()` (`metrics.py:1020`) compared only with `is`/`is not` at four
sites (1094, 1107, 1109, 1251); never `==`, never assigned into an event or narrative leaf → it
cannot reach a returned dict, an archive column, or JSON.

**F3 — dashboard conditional + other sub-score iterators.** `sub_payload` (`dashboard.py:171-186`)
is an explicit 14-key whitelist comprehension plus the guarded 15th key. Flag-off the key is absent
from `_sub_scores` (per the `scoring.py:296` guard), so the `if 'puzzle_quality' in sub` branch is
skipped → payload byte-identical. The two OTHER `_sub_scores` consumers — `archive/writer.py:451+`
and `archive/seed.py:362+` — map by explicit per-column `sub.get("named_key")` with NO
`puzzle_quality` column, so they cannot leak the key on any path (even flag-on it is silently
dropped). No presence-based key iteration over `_sub_scores` exists anywhere.

**F4 — new key + assertion.** `lps_pre_v_dropped` requires `injected_lps is not _DETECT`
(`metrics.py:1251`) → always False on the detect/measure-only path; the trace line (1320-1322) is
gated on the same. The `assert int(lp.start_bar) >= start` (`metrics.py:1113`) is inside
`if lps is not _DETECT` → unreachable on flag-off / measure-only. `assemble_box_narrative` has no
flag-off production caller (only `evaluation.py:463` flag-gated, `l2_staircase_audit.py:105` manual
tool, and tests).

**F5 — determinism.** Injected bricks are `structure.spring`/`structure.lps` off the same in-eval
`structure` object — no new detector call, no new entropy. The fix removes two detector passes per
fire; it cannot add nondeterminism.

---

FINDING:
- Title: `lps_pre_v_dropped` widens the narrative-dict shape on the measure-only path (byte-neutral but off-contract)
- File: core/structure/metrics.py:1209, 1335 (and the empty-narrative branch at 1204-1210)
- Principle: Minimise state — the less you store, the less you lose (Principle 3); Assume corruption / know your contract (Principle 9)
- Severity: P3=clarity
- What's wrong: The new `lps_pre_v_dropped` key is added to EVERY returned narrative dict, including the default `_DETECT` measure-only path where it is unconditionally `False` — so the "measure-only `read_box_events`/`assemble_box_narrative` byte-identical" contract now technically ships a wider dict shape than main, not an identical one.
- Consequence: No live consumer breaks (the narrative is never persisted; the audit tool and `_puzzle_quality` read only named keys), but a future consumer that snapshots the whole narrative dict for a golden/byte-parity guard would see a new always-present key on the measure-only path and could not tell an intentional shape bump from drift.
- Fix: Keep the key (it is JSON-friendly and correctly `False`), but tighten the invariant's wording so "measure-only byte-identical" is documented as "identical VALUES for pre-existing keys" rather than "identical dict"; alternatively omit the key on the pure-detect path if a downstream golden ever pins the full dict.

---

**No P1/P2 integrity findings.** The flag-off and measure-only paths are inert and byte-identical:
the injection, the `s_puzzle` term, the `puzzle_quality` result key, the dashboard chip, the
assertion, and the `lps_pre_v_dropped` trace line are each gated (flag or `is not _DETECT`) so none
fires on a flag-off or measure-only run; the `_ramp` guard is provably dead code for all seven live
anchors; the `_DETECT` sentinel is `is`-only and cannot leak into any dict, archive column, or JSON;
and both non-dashboard `_sub_scores` consumers are key-explicit so they cannot leak `puzzle_quality`.
