"""IBKR connection control endpoints."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import broker_config
from ibkr import get_ibkr_service

router = APIRouter(prefix="", tags=["ibkr"])


class ModePayload(BaseModel):
    mode: str
    confirm: bool = False


class ClientPayload(BaseModel):
    client: str


class ReconnectPayload(BaseModel):
    confirm: bool = False


@router.get("/ibkr/status")
def ibkr_status():
    svc = get_ibkr_service()
    snap = svc.snapshot()
    return {
        "available": svc.is_available(),
        "connected": snap["connected"],
        "mode": snap["mode"],
        "client": snap["client"],
        "host": snap["host"],
        "port": snap["port"],
        "client_id": snap["client_id"],
        "last_update": snap["last_update"],
        "last_error": snap["last_error"],
        "stale": snap.get("stale", False),
        "daily_restart": snap.get("daily_restart", False),
        "session_competition": snap.get("session_competition", False),
        "paused": svc.is_paused(),
    }


@router.post("/ibkr/mode")
def set_ibkr_mode(payload: ModePayload):
    mode = payload.mode.strip().lower()
    if mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="mode must be 'paper' or 'live'")
    if mode == "live" and not payload.confirm:
        raise HTTPException(status_code=400, detail="switching to live requires confirm=true")

    svc = get_ibkr_service()
    _stop_service(svc, "mode switch")
    broker_config.set_mode(mode)
    svc.apply_settings()
    _start_service(svc, "mode switch", confirmed=payload.confirm)
    return _connection_response(svc)


@router.post("/ibkr/client")
def set_ibkr_client(payload: ClientPayload):
    client = payload.client.strip().lower()
    if client not in ("tws", "gateway"):
        raise HTTPException(status_code=400, detail="client must be 'tws' or 'gateway'")

    svc = get_ibkr_service()
    _stop_service(svc, "client switch")
    broker_config.set_client(client)
    svc.apply_settings()
    _start_service(svc, "client switch")
    return _connection_response(svc)


@router.post("/ibkr/reconnect")
def ibkr_reconnect(payload: Optional[ReconnectPayload] = None):
    svc = get_ibkr_service()
    svc.resume()
    _start_service(svc, "manual reconnect", confirmed=bool(payload.confirm) if payload else False)
    snap = svc.snapshot()
    return {
        "connected": snap["connected"],
        "session_competition": snap.get("session_competition", False),
        "paused": svc.is_paused(),
        "last_error": snap.get("last_error"),
    }


@router.post("/ibkr/disconnect")
def ibkr_disconnect():
    svc = get_ibkr_service()
    _stop_service(svc, "manual disconnect")
    snap = svc.snapshot()
    return {
        "connected": snap["connected"],
        "session_competition": snap.get("session_competition", False),
        "paused": svc.is_paused(),
    }


def _start_service(svc, action: str, confirmed: bool = False) -> None:
    try:
        svc.start(confirmed=confirmed)
    except Exception:
        logging.exception("Failed to start IBKR after %s", action)


def _stop_service(svc, action: str) -> None:
    try:
        svc.stop()
    except Exception:
        logging.exception("Failed to stop IBKR before %s", action)


def _connection_response(svc) -> dict:
    snap = svc.snapshot()
    return {
        "client": snap["client"],
        "mode": snap["mode"],
        "port": snap["port"],
        "connected": snap["connected"],
        "last_error": snap.get("last_error"),
    }
