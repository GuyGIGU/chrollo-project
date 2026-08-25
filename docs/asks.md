# Asks — every open question owed to the operator, one line each

**The landing rule (council 2026-08-22):** a session appends its ask in the SAME change that
creates it; a ruling received in chat lands its decisions.md row AND closes its ask row in the
same session. An unlanded ruling stays visible here instead of surviving only in an agent memory.
Closed asks move to the bottom with their resolution — never deleted.

| Asked | The question | Blocks | Look at |
|---|---|---|---|
| 2026-08-25 | **The 166.6 MB error log is now INERT — rule on deleting it**, and the elevated `nssm set ChrolloDashboard AppRotate…` block (now a BACKSTOP, no longer the remedy). Measured after both redeploys: 1 line since the last restart, the startup banner. Nothing is writing to it; it is 166.6 MB of history. NSSM holds the handle, so it needs the service stopped (or an online rotate) — an elevated action, yours. | Disk (166.6 MB) | decisions.md 2026-08-25 rows |
| 2026-08-23 | **Type names**: rule the operator-facing names for the two chain lanes (proposals ride the plan's Task 1, drawn from your own words — "base on base", the shakeout-recovery family, "tactical long"). Wire keys and archive columns freeze forever, so nothing serializes before this ruling. | Plan Tasks 8/13/14 (archive, profiles, wire) | [pattern_register.md](pattern_register.md) rows 8–9 |
| 2026-08-23 | **Chain specimens**: round 1 (40 candidates) **RULED ALL-JUNK 2026-08-25** — the crude screen adversely selected deal-pinned/buyout stocks (gap → near-zero spread and volume). The ask stays open: a round-2 sheet is owed once the miner grows a deal-pinned exclusion — or name 2–3 of your own charts per chain directly, which short-circuits the mining entirely. | The wall fixture (plan Task 3) + every threshold the program will propose | decisions.md 2026-08-25 row + **[story_chain_candidates_2026-08.md](story_chain_candidates_2026-08.md)** |
| 2026-08-22 | **Graduation sitting**: the live marks DB holds 34 marks (+1 beyond the sealed 33) and both fingerprints drifted past the pin ~2026-07-27 — review the delta, re-approve, re-pin. The Trigger-coverage seal gap (decisions.md 2026-08-20) can ONLY close inside this event, so the recipe widening rides it. | The engine's test standard ingesting your newest ground truth | `python -m tools.marks_corpus --check` (the advisory line) + the workbench |
| 2026-08-22 | **Signal-edge program: live or die?** 2,246 lines of honest-edge measurement parked on `wip/signal-edge-backtest` since 2026-07-13. | Pattern Register row 6 | [pattern_register.md](pattern_register.md) row 6 |
| 2026-08-22 | **Trend-terminal kill-by 2026-08-31**: the ledger's own record says the unblock is the `segment_trends` box-blindness fix + a fresh A/B (the 2026-07-28 eyeball happened — IRMD/IART/CYRX KEEP, "not wrong, early"). Extend-with-ruling, open the fix program, or kill the flag? | `TREND_TERMINAL_BOX_GATE_ENABLED` | [flag_ledger.md](flag_ledger.md) row + `tools/fidelity/trend_terminal_2026-08-13/` |
| 2026-08-22 | **AR-diff re-measure** (one command, waiting since 2026-08-19): re-run the anchor diff against the re-keyed climax so the AR flag's kill-by (2026-09-15) is decided on current arithmetic. | `AR_FIRST_REACTION_ENABLED` kill-by | [flag_ledger.md](flag_ledger.md) AR row |
| 2026-08-22 | **June forming-bar era** (2,299 rows, 2026-06): cohort-shift impossible, per-row evidence preserved — rule the row-grain pass in, or accept the era as-is. | Archive history hygiene | decisions.md 2026-08-11 row |
| 2026-08-22 | **`claude/focused-ellis-499011`**: locate the cloud session carrying the lens-tweaks build, or declare it dead. | Pattern Register row 7 | [pattern_register.md](pattern_register.md) row 7 |

## Closed

| Asked | The question | Resolution |
|---|---|---|
| 2026-08-22 | **Redeploy + log rotation** — make the retirement, the log-flood fix and the dependency bump live. | **CLOSED 2026-08-25 — operator redeployed twice, and both rounds were VERIFIED IN PRODUCTION rather than assumed.** Round 1 proved the stderr half (5 lines in the error log since restart, zero `chrollo.request`) and FALSIFIED the rest: `uvicorn.access` was a twin with no quiet list, so the flood moved to stdout — 2,296 of the next 3,000 lines. Round 2 silenced it. Controlled test after: 3× `/health` (quiet) → **0 lines**, 1× `/screener-data/` (not quiet) → **exactly 1 line**, ours, with request id and duration; zero uvicorn twins; 100 bytes for four requests where the old path wrote five lines. CI green on main twice running. |
| 2026-08-23 | **Story-chain build: go / no-go** — the 15-task council plan for disjointed setups (base on base + after-shakeout recovery as typed lanes). | **CLOSED same day — operator: "go."** Build opened (council-implement run `2026-08-23-1420`); program record: [story_chain_program_2026-08.md](story_chain_program_2026-08.md) |
