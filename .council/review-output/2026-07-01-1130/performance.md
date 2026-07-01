# Performance Review — E3 faithfulness fix (detector-reuse)

Reviewer seat: Performance (numerical pandas/numpy hot path).
Scope: `core/structure/metrics.py` (`_box_events_with_meta` injected path), `core/pipeline/evaluation.py` (E3 call site), with `core/structure/bricks.py::find_lps`/`find_spring` and `core/structure/narrative.py::read_structure` read for cost accounting.

## Verdict summary

The fix is a genuine, correctly-scoped **net subtraction** on the flag-on hot path, with only O(1)/bounded new bookkeeping and provably zero flag-off delta. All four focus points check out. No P1/P2 findings. Two P3 transparency notes recorded below.

---

## Focus 1 — Is the fix a net subtraction on the flag-on hot path? (CONFIRMED, honestly quantified)

Before the fix, E3 called `assemble_box_narrative(df, structure.box, atr)`; with the default `spring=_DETECT`/`lps=_DETECT` sentinels, `_box_events_with_meta` re-ran BOTH `find_spring(df, box, atr)` (metrics.py:1094) and `find_lps(df, box, atr)` (metrics.py:1107) on the parent box — a second full election, on top of the one `read_structure` already ran during `narrative.py` (find_spring @330, find_lps @342/345). The fix injects `structure.spring`/`structure.lps` (evaluation.py:462-466), which are the exact objects `read_structure` parked on the `Structure` (narrative.py:383-384), so the `is _DETECT` branches take the else and reuse the elected bricks verbatim. Two detector passes per fire are removed.

The removed `find_lps` pass is the more expensive of the two: it does a full-length `work_df.assign(Spread=High-Low)` allocating a new column over the ENTIRE df (bricks.py:341), a `base_df["Spread"].quantile(...)` over the base slice (bricks.py:348), and the `detect_lms`/`detect_lps` swing scan (bricks.py:352). `find_spring` adds a second in-box swing/excursion scan. Both are eliminated per fire.

Honest sizing: this is a **per-fire** saving on a **small population**. Phase-0 reports 31 firing tickers (shadow) / 51 flag-on A/B fires — order tens, not thousands. It is NOT a per-bar or per-universe-member cost; the whole scan already ran `find_spring`/`find_lps` once during election regardless. So the real-world magnitude is "two redundant detector passes × ~dozens of fires, only when the flag is on" — a clean correctness-plus-efficiency win, not a headline throughput change. The diff's own comment ("drops two redundant detector passes per fire") states it accurately and does not oversell.

## Focus 2 — Any NEW per-fire cost added? (CONFIRMED negligible / O(1) / bounded)

