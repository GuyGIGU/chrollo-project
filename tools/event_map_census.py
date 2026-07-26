"""Event Map census — the promoted rail-episode sequence instrument.

The durable home of the 2026-07-25 sequence probe (Event Map program, PLAN
Task 4): reads every Guided List drawn box and every respect-surviving junk
candidate as a chronological rail-episode sentence, through the ONE engine
reader (``engine_alpha.structure.event_map.read_rail_episodes`` — this tool
contains no reading logic and no mark-loading of its own). Research-grade
computation lives HERE, permanently off the scan path.

Roles stay named: ``tools.calibration_stat_card`` measures drawn geometry,
``tools.shelf_harness`` grades the LPS detector, THIS instrument reads the
sequence story. The v1 parse rule (pre-registered in the probe: completed-S
>= 2 AND completed-R >= 2 AND alternations >= 2 AND no terminal support
drift) is reported as the recorded baseline only — admission-form research
is the census layer on top (PLAN Task 5), and the ruled form will be a
separate predicate, never baked into the reader.

``--check`` is the promotion regression AND a standing gate (run it before
any merge/flip that touches the episode reader): the headline evidence the
program was approved on (EGBN's three completed support tests + terminal
resistance posture; the drift-junk zeros DGII 0/11, CHCT 0/7, COLM 0/10,
FLG 0/2; 15/33 marks under v1; 17 parse-passing junk of 95) must reproduce
exactly, AND the marks fingerprint must equal the promotion-time pin — the
outcome pins alone cannot see the drawn windows being re-drawn under them
(the calibration DB is editable ground truth by design, EC-9; a legitimate
re-draw moves the fingerprint and the pin fails LOUDLY, which is the point:
re-pin deliberately, never drift silently). Exit 1, named diffs.

Deterministic + stamped (EC-13): marks load through the ONE validated
loader; frames come from the committed sealed-fixture parquets (git-tracked;
their content digests are verified by the ``tools.marks_corpus --check``
gate, not re-verified here); every report stamps the populations, the marks
fingerprint, and the engine manifest hash. Writes are guarded (EC-14).
Read-only against the DB.

Usage (ChrolloDashboard venv python, from repo root):
    python -m tools.event_map_census            # full report
    python -m tools.event_map_census --check    # pinned promotion regression
    python -m tools.event_map_census --json OUT # report rows as JSON
    python -m tools.event_map_census --ticker T # one mark's as-of drill-down
(modes run alone — combined flags are refused loudly, never dropped)
"""
from __future__ import annotations

import argparse
import json

try:
    from tools._bootstrap import configure_path, refuse_sealed_output
except ModuleNotFoundError:
    from _bootstrap import configure_path, refuse_sealed_output

_PROJECT_ROOT = configure_path(backend=True)

import database  # noqa: E402

from config import settings  # noqa: E402
from engine_alpha.freeze.manifest import manifest_hash  # noqa: E402
from engine_alpha.structure.event_map import (  # noqa: E402
    episode_sequence_stats,
    read_rail_episodes,
    story_admission,
)
from engine_alpha.structure.metrics import measure_equilibrium  # noqa: E402
from engine_alpha.structure.narrative import read_structure  # noqa: E402
from tools import negative_corpus  # noqa: E402
from tools.calibration_harness import load_box_marks  # noqa: E402
from tools.marks_corpus import load_corpus, setup_key  # noqa: E402
from tools.replay import (  # noqa: E402
    drawn_box_window,
    fixture_frame,
    judged_window,
    load_sealed_fixture,
    prepared_frame,
    prepared_frame_with_reason,
    session_pos,
)

# The probe's pre-registered v1 parse rule — the recorded baseline, nothing
# more. Candidate admission forms are Task-5 research; the ruled form is a
# separate predicate at the pool seam.
def _v1_parses(st: dict) -> bool:
    return (st["n_completed_s"] >= 2 and st["n_completed_r"] >= 2
            and st["alternations"] >= 2 and not st["terminal_s_drift"])


