import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import repository
from app.config import settings
from app.db import create_client


async def main() -> None:
    client = create_client()
    db = client[settings.mongo_db_name]

    await repository.ensure_indexes(db)
    print(f"DB index setting check process{settings.mongo_db_name}\n")

    for name in (repository.RESULTS, repository.ALERTS):
        print(f"[{name}]")
        has_ttl = False
        async for ix in await db[name].list_indexes():
            keys = ", ".join(f"{k}:{v}" for k, v in ix["key"].items())
            ttl = ix.get("expireAfterSeconds")
            if ttl is None:
                note = ""
            else:
                has_ttl = True
                note = f"  ← TTL {ttl} s({ttl / 3600:g} hour)"
            print(f"  {ix['name']:<20} {{{keys}}}{note}")

            if ix["name"] == "ts_-1":
                print("index replaced")

        print(
            f"  → TTL setting {'success' if has_ttl else 'index is not exist, setting failed (check ensure_indexes)'}\n"
        )

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
