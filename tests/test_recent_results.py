import asyncio
from datetime import datetime, timedelta, timezone

from app import repository
from app.gql.schema import schema
from tests.fakes import FakeDB


def fill(db: FakeDB, station: str, results: list[str]) -> None:
    t0 = datetime(2026, 10, 3, tzinfo=timezone.utc)
    for i, result in enumerate(results):
        db.cols.setdefault(repository.RESULTS, db[repository.RESULTS]).docs.append(
            {"station": station, "result": result, "ts": t0 + timedelta(seconds=i)}
        )


def test_returns_the_latest_n_per_station_oldest_first():
    db = FakeDB()
    fill(db, "ST-01", ["pass", "fail", "pass", "pass"])
    fill(db, "ST-02", ["fail", "fail"])

    rows = asyncio.run(repository.recent_results_by_station(db, limit=3))

    assert rows == [
        {"station": "ST-01", "passed": [False, True, True]},
        {"station": "ST-02", "passed": [False, False]},
    ]


def test_graphql_exposes_recent_results():
    db = FakeDB()
    fill(db, "ST-03", ["pass", "fail", "pass"])

    async def run():
        return await schema.execute(
            "{ recentResults(limit: 2) { station passed } }",
            context_value={"db": db},
        )

    r = asyncio.run(run())

    assert r.errors is None
    assert r.data["recentResults"] == [{"station": "ST-03", "passed": [False, True]}]