def read_mark_sentences() -> tuple[list[dict], str]:
    """Every Guided List drawn box (drawn window + drawn rails) as a
    sentence, plus the marks fingerprint the rows were computed on."""
    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    status = {e["key"]: e["status"] for e in baseline["setups"]}

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        key = setup_key(s)
        mark = by_key[(s["ticker"], s["as_of"])]
        raw = fixture_frame(frames, key)
        base_df, atr = drawn_box_window(raw, mark.box_start_date,
                                        mark.box_end_date)
        read = read_rail_episodes(base_df, float(s["rails_drawn"]["R"]),
                                  float(s["rails_drawn"]["S"]), atr)
        st = episode_sequence_stats(read)
        rows.append({
            "key": key, "status": status[key], "n_bars": len(base_df),
            "parses_v1": _v1_parses(st), **st,
        })
    rows.sort(key=lambda r: r["key"])
    return rows, fingerprint


def read_junk_sentences() -> list[dict]:
    """Every respect-surviving strict candidate on the negative corpus (the
    probe's population: not rescued, and not killed at width/window/respect)."""
    jframes, meta = negative_corpus._load_fixture()
    rows = []
    for case in meta["cases"]:
        key = case.get("key", case["ticker"])
        df, atr = prepared_frame(jframes.get(key), case["as_of"])
        trace = []
        read_structure(df, atr, trace=trace)
        # Last-resort reachability: the story pool is consulted ONLY when no
        # ordinary candidate (strict/rescued/band) is valid. Any surviving
        # "valid" verdict anywhere in the walk means the pool is structurally
        # unreachable for this case.
        any_valid = any(rec["verdict"] == "valid"
                        for root in trace
                        for rec in (root.get("box_cascade") or []))
        seen = set()
        for root in trace:
            for rec in root.get("box_cascade") or []:
                if rec["rescued"] or rec["stage"] in ("width", "window", "respect"):
                    continue
                sig = (rec["R"], rec["S"], rec["cand_start"])
                if sig in seen:
                    continue
                seen.add(sig)
                window = judged_window(df, int(rec["cand_start"]))
                if len(window) < 2:
                    continue
                R, S = float(rec["R"]), float(rec["S"])
                read = read_rail_episodes(window, R, S, atr)
                st = episode_sequence_stats(read)
                asof = episode_sequence_stats(read, as_of_bar=len(window) - 1)
                died_at = rec["stage"] or "passed"
                trav = None
                if died_at == "occupancy":
                    eq = measure_equilibrium(window, R, S, atr)
                    nf, ns = eq["n_full_traversals"], eq["n_swings"]
                    trav = ("kills" if not (
                        nf >= settings.TRAVERSAL_MIN and ns > 0
                        and nf / ns >= settings.TRAVERSAL_MIN_DENSITY)
                        else "passes")
                rows.append({
                    "key": key, "label": case["label"], "died_at": died_at,
                    "traversal_in_pool": trav,
                    "pool_reachable": not any_valid,
                    "parses_v1": _v1_parses(st),
                    "asof": {k: asof[k] for k in
                             ("n_completed_s", "n_completed_r", "alternations",
                              "terminal_s_drift", "terminal_r_posture")},
                    **st,
                })
    rows.sort(key=lambda r: r["key"])
    return rows


