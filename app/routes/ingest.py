from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app import pipeline
from app.config import ingest_allowed
from app.models import ResultIn

router = APIRouter()


@router.websocket("/ws/station")
async def station_ws(websocket: WebSocket):
    if not ingest_allowed(websocket.query_params.get("token")):
        await websocket.close(code=1008)
        return

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

            doc = await pipeline.handle_result(db, monitor, item)

            await websocket.send_json({"ok": True, "id": doc["id"]})
    except WebSocketDisconnect:
        pass
