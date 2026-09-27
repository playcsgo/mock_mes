from pymongo.asynchronous.database import AsyncDatabase

from app import repository
from app.alerts import YeildMonitor
from app.models import ResultIn
from app.ws_manager import manager


async def handle_result(
    db: AsyncDatabase, monitor: YeildMonitor, item: ResultIn
) -> dict:
    doc = await repository.insert_result(db, item)
    await manager.broadcast({"type": "result", "data": doc})

    alert = monitor.add(item.station, item.result == "pass")
    if alert:
        alert_doc = await repository.insert_alert(db, alert)
        await manager.broadcast({"type": "alert", "data": alert_doc})

    return doc
