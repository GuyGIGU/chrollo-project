"""Measure the base's main zigzag and how its significant turns establish the rails."""
from __future__ import annotations

from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes.grade import ending_sos, own_swings
from engine_alpha.two_eyes.record import SPRING, UPTHRUST


def measure(line, events, days, *, R: float, S: float, opening_bar: int, read_bar: int) -> dict:
    """Facts only, on the grade's base and the already-built fine/far swing line.

    Travel uses identical fine-line endpoints. Rail distances use the box height;
    a spring's below-support valley or upthrust's above-resistance peak belongs
    to its event only within that event's own, already-known swing.
    """
    days = list(days)
    sos = ending_sos(events, days, opening_bar)
    end = days.index(sos.first_day) - 1 if sos is not None else read_bar
    known = [e for e in events if e.committed and (e.known_day is None or e.known_day <= days[read_bar])]
    fine = [t for t in line.committed if opening_bar <= t.bar <= end]
    far = [t for t in line.far(M.FAR_VIEW_FLOOR_RANGES)
           if t.committed and opening_bar <= t.bar <= end]
    # Far turns are fine turns; their common endpoints keep the travel ratio bounded.
    positions = {(t.bar, t.kind): i for i, t in enumerate(fine)}
    far = [t for t in far if (t.bar, t.kind) in positions]
    main_travel = fine_travel = 0.0
    fine_legs = 0
    for a, b in zip(far, far[1:]):
        first, last = positions[a.bar, a.kind], positions[b.bar, b.kind]
        legs = list(zip(fine[first:last], fine[first + 1:last + 1]))
        main_travel += abs(b.price - a.price)
        fine_travel += sum(abs(y.price - x.price) for x, y in legs)
        fine_legs += len(legs)
    errors = []
    explained = 0
    turn_days = [t.day for t in line.committed]
    spans = {kind: own_swings([e for e in known if e.kind == kind], turn_days, days[0], days[read_bar])
             for kind in (UPTHRUST, SPRING)}
    for turn in far:
        rail = R if turn.kind == "peak" else S
        kind = UPTHRUST if turn.kind == "peak" else SPRING
        outside = turn.price > R if turn.kind == "peak" else turn.price < S
        named = outside and any(a <= turn.day <= b for a, b in spans[kind])
        explained += int(named)
        if not named:
            errors.append(abs(turn.price - rail) / (R - S))
    return {
        "base_start": days[opening_bar].isoformat(),
        "base_end": days[end].isoformat(),
        "main_legs": max(0, len(far) - 1),
        "fine_legs": fine_legs,
        "main_travel": main_travel,
        "fine_travel": fine_travel,
        "main_swing_share": main_travel / fine_travel if fine_travel > 0 else None,
        "rail_alignment_error": (sum(errors) / len(errors)
                                 if errors and {t.kind for t in far} == {"peak", "valley"} else None),
        "rail_turns": len(errors),
        "event_turns": explained,
    }
