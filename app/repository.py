from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.models import ResultIn

RESULTS = "results"


async def ensure_indexes(db: AsyncDatabase) -> None:
    (await db[RESULTS].create_index([("station", ASCENDING), ("ts", DESCENDING)]))
    (await db[RESULTS].create_index([("lot", ASCENDING), ("ts", DESCENDING)]))


def to_public(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def insert_result(db: AsyncDatabase, item: ResultIn) -> dict:
    doc = item.model_dump()
    await db[RESULTS].insert_one(doc)
    return to_public(doc)


async def latest_results(db: AsyncDatabase, limit: int = 10) -> list[dict]:
    cursor = db[RESULTS].find().sort("ts", DESCENDING).limit(limit)
    return [to_public(d) async for d in cursor]
