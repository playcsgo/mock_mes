from pymongo import ASCENDING, DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.models import ResultIn, utc_now

RESULTS = "results"
ALERTS = "alerts"
DATA_TTL_S = 4 * 60 * 60


async def ensure_indexes(db: AsyncDatabase) -> None:
    (await db[RESULTS].create_index([("station", ASCENDING), ("ts", DESCENDING)]))
    (await db[RESULTS].create_index([("lot", ASCENDING), ("ts", DESCENDING)]))
    await db[ALERTS].create_index([("ts", DESCENDING)])

    # set TTL
    await db[RESULTS].create_index("ts", expireAfterSeconds=DATA_TTL_S)
    await db[ALERTS].create_index("ts", expireAfterSeconds=DATA_TTL_S)


def to_public(doc: dict) -> dict:
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def insert_result(db: AsyncDatabase, item: ResultIn) -> dict:
    doc = item.model_dump()
    await db[RESULTS].insert_one(doc)
    return to_public(doc)


# async def latest_results(db: AsyncDatabase, limit: int = 10) -> list[dict]:
#     cursor = db[RESULTS].find().sort("ts", DESCENDING).limit(limit)

#     return [to_public(d) async for d in cursor]


def build_filter(station=None, lot=None, result=None, since=None, until=None) -> dict:
    """find DB with with query param"""

    q: dict = {}
    if station:
        q["station"] = station
    if lot:
        q["lot"] = lot
    if result:
        q["result"] = result
    if since or until:
        q["ts"] = {}
        if since:
            q["ts"]["$gte"] = since  # #get: greater than
        if until:
            q["ts"]["$lt"] = until  # #lt: less than
    return q


async def find_results(db: AsyncDatabase, limit: int = 20, **filters) -> list[dict]:
    limit = max(1, min(limit, 200))

    cursor = (
        db[RESULTS].find(build_filter(**filters)).sort("ts", DESCENDING).limit(limit)
    )
    return [to_public(d) async for d in cursor]


async def latest_results(db: AsyncDatabase, limit: int = 10) -> list[dict]:
    return await find_results(db, limit=limit)


async def yield_by_station(db: AsyncDatabase, lot=None, since=None) -> list[dict]:
    pipeline = [
        # 1 match for filter
        {"$match": build_filter(lot=lot, since=since)},
        # 2 group for calculation
        {
            "$group": {
                "_id": "$station",
                "total": {"$sum": 1},
                "passed": {"$sum": {"$cond": [{"$eq": ["$result", "pass"]}, 1, 0]}},
            }
        },
        # 3 format of request
        {
            "$project": {
                "_id": 0,
                "station": "$_id",
                "total": 1,
                "passed": 1,
                "yield_rate": {"$divide": ["$passed", "$total"]},
            }
        },
        # 4 sort
        {"$sort": {"station": 1}},
    ]

    cursor = await db[RESULTS].aggregate(pipeline)
    return await cursor.to_list()


async def top_failures(
    db: AsyncDatabase, station=None, lot=None, since=None, limit: int = 5
) -> list[dict]:
    match = build_filter(station=station, lot=lot, since=since, result="fail")

    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": {"station": "$station", "fail_code": "$fail_code"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": max(1, min(limit, 50))},
        {
            "$project": {
                "_id": 0,
                "station": "$_id.station",
                "fail_code": "$_id.fail_code",
                "count": 1,
            }
        },
    ]

    cursor = await db[RESULTS].aggregate(pipeline)
    return await cursor.to_list()


async def insert_alert(db: AsyncDatabase, alert: dict) -> dict:
    doc = {**alert, "ts": utc_now()}
    await db[ALERTS].insert_one(doc)
    return to_public(doc)


async def latest_alerts(db: AsyncDatabase, limit: int = 10) -> list[dict]:
    limit = max(1, min(limit, 100))
    cursor = db[ALERTS].find().sort("ts", DESCENDING).limit(limit)
    return [to_public(d) async for d in cursor]
