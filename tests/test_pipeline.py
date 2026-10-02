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
