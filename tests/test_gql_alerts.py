import asyncio
from datetime import datetime, timezone

from app import repository
from app.gql.schema import schema
from tests.fakes import FakeDB


def query_alerts(db: FakeDB) -> dict:
    async def run():
        return await schema.execute(
            '{ alerts { id station yieldRate threshold } }',
            context_value={'db': db}
        )

    return asyncio.run(run())


def test_alerts_query_ignores_extra_fields_stored_on_the_alert(monkeypatch):
    stored = [{"id": "a1", "station": "ST-03", "yield_rate": 0.7, "window": 50,
               "threshold": 0.9, "ts": datetime(2026, 9, 29, tzinfo=timezone.utc),
               "new_incident": True}]

    async def fake_latest(db, limit):
        return stored

    monkeypatch.setattr(repository, 'latest_alerts', fake_latest)
    r = query_alerts(FakeDB())

    assert r.errors is None
    assert r.data['alerts'][0]['station'] == 'ST-03'


def test_alerts_query_exposes_who_claimed_it(monkeypatch):
    ts = datetime(2026, 9, 29, tzinfo=timezone.utc)
    stored = [
        {"id": "a1", "station": "ST-03", "yield_rate": 0.7, "window": 50,
         "threshold": 0.9, "ts": ts, "ack_by": "Amy", "ack_at": ts},
        # alerts stored before claiming existed have no ack fields at all
        {"id": "a0", "station": "ST-03", "yield_rate": 0.7, "window": 50,
         "threshold": 0.9, "ts": ts},
    ]

    async def fake_latest(db, limit):
        return stored

    monkeypatch.setattr(repository, "latest_alerts", fake_latest)

    async def run():
        return await schema.execute(
            "{ alerts { id ackBy ackAt } }", context_value={"db": FakeDB()}
        )

    r = asyncio.run(run())

    assert r.errors is None
    assert r.data["alerts"][0]["ackBy"] == "Amy"
    assert r.data["alerts"][0]["ackAt"] is not None
    assert r.data["alerts"][1]["ackBy"] is None
