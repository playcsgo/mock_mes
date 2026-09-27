import asyncio

from app import repository
from tests.fakes import FakeDB


def ttl_options(db: FakeDB, collection: str) -> dict:
    for keys, options in db[collection].indexes:
        if keys == "ts" and "expireAfterSeconds" in options:
            return options

    return {}


def test_both_collections_expire_after_four_hours():
    db = FakeDB()
    asyncio.run(repository.ensure_indexes(db))  # type: ignore[arg-type]

    four_hours = 4 * 60 * 60

    assert repository.DATA_TTL_S == four_hours
    assert ttl_options(db, repository.RESULTS) == {"expireAfterSeconds": four_hours}
    assert ttl_options(db, repository.ALERTS) == {"expireAfterSeconds": four_hours}
