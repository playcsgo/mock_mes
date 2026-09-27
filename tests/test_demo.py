import asyncio
import random
from collections import Counter
from types import SimpleNamespace

from app import demo, repository
from tests.fakes import FakeDB


def test_make_record_fail_carries_a_matching_code():
    random.seed(1)
    r = demo.make_record("ST-01", "LOT-T", 1, fail_rate=1.0)

    assert r["result"] == "fail"
    field, bad_value = demo.FAIL_CODES[r["fail_code"]]
    assert r["measurements"][field] == bad_value


def test_make_record_pass_has_no_fail_code():
    r = demo.make_record("ST-01", "LOT-T", 1, fail_rate=0.0)

    assert r["result"] == "pass"
    assert "fail_code" not in r


def test_backfill_fills_one_hour_and_degrades_the_bad_station():
    random.seed(42)
    db = FakeDB()
    added = asyncio.run(demo.backfill_if_sparse(db))

    full = demo.BACKFILL_MINUTES * 60 // demo.BACKFILL_EVERY_S * len(demo.STATIONS)
    assert full * 0.80 < added < full

    docs = db[repository.RESULTS].docs
    assert len(docs) == added
    assert docs[0]["ts"] < docs[-1]["ts"]

    def yield_of(station: str) -> float:
        rows = [d for d in docs if d["station"] == station]
        return sum(d["result"] == "pass" for d in rows) / len(rows)

    assert yield_of(demo.BAD_STATION) < 0.90
    assert all(yield_of(s) >= 0.95 for s in demo.STATIONS if s != demo.BAD_STATION)


def test_stations_do_not_all_produce_the_same_amount():
    """Equal row counts per station look fake: takt times differ, fails get retested."""
    random.seed(42)
    db = FakeDB()
    asyncio.run(demo.backfill_if_sparse(db))

    counts = Counter(d["station"] for d in db[repository.RESULTS].docs)
    assert len(set(counts.values())) > 1

    spread = (max(counts.values()) - min(counts.values())) / max(counts.values())
    assert spread > 0.05

    fastest = max(demo.STATION_SPEED, key=demo.STATION_SPEED.get)
    assert counts.most_common(1)[0][0] == fastest


def test_backfill_skipped_when_window_already_has_data():
    db = FakeDB()
    db[repository.RESULTS].docs = [{"_id": i} for i in range(demo.BACKFILL_MIN_DOCS)]

    assert asyncio.run(demo.backfill_if_sparse(db)) == 0


def test_second_viewer_does_not_start_a_second_simulator(monkeypatch):
    async def never_ending(_app):
        await asyncio.sleep(3600)

    monkeypatch.setattr(demo, "_run", never_ending)

    async def scenario():
        app = SimpleNamespace(state=SimpleNamespace())
        demo.ensure_running(app)
        first = app.state.demo_task
        demo.ensure_running(app)
        assert app.state.demo_task is first
        await demo.stop(app)
        assert first.cancelled()

    asyncio.run(scenario())