def read_mark_asof_sentences() -> list[dict]:
    """The consultation-day read: for each mark, the live-twin prepared frame
    at ``as_of`` (2y trim, live ATR — what the engine actually sees on
    decision day), the window from the drawn box start to the frame end, the
    DRAWN rails, and as-of stats counting only episodes knowable by the frame
    end. Forms are learned on THIS read, never the hindsight drawn window
    (the contract's as-of rule). A universe-refused prep is reported as
    REFUSED(gate) — the pool would never be consulted there."""
    frames, baseline = load_sealed_fixture()
    setups = load_corpus()
    status = {e["key"]: e["status"] for e in baseline["setups"]}

    session = database.SessionLocal()
    try:
        marks, fingerprint = load_box_marks(session)
    finally:
        session.close()
    by_key = {(m.ticker, str(m.as_of_date)): m for m in marks}

    rows = []
    for s in setups:
        key = setup_key(s)
        mark = by_key[(s["ticker"], s["as_of"])]
        raw = fixture_frame(frames, key)
        prep, reason = prepared_frame_with_reason(raw, s["as_of"])
        if prep is None:
            rows.append({"key": key, "status": status[key],
                         "refused": reason[0], "episodes": []})
            continue
        df, atr = prep
        bs = session_pos(df.index, mark.box_start_date)
        window = df.iloc[bs:]
        read = read_rail_episodes(window, float(s["rails_drawn"]["R"]),
                                  float(s["rails_drawn"]["S"]), atr)
        st = episode_sequence_stats(read, as_of_bar=len(window) - 1)
        dates = window.index
        rows.append({
            "key": key, "status": status[key], "refused": None,
            "n_bars": len(window), **st,
            "episodes": [{
                "rail": e["rail"], "outcome": e["outcome"],
                "terminal_posture": e["terminal_posture"],
                "span": [str(dates[e["start_bar"]].date()),
                         str(dates[e["end_bar"]].date())],
                "n_bars": e["n_bars"],
                "knowable": (str(dates[e["knowable_bar"]].date())
                             if e["knowable_bar"] is not None else None),
            } for e in read["episodes"]],
        })
    rows.sort(key=lambda r: r["key"])
    return rows


# ---------------------------------------------------------------------------
# Candidate admission forms — PRE-REGISTERED 2026-07-25. Hypothesis-first
# from the reading doctrine, scored ONCE against both populations on the
# as-of reads (McKinney discipline: do NOT iterate forms against these
# tables; a new candidate needs a new pre-registration and a fresh run).
# The ruled form becomes a separate predicate at the pool seam — never part
# of the reader.
# ---------------------------------------------------------------------------

def _no_drift(st) -> bool:
    return not st["terminal_s_drift"]


FORMS: dict[str, tuple[str, object]] = {
    "v1": ("two-sided worked range (the probe's pre-registered rule; "
           "recorded WRONG on the R side — it demands mid-window "
           "R-rejections of material that ENDS at R)",
           lambda st: (st["n_completed_s"] >= 2 and st["n_completed_r"] >= 2
                       and st["alternations"] >= 2 and _no_drift(st))),
    # Form A delegates to THE ruled live predicate (EC-3: one implementation
    # — a re-ruling that replaces event_map.story_admission re-scores here
    # automatically; the pre-registration record is preserved because the
    # ruled truth table equals the pre-registered lambda, pinned in
    # test_event_map's truth table).
    "A": ("worked support + terminal resistance engagement (>=2 completed "
          "support tests, window ends engaging R in pre-breakout posture) "
          "== the RULED live predicate (event_map.story_admission)",
          story_admission),
    "B": ("worked support + any resistance evidence (>=2 completed support "
          "tests, plus a completed resistance rejection OR terminal posture)",
          lambda st: (st["n_completed_s"] >= 2
                      and (st["n_completed_r"] >= 1
                           or st["terminal_r_posture"])
                      and _no_drift(st))),
    "C": ("worked support only (>=2 completed support tests, no drift — "
          "the loosest doctrine-legal floor: Phase B is proven at S)",
          lambda st: st["n_completed_s"] >= 2 and _no_drift(st)),
    "D": ("EGBN admission-certain class (>=3 completed support tests + "
          "terminal resistance posture — the tightest read of the flagship's "
          "ADMISSION; its conversion stays rail-placement-blocked upstream)",
          lambda st: (st["n_completed_s"] >= 3 and st["terminal_r_posture"]
                      and _no_drift(st))),
}


