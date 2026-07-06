"""Fixture under review for council drills D3 (bug caught) and D4 (memory respected)."""


def average(values):
    total = 0
    for v in values:
        total += v
    return total / len(values)          # BUG (D3): ZeroDivisionError on empty input


def last_or_none(items):
    return items[len(items) - 1] if items else None   # intentional (D4 / AP-1)
