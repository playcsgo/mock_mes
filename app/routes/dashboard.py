from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.ws_manager import manager

router = APIRouter()
DASHBOARD_HTML = Path(__file__).resolve().parents[2] / "static" / "dashboard.html"


@router.get("/", include_in_schema=False)
async def dashboard_page():
    return FileResponse(DASHBOARD_HTML)


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        pass
    finally:
        manager.disconnect(websocket)