- **`is _DETECT` checks** (metrics.py:1094, 1107, 1109): identity comparisons against a module-level sentinel — O(1), no `__eq__`, correctly `is`-only (the sentinel comment at metrics.py:1018-1019 explicitly forbids `==`, avoiding a dataclass `__eq__` touch). Negligible.
- **`injected_lps = lps` capture** (metrics.py, in `assemble_box_narrative`): a single name bind of an already-materialized reference before the spine locals shadow `lps`. Zero allocation, O(1).
- **`lps_pre_v_dropped` computation**: a short-circuited boolean of three identity/`is None` checks (`injected_lps is not _DETECT and injected_lps is not None and lps is None and has_valley`) — O(1), NOT an `any()` scan over events (the brief's phrasing "any() scan" does not match the code; the actual expression is constant-time). One extra `bool(...)` in the returned dict and one conditional `trace.append`. Negligible.
- **The injected-path `assert int(lp.start_bar) >= start`** (metrics.py:1113): two int coercions + one comparison, only on the injected branch. O(1). (Assertion-discipline correctness is Hunt's seat, not performance; cost-wise it is free.)
- **F3 `upthrust_terminal` change**: the `resolved_after = any(... for e in events)` generator is a single linear pass over `events` that ALREADY existed pre-fix; the fix only adds an extra `or (e["type"] == "range" and int(e["anchor_bar"]) > v_bar)` term inside the same predicate. No new pass, no change in complexity — still O(len(events)), and `events` is the small per-box event list. Negligible.

No new per-fire cost is material.

## Focus 3 — Flag-off perf delta (CONFIRMED zero)

The E3 narrative is gated behind `if settings.PUZZLE_SCORE_ENABLED:` (evaluation.py:461); `narrative` stays `None` and `assemble_box_narrative` is never called when the flag is off. Flag-off never enters the injected path, so there is exactly zero delta — consistent with the Phase-0 shadow-diff PASS (flag-off byte-identical). The measure-only `read_box_events` public path keeps calling `_box_events_with_meta` with default sentinels, so its detect behavior is unchanged (byte-identical), matching invariant 2.

## Focus 4 — Redundant work remaining this fix could have removed but didn't (CHECKED — none extractable here)

The single `read_box_staircase(base_df, R, S, atr_val)` build (metrics.py:1082) is correctly single-sourced: it runs ONCE and its `swings` feed the V resolution, the R-rail `measure_resistance_events` (via `swings=swings`, metrics.py:1088) and the S-rail `measure_support_tests` (via `swings=swings`, metrics.py:1091) — the heaviest L2 primitive is not re-run 3x. That staircase is built from `base_df` inside `_box_events_with_meta` and is not exposed on the `Structure`, so there is no already-elected staircase to inject/reuse the way spring/LPS were; it is genuinely needed here and is not reusable-from-elsewhere. Hoisting it would require `read_structure` to surface its own staircase on the `Structure`, which is a larger structural change out of this fix's scope — correctly left alone. No redundant work this fix omitted.

---

## FINDING (P3)

FINDING:
- Title: Brief's "any() scan" description overstates the `lps_pre_v_dropped` cost (doc/expectation drift, not a code cost)
- File: core/structure/metrics.py (the `lps_pre_v_dropped = (...)` expression in `assemble_box_narrative`)
- Principle: Carmack — "if you can't see the cost, you can't reason about correctness" (cost transparency)
- Severity: P3
- What's wrong: The context brief characterizes `lps_pre_v_dropped` as an "any() scan over events," but the implemented expression is a constant-time chain of identity/`is None`/`has_valley` checks with no iteration. The code is cheaper than its own review brief implies.
- Consequence: No runtime cost; only a risk that a future reader trusts the brief and believes a per-event scan exists where none does.
- Fix: None required in code; if anything, note in the PR that the observable is O(1), not a scan, so the cost accounting stays accurate.

## FINDING (P3)

FINDING:
- Title: Shared staircase is single-sourced but not surfaced on `Structure` for cross-call reuse
- File: core/structure/metrics.py:1082 (build) vs core/structure/narrative.py:320-345 (election)
- Principle: DRY-of-work / single-source-of-computation (reuse-elected-artifact, the same principle this fix applies to spring/LPS)
- Severity: P3
- What's wrong: `read_structure` and `_box_events_with_meta` each build their own `read_box_staircase`/swing view of the base; unlike spring/LPS, the election's swing/staircase artifact is not parked on the `Structure`, so E3 cannot reuse it and rebuilds it once per fire. This is correct and in-scope-safe as-is, but is the next same-shaped reuse opportunity.
- Consequence: One extra staircase build per flag-on fire (~dozens/scan) that a future "elect once, inject everywhere" pass could remove — same per-fire, small-population magnitude as the passes this fix already removed.
- Fix: Out of scope for this fix; a later change could surface the elected base-swing view on `Structure` and thread it in like `spring`/`lps`, provided byte-parity of the measure-only path is preserved.

---

No P1 or P2 performance findings. The fix removes two per-fire detector passes (the heavier being `find_lps`'s full-length `assign(Spread)` + `.quantile` + swing scan) by reusing already-elected bricks, adds only O(1)/bounded bookkeeping, and has provably zero flag-off delta.
