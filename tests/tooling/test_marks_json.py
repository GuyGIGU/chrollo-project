"""tools.marks_json — the ONE validated loader for the docs/ JSON marks
corpora (EC-13): a malformed row refuses loudly NAMING the offender (never a
silent skip), legal shapes from the real corpora load verbatim, and the
fingerprint tracks exactly the set scored."""
import json
import os

import pytest

from _paths import REPO_ROOT
from tools.marks_json import VERDICTS, load_marks_json, marks_json_fingerprint

_ROOT = str(REPO_ROOT)


def _write(tmp_path, corpus):
    p = tmp_path / "marks.json"
    p.write_text(json.dumps(corpus), encoding="utf-8")
    return str(p)


def _mark(**over):
    base = {"ticker": "MAN", "source": "operator", "as_of": "2026-08-14"}
    base.update(over)
    return base


# ── the real corpora are the legal-shape spec ───────────────────────────────

def test_repo_corpora_load():
    trend_end = load_marks_json(
        os.path.join(_ROOT, "docs", "trend_end_marks_2026-08.json"))
    assert len(trend_end) >= 15          # append-only: may grow, never shrink
    power_play = load_marks_json(
        os.path.join(_ROOT, "docs", "power_play_marks_2026-08.json"))
    assert isinstance(power_play, list)


def test_null_and_absent_optional_fields_are_legal(tmp_path):
    # The AMH shape (ar: null) and the NRIM shape (no dated fields at all).
    marks = load_marks_json(_write(tmp_path, {"marks": [
        _mark(trend_end="2026-07-07", ar=None),
        _mark(ticker="NRIM", ruling="NOT RULED"),
        _mark(ticker="LZB", root_swing_span=["2026-06-18", "2026-06-24"]),
        _mark(ticker="FTNT", verdict="keep", certified=False),
    ]}))
    assert [m["ticker"] for m in marks] == ["MAN", "NRIM", "LZB", "FTNT"]


# ── one refusal case per validation KIND, each naming the offender ──────────

def test_corpus_without_marks_list_refuses(tmp_path):
    with pytest.raises(ValueError, match="'marks' list"):
        load_marks_json(_write(tmp_path, {"rows": []}))


def test_transposed_span_refuses_naming_the_mark(tmp_path):
    # The glossary defines spans start-then-end, and the readme warns the
    # operator's dates arrive day-month — a transposed pair would slice to an
    # empty window downstream, the silently-shrunk denominator this loader
    # aborts on (2026-08-17 review, Leach).
    with pytest.raises(ValueError, match=r"\(LZB\).*starts after it ends"):
        load_marks_json(_write(tmp_path, {"marks": [
            _mark(ticker="LZB",
                  root_swing_span=["2026-06-24", "2026-06-18"])]}))


def test_row_missing_ticker_refuses_with_identity(tmp_path):
    with pytest.raises(ValueError, match=r"mark\[0\] \(<no ticker>\).*'ticker'"):
        load_marks_json(_write(tmp_path, {"marks": [
            {"source": "operator", "as_of": "2026-08-14"}]}))


def test_bad_as_of_refuses(tmp_path):
    with pytest.raises(ValueError, match=r"\(MAN\): as_of"):
        load_marks_json(_write(tmp_path, {"marks": [
            {"ticker": "MAN", "source": "operator", "as_of": "14/08/2026"}]}))


def test_non_iso_date_field_refuses(tmp_path):
    # The exact trap the loader exists for: an untranscribed DD/MM date.
    with pytest.raises(ValueError, match=r"\(MAN\): trend_end '17/07/2026'"):
        load_marks_json(_write(tmp_path, {"marks": [
            _mark(trend_end="17/07/2026")]}))


def test_malformed_span_refuses(tmp_path):
    with pytest.raises(ValueError, match=r"\(LZB\): root_swing_span"):
        load_marks_json(_write(tmp_path, {"marks": [
            _mark(ticker="LZB", root_swing_span=["2026-06-18"])]}))


def test_unknown_verdict_refuses(tmp_path):
    assert VERDICTS == ("keep", "junk")
    with pytest.raises(ValueError, match=r"\(MAN\): verdict 'maybe'"):
        load_marks_json(_write(tmp_path, {"marks": [_mark(verdict="maybe")]}))


def test_non_bool_certified_refuses(tmp_path):
    with pytest.raises(ValueError, match=r"\(MAN\): certified"):
        load_marks_json(_write(tmp_path, {"marks": [_mark(certified="yes")]}))


# ── the fingerprint tracks exactly the set scored ───────────────────────────

def test_fingerprint_is_order_insensitive_and_set_exact():
    a = _mark(verdict="keep")
    b = _mark(ticker="FTNT", verdict="junk")
    fp = marks_json_fingerprint([a, b])
    assert len(fp) == 64
    assert fp == marks_json_fingerprint([b, a])          # order never matters
    assert fp != marks_json_fingerprint([a])             # a filtered run claims less
    assert fp != marks_json_fingerprint([a, _mark(ticker="FTNT", verdict="keep")])
