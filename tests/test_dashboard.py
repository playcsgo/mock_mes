import asyncio

import pytest
from fastapi import WebSocketDisconnect

from app.routes.dashboard import dashboard_ws
from app.ws_manager import manager


class MockWs:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def accept(self) -> None:
        pass

    async def receive_text(self) -> str:
        raise self.error


def test_removed_after_normal_disconnect():
    ws = MockWs(WebSocketDisconnect())
    asyncio.run(dashboard_ws(ws))  # type: ignore[arg-type]

    assert ws not in manager.active


def test_removed_after_unexpected_error():
    ws = MockWs(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        asyncio.run(dashboard_ws(ws))  # type: ignore[arg-type]

    assert ws not in manager.active