def score_forms(mark_asof_rows, junk_rows) -> dict:
    """Both legs of every candidate form, on the as-of reads: marks covered
    (every miss NAMED — the 8 S-poor profiles are never silently dropped)
    and junk admitted (named, with the died-at stage and the in-pool
    traversal verdict for occupancy deaths)."""
    out = {}
    for name, (desc, pred) in FORMS.items():
        covered, missed, refused = [], [], []
        for r in mark_asof_rows:
            if r["refused"]:
                refused.append(f"{r['key']} REFUSED({r['refused']})")
            elif pred(r):
                covered.append(r["key"])
            else:
                missed.append(r["key"])
        admitted = [r for r in junk_rows if pred(r["asof"])]
        out[name] = {"desc": desc, "covered": covered, "missed": missed,
                     "refused": refused,
                     "junk_admitted": [
                         {"key": a["key"], "died_at": a["died_at"],
                          "traversal_in_pool": a["traversal_in_pool"],
                          "pool_reachable": a["pool_reachable"],
                          "exposure": _exposure(a),
                          "profile": a["profile"]} for a in admitted]}
    return out


def _exposure(a) -> str:
    """The bench consequence of one admitted junk sentence, mechanically:
    unreachable cases never consult the pool; traversal-killed windows die
    again in-pool (unchanged gates); everything else is live exposure the
    ruled form must own."""
    if not a["pool_reachable"]:
        return "blocked (ordinary election stands)"
    if a["died_at"] == "traversal" or a["traversal_in_pool"] == "kills":
        return "traversal kills in-pool"
    return "LIVE EXPOSURE"


def _report(mark_rows, junk_rows, fingerprint) -> None:
    print("=" * 78)
    print("  EVENT MAP CENSUS — chronological rail-episode sentences")
    print(f"  marks fingerprint {fingerprint}  |  engine {manifest_hash()[:16]}")
    print("  populations: Guided List drawn boxes (sealed corpus + calibration "
          "DB windows); negative-corpus respect-surviving strict candidates")
    print("=" * 78)
    print("\nMARKS — drawn windows + drawn rails:")
    print(f"  {'case':22} {'st':4} {'n':>3}  S+/R+/alt drift v1     profile")
    for r in mark_rows:
        print(f"  {r['key']:22} {'HIT ' if r['status'] == 'hit' else 'MISS'}"
              f" {r['n_bars']:>3}  {r['n_completed_s']}/{r['n_completed_r']}"
              f"/{r['alternations']}   {'Y' if r['terminal_s_drift'] else '.'}"
              f"    {'PASS' if r['parses_v1'] else 'FAIL'}"
              f"   {r['profile']}")
    n_parse = sum(r["parses_v1"] for r in mark_rows)
    print(f"\n  marks parse (v1): {n_parse}/{len(mark_rows)}")

    per_case: dict[str, list[int]] = {}
    for r in junk_rows:
        per_case.setdefault(r["key"], [0, 0])
        per_case[r["key"]][1] += 1
        per_case[r["key"]][0] += r["parses_v1"]
    n_pass = sum(r["parses_v1"] for r in junk_rows)
    print(f"\nJUNK — {len(junk_rows)} respect-surviving candidates; "
          f"parse-pass (v1): {n_pass}")
    for key, (p, t) in sorted(per_case.items()):
        print(f"    {key:12} {p}/{t}{'   <-- parse-pass' if p else ''}")


