import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from services import notify


def test_post_webhook_uses_configured_env_name(monkeypatch):
    captured = {}

    class Response:
        def close(self):
            captured["closed"] = True

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        notify,
        "load_core_settings",
        lambda: SimpleNamespace(ALERT_WEBHOOK_URL_ENV="TEST_ALERT_WEBHOOK_URL"),
    )
    monkeypatch.setenv("TEST_ALERT_WEBHOOK_URL", "https://example.test/webhook")
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)

    assert notify.post_webhook("hello") is True
    assert captured == {
        "url": "https://example.test/webhook",
        "body": {"text": "hello"},
        "timeout": 10,
        "closed": True,
    }


def test_post_webhook_returns_false_when_unconfigured(monkeypatch):
    called = []

    monkeypatch.setattr(
        notify,
        "load_core_settings",
        lambda: SimpleNamespace(ALERT_WEBHOOK_URL_ENV="MISSING_ALERT_WEBHOOK_URL"),
    )
    monkeypatch.delenv("MISSING_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(notify.urllib.request, "urlopen", lambda *args, **kwargs: called.append(args))

    assert notify.post_webhook("hello") is False
    assert called == []
