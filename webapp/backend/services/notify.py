"""Shared webhook notification helpers."""
from __future__ import annotations

import json
import logging
import os
import urllib.request

from services.core_settings import load_core_settings

log = logging.getLogger("chrollo.notify")


def post_webhook(text: str) -> bool:
    """Post a simple text payload to the configured alert webhook."""
    settings = load_core_settings()
    env_name = getattr(settings, "ALERT_WEBHOOK_URL_ENV", "ALERT_WEBHOOK_URL")
    url = os.environ.get(env_name)
    if not url:
        return False

    payload = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10).close()
        return True
    except Exception:
        log.exception("alert webhook failed")
        return False