def _census(mark_asof_rows, junk_rows, forms) -> None:
    print("\n" + "=" * 78)
    print("  FORM-RESEARCH CENSUS — consultation-day (as-of) reads, drawn rails")
    print("  STANDING RULING: Option A (operator, 2026-07-25 — sealed in")
    print("  strategy_alpha 'The rail-episode read'). Executed fire A/B (Task 14,")
    print("  2026-07-25): 26->28/33 — NKTR + YPF convert; EGBN is ADMISSION-certain")
    print("  at drawn rails but conversion is blocked upstream by rail PLACEMENT")
    print("  (never proposed at a story-passing shape). PKE/ORMP respect-killed =")
    print("  correct misses; SKYT = universe call. Do NOT chase the S-poor eight")
    print("  with bespoke forms.")
    print("=" * 78)

    print("\nMARKS AS-OF — prepared live-twin frame at as_of, drawn rails,")
    print("knowable episodes only:")
    print(f"  {'case':22} {'st':4} {'n':>3}  S+/R+/alt drift post  profile")
    for r in mark_asof_rows:
        flag = "HIT " if r["status"] == "hit" else "MISS"
        if r["refused"]:
            print(f"  {r['key']:22} {flag}   REFUSED({r['refused']})")
            continue
        print(f"  {r['key']:22} {flag} {r['n_bars']:>3}  {r['n_completed_s']}"
              f"/{r['n_completed_r']}/{r['alternations']}"
              f"   {'Y' if r['terminal_s_drift'] else '.'}"
              f"    {'Y' if r['terminal_r_posture'] else '.'}"
              f"   {r['profile']}")

    print("\nPOOL ELIGIBILITY — the open question resolved per candidate:")
    print("which junk deaths are occupancy-only, and does the traversal gate")
    print("(which never ran on them) catch the window in-pool?")
    by_stage: dict[str, int] = {}
    for r in junk_rows:
        by_stage[r["died_at"]] = by_stage.get(r["died_at"], 0) + 1
    print(f"  died-at histogram: "
          + ", ".join(f"{k}={v}" for k, v in sorted(by_stage.items())))
    occ = [r for r in junk_rows if r["died_at"] == "occupancy"]
    print(f"  occupancy deaths: {len(occ)} candidates — traversal in-pool: "
          f"kills {sum(1 for r in occ if r['traversal_in_pool'] == 'kills')}, "
          f"passes {sum(1 for r in occ if r['traversal_in_pool'] == 'passes')}")
    for key in ("KWR", "NVT", "GOOD", "RLGT"):
        cands = [r for r in junk_rows if r["key"] == key]
        if not cands:
            continue
        reach = ("POOL-REACHABLE (no ordinary election)"
                 if cands[0]["pool_reachable"]
                 else "unreachable — ordinary election stands")
        detail = "; ".join(
            f"{r['died_at']}"
            + (f"/trav-{r['traversal_in_pool']}" if r["traversal_in_pool"] else "")
            + (" PARSES-v1" if r["parses_v1"] else "")
            for r in cands)
        print(f"    {key:6} {reach} — {len(cands)} cand: {detail}")

    print("\nCANDIDATE ADMISSION FORMS — pre-registered, scored once, both legs:")
    for name, f in forms.items():
        total = len(f["covered"]) + len(f["missed"]) + len(f["refused"])
        print(f"\n  FORM {name}: {f['desc']}")
        print(f"    marks covered: {len(f['covered'])}/{total}"
              f"  (hits {sum(1 for k in f['covered'] if _is_hit(k, mark_asof_rows))}"
              f", misses {sum(1 for k in f['covered'] if not _is_hit(k, mark_asof_rows))})")
        print(f"    marks NOT admitted ({len(f['missed'])}): "
              + (", ".join(f["missed"]) or "—"))
        if f["refused"]:
            print(f"    refused at prep: {', '.join(f['refused'])}")
        if f["junk_admitted"]:
            print(f"    junk admitted ({len(f['junk_admitted'])}):")
            for a in f["junk_admitted"]:
                print(f"      {a['key']:12} died-at={a['died_at']:10} "
                      f"[{a['exposure']}]   {a['profile']}")
        else:
            print("    junk admitted: NONE")

    print("\n" + "=" * 78)
    print("  DECISION MENU — CLOSED: the Task-6 ruling landed on OPTION A")
    print("  (operator, 2026-07-25). The menu stays printed for RE-RULING")
    print("  research only — a re-ruling replaces event_map.story_admission,")
    print("  cuts a new archive seam, and re-runs this census. Each option")
    print("  names both legs; accepted ADMISSION-misses are part of a ruling,")
    print("  not recall regressions (most fire via ordinary election).")
    print("=" * 78)
    for name, f in forms.items():
        if name == "v1":
            continue    # recorded-wrong baseline, shown above for honesty
        live = sorted({a["key"] for a in f["junk_admitted"]
                       if a["exposure"] == "LIVE EXPOSURE"})
        trav = sorted({a["key"] for a in f["junk_admitted"]
                       if a["exposure"] == "traversal kills in-pool"})
        blocked = sorted({a["key"] for a in f["junk_admitted"]
                          if a["exposure"].startswith("blocked")})
        ruled = "   <== THE STANDING RULING" if name == "A" else ""
        print(f"\n  OPTION {name}{ruled} — {f['desc']}")
        print(f"    admits {len(f['covered'])}/33 marks; accepted misses: "
              + (", ".join(f["missed"] + f["refused"]) or "none"))
        print(f"    junk LIVE EXPOSURE (reachable, survives unchanged gates): "
              + (", ".join(live) or "NONE"))
        if trav:
            print(f"    junk parsed but traversal kills in-pool: {', '.join(trav)}")
        if blocked:
            print(f"    junk parsed but unreachable (ordinary election stands): "
                  + ", ".join(blocked))


