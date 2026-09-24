"""The doctrine gate's plumbing lives IN pytest so it cannot go dark (again).

``tools.doctrine_audit`` is the ONE offline guard that proves the reading is
RIGHT rather than merely unchanged — and until now the only one with zero
pytest presence. It has already gone silently dark once: a monkey-patched spy
pinned an old engine signature, every read raised TypeError inside the spy,
and the gate asserted nothing for a day (the arity trap, re-lit at 9fbbca3).

This module is the cheap, hermetic guard-the-guard on the
``tests/test_pointer_audit.py`` pattern:

  * the engine seams the audit spies/calls are SIGNATURE-PINNED, so a future
    seam change goes RED here — a named, readable failure — instead of
    silently blinding the offline battery;
  * one synthetic frame drives the tool's full check battery end to end,
    asserting a doctrinally sound structure passes every applied invariant;
  * bite-proofs: deliberately wrong structures must produce violations, one
    per mutated leg (EC-27: the test names WHICH invariant refused).

The full live-payload audit stays offline (it needs the payload + live cache);
only this plumbing enters pytest.
"""
from __future__ import annotations

import inspect
from collections import defaultdict
from types import SimpleNamespace

import numpy as np
import pandas as pd

import config.settings as settings
from engine_alpha import evaluation
from engine_alpha.structure.narrative import bricks
from engine_alpha.structure.narrative.reader import read_structure
from tools import doctrine_audit


# ── (a) The spied/called engine seams: signature pins ────────────────────────
def test_the_spied_cause_seam_signature_still_matches():
    """The audit spies ``bricks._cause_is_up`` by assignment and relies on its
    call semantics (once per resolve_phase_a, last value before return belongs
    to the elected Structure). The spy itself is *args/**kwargs-transparent —
    deliberately, after the arity trap — so a seam change would NOT crash it;
    it would silently change what the spy's captured value MEANS. Red here =
    re-verify the spy comment in tools/doctrine_audit.py against the new seam,
    then update this pin deliberately."""
    params = list(inspect.signature(bricks._cause_is_up).parameters)
    assert params == ["df", "root", "pbs", "terminal_floor"], (
        f"bricks._cause_is_up signature moved (now {params}) — the doctrine "
        "audit's cause spy interprets this seam's calls; re-verify the spy "
        "semantics in tools/doctrine_audit.py before updating this pin"
    )
    # The audit patches exactly this attribute; if the spy is ever re-pointed,
    # this pin must move with it in the same change.
    assert "bricks._cause_is_up" in inspect.getsource(doctrine_audit), (
        "tools/doctrine_audit.py no longer references bricks._cause_is_up — "
        "the spy moved; re-point this suite's signature pins at the new seam"
    )


def test_the_called_engine_seams_still_match_the_audit():
    """Every seam run_audit calls positionally / by keyword, pinned so an
    engine signature change fails HERE with a message instead of blinding or
    crashing the offline gate."""
    # read_structure(daily, atr) and read_structure(daily, atr, trace=...)
    sig = inspect.signature(read_structure)
    params = list(sig.parameters)
    assert params[:2] == ["df", "atr"], (
        f"read_structure's leading parameters moved (now {params}) — the "
        "audit calls it as read_structure(daily, atr)"
    )
    assert "trace" in sig.parameters, (
        "read_structure lost its trace kwarg — the audit's cause-before-effect "
        "abstention read (vetoed vs refused) depends on it"
    )
    # evaluation._prepare_eval_frame(df) — the eval-twin prep the audit replays.
    prep_params = list(inspect.signature(evaluation._prepare_eval_frame).parameters)
    assert prep_params == ["df"], (
        f"_prepare_eval_frame signature moved (now {prep_params}) — the audit "
        "replays every payload ticker through it"
    )
    # The settings knobs the audit reads at check time.
    assert hasattr(settings, "PHASE_A_CLIMAX_TERMINALITY_EXCESS")
    assert hasattr(settings, "STRUCTURE_ATR_SAMPLE_OFFSET")


