import asyncio

from app import repository
from tests.fakes import FakeDB


def ttl_options(db: FakeDB, collection: str) -> dict:
    for keys, options in db[collection].indexes:
        if keys == "ts" and "expireAfterSeconds" in options:
            return options

    return {}


def test_both_collections_expire_after_one_week():
    db = FakeDB()
    asyncio.run(repository.ensure_indexes(db))  # type: ignore[arg-type]

    one_week = 7 * 24 * 60 * 60

    assert repository.DATA_TTL_S == one_week
    assert ttl_options(db, repository.RESULTS) == {"expireAfterSeconds": one_week}
    assert ttl_options(db, repository.ALERTS) == {"expireAfterSeconds": one_week}


def test_ttl_change_uses_collmod_instead_of_failing():
    """Changing DATA_TTL_S must not crash startup on an existing database.

    create_index refuses a same-named index with different options
    (IndexOptionsConflict), so the duration has to change via collMod.
    """
    db = FakeDB()
    for name in (repository.RESULTS, repository.ALERTS):
        db[name].conflict_on_ttl = True

    asyncio.run(repository.ensure_indexes(db))

    assert db.commands == [
        {"collMod": name,
         "index": {"keyPattern": {"ts": 1}, "expireAfterSeconds": repository.DATA_TTL_S}}
        for name in (repository.RESULTS, repository.ALERTS)
    ]
