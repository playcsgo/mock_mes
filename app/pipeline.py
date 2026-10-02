from pymongo.asynchronous.database import AsyncDatabase

from app import repository
from app.alerts import YieldMonitor
from app.models import ResultIn
from app.notifier import LineNotifier
from app.ws_manager import manager


async def handle_result(
    db: AsyncDatabase,
    monitor: YieldMonitor,
    item: ResultIn,
    notifier: LineNotifier | None = None,
) -> dict:
    doc = await repository.insert_result(db, item)
    await manager.broadcast({"type": "result", "data": doc})

    alert = monitor.add(item.station, item.result == "pass")
    if alert:
        alert_doc = await repository.insert_alert(db, alert)
        await manager.broadcast({"type": "alert", "data": alert_doc})
        if notifier:
            notifier.enqueue(alert_doc)  # non-blocking; a worker pushes to LINE

    return doc