# ── (b) One synthetic frame through the full check battery ───────────────────
def _sound_case():
    """A hand-built frame + Structure satisfying every Reading Model invariant
    the battery asserts (up-cause). Bars: climax high 120 at bar 2, AR low 98
    at bar 4, box opens at 6, R anchored bar 8 (high 110), S anchored bar 12
    (low 100), spring tips bar 20 (low 99) and reclaims at 21 (close 100.5),
    LPS 30..34 (low bar 31), terminator = lps, inner box from bar 10 with
    rails 102/108."""
    n = 40
    H = np.full(n, 106.0)
    L = np.full(n, 101.0)
    C = np.full(n, 104.0)
    H[2] = 120.0    # climax high — the trend-end extreme
    L[4] = 98.0     # AR low
    H[8] = 110.0    # the R anchor PRODUCES R
    L[12] = 100.0   # the S anchor PRODUCES S
    L[20] = 99.0    # spring tip under S
    C[21] = 100.5   # reclaim close back above S
    daily = pd.DataFrame({"High": H, "Low": L, "Close": C})
    s = SimpleNamespace(
        climax_bar=2, ar_bar=4, phase_b_start_bar=6, phase_b_end_bar=30,
        R=110.0, S=100.0,
        box=SimpleNamespace(start_bar=6, r_anchor_bar=8, s_anchor_bar=12),
        spring=SimpleNamespace(tip_bar=20, recovery_bar=21,
                               spring_type="SPRING", undercut_atr=0.4),
        lps=SimpleNamespace(start_bar=30, end_bar=34, low_bar=31,
                            low=101.0, high=104.0, zone_type="S_RECLAIM"),
        inner=SimpleNamespace(start_bar=10, R=108.0, S=102.0),
        lps_in_inner=False, terminator="lps",
    )
    # The payload cells B6 asserts immobility against (2-dp quantized rails).
    payload = {"R": 110.0, "S": 100.0, "base_len": n - 6}
    return daily, 1.5, s, payload


def _run_battery(daily, atr, s, payload, cause_up=True):
    """Drive _audit_setup with run_audit's own check-collector shape."""
    counts: dict = defaultdict(int)
    violations: dict = defaultdict(list)

    def check(inv, tk, ok, detail=""):
        counts[inv] += 1
        if not ok:
            violations[inv].append((tk, detail))

    doctrine_audit._audit_setup("SYN", daily, atr, s, cause_up, payload, check)
    return counts, dict(violations)


def test_a_sound_structure_passes_every_applied_invariant():
    daily, atr, s, payload = _sound_case()
    counts, violations = _run_battery(daily, atr, s, payload)
    assert violations == {}, (
        f"a doctrinally sound synthetic structure produced violations: {violations}"
    )
    # Guard the guard: an emptied battery would pass vacuously. The full
    # invariant set this case exercises must actually have been APPLIED
    # (D5 legitimately absent — the LPS zone is not OVERSHOOT_R here).
    expected = {
        "A1 climax<=ar", "A2 ar<=box_start", "A3 terminality",
        "B1 S<R", "B2 High[r_anchor]==R", "B3 Low[s_anchor]==S",
        "B4 anchors-in-box", "B5 box.start==pbs", "B6 payload-immobility",
        "C1 spring-low<S", "C2 reclaim-window", "C3 spring-reclaim>=S",
        "C4 spring-in-box", "C5 undercut>0", "C6 spring<=lps",
        "D1 lps-exists", "D2 lps-window-order", "D3 lps-in-box",
        "D4 lps-price-order", "D6 terminator", "D7 A-B-spine",
        "E1 inner-starts-in-parent", "E2 inner-rails-ordered",
    }
    assert expected <= set(counts), (
        f"the check battery shrank — invariants no longer applied: "
        f"{sorted(expected - set(counts))}"
    )


def test_no_terminality_claim_when_the_engine_keyed_no_cause():
    """cause_up None = the engine made no terminality claim on this frame, so
    neither may the gate (the Tested-DEAD root.kind keying stays dead)."""
    daily, atr, s, payload = _sound_case()
    counts, violations = _run_battery(daily, atr, s, payload, cause_up=None)
    assert "A3 terminality" not in counts
    assert violations == {}


# ── (c) Bite-proofs: a wrong structure must produce a violation ──────────────
def test_bite_inverted_rails():
    daily, atr, s, payload = _sound_case()
    s.S = s.R + 1.0  # support above resistance — doctrinally impossible
    _, violations = _run_battery(daily, atr, s, payload)
    assert "B1 S<R" in violations, "inverted rails sailed through the battery"


def test_bite_overshoot_lps_below_its_rail():
    daily, atr, s, payload = _sound_case()
    s.lps.zone_type = "OVERSHOOT_R"  # claims above-R with low 101 under R 110
    _, violations = _run_battery(daily, atr, s, payload)
    assert "D5 lps-above-R" in violations, (
        "an OVERSHOOT_R LPS sitting under its active rail was not flagged"
    )


def test_bite_a_post_climax_poke_breaks_terminality():
    daily, atr, s, payload = _sound_case()
    daily.loc[5, "High"] = 500.0  # blows past the climax before the box opens
    _, violations = _run_battery(daily, atr, s, payload)
    assert "A3 terminality" in violations, (
        "a post-climax excess far beyond the sanctioned poke was not flagged"
    )


def test_bite_a_moved_payload_rail():
    daily, atr, s, payload = _sound_case()
    payload["R"] = 111.0  # the payload shows a rail today's engine won't reproduce
    _, violations = _run_battery(daily, atr, s, payload)
    assert "B6 payload-immobility" in violations, (
        "an engine/payload rail disagreement was not flagged"
    )
