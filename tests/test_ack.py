import asyncio

from app import repository
from tests.fakes import FakeDB


def stored_alert(db: FakeDB) -> str:
    alert = {"station": "ST-03", "yield_rate": 0.7, "window": 50, "threshold": 0.9}
    return asyncio.run(repository.insert_alert(db, alert))["id"]


def test_first_claim_wins_and_is_recorded():
    db = FakeDB()
    alert_id = stored_alert(db)

    doc, claimed = asyncio.run(repository.ack_alert(db, alert_id, "Amy"))

    assert claimed is True
    assert doc["id"] == alert_id
    assert doc["ack_by"] == "Amy"
    assert doc["ack_at"] is not None


def test_second_claim_loses_and_sees_who_has_it():
    db = FakeDB()
    alert_id = stored_alert(db)

    async def run():
        await repository.ack_alert(db, alert_id, "Amy")
        return await repository.ack_alert(db, alert_id, "Bob")

    doc, claimed = asyncio.run(run())

    assert claimed is False
    assert doc["ack_by"] == "Amy"


def test_unknown_alert_returns_none():
    db = FakeDB()
    stored_alert(db)

    assert asyncio.run(repository.ack_alert(db, "no-such-id", "Amy")) is None


def test_new_alert_starts_unclaimed():
    db = FakeDB()
    stored_alert(db)

    assert db[repository.ALERTS].docs[0]["ack_by"] is None
