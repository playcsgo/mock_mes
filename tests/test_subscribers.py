import asyncio

from app import repository
from tests.fakes import FakeDB


def test_follow_twice_keeps_one_subscriber():
    db = FakeDB()

    async def run():
        await repository.add_subscriber(db, "U1")
        await repository.add_subscriber(db, "U1")
        await repository.add_subscriber(db, "U2")
        return await repository.subscriber_ids(db)

    assert asyncio.run(run()) == ["U1", "U2"]


def test_unfollow_removes_subscriber():
    db = FakeDB()

    async def run():
        await repository.add_subscriber(db, "U1")
        await repository.remove_subscriber(db, "U1")
        await repository.remove_subscriber(db, "U-never-followed")
        return await repository.subscriber_ids(db)

    assert asyncio.run(run()) == []
