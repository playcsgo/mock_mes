from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app import repository
from app.models import ResultIn
from app.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/station")
async def station_ws(websocket: WebSocket):
    await websocket.accept()
    db = websocket.app.state.db
    monitor = websocket.app.state.monitor

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                item = ResultIn.model_validate_json(raw)

            except ValidationError as e:
                await websocket.send_json(
                    {
                        "ok": False,
                        "error": e.errors(include_url=False, include_context=False),
                    }
                )
                continue

            doc = await repository.insert_result(db, item)
            await manager.broadcast({"type": "result", "data": doc})

            alert = monitor.add(item.station, item.result == "pass")
            if alert:
                alert_doc = await repository.insert_alert(db, alert)
                await manager.broadcast({"type": "alert", "data": alert_doc})

            # ack
            await websocket.send_json({"ok": True, "id": doc["id"]})
    except WebSocketDisconnect:
        pass
