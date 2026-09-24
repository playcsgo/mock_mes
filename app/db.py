from pymongo import AsyncMongoClient

from app.config import settings


def create_client() -> AsyncMongoClient:
    return AsyncMongoClient(
        settings.mongo_uri,
        tz_aware=True,
        serverSelectionTimeoutMs=3000,
    )
