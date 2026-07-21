"""Calibration marking surface — chart lookup + marks CRUD.

The chart lookup is the first backend surface fed by free-typed operator
input: strict validation at the boundary (reject, never sanitize past
case/whitespace normalization), every vendor read through the one market-data
doorway (inherits the provider's hang bound + shared rate-limit bucket), and
every operational failure mapped to a DISTINCT, renderable answer — degrade,
never 500 (EC-6 pattern). The payload carries the point-in-time provenance a
saved mark must echo (data regime, engine config version, the as-of bar's
close): marks are born on the exact frame the operator looked at, never
re-stamped after the fact.

Marks CRUD is a GROUND-TRUTH WRITE surface (EC-9): saves validate through the
one shared judgment (`marks_validity.validate_mark`), writes fail loud and
echo back the row as persisted, saving never triggers a vendor fetch, and
every mutating request must carry the same-app header — any web page open in
the operator's browser can fire blind cross-origin writes at localhost, and
custom headers force a CORS preflight such pages cannot pass.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from marks_validity import TICKER_RE, parse_iso_date, validate_mark
from models import CalibrationMark, CalibrationMarkEvent

router = APIRouter(prefix="/calibration", tags=["calibration"])
logger = logging.getLogger("chrollo.calibration")

_CLIENT_HEADER_VALUE = "chrollo-dashboard"


def require_same_app(x_chrollo_client: str = Header(default="")):
    """Mutating calibration requests only from our own frontend."""
    if x_chrollo_client != _CLIENT_HEADER_VALUE:
        raise HTTPException(status_code=403, detail={
            "class": "cross_app_write",
            "message": "calibration writes require the X-Chrollo-Client header",
        })

_LOOKBACK_DAYS = 900   # calendar lead-in behind the as-of bar (~2y of sessions + margin)
_FORWARD_DAYS = 45     # hindsight context after it (archive-chart precedent)
_DATE_FLOOR = "2000-01-01"
_SHORT_FRAME_BARS = 300  # below this the engine's 2y frame is visibly truncated


def _refuse(status: int, reason_class: str, message: str, ticker: str, as_of: str):
    """One structured log line per degraded outcome class, then the refusal."""
    logger.info("chart %s ticker=%s as_of=%s: %s", reason_class, ticker, as_of, message)
    raise HTTPException(status_code=status,
                        detail={"class": reason_class, "message": message})


@router.get("/chart", dependencies=[Depends(require_same_app)])
def calibration_chart(ticker: str = Query(...), as_of: str = Query(...)):
    """Daily candles for any ticker anchored at any historical as-of date.

    Guarded like the writes: this GET has side effects (it spends the shared
    vendor rate bucket and freezes a replay frame), so a drive-by cross-origin
    request must not reach it — only our own frontend ever calls it.
    """
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, as_of)
    as_of_dt = parse_iso_date(as_of)
    if as_of_dt is None:
        _refuse(400, "bad_date", "as_of must be exactly YYYY-MM-DD", symbol, as_of)
    if as_of < _DATE_FLOOR:
        _refuse(400, "bad_date", f"as_of before the {_DATE_FLOOR} floor", symbol, as_of)
    if as_of_dt.date() > datetime.now(timezone.utc).date():
        _refuse(400, "future_date", "as_of is in the future", symbol, as_of)

    import pandas as pd

    from core.pipeline.downloads import _price_regime, price_auto_adjust  # noqa: PLC0415 — lazy, yfinance-heavy chain
    from engine_alpha.freeze.manifest import manifest_hash  # noqa: PLC0415
    from services.candle_cache import load_candles  # noqa: PLC0415 — session cache + resilient fetch
    from services.market_data import chart_candles  # noqa: PLC0415

    as_of_ts = pd.Timestamp(as_of)
    start = (as_of_ts - pd.Timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = (as_of_ts + pd.Timedelta(days=_FORWARD_DAYS)).strftime("%Y-%m-%d")
    # Session cache + transient-throttle-aware fetch: a day-scrub slices a cached
    # window instead of re-pulling ~900 bars, and a rate-limit blip surfaces as a
    # calm, distinct class (never the scary "delisted?" copy) with any loaded
    # chart left up. The cache is display-only — the freeze below reads this
    # frame, but the digest is computed exactly as before.
    raw, fetch_status = load_candles(symbol, start, end, price_auto_adjust())
    if fetch_status == "rate_limited":
        _refuse(503, "rate_limited",
                "the market-data vendor is throttling right now — any chart you "
                "already loaded stays up; wait a few seconds and retry", symbol, as_of)
    if raw.empty:
        _refuse(404, "no_data",
                "no data for this ticker — it may be unknown or delisted, or the "
                "vendor may be briefly throttling; wait a moment and retry",
                symbol, as_of)

    frame = raw[raw.index <= as_of_ts]
    if frame.empty:
        first = raw.index[0].strftime("%Y-%m-%d")
        _refuse(404, "no_bars_at_date",
                f"history for {symbol} starts {first}, after the requested as-of",
                symbol, as_of)

    as_of_session = frame.index[-1].strftime("%Y-%m-%d")
    anchor_close = frame.iloc[-1]["Close"]
    try:
        anchor_close = float(anchor_close)
    except (TypeError, ValueError):
        anchor_close = float("nan")
    if not (anchor_close == anchor_close and anchor_close > 0):  # NaN-safe
        _refuse(404, "no_data", f"no finite close on {as_of_session}", symbol, as_of)

    warnings = []
    if as_of_session != as_of:
        warnings.append(f"{as_of} is not a session; resolved to {as_of_session}")
    if len(frame) < _SHORT_FRAME_BARS:
        warnings.append(f"short history ({len(frame)} bars): the engine's 2y frame "
                        "is truncated here — marks may grade edge-uncertain")

    # Freeze the replay-relevant (<= as-of) frame and bind the mark to what
    # the operator is LOOKING at (Task 7). A digest divergence means the
    # vendor restated since the first freeze — the store versions the new
    # rendering by digest, so marks on either rendering keep their basis.
    # Freeze I/O failures get a named class: a chart whose frame could not
    # be frozen would produce unreplayable marks, so it is withheld loudly.
    from frame_store import freeze_frame, freeze_grading_frame  # noqa: PLC0415 — file I/O module, lazy like the fetch chain
    try:
        current_digest, stored_digest = freeze_frame(symbol, as_of_session, frame)
    except Exception as exc:
        _refuse(503, "freeze_failed",
                f"could not freeze the replay frame ({exc.__class__.__name__}) — "
                "marks made on this chart would not be replayable; check disk "
                "space / calibration_frames permissions and retry", symbol, as_of)
    if current_digest != stored_digest:
        warnings.append("the vendor restated this data since the chart was first "
                        "frozen — today's rendering is frozen alongside the "
                        "original, and marks replay against the frame matching "
                        "their own digest (nothing is lost)")

    # Freeze the forward-inclusive frame too (Task 2), so a Trigger grade — a buy
    # AFTER as-of — can replay frozen-only (no vendor fetch, no lookahead). Best-
    # effort and non-blocking: the mark's <= as-of basis is already frozen and
    # savable above; if the grading frame cannot be written the Trigger grade is
    # merely unavailable until a reload, never a lost or unreplayable mark. `raw`
    # spans [frame_start, frame_end] and is addressed by the <= as-of digest.
    try:
        freeze_grading_frame(symbol, as_of_session, raw, current_digest)
    except Exception:
        logger.info("grading-frame freeze skipped %s@%s", symbol, as_of_session)

    candles, volumes = chart_candles(
        raw,
        up_color="rgba(38, 166, 154, 0.5)",
        down_color="rgba(239, 83, 80, 0.5)",
        require_finite=True,
        volume_as_int=True,
    )
    # Adjacent SESSIONS, named by the server (it holds the whole frame): the
    # day-scrub steps real sessions instead of guessing calendar days into
    # weekends/holidays. None = the edge of the fetched window.
    forward_idx = raw.index[raw.index > frame.index[-1]]
    prev_session = frame.index[-2].strftime("%Y-%m-%d") if len(frame) > 1 else None
    next_session = forward_idx[0].strftime("%Y-%m-%d") if len(forward_idx) else None

    return {
        "ticker": symbol,
        "as_of": as_of,
        "as_of_session": as_of_session,
        "prev_session": prev_session,
        "next_session": next_session,
        "anchor_close": anchor_close,
        "bar_count": int(len(frame)),
        "forward_bars": int((raw.index > as_of_ts).sum()),
        "frame_start": raw.index[0].strftime("%Y-%m-%d"),
        "frame_end": raw.index[-1].strftime("%Y-%m-%d"),
        "data_regime": _price_regime(),
        "engine_config_version": manifest_hash(),
        "frame_digest": current_digest,
        "warnings": warnings,
        "candles": candles,
        "volumes": volumes,
    }


# ── Engine-read overlay ──────────────────────────────────────────────

# One structure read per frame identity per process — a sitting revisits the
# same frames constantly and the read is pure compute over a frozen file.
_ENGINE_READS: dict = {}


@router.get("/engine-read", dependencies=[Depends(require_same_app)])
def calibration_engine_read(ticker: str = Query(...), as_of: str = Query(...),
                            frame_digest: Optional[str] = Query(None)):
    """The engine's read of a FROZEN calibration frame, through the agreement
    harness's own lens (``tools.replay.snapped_election`` + the shared
    ``election_identity.projection``) — the same lens the harness scores, never
    a richer parallel read (one-lens rule, Task 6). Parity is exact for a BOX
    verdict; the overlay always walks back the snap window, whereas the harness
    grades a NEGATIVE mark at snap 0 — so for a negative session the overlay's
    snapped-back election can differ from the harness's no-read grade.

    Frozen-or-refuse: never triggers a vendor fetch — the chart lookup must
    have frozen this session first. Guarded like the chart GET (it runs a
    full structure read; drive-by pages don't get to spend that). The UI
    keeps the overlay default-OFF: the operator marks first, peeks after —
    anchoring marks on the engine's read corrupts the ground truth.
    """
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, as_of)
    if parse_iso_date(as_of) is None:
        _refuse(400, "bad_date", "as_of must be exactly YYYY-MM-DD", symbol, as_of)

    from frame_store import load_frame  # noqa: PLC0415 — file I/O module, lazy
    frozen = load_frame(symbol, as_of, digest=frame_digest)
    if frozen is None:
        _refuse(404, "unbound_frame",
                "no frozen frame for this session — load the chart first; the "
                "engine overlay replays frozen frames only", symbol, as_of)

    from engine_alpha.freeze.manifest import manifest_hash  # noqa: PLC0415
    key = (symbol, as_of, frame_digest or "", manifest_hash())
    if key in _ENGINE_READS:
        return _ENGINE_READS[key]

    from engine_alpha.election_identity import projection  # noqa: PLC0415
    from tools import replay  # noqa: PLC0415 — pandas/scipy-heavy chain

    result = {
        "ticker": symbol,
        "as_of_session": as_of,
        "snap_back": replay.SNAP_BACK_SESSIONS,
        "engine_config_version": manifest_hash(),
        "elected": False,
    }
    snapped = replay.snapped_election(frozen, as_of, [{}])
    if snapped is None:
        result["reason"] = "prep refuses every candidate session (frame too thin)"
    else:
        (df, _atr, reads), eval_ts, snapped_k = snapped
        result["eval_session"] = eval_ts.strftime("%Y-%m-%d")
        result["snapped"] = snapped_k
        read = projection(reads[0], df)
        if read is None:
            result["reason"] = "no structure elects within the snap window"
        else:
            result["elected"] = True
            result.update(read)
    _ENGINE_READS[key] = result
    logger.info("engine-read %s@%s elected=%s", symbol, as_of, result["elected"])
    return result


# ── Engine agreement (v2 ledger "Engine" chip) ───────────────────────


@router.get("/agreement", dependencies=[Depends(require_same_app)])
def calibration_agreement(ticker: str = Query(...), db: Session = Depends(get_db)):
    """Per-mark engine agreement for a ticker's marks — the ledger 'Engine'
    chip. Answers the operator's HEADLINE question (did the engine SURFACE a
    setup at my pick?) via the harness's own election grade, so the chip never
    drifts from ``python -m tools.calibration_harness``. Guarded like
    /engine-read: box marks run a real structure read (drive-by pages don't get
    to spend that), and the result is memoized per (mark id, revision, engine
    manifest). Frozen-or-refuse + read-only: never a vendor fetch, never a
    write. Not the sharper fired-in-window criterion — that is a later layer.
    """
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, "")
    marks = (db.query(CalibrationMark)
             .filter(CalibrationMark.ticker == symbol)
             .order_by(CalibrationMark.as_of_date).all())
    from services.calibration_agreement import agreement_for_marks  # noqa: PLC0415 — harness/pandas chain, lazy
    return {"ticker": symbol, "marks": agreement_for_marks(marks)}


# ── Frame thumbnail (v2 ledger mini-chart) ───────────────────────────

# A frame's downsampled preview is pure price geometry — invariant to the
# engine, uniquely addressed by the content digest. A restatement is a new
# digest = a new key, so the cache invalidates by construction (never key by
# (ticker, as_of), which collides across restatements). Regenerable from the
# parquet, unlike the load-bearing frames themselves.
_FRAME_PREVIEWS: dict = {}


@router.get("/frame-thumb", dependencies=[Depends(require_same_app)])
def calibration_frame_thumb(ticker: str = Query(...), as_of: str = Query(...),
                            frame_digest: str = Query(...)):
    """A downsampled close-line + price envelope for the ledger frame
    thumbnail. Frozen-or-refuse + read-only (never a vendor fetch), computed
    once per digest and cached — the render path never re-reads the parquet.
    The operator's box overlay is drawn client-side from the mark's own rails,
    NOT carried here, so this feed stays pure price geometry.
    """
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, as_of)
    if parse_iso_date(as_of) is None:
        _refuse(400, "bad_date", "as_of must be exactly YYYY-MM-DD", symbol, as_of)
    if not frame_digest:
        _refuse(400, "bad_digest", "frame_digest is required", symbol, as_of)

    cached = _FRAME_PREVIEWS.get(frame_digest)
    if cached is not None:
        return cached

    from frame_store import load_frame, preview_series  # noqa: PLC0415 — file I/O module, lazy
    frozen = load_frame(symbol, as_of, digest=frame_digest)
    if frozen is None:
        _refuse(404, "unbound_frame",
                "no frozen frame matches this digest — the thumbnail replays "
                "frozen frames only", symbol, as_of)
    result = {"ticker": symbol, "as_of_session": as_of,
              "frame_digest": frame_digest, **preview_series(frozen)}
    _FRAME_PREVIEWS[frame_digest] = result
    return result


# ── Fired-in-window grade (the sharper ledger chip) ──────────────────


@router.get("/fired", dependencies=[Depends(require_same_app)])
def calibration_fired(ticker: str = Query(...), db: Session = Depends(get_db)):
    """Per-mark FIRED-in-window grade — the operator's "pops-up-live" bar: would
    this pick have appeared on the nightly screener? Runs the FULL scoring
    pipeline per box mark (~1s/session), so it NEVER blocks the request: a cache
    miss is enqueued to a single background worker and returned as 'pending', and
    the client polls `computing` until it settles. Guarded + read-only +
    frozen-or-refuse; degrade-never-500. This is the sharper criterion the
    concordance chip (/agreement) points at.
    """
    symbol = ticker.strip().upper()
    if not TICKER_RE.match(symbol):
        _refuse(400, "bad_ticker",
                "ticker must be 1-10 chars of A-Z, 0-9, '.' or '-'", symbol, "")
    marks = (db.query(CalibrationMark)
             .filter(CalibrationMark.ticker == symbol)
             .order_by(CalibrationMark.as_of_date).all())
    from services.calibration_fired import fired_for_marks  # noqa: PLC0415 — harness/pandas chain, lazy
    return {"ticker": symbol, **fired_for_marks(marks)}


# ── Marks CRUD (Task 4) ──────────────────────────────────────────────


class EventIn(BaseModel):
    event_type: str
    start_date: str
    end_date: str
    tip_date: Optional[str] = None
    tip_price: Optional[float] = None
    source: str = "operator"


class MarkIn(BaseModel):
    """Full mark payload. Cross-field sanity lives in the ONE shared judgment
    (marks_validity) — this model only shapes/types the boundary."""
    ticker: str
    as_of_date: str
    label: str = ""
    verdict: str
    resistance: Optional[float] = None
    support: Optional[float] = None
    box_start_date: Optional[str] = None
    box_end_date: Optional[str] = None
    r_anchor_date: Optional[str] = None
    s_anchor_date: Optional[str] = None
    first_rail: Optional[str] = None
    # The Trigger (the operator's buy) — shape here, semantics in shared validity
    # (box-only, requires an LPS, forward-of-as-of); the frame-dependent upper
    # bound (a real session <= frame_end) is enforced at the write boundary.
    trigger_date: Optional[str] = None
    trigger_price: Optional[float] = None
    rails_source: str = "operator"
    knowable_from_date: Optional[str] = None
    note: Optional[str] = None
    data_regime: str
    engine_config_version: str
    anchor_close: float
    frame_digest: Optional[str] = None
    events: List[EventIn] = []


class EventOut(EventIn):
    id: int
    model_config = {"from_attributes": True}


class MarkOut(BaseModel):
    id: int
    ticker: str
    as_of_date: str
    label: str
    verdict: str
    resistance: Optional[float] = None
    support: Optional[float] = None
    box_start_date: Optional[str] = None
    box_end_date: Optional[str] = None
    r_anchor_date: Optional[str] = None
    s_anchor_date: Optional[str] = None
    first_rail: Optional[str] = None
    # Presented as explicit null (never omitted) so the client can always read
    # "no buy marked" without guessing.
    trigger_date: Optional[str] = None
    trigger_price: Optional[float] = None
    rails_source: str
    knowable_from_date: Optional[str] = None
    note: Optional[str] = None
    data_regime: str
    engine_config_version: str
    anchor_close: float
    frame_digest: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    revision: int
    events: List[EventOut] = []

    model_config = {"from_attributes": True}


def _reject_invalid(payload: MarkIn):
    # Normalize-then-judge, same order as the chart lookup: the shared
    # judgment sees exactly the identity the row will be saved under.
    # Label is an identity component too — "lps", "lps " and "LPS" must be
    # ONE identity, or near-duplicates slip past the unique key.
    data = {**payload.model_dump(exclude={"events"}),
            "events": [e.model_dump() for e in payload.events]}
    data["ticker"] = (data.get("ticker") or "").strip().upper()
    data["label"] = (data.get("label") or "").strip().lower()
    problems = validate_mark(data)
    if problems:
        raise HTTPException(status_code=422, detail={
            "class": "invalid_mark", "problems": problems,
        })


def _reject_unbound(payload: MarkIn):
    """The mark→frame binding contract: as_of_date must be the exact session
    key a chart freeze created, and frame_digest must match one frozen
    rendering (base, or the digest-qualified sibling a restatement created).
    A pure local-file check — saving never triggers a vendor fetch."""
    from frame_store import load_frame  # noqa: PLC0415 — file I/O module, lazy
    ticker = (payload.ticker or "").strip().upper()
    if load_frame(ticker, payload.as_of_date, digest=payload.frame_digest) is None:
        raise HTTPException(status_code=422, detail={
            "class": "unbound_mark",
            "message": f"no frozen frame for ({ticker}, {payload.as_of_date}) "
                       "matches this frame_digest — load the chart for that "
                       "session first; marks bind to the exact frame the "
                       "operator looked at",
        })


def _reject_unframed_trigger(payload: MarkIn):
    """The Trigger's upper bound is FRAME-DEPENDENT, so it is enforced here (not
    in pure validity, which stays import-anywhere): trigger_date must be a real
    session in the frozen forward GRADING frame — which is `<= frame_end` by
    construction, and is exactly the frozen basis the Trigger grade replays on.
    A pure local-file check; saving never triggers a vendor fetch. No trigger =>
    nothing to check."""
    if payload.trigger_date is None:
        return
    from frame_store import load_grading_frame  # noqa: PLC0415 — file I/O module, lazy
    ticker = (payload.ticker or "").strip().upper()
    grading = load_grading_frame(ticker, payload.as_of_date, payload.frame_digest)
    if grading is None:
        raise HTTPException(status_code=422, detail={
            "class": "unframed_trigger",
            "message": "the forward grading frame for this setup is not frozen — "
                       "reload the chart for that session (it freezes the forward "
                       "bars a Trigger is graded against), then save",
        })
    sessions = set(grading.index.strftime("%Y-%m-%d"))
    if payload.trigger_date not in sessions:
        raise HTTPException(status_code=422, detail={
            "class": "trigger_not_a_session",
            "message": f"trigger_date {payload.trigger_date} is not a real session "
                       "in the frozen forward window — the buy must land on a "
                       "trading day at or before the frame end",
        })


def _apply_payload(mark: CalibrationMark, payload: MarkIn):
    for field in ("ticker", "as_of_date", "label", "verdict", "resistance",
                  "support", "box_start_date", "box_end_date",
                  "r_anchor_date", "s_anchor_date", "first_rail",
                  "trigger_date", "trigger_price",
                  "rails_source", "knowable_from_date", "note", "data_regime",
                  "engine_config_version", "anchor_close", "frame_digest"):
        setattr(mark, field, getattr(payload, field))
    mark.ticker = mark.ticker.strip().upper()
    mark.label = (mark.label or "").strip().lower()
    mark.events = [CalibrationMarkEvent(**e.model_dump()) for e in payload.events]


@router.get("/marks", response_model=List[MarkOut])
def list_marks(ticker: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(CalibrationMark)
    if ticker:
        q = q.filter(CalibrationMark.ticker == ticker.strip().upper())
    return q.order_by(CalibrationMark.ticker, CalibrationMark.as_of_date).all()


def _mark_by_identity(db: Session, ticker: str, as_of_date: str, label: str):
    """The one mark under an identity grain (ticker, as_of_date, label), or
    None. Identity is normalized exactly as the write path normalizes it, so
    'lps', 'LPS ' and 'lps' resolve to the SAME row the unique key protects."""
    return (db.query(CalibrationMark)
            .filter(CalibrationMark.ticker == (ticker or "").strip().upper(),
                    CalibrationMark.as_of_date == as_of_date,
                    CalibrationMark.label == (label or "").strip().lower())
            .first())


@router.post("/marks", response_model=MarkOut,
             dependencies=[Depends(require_same_app)])
def create_mark(payload: MarkIn, db: Session = Depends(get_db)):
    _reject_invalid(payload)
    _reject_unbound(payload)
    _reject_unframed_trigger(payload)
    now = datetime.now(timezone.utc)
    mark = CalibrationMark(created_at=now, updated_at=now, revision=1)
    _apply_payload(mark, payload)
    ident = (mark.ticker, mark.as_of_date, mark.label)  # capture pre-rollback
    db.add(mark)
    try:
        db.commit()
    except IntegrityError:
        # A save under an identity that already exists is a correction, not a
        # collision (marks are editable ground truth, EC-9). The frontend
        # resolves this to a PUT before it ever gets here; this backstop names
        # the existing row's id so a racy/stale client can recover without a
        # dead-end. A genuinely distinct mark needs a distinct label.
        db.rollback()
        existing = _mark_by_identity(db, *ident)
        if existing is None:
            # No identity row — a frozen CHECK constraint (defence-in-depth over
            # validate_mark) fired, not the uniqueness collision. Name it
            # distinctly so a real constraint bug isn't disguised as a duplicate.
            raise HTTPException(status_code=422, detail={
                "class": "constraint_violation",
                "message": "the mark violates a database constraint",
            })
        raise HTTPException(status_code=409, detail={
            "class": "duplicate_mark",
            "existing_id": existing.id,
            "message": f"a mark for ({ident[0]}, {ident[1]}, {ident[2]!r}) "
                       "already exists — saving updates it (revision bumps)",
        })
    db.refresh(mark)
    logger.info("mark saved id=%s %s@%s verdict=%s", mark.id, mark.ticker,
                mark.as_of_date, mark.verdict)
    return mark


@router.put("/marks/{mark_id}", response_model=MarkOut,
            dependencies=[Depends(require_same_app)])
def update_mark(mark_id: int, payload: MarkIn, db: Session = Depends(get_db)):
    mark = db.query(CalibrationMark).filter(CalibrationMark.id == mark_id).first()
    if not mark:
        raise HTTPException(status_code=404, detail={
            "class": "unknown_mark", "message": f"no mark {mark_id}"})
    _reject_invalid(payload)
    _reject_unbound(payload)
    _reject_unframed_trigger(payload)
    # A mark's frame binding is IMMUTABLE (the module contract: provenance is
    # "never re-stamped after the fact"). The ledger lists every session's marks
    # for a ticker, so a cross-frame edit could otherwise silently move a mark's
    # replay basis to whatever frame is on screen. Refuse it loudly — an edit may
    # change geometry/verdict/label/note, never the frame the mark binds to.
    if ((payload.ticker or "").strip().upper() != mark.ticker
            or payload.as_of_date != mark.as_of_date
            or payload.frame_digest != mark.frame_digest):
        raise HTTPException(status_code=409, detail={
            "class": "frame_rebind_rejected",
            "message": "a mark's frame binding is immutable — edit it on the "
                       "frame it was drawn on; provenance is never re-stamped "
                       "onto a different session",
        })
    _apply_payload(mark, payload)
    mark.revision = mark.revision + 1  # every correction is visible
    mark.updated_at = datetime.now(timezone.utc)
    ident = (mark.ticker, mark.as_of_date, mark.label)  # capture pre-rollback
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        other = _mark_by_identity(db, *ident)
        if other is None or other.id == mark_id:
            # Not the identity collision — a frozen CHECK constraint fired.
            raise HTTPException(status_code=422, detail={
                "class": "constraint_violation",
                "message": "the edit violates a database constraint",
            })
        raise HTTPException(status_code=409, detail={
            "class": "duplicate_mark",
            "existing_id": other.id,
            "message": "edit collides with another mark's identity",
        })
    db.refresh(mark)
    logger.info("mark updated id=%s rev=%s", mark.id, mark.revision)
    return mark


@router.delete("/marks/{mark_id}", dependencies=[Depends(require_same_app)])
def delete_mark(mark_id: int, db: Session = Depends(get_db)):
    mark = db.query(CalibrationMark).filter(CalibrationMark.id == mark_id).first()
    if not mark:
        raise HTTPException(status_code=404, detail={
            "class": "unknown_mark", "message": f"no mark {mark_id}"})
    db.delete(mark)  # hard delete — no soft-delete predicate tax
    db.commit()
    logger.info("mark deleted id=%s %s@%s", mark_id, mark.ticker, mark.as_of_date)
    return {"status": "deleted", "id": mark_id}
