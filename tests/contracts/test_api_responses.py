"""Core HTTP contracts and the browser fixture share the Python source of truth.

A small FastAPI instance mounts only the data router; it never imports main,
runs migrations, starts the scheduler or opens a broker connection.
"""
import asyncio
import copy
import json
import os
import subprocess
import sys

import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from _paths import BACKEND_DIR, REPO_ROOT

sys.path.insert(1, str(BACKEND_DIR))
from domains.screener.schemas import ScreenerResponse
from tools.audits import api_contracts

FIXTURE = REPO_ROOT / "webapp/frontend/e2e/fixtures/screener.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_browser_fixture_uses_the_real_response_contract(payload):
    parsed = ScreenerResponse.model_validate(payload)
    assert parsed.ordered_tickers == ["DEMOA", "DEMOB", "DEMOC"]
    assert parsed.chart_data["DEMOC"].price is None
    assert parsed.chart_data["DEMOC"].base_len is None


@pytest.mark.parametrize(("field", "value"), [
    ("score", float("nan")), ("price", float("inf")),
    ("tier", "BUY"), ("base_len", -1), ("ta_grade", 101), ("candles", {}),
    ("price", "98.0"), ("base_len", True),
])
def test_malformed_chart_metadata_is_rejected(payload, field, value):
    payload["chart_data"]["DEMOA"][field] = value
    with pytest.raises(ValidationError):
        ScreenerResponse.model_validate(payload)


def test_legacy_fields_and_additive_reader_facts_are_preserved(payload):
    payload.pop("scan_identity")
    chart = payload["chart_data"]["DEMOA"]
    chart.pop("base_len")
    chart.pop("ta_grade")
    chart["score"] = 125  # Legacy raw score is not the technical grade.
    chart["future_reader_fact"] = {"measured": True}
    payload["future_panel"] = [1, 2]
    parsed = ScreenerResponse.model_validate(payload).model_dump()
    assert parsed["chart_data"]["DEMOA"]["future_reader_fact"] == {"measured": True}
    assert parsed["chart_data"]["DEMOA"]["base_len"] is None
    assert parsed["future_panel"] == [1, 2]


def test_ungraded_fire_may_have_no_chart_but_charts_must_belong_to_the_order(payload):
    payload["ordered_tickers"].append("NODRAW")
    ScreenerResponse.model_validate(payload)
    payload["chart_data"]["ORPHAN"] = copy.deepcopy(payload["chart_data"]["DEMOA"])
    with pytest.raises(ValidationError, match="belong to ordered_tickers"):
        ScreenerResponse.model_validate(payload)


def test_duplicate_order_is_rejected(payload):
    payload["ordered_tickers"].append("DEMOA")
    with pytest.raises(ValidationError, match="duplicates"):
        ScreenerResponse.model_validate(payload)


def _app(monkeypatch, payload):
    from domains.screener import router

    monkeypatch.setattr(router, "_artifact_state", lambda _: (
        type("Universe", (), {"key": "us_stocks"})(), "unused", "ready", payload["scanned_at"],
    ))
    monkeypatch.setattr(router, "read_screener_data", lambda _: payload)
    monkeypatch.setattr(router.scan_diagnosis, "current_scan_stale_after", lambda _: payload["stale_after"])
    app = FastAPI()
    app.include_router(router.router)
    return app


def _get(app, path="/screener-data/", *, raise_errors=True):
    """Drive ASGI directly, following the existing upload-handler tests.

    Only HTTP scope is sent: no listener, lifespan or extra HTTP test library.
    """
    status, chunks = [], []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])
        if message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    scope = {"type": "http", "http_version": "1.1", "method": "GET",
             "path": path, "query_string": b"", "headers": [], "scheme": "http"}
    try:
        asyncio.run(app(scope, receive, send))
    except ValidationError:
        if raise_errors:
            raise
    return status[-1], b"".join(chunks)


def test_http_response_preserves_extra_fields_and_does_not_invent_legacy_measurements(monkeypatch, payload):
    payload["chart_data"]["DEMOA"].pop("base_len")
    payload["new_top_level_fact"] = {"engine_owned": True}
    app = _app(monkeypatch, payload)
    status, body = _get(app)
    assert status == 200
    assert json.loads(body) == payload
    schema = app.openapi()
    assert schema["paths"]["/screener-data/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/ScreenerResponse")


def test_http_route_cannot_serve_a_broken_core_contract(monkeypatch, payload):
    payload["chart_data"]["DEMOA"].pop("price")
    status, _ = _get(_app(monkeypatch, payload), raise_errors=False)
    assert status == 500


def test_generated_contracts_are_current_and_the_check_detects_drift(monkeypatch, tmp_path):
    rendered = api_contracts.render()
    for name, content in rendered.items():
        assert (api_contracts.DESTINATION / name).read_text(encoding="utf-8") == content
        (tmp_path / name).write_text(content, encoding="utf-8")
    monkeypatch.setattr(api_contracts, "DESTINATION", tmp_path)
    monkeypatch.setattr(sys, "argv", ["api_contracts", "--check"])
    assert api_contracts.main() == 0
    path = tmp_path / "contracts.js"
    path.write_text("stale", encoding="utf-8")
    assert api_contracts.main() == 1
    assert path.read_text(encoding="utf-8") == "stale"  # check never repairs itself.


def test_exporter_import_does_not_connect_to_sqlite_or_load_app_startup(tmp_path):
    code = """
import sqlite3, sys
def refuse(*args, **kwargs):
    raise AssertionError('API contract export must not connect to a database')
sqlite3.connect = refuse
from tools.audits import api_contracts
assert api_contracts.render()
assert 'main' not in sys.modules and 'app.startup' not in sys.modules
assert not any(name == 'engine_alpha' or name.startswith('engine_alpha.') for name in sys.modules)
"""
    database = tmp_path / "unused.db"
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT,
        env={**os.environ, "CHROLLO_DB_PATH": str(database)}, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not database.exists()
