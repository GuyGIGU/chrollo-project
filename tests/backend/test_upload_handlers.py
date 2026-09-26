"""The two converted upload handlers, driven end to end through the real
multipart parser — and the attachment URL they mint.

Council 2026-09-07 finding 12 turned ``/ibkr/import-csv`` and the journal
attachment upload from ``async def`` + ``await file.read()`` into sync ``def``
+ ``file.file.read()``. ``test_handler_concurrency_shape.py`` pins the SHAPE;
nothing pinned that the BYTES still arrive. That swap depends entirely on the
spooled upload being positioned at 0 — get it wrong and both handlers read
``b""`` and answer a cheerful ``400 "Empty file"`` forever, with every test
still green (fix review 2026-09-07, finding 4).

So: a hand-built multipart body pushed through the router's own ASGI app —
Starlette's real parser, python-multipart's real spooling, both regimes (the
in-memory spool and one that has spilled past Starlette's 1 MB threshold to a
real temp file). No ``httpx`` (not a project dependency, so no ``TestClient``),
no booted app, no live DB: EC-22's throwaway in-memory SQLite, with the upload
root redirected into ``tmp_path``.

The same round trip pins the attachment ``url`` contract (fix review finding
1): it must be RELATIVE. An absolute API-origin URL is same-origin in
production but cross-origin under ``npm run dev``, where the browser loads it
as a no-cors ``<img>`` subresource that carries no ``Origin`` — nothing for the
same-app guard's dev allowlist to match — and the guard refuses it. The other
half of that contract, the Vite dev proxy, is pinned here too: the two are only
correct together.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys

import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models  # noqa: E402
from database import get_db  # noqa: E402
from domains.trading import journal
from domains.portfolio import router as portfolio  # noqa: E402

_BOUNDARY = "----chrollo-upload-test"
# Starlette spools a part in memory up to 1 MB, then spills it to a real temp
# file. The spilled regime is the one where a stale stream position would bite.
_SPILLED = 1024 * 1024 + 4096


def _multipart(filename: str, content_type: str, payload: bytes) -> bytes:
    head = (
        f"--{_BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("latin-1")
    return head + payload + f"\r\n--{_BOUNDARY}--\r\n".encode("latin-1")


def _post(app, path: str, body: bytes):
    """One real POST through the app's ASGI callable. Returns (status, json)."""
    status, chunks, delivered = {}, [], {"done": False}

    async def receive():
        if delivered["done"]:
            return {"type": "http.disconnect"}
        delivered["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status["value"] = message["status"]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "client": ("127.0.0.1", 54321),
        "server": ("localhost", 8000),
        "headers": [
            (b"host", b"localhost:8000"),
            (b"content-type",
             f"multipart/form-data; boundary={_BOUNDARY}".encode("latin-1")),
            (b"content-length", str(len(body)).encode()),
        ],
    }
    asyncio.run(app(scope, receive, send))
    raw = b"".join(chunks)
    return status.get("value"), (json.loads(raw) if raw else None)


@pytest.fixture()
def db_session():
    # StaticPool + check_same_thread: the handler is sync `def`, so FastAPI runs
    # it in a THREADPOOL worker (the very property finding 12 restored). Default
    # SQLite pooling would hand that thread its own empty :memory: database.
    engine = create_engine("sqlite:///:memory:", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def journal_app(db_session, tmp_path, monkeypatch):
    """The journal router alone, on a throwaway DB and a throwaway upload root."""
    monkeypatch.setattr(journal, "UPLOAD_ROOT", str(tmp_path))
    monkeypatch.setattr(journal, "_UPLOAD_ROOT_REAL", os.path.realpath(str(tmp_path)))
    db_session.add(models.TradeLog(id=1, ticker="NVDA", direction="L"))
    db_session.commit()

    app = FastAPI()
    app.include_router(journal.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return app


@pytest.mark.parametrize("size", [11, _SPILLED], ids=["in-memory-spool", "spilled-to-disk"])
def test_the_attachment_upload_stores_the_exact_bytes_it_was_sent(journal_app, tmp_path, size):
    payload = (b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * (size // 256 + 1))[:size]
    sha = hashlib.sha256(payload).hexdigest()

    status, body = _post(journal_app, "/trades/1/attachments",
                         _multipart("chart.png", "image/png", payload))

    assert status == 200, body
    assert body["size_bytes"] == len(payload)
    stored = tmp_path / "1" / f"{sha}.png"
    assert stored.exists(), "the handler stored nothing under the content hash"
    assert stored.read_bytes() == payload, "the stored bytes are not the sent bytes"


def test_the_attachment_url_is_relative_so_the_browser_loads_it_same_origin(journal_app):
    """An absolute API-origin URL is refused by the same-app guard under
    `npm run dev`: the browser loads it as a no-cors <img> subresource, which
    sends no Origin for the dev allowlist to match (fix review finding 1)."""
    _, body = _post(journal_app, "/trades/1/attachments",
                    _multipart("chart.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 32))

    assert body["url"] == f"/attachments/{body['id']}/file", (
        "the attachment URL must be relative; an absolute one is cross-origin "
        "in dev and the same-app guard refuses the image load"
    )


def test_the_dev_server_proxies_the_attachment_path():
    """The other half of that contract: relative only reaches the API in dev
    because Vite forwards /attachments. Drop the proxy and the thumbnails 404."""
    config = (ROOT / "webapp" / "frontend" / "vite.config.js").read_text(encoding="utf-8")
    assert "'/attachments'" in config and "proxy" in config, (
        "vite.config.js must proxy /attachments to the API, or the relative "
        "attachment URL resolves to the dev server and never reaches the backend"
    )


def test_the_ibkr_statement_import_parses_the_exact_bytes_it_was_sent(monkeypatch):
    """The handler's whole job before the service call is reading the upload:
    `await file.read()` -> `file.file.read()` is exactly the swap that silently
    yields b"" and answers 400 "Empty file"."""
    seen = {}

    def _fake_import(content: str):
        seen["content"] = content
        return {"imported": 1}

    monkeypatch.setattr(portfolio.csv_import, "import_activity_statement", _fake_import)

    # BOM-prefixed, because IBKR statements are and `_decode_statement` strips it.
    statement = "\ufeffTrades,Header,Symbol\r\nTrades,Data,NVDA\r\n"
    app = FastAPI()
    app.include_router(portfolio.router)

    status, body = _post(app, "/ibkr/import-csv",
                         _multipart("statement.csv", "text/csv",
                                    statement.encode("utf-8")))

    assert status == 200, body
    assert body == {"imported": 1}
    assert seen["content"] == statement.lstrip("\ufeff")