def _is_hit(key, mark_asof_rows) -> bool:
    return next(r["status"] for r in mark_asof_rows if r["key"] == key) == "hit"


def _drill(mark_asof_rows, ticker: str) -> None:
    rows = [r for r in mark_asof_rows if r["key"].startswith(ticker)]
    if not rows:
        print(f"no mark rows for {ticker}")
        return
    for r in rows:
        print(f"\n{r['key']} ({'HIT' if r['status'] == 'hit' else 'MISS'})"
              + (f" REFUSED({r['refused']})" if r["refused"] else
                 f"  profile: {r['profile']}"))
        for e in r["episodes"]:
            post = "  TERMINAL-POSTURE" if e["terminal_posture"] else ""
            know = e["knowable"] or "in-progress"
            print(f"  {e['rail']} {e['outcome']:9} {e['span'][0]}..{e['span'][1]}"
                  f"  ({e['n_bars']} bars)  knowable {know}{post}")


# The promotion regression: the exact evidence the program was approved on
# (probe capture 2026-07-25; committed record: docs/event_map_program_2026-07.md).
# The fingerprint pins the GROUND-TRUTH IDENTITY — the exact drawn marks the
# outcome pins were computed on. The calibration DB is editable by design
# (EC-9): a re-drawn window moves the fingerprint and fails this check BY
# NAME, so evidence is re-pinned deliberately, never re-based silently.
_PINNED_MARKS_FINGERPRINT = (
    "b671e056a91fc14fea5b8a724b843c7321a26f4d7d7a6aa5b00741dc93df2523")
_PINNED_MARKS_PARSE_V1 = 15
_PINNED_MARKS_TOTAL = 33
_PINNED_JUNK_TOTAL = 95
_PINNED_JUNK_PARSE_V1 = 17
_PINNED_CASES = {
    "EGBN:2026-01-15": {"n_completed_s": 3, "n_completed_r": 0,
                        "terminal_r_posture": True,
                        "profile": "S+ S+ S+ R^"},
}
_PINNED_JUNK_ZEROS = {"DGII": 11, "CHCT": 7, "COLM": 10, "FLG": 2}


