import asyncio
from types import SimpleNamespace

import pytest
from fastapi import WebSocketDisconnect

from app import demo
from app.routes.dashboard import dashboard_ws
from app.ws_manager import manager


@pytest.fixture(autouse=True)
def no_demo(monkeypatch):
    monkeypatch.setattr(demo, "ensure_running", lambda _app: None)


class FakeWs:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.app = SimpleNamespace(state=SimpleNamespace())
        self.headers = {}

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        raise self.error


def test_removed_after_normal_disconnect():
    ws = FakeWs(WebSocketDisconnect())
    asyncio.run(dashboard_ws(ws))  # type: ignore[arg-type]

    assert ws not in manager.active


def test_removed_after_unexpected_error():
    ws = FakeWs(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        asyncio.run(dashboard_ws(ws))  # type: ignore[arg-type]

    assert ws not in manager.active
