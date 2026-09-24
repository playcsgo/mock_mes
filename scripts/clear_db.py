"""remove test data"""

import argparse
import asyncio

from app.config import settings
from app.db import create_client


async def main(auto_yes: bool) -> None:
    client = create_client()
    db = client[settings.mongo_db_name]
    try:
        names = await db.list_collection_names()
        if not names:
            print("nothing to clear")
            return

        counts = {name: await db[name].count_documents({}) for name in names}
        print(f"database: {settings.mongo_db_name}")
        for name, n in counts.items():
            print(f"  {name}: {n} documents")

        if not auto_yes and input("delete all of them? [y/N] ").strip().lower() != "y":
            print("cancelled")
            return

        for name in names:
            result = await db[name].delete_many({})
            print(f"  {name}: deleted {result.deleted_count}")
    finally:
        await client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="clear all documents")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    asyncio.run(main(p.parse_args().yes))
