"""mock monogoDB for unit test"""

from pymongo.errors import OperationFailure


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []
        self.conflict_on_ttl = False

    async def insert_one(self, doc: dict) -> None:
        doc["_id"] = f"fake{len(self.docs)}"
        self.docs.append(doc)

    async def insert_many(self, docs: list[dict]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    def _match(self, doc: dict, filter: dict) -> bool:
        return all(doc.get(k) == v for k, v in filter.items())

    async def update_one(self, filter: dict, update: dict, upsert: bool = False):
        for doc in self.docs:
            if self._match(doc, filter):
                doc.update(update.get("$set", {}))
                return
        if upsert:
            doc = {**filter, **update.get("$set", {}), **update.get("$setOnInsert", {})}
            await self.insert_one(doc)

    async def delete_one(self, filter: dict) -> None:
        for i, doc in enumerate(self.docs):
            if self._match(doc, filter):
                del self.docs[i]
                return

    def find(self, filter: dict | None = None, projection: dict | None = None):
        rows = [d for d in self.docs if self._match(d, filter or {})]

        async def gen():
            for d in rows:
                yield dict(d)

        return gen()

    async def count_documents(self, filter: dict | None = None) -> int:
        if not filter:
            return len(self.docs)
        return sum(
            all(d.get(k) == v for k, v in filter.items() if not isinstance(v, dict))
            for d in self.docs
        )

    async def create_index(self, keys, **options) -> str:
        if self.conflict_on_ttl and "expireAfterSeconds" in options:
            raise OperationFailure("index options conflict", 85)
        self.indexes.append((keys, options))
        return "fake_index"


class FakeDB:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}
        self.commands: list[dict] = []

    async def command(self, cmd: dict) -> dict:
        self.commands.append(cmd)
        return {"ok": 1}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())
