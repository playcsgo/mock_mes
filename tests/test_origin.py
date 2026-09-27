import asyncio

import pytest

from app.config import is_allowed_origin, settings
from app.routes.dashboard import dashboard_ws
from app.ws_manager import manager


@pytest.mark.parametrize("origin", [
    None,
    "https://agilenpi.com",
    "https://agilenpi-landing-page.pages.dev",
    "http://localhost:8000",
    "http://127.0.0.1:5500",
])
def test_allowed(origin):
    assert is_allowed_origin(origin) is True


@pytest.mark.parametrize("origin", [
    "https://evil.example.com",
    "http://agilenpi.com.evil.example.com",
    "https://agilenpi.com.tw",
])
def test_rejected(origin):
    assert is_allowed_origin(origin) is False


def test_settings_parses_comma_separated_env(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", " https://a.com , https://b.com ,")
    assert settings.origin_list == ["https://a.com", "https://b.com"]


class MockWs:
    def __init__(self, origin: str) -> None:
        self.headers = {"origin": origin}
        self.closed_with = None

    async def close(self, code: int) -> None:
        self.closed_with = code


def test_bad_origin_is_closed_and_not_tracked():
    ws = MockWs("https://evil.example.com")
    asyncio.run(dashboard_ws(ws))  # type: ignore[arg-type]

    assert ws.closed_with == 1008
    assert ws not in manager.active
