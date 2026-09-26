"""Helpers for serving the built React frontend."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_log = logging.getLogger("chrollo.frontend")

_INDEX_HEADERS = {
    "Cache-Control": "no-store, max-age=0, must-revalidate",
    "Expires": "0",
    "Pragma": "no-cache",
}


def mount_frontend_assets(app: FastAPI, assets_dir: str) -> None:
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")
        return
    _log.warning("frontend not built - run setup.bat to create webapp/frontend/dist")


def serve_frontend_index(index_path: str) -> FileResponse:
    if os.path.exists(index_path):
        return FileResponse(index_path, headers=_INDEX_HEADERS)
    raise HTTPException(
        status_code=503,
        detail="frontend not built - run setup.bat to create webapp/frontend/dist",
    )