def check(mark_rows, junk_rows, fingerprint) -> list[str]:
    """Exact-match assertions on the headline evidence; returns named diffs."""
    diffs = []

    def _pin(name, got, want):
        if got != want:
            diffs.append(f"{name}: got {got!r}, pinned {want!r}")

    _pin("marks fingerprint (ground-truth identity)", fingerprint,
         _PINNED_MARKS_FINGERPRINT)
    _pin("marks total", len(mark_rows), _PINNED_MARKS_TOTAL)
    _pin("marks parse (v1)", sum(r["parses_v1"] for r in mark_rows),
         _PINNED_MARKS_PARSE_V1)
    _pin("junk candidates", len(junk_rows), _PINNED_JUNK_TOTAL)
    _pin("junk parse-pass (v1)", sum(r["parses_v1"] for r in junk_rows),
         _PINNED_JUNK_PARSE_V1)

    by_key = {r["key"]: r for r in mark_rows}
    for key, want in _PINNED_CASES.items():
        row = by_key.get(key)
        if row is None:
            diffs.append(f"{key}: missing from mark rows")
            continue
        for field, val in want.items():
            _pin(f"{key}.{field}", row[field], val)

    for key, total in _PINNED_JUNK_ZEROS.items():
        rows = [r for r in junk_rows if r["key"] == key]
        _pin(f"{key} candidates", len(rows), total)
        _pin(f"{key} parse-pass", sum(r["parses_v1"] for r in rows), 0)
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="pinned promotion regression (exit 1 on drift)")
    ap.add_argument("--json", help="write report rows as JSON to this path")
    ap.add_argument("--ticker", help="per-episode drill-down for one mark")
    args = ap.parse_args()

    # Modes run ALONE. Refuse combinations loudly — a silently dropped --json
    # leaves a stale artifact at the target path masquerading as fresh
    # evidence; a silently dropped --ticker hides the drill the operator
    # asked for.
    if args.check and (args.json or args.ticker):
        ap.error("--check runs alone; combine with no other flag")
    if args.ticker and args.json:
        ap.error("--ticker is a read-only drill-down; it writes no JSON")

    if args.check:
        mark_rows, fingerprint = read_mark_sentences()
        junk_rows = read_junk_sentences()
        diffs = check(mark_rows, junk_rows, fingerprint)
        if diffs:
            print("EVENT MAP CENSUS CHECK: DRIFT — the instrument no longer "
                  "reproduces the recorded evidence:")
            for d in diffs:
                print(f"  {d}")
            return 1
        print(f"EVENT MAP CENSUS CHECK: OK — headline evidence reproduces "
              f"(marks {_PINNED_MARKS_PARSE_V1}/{_PINNED_MARKS_TOTAL} v1, "
              f"junk {_PINNED_JUNK_PARSE_V1}/{_PINNED_JUNK_TOTAL}; "
              f"fingerprint {fingerprint}, engine {manifest_hash()[:16]})")
        return 0

    if args.ticker:
        # The drill needs ONLY the as-of rows — never the junk-corpus engine
        # walks (the census's dominant cost). Keep it snappy: this is the
        # surface the operator lives on during a per-fire eyeball campaign.
        _drill(read_mark_asof_sentences(), args.ticker)
        return 0

    mark_rows, fingerprint = read_mark_sentences()
    junk_rows = read_junk_sentences()
    mark_asof_rows = read_mark_asof_sentences()
    forms = score_forms(mark_asof_rows, junk_rows)

    if args.json:
        path = refuse_sealed_output(args.json)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": fingerprint,
                       "engine_manifest": manifest_hash(),
                       "marks_drawn": mark_rows,
                       "marks_asof": mark_asof_rows,
                       "junk": junk_rows,
                       "forms": {k: {kk: vv for kk, vv in v.items()
                                     if kk != "pred"}
                                 for k, v in forms.items()}}, fh, indent=1)
        print(f"wrote {path}")

    _report(mark_rows, junk_rows, fingerprint)
    _census(mark_asof_rows, junk_rows, forms)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
