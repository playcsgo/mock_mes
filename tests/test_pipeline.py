# type: ignore[arg-type]
import asyncio
from typing import Literal

from app import pipeline, repository
from app.alerts import YieldMonitor
from app.models import ResultIn
from tests.fakes import FakeDB

TestResult = Literal["pass", "fail"]


def make_item(result: TestResult) -> ResultIn:
    return ResultIn(
        station="ST-01",
        lot="LOT-T",
        serial="SN-T",
        result=result,
        fail_code="V_OUT_LOW" if result == "fail" else None,
    )


def feed(db: FakeDB, monitor: YieldMonitor, result: TestResult, times: int) -> None:
    async def run() -> None:
        for _ in range(times):
            await pipeline.handle_result(db, monitor, make_item(result))

    asyncio.run(run())


def test_result_is_stored_and_returned_with_id():
    db, monitor = FakeDB(), YieldMonitor()
    doc = asyncio.run(pipeline.handle_result(db, monitor, make_item("pass")))
    assert doc["id"] == "fake0"
    assert len(db[repository.RESULTS].docs) == 1
    assert db[repository.ALERTS].docs == []


def test_alert_is_stored_when_yield_drops():
    db, monitor = FakeDB(), YieldMonitor(min_samples=20, threshold=0.9)
    feed(db, monitor, "fail", 20)

    assert len(db[repository.RESULTS].docs) == 20
    assert len(db[repository.ALERTS].docs) == 1
    assert db[repository.ALERTS].docs[0]["station"] == "ST-01"


def test_no_alert_before_min_samples():
    db, monitor = FakeDB(), YieldMonitor(min_samples=20, threshold=0.9)
    feed(db, monitor, "fail", 10)

    assert len(db[repository.ALERTS].docs) == 0


class SpyNotifier:
    def __init__(self) -> None:
        self.enqueued: list[dict] = []

    def enqueue(self, alert: dict) -> bool:
        self.enqueued.append(alert)
        return True


def test_alert_is_handed_to_notifier_with_its_id():
    db, monitor, spy = (
        FakeDB(),
        YieldMonitor(min_samples=20, threshold=0.9),
        SpyNotifier(),
    )

    async def run() -> None:
        for _ in range(20):
            await pipeline.handle_result(db, monitor, make_item("fail"), notifier=spy)

    asyncio.run(run())

    assert len(spy.enqueued) == 1
    assert spy.enqueued[0]["id"] == db[repository.ALERTS].docs[0]["_id"]
    assert spy.enqueued[0]["new_incident"] is True


def test_no_notifier_configured_is_fine():
    db, monitor = FakeDB(), YieldMonitor(min_samples=20, threshold=0.9)
    feed(db, monitor, "fail", 20)  # notifier defaults to None

    assert len(db[repository.ALERTS].docs) == 1
