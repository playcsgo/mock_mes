import asyncio
import random
import time
from datetime import timedelta

from app import pipeline, repository
from app.models import ResultIn, utc_now
from app.ws_manager import manager

FAIL_CODES = {
    "V_OUT_LOW": ("v_out", 4.6),
    "CURRENT_HIGH": ("current_a", 1.6),
    "TEMP_HIGH": ("temp_c", 72.0),
}

STATIONS = [f"ST-{i:02d}" for i in range(1, 6)]
BAD_STATION = "ST-03"
BAD_RATE = 0.30
FAIL_RATE = 0.01

STATION_SPEED = {
    "ST-01": 4.00,
    "ST-02": 0.65,
    "ST-03": 0.80,
    "ST-04": 2.50,
    "ST-05": 1.00,
}


BACKFILL_MINUTES = 60
BACKFILL_MIN_DOCS = 300
BACKFILL_EVERY_S = 10
BACKFILL_BAD_RATE = 0.18

TICK_S = 0.5
IDLE_GRACE_S = 60
MAX_RUN_S = 20 * 60


def current_lot() -> str:
    return f"LOT-{utc_now():%Y%m%d}"


def make_record(station: str, lot: str, n: int, fail_rate: float) -> dict:
    m = {
        "v_out": round(random.gauss(5.0, 0.03), 3),
        "current_a": round(random.gauss(1.2, 0.03), 3),
        "temp_c": round(random.gauss(40, 2), 1),
    }

    record = {
        "station": station,
        "lot": lot,
        "serial": f"SN-{station[-2:]}{n:06d}",
        "measurements": m,
    }

    if random.random() < fail_rate:
        code = random.choice(list(FAIL_CODES))
        key, bad_value = FAIL_CODES[code]
        m[key] = bad_value
        record.update(result="fail", fail_code=code)
    else:
        record["result"] = "pass"

    return record


def fail_rate_for(station: str, bad_rate: float) -> float:
    return bad_rate if station == BAD_STATION else FAIL_RATE


def produces_this_round(station: str) -> bool:
    return random.random() <= STATION_SPEED.get(station, 1.0)


async def backfill_if_sparse(db) -> int:
    if await db[repository.RESULTS].count_documents({}) >= BACKFILL_MIN_DOCS:
        return 0

    since = utc_now() - timedelta(minutes=BACKFILL_MINUTES)
    lot, docs, n = current_lot(), [], 0
    for step in range(BACKFILL_MINUTES * 60 // BACKFILL_EVERY_S):
        ts = since + timedelta(seconds=step * BACKFILL_EVERY_S)
        for station in STATIONS:
            if not produces_this_round(station):
                continue
            n += 1
            rate = fail_rate_for(station, BACKFILL_BAD_RATE)
            docs.append(
                ResultIn(**make_record(station, lot, n, rate), ts=ts).model_dump()
            )

    await db[repository.RESULTS].insert_many(docs)
    return len(docs)


async def _run(app) -> None:
    """private function only called by ensure_running()"""
    db, monitor = app.state.db, app.state.monitor
    added = await backfill_if_sparse(db)

    if added:
        print(f"[demo] backfilled {added} docs.")

    lot = current_lot()
    started = time.monotonic()
    idle_since: float | None = None
    n = 0
    reason = "no viewer"

    while True:
        if manager.active:
            idle_since = None
        elif idle_since is None:
            idle_since = time.monotonic()
        elif time.monotonic() - idle_since > IDLE_GRACE_S:
            break
        if time.monotonic() - started > MAX_RUN_S:
            reason = "reach to max demo data"
            break

        for station in STATIONS:
            t0 = time.monotonic()

            if produces_this_round(station):
                n += 1
                item = ResultIn(
                    **make_record(station, lot, n, fail_rate_for(station, BAD_RATE))
                )

                await pipeline.handle_result(db, monitor, item)

            gap = TICK_S / len(STATIONS) * random.uniform(0.7, 1.3) - (
                time.monotonic() - t0
            )
            if gap > 0:
                await asyncio.sleep(gap)

    print(f"demo stopped due to {reason}")


def ensure_running(app) -> None:
    task = getattr(app.state, "demo_task", None)
    if task is None or task.done():
        app.state.demo_task = asyncio.create_task(_run(app))


async def stop(app) -> None:
    task = getattr(app.state, "demo_task", None)
    if task and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
